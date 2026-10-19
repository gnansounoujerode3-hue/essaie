"""Analyse tempo / beats / énergie sans dépendance (FFmpeg + stdlib)."""

from __future__ import annotations

import array
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Sequence

from .common import SkillError, clamp, info, warn
from .ffmpeg import ffmpeg_bin, media_info

SAMPLE_RATE = 22050
HOP = 512
WINDOW = 1024


def _decode_mono(path: str | Path, sample_rate: int = SAMPLE_RATE) -> array.array:
    with tempfile.TemporaryDirectory(prefix="vesk-music-") as tmp:
        wav_path = Path(tmp) / "audio.wav"
        proc = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-y", "-i", str(path), "-vn",
             "-ac", "1", "-ar", str(sample_rate), "-acodec", "pcm_s16le", str(wav_path)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not wav_path.exists():
            raise SkillError(f"Décodage audio impossible : {(proc.stderr or '').strip()[-400:]}")
        with wave.open(str(wav_path), "rb") as handle:
            raw = handle.readframes(handle.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    if not samples:
        raise SkillError(f"Aucun échantillon audio dans {path}")
    if __import__("sys").byteorder != "little":  # pragma: no cover
        samples.byteswap()
    return samples


def _rms_envelope(samples: array.array) -> list[float]:
    envelope = []
    for start in range(0, len(samples) - WINDOW, HOP):
        window = samples[start:start + WINDOW]
        energy = sum(float(s) * float(s) for s in window) / len(window)
        envelope.append(math.sqrt(energy) / 32768.0)
    return envelope


def _onset_envelope(rms: Sequence[float]) -> list[float]:
    """Flux spectral simplifié : dérivée positive de l'énergie (compressée en log)."""
    log_energy = [math.log1p(value * 1000.0) for value in rms]
    onsets = [0.0] * len(log_energy)
    for index in range(1, len(log_energy)):
        onsets[index] = max(0.0, log_energy[index] - log_energy[index - 1])
    maximum = max(onsets) or 1.0
    return [value / maximum for value in onsets]


def _autocorrelate(signal: Sequence[float], min_lag: int, max_lag: int) -> list[float]:
    scores = []
    for lag in range(min_lag, max_lag + 1):
        total = 0.0
        for index in range(0, len(signal) - lag):
            total += signal[index] * signal[index + lag]
        scores.append(total / max(1, len(signal) - lag))
    return scores


def analyze(
    media: str | Path,
    *,
    start: float = 0.0,
    end: float | None = None,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    max_candidates: int = 12,
) -> dict[str, Any]:
    """Estime le tempo et propose une grille de beats stable (phase optimisée)."""
    info_ = media_info(media)
    if not info_["has_audio"]:
        raise SkillError(f"Aucune piste audio dans {media}")
    duration = float(info_["duration"])
    end = min(duration, float(end)) if end else duration
    if end - start < 1.0:
        raise SkillError("Extrait trop court pour analyser le tempo (min 1 s).")
    info(f"Analyse du tempo sur {end - start:.1f}s…")
    samples = _decode_mono(media)
    fps_env = SAMPLE_RATE / HOP
    first = int(start * fps_env)
    last = min(len(samples), int(end * fps_env) * HOP)
    rms = _rms_envelope(samples[first * HOP:last])
    onsets = _onset_envelope(rms)
    if not onsets:
        raise SkillError("Signal audio vide.")

    max_lag = int(fps_env * 60.0 / max(1.0, min_bpm))
    min_lag = max(1, int(fps_env * 60.0 / max_bpm))
    max_lag = min(max_lag, len(onsets) - 2)
    if max_lag <= min_lag:
        raise SkillError("Intervalle de BPM trop étroit pour ce signal.")
    scores = _autocorrelate(onsets, min_lag, max_lag)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    candidates: list[dict[str, float]] = []
    used = set()
    for index in ranked:
        lag = min_lag + index
        if any(abs(lag - other) <= 2 for other in used):
            continue
        used.add(lag)
        bpm = 60.0 * fps_env / lag
        candidates.append({"bpm": round(_fold_bpm(bpm), 2),
                           "lag": lag, "score": round(scores[index], 5)})
        if len(candidates) >= max_candidates:
            break
    if not candidates:
        raise SkillError("Impossible d'estimer le tempo.")
    best = candidates[0]
    bpm = best["bpm"]
    period = 60.0 / bpm
    beats = _beat_grid(onsets, fps_env, period, start)
    confidence = _confidence(scores, onsets, fps_env, period)
    if confidence < 0.12:
        warn("Signal rythmique faible : la musique est peut-être absente ou très douce.")
    return {
        "file": str(Path(media).resolve()),
        "start": round(start, 3),
        "end": round(end, 3),
        "bpm": round(bpm, 2),
        "period": round(period, 4),
        "confidence": round(confidence, 3),
        "beat_count": len(beats),
        "beats": [round(b, 3) for b in beats],
        "candidates": candidates[:5],
        "energy_curve": _energy_curve(rms, fps_env, start),
    }


def _fold_bpm(bpm: float) -> float:
    while bpm < 75.0:
        bpm *= 2.0
    while bpm > 170.0:
        bpm /= 2.0
    return bpm


def _beat_grid(onsets: Sequence[float], fps_env: float, period: float,
               offset: float) -> list[float]:
    """Choisit la phase qui maximise l'énergie d'onset sur la grille."""
    steps = int(round(period * fps_env))
    steps = max(1, steps)
    best_phase, best_score = 0, -1.0
    for phase in range(steps):
        total = 0.0
        index = phase
        while index < len(onsets):
            total += onsets[index]
            index += steps
        if total > best_score:
            best_score, best_phase = total, phase
    beats: list[float] = []
    position = best_phase + steps
    while position < len(onsets):
        beats.append(offset + position / fps_env)
        position += steps
    return beats


def _confidence(scores: Sequence[float], onsets: Sequence[float], fps_env: float,
                period: float) -> float:
    if not scores:
        return 0.0
    peak = max(scores) or 1e-9
    mean = sum(scores) / len(scores) or 1e-9
    periodicity = min(1.0, (peak / mean - 1.0) / 3.0)
    steps = max(1, int(round(period * fps_env)))
    total = 0.0
    count = 0
    for phase in range(steps):
        index = phase
        while index < len(onsets):
            total += onsets[index]
            count += 1
            index += steps
    pulse = total / max(1, count)
    return clamp(0.65 * periodicity + 0.35 * pulse, 0.0, 1.0)


def _energy_curve(rms: Sequence[float], fps_env: float, offset: float) -> list[dict[str, float]]:
    curve = []
    bucket = max(1, int(fps_env))
    for index in range(0, len(rms), bucket):
        chunk = rms[index:index + bucket]
        if not chunk:
            continue
        curve.append({
            "time": round(offset + index / fps_env, 2),
            "rms": round(sum(chunk) / len(chunk), 4),
        })
    return curve


def segment_energy(media: str | Path,
                   segments: Sequence[dict[str, Any]]) -> list[dict[str, float]]:
    """Énergie RMS normalisée (0→1) pour chaque segment horodaté."""
    samples = _decode_mono(media)
    rms = _rms_envelope(samples)
    fps_env = SAMPLE_RATE / HOP
    if not rms:
        return [{"mean": 0.0, "peak": 0.0} for _ in segments]
    ordered = sorted(rms)
    reference = ordered[int(len(ordered) * 0.95)] or 1e-6
    output = []
    for segment in segments:
        first = max(0, int(float(segment["start"]) * fps_env))
        last = min(len(rms), max(first + 1, int(float(segment["end"]) * fps_env)))
        chunk = rms[first:last] or [0.0]
        output.append({
            "mean": round(min(1.0, (sum(chunk) / len(chunk)) / reference), 3),
            "peak": round(min(1.0, max(chunk) / reference), 3),
        })
    return output


def snap_times(times: Sequence[float], beats: Sequence[float],
               *, tolerance: float = 0.25) -> list[dict[str, float]]:
    snapped = []
    for time in times:
        nearest = min(beats, key=lambda beat: abs(beat - time)) if beats else time
        delta = nearest - time
        snapped.append({
            "original": round(time, 3),
            "snapped": round(nearest if abs(delta) <= tolerance else time, 3),
            "delta": round(delta, 3),
            "snapped_to_beat": abs(delta) <= tolerance,
        })
    return snapped


def plan_cuts(duration: float, bpm: float, *, every: int = 4,
              start: float = 0.0) -> list[float]:
    """Points de coupe réguliers tous ``every`` temps (utile pour un montage rythmé)."""
    period = 60.0 / max(1.0, bpm)
    step = period * max(1, int(every))
    return [round(t, 3) for t in _frange(start, duration, step)]


def _frange(start: float, stop: float, step: float):
    value = start
    while value < stop:
        yield value
        value += step


def render_accent(
    video: str | Path,
    out: str | Path,
    beats: Sequence[float],
    *,
    style: str = "flash",
    strength: float = 0.16,
    duration: float = 0.09,
    max_accents: int = 240,
    crf: int = 18,
    preset: str = "medium",
    dry_run: bool = False,
) -> Path:
    """Accentue visuellement chaque beat : flash blanc, vignette ou barres."""
    if not beats:
        raise SkillError("Aucun beat fourni.")
    beats = sorted(beats)
    if len(beats) > max_accents:
        step = max(1, len(beats) // max_accents)
        beats = beats[::step]
    info_ = media_info(video)
    if not info_["has_video"]:
        raise SkillError("Pas de piste vidéo.")
    if style == "flash":
        enable = "+".join(f"between(t,{b:.3f},{b + duration:.3f})" for b in beats)
        vf = f"drawbox=x=0:y=0:w=iw:h=ih:color=white@{strength:.3f}:t=fill:enable='{enable}'"
    elif style == "bars":
        enable = "+".join(f"between(t,{b:.3f},{b + duration:.3f})" for b in beats)
        bar = max(6, int(info_["height"] * 0.035)) if info_["height"] else 24
        vf = (f"drawbox=x=0:y=ih-{bar * 2}:w=iw:h={bar * 2}:color=black@{min(0.9, strength * 3):.2f}:t=fill:"
              f"enable='{enable}'")
    elif style == "pulse":
        # zoom léger uniquement sur les beats, recadrage centré
        expr = "+".join(f"between(t,{b:.3f},{b + duration:.3f})" for b in beats)
        vf = (
            "scale=iw*1.04:ih*1.04,"
            "crop=w=iw/1.04:h=ih/1.04:"
            f"x='(iw-ow)/2+if({expr},8*sin(2*PI*(t-0.0)/0.2),0)':y='(ih-oh)/2'"
        )
    else:
        raise SkillError(f"Style d'accent inconnu : {style} (flash, bars, pulse)")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(video), "-vf", vf, "-c:v", "libx264", "-preset", preset,
            "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if info_["has_audio"]:
        args += ["-c:a", "copy"]
    args.append(str(out_path))
    info(f"Accents « {style} » sur {len(beats)} beats…")
    from .ffmpeg import ffmpeg

    ffmpeg(args, dry_run=dry_run)
    return out_path
