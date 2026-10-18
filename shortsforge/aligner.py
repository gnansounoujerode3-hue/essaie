"""Alignement de la voix et des sous-titres.

On détecte les segments de parole dans le voice-over (silencedetect FFmpeg),
puis on répartit chaque ligne sur l'horloge de parole pondérée par la longueur
et la ponctuation. Les pauses restent dans la timeline sans raccourcir la
légende suivante à quelques dixièmes de seconde.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .captions import plan_words
from .ffmpeg import ffmpeg_bin
from .spec import CaptionLine, ShortSpec


@dataclass
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def detect_speech(audio: str | Path, noise_db: float = -34.0, min_silence: float = 0.16) -> List[Segment]:
    """Détecte les segments de parole dans un fichier audio."""
    path = str(audio)
    proc = subprocess.run(
        [
            ffmpeg_bin(),
            "-hide_banner",
            "-i",
            path,
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    text = proc.stderr or ""
    silences: List[Tuple[float, float]] = []
    pending_start: Optional[float] = None
    for line in text.splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            pending_start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m and pending_start is not None:
            silences.append((pending_start, float(m.group(1))))
            pending_start = None
    if pending_start is not None:
        silences.append((pending_start, 1e9))

    duration = _duration(path)
    segments: List[Segment] = []
    cursor = 0.0
    for s, e in silences:
        if s > cursor:
            segments.append(Segment(cursor, s))
        cursor = max(cursor, e)
    if duration and cursor < duration:
        segments.append(Segment(cursor, duration))
    return [s for s in segments if s.duration > 0.06]


def _duration(path: str) -> float:
    from .ffmpeg import probe

    try:
        return probe(path).duration
    except Exception:
        return 0.0


def _word_weights(text: str) -> List[float]:
    tokens = [t for t in re.split(r"(\s+)", text) if t.strip()]
    weights = []
    for token in tokens:
        word = token.strip()
        w = max(len(word), 1)
        if word.endswith((",", ";", ":")):
            w += 2.1
        elif word.endswith((".", "!", "?")):
            w += 3.6
        weights.append(w)
    return weights


def align_captions(
    spec: ShortSpec,
    audio: str | Path,
    *,
    leading_silence: float = 0.10,
) -> Tuple[ShortSpec, List[str]]:
    """Recale les légendes sur la voix. Retourne (spec, avertissements)."""
    warnings: List[str] = []
    segments = detect_speech(audio)
    lines: List[CaptionLine] = list(spec.captions)
    if not segments or not lines:
        warnings.append("Aucune zone de parole détectée : timing conservé.")
        return spec, warnings
    speed = max(0.5, float(spec.voiceover.speed or 1.0))
    offset = max(0.0, float(spec.voiceover.start or 0.0))
    # Le filtre atempo compresse le temps; le décalage de piste est ajouté
    # ensuite par adelay dans le graphe audio.
    segments = [Segment(offset + s.start / speed, offset + s.end / speed) for s in segments]

    # --- horloge de parole (le temps cumulé des segments parlés) -----------
    cum: List[float] = [0.0]
    for seg in segments:
        cum.append(cum[-1] + seg.duration)
    total_speech = cum[-1]

    def clock_to_time(target: float) -> float:
        """Convertit le temps parlé cumulé en temps réel, en gardant les pauses."""
        elapsed = 0.0
        for seg in segments:
            if target <= elapsed + seg.duration:
                return seg.start + max(0.0, target - elapsed)
            elapsed += seg.duration
        return segments[-1].end

    # --- cible de chaque frontière de phrase, en horloge de parole ---------
    # L'interpolation dans les segments détectés évite qu'un silence long ou
    # une pause de respiration ne comprime la dernière légende à quelques
    # dixièmes de seconde. Les pauses restent visibles dans le temps réel.
    weights = [sum(_word_weights(c.text)) or 1 for c in lines]
    total_w = sum(weights)
    boundaries: List[float] = []
    acc = 0
    for w in weights[:-1]:
        acc += w
        target = (acc / total_w) * total_speech
        boundaries.append(clock_to_time(target))

    starts = [0.0] + boundaries
    ends = boundaries + [max(segments[-1].end, boundaries[-1] if boundaries else 0.0)]

    for cap, start, end in zip(lines, starts, ends):
        dur = max(0.3, end - start)
        cap.start = round(max(0.0, start - leading_silence), 3)
        cap.duration = round(dur, 3)
        cap.words = plan_words(cap.text, cap.start, dur)

    # Contrôle de cohérence avec la durée du short.
    last = lines[-1]
    if last.start + last.duration > spec.duration + 0.6:
        warnings.append(
            f"La dernière légende dépasse la durée du short ({last.start + last.duration:.1f}s > {spec.duration:.1f}s)."
        )
    return spec, warnings


def fit_captions_to_duration(spec: ShortSpec) -> ShortSpec:
    """Recale la fin des légendes pour ne pas déborder de la durée du short."""
    for cap in spec.captions:
        if cap.start + cap.duration > spec.duration:
            cap.duration = max(0.25, spec.duration - cap.start)
            cap.words = plan_words(cap.text, cap.start, cap.duration)
    return spec
