"""Plan de montage : transforme un script en plan de coupe + légendes.

Règles appliquées (méthode « Short performant ») :
  * hook de 0 à 3 s : phrase la plus percutante, 3 à 8 mots ;
  * corps : une idée par plan, 1,5 à 3 s par plan ;
  * CTA / boucle sur les 3 dernières secondes.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .captions import plan_words
from .spec import CaptionLine, Hook, ShortSpec, Shot, TextOverlay

# Mots « à fort impact » pour l'accroche.
POWER_WORDS = (
    "pourquoi", "comment", "erreur", "faut", "jamais", "toujours", "secret", "astuce",
    "gratuit", "simple", "rapide", "incroyable", "interdit", "unique", "nouveau",
    "moins", "plus", "aucun", "personne", "tout", "vrai", "faux", "arrête", "stop",
)


@dataclass
class PlanItem:
    """Une phrase du script, prête à être jouée."""

    text: str
    start: float
    duration: float
    shot_index: int
    role: str  # hook | body | cta

    @property
    def end(self) -> float:
        return self.start + self.duration


def split_sentences(text: str) -> List[str]:
    """Découpe un script en phrases (en gardant la ponctuation)."""
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?…])\s+", text)
    out: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Les phrases longues sont découpées sur les virgules.
        if len(part.split()) > 14:
            chunks = re.split(r"(?<=,)\s+", part)
            buf = ""
            for chunk in chunks:
                if len((buf + " " + chunk).split()) <= 12:
                    buf = (buf + " " + chunk).strip()
                else:
                    if buf:
                        out.append(buf)
                    buf = chunk
            if buf:
                out.append(buf)
        else:
            out.append(part)
    return out


def score_hook(sentence: str) -> int:
    """Note la force d'une accroche (0-100)."""
    words = sentence.lower().split()
    normalized = [re.sub(r"[^\w]", "", word, flags=re.UNICODE) for word in words]
    score = 40
    if len(words) <= 8:
        score += 15
    elif len(words) <= 12:
        score += 5
    else:
        score -= 10
    if any(any(pw in word for pw in POWER_WORDS) for word in normalized):
        score += 20
    if sentence.strip().endswith("?"):
        score += 12
    if any(ch.isdigit() for ch in sentence):
        score += 8
    if any(ch in sentence for ch in ("!", "💥", "🔥")):
        score += 8
    if any(w in normalized for w in ("je", "tu", "nous", "vous")):
        score += 6
    if len(sentence) < 12:
        score -= 8
    return max(0, min(100, score))


def pick_hook(sentences: Sequence[str]) -> int:
    """Index de la meilleure accroche du script."""
    if not sentences:
        return 0
    return max(range(len(sentences)), key=lambda i: score_hook(sentences[i]))


def plan_durations(sentences: Sequence[str], total: float, *, min_shot: float = 1.2, max_shot: float = 3.0) -> List[float]:
    """Répartit une durée en respectant les bornes dès que c'est possible.

    Les bornes sont assouplies seulement si le nombre de segments rend la
    contrainte mathématiquement impossible. Le résultat somme toujours à
    ``total`` : pas de vidéo plus courte que la spec.
    """
    if not sentences:
        return []
    total = max(0.0, float(total))
    if total == 0:
        return [0.0] * len(sentences)
    n = len(sentences)
    weights = [max(len(s.split()), 1) for s in sentences]
    lower = max(0.0, float(min_shot))
    upper = max(lower, float(max_shot))
    if lower * n > total:
        lower = total / n
    if upper * n < total:
        upper = total / n

    weight_sum = sum(weights)
    durations = [max(lower, min(upper, total * w / weight_sum)) for w in weights]
    drift = total - sum(durations)
    # Redistribue le reliquat aux segments qui ont encore de la marge.
    for _ in range(n + 2):
        if abs(drift) < 1e-7:
            break
        if drift > 0:
            active = [i for i, d in enumerate(durations) if d < upper - 1e-9]
        else:
            active = [i for i, d in enumerate(durations) if d > lower + 1e-9]
        if not active:
            break
        wsum = sum(weights[i] for i in active)
        moved = 0.0
        for i in active:
            share = drift * weights[i] / wsum
            if drift > 0:
                change = min(share, upper - durations[i])
            else:
                change = max(share, lower - durations[i])
            durations[i] += change
            moved += change
        drift -= moved
    # Corrige les derniers flottants, sans jamais sortir des bornes.
    if abs(drift) > 1e-6:
        for i in range(n - 1, -1, -1):
            room = (upper - durations[i]) if drift > 0 else (durations[i] - lower)
            change = min(abs(drift), max(0.0, room)) * (1 if drift > 0 else -1)
            durations[i] += change
            drift -= change
            if abs(drift) <= 1e-6:
                break
    return durations


def _visual_segments(sentences: Sequence[str], total: float, min_shot: float, max_shot: float) -> List[str]:
    """Découpe le corps en unités de sous-titres qui correspondent aux coupes."""
    words = [word for sentence in sentences for word in sentence.split()]
    if not words or total <= 0:
        return []
    lo = max(0.5, min_shot)
    hi = max(lo, max_shot)
    count = max(1, int(math.ceil(total / hi)))
    count = min(count, max(1, int(total / lo)) if total >= lo else 1, len(words))
    if count == 1:
        return [" ".join(words)]

    # Cherche des limites proches d'une répartition égale, en privilégiant
    # une ponctuation de fin de phrase quand elle est à moins de deux mots.
    parts: List[str] = []
    start = 0
    for part_no in range(1, count):
        remaining_parts = count - part_no
        target = round(len(words) * part_no / count)
        low = max(start + 1, target - 2)
        high = min(len(words) - remaining_parts, target + 2)
        candidates = range(low, max(low + 1, high + 1))
        candidates = [i for i in candidates if i < len(words) - remaining_parts]
        if not candidates:
            cut = max(start + 1, min(len(words) - remaining_parts, target))
        else:
            punctuation = [i for i in candidates if words[i - 1].endswith((".", "!", "?", ";", ":"))]
            pool = punctuation or candidates
            cut = min(pool, key=lambda i: abs(i - target))
        parts.append(" ".join(words[start:cut]))
        start = cut
    parts.append(" ".join(words[start:]))
    return [part for part in parts if part]


def build_plan(
    script: str,
    *,
    duration: float = 30.0,
    hook_duration: float = 2.8,
    cta: Optional[str] = "Abonne-toi",
    cta_duration: float = 2.8,
    min_shot: float = 1.4,
    max_shot: float = 3.0,
    sources: Optional[Sequence[str]] = None,
    motions: Optional[Sequence[str]] = None,
) -> Tuple[List[Shot], List[CaptionLine], Hook, dict]:
    """Construit (plans, légendes, hook, méta) à partir d'un script brut.

    Les phrases sont segmentées en unités visuelles de 1,5 à 3 s. Un plan
    CTA explicite ferme la timeline afin que les plans somment à la durée.
    """
    sentences = split_sentences(script)
    if len(sentences) < 2:
        raise ValueError("Script trop court : donne au moins un hook et une phrase de corps.")
    hook_idx = pick_hook(sentences)
    hook_text = sentences[hook_idx]
    body = [s for i, s in enumerate(sentences) if i != hook_idx]

    duration = max(1.0, float(duration))
    hook_duration = min(max(0.4, float(hook_duration)), 3.0, duration - 0.5)
    cta_duration = min(max(0.0, float(cta_duration)), max(0.0, duration - hook_duration - 0.5)) if cta else 0.0

    # Si le CTA est déjà la dernière phrase parlée, on la place dans le plan
    # CTA et on conserve sa légende au même timecode.
    spoken_cta: Optional[str] = None
    normalize = lambda value: re.sub(r"[^\w]+", " ", value.lower()).strip()
    if cta and body and normalize(body[-1]).startswith(normalize(cta)):
        spoken_cta = body.pop()

    body_total = max(0.0, duration - hook_duration - cta_duration)
    segments = _visual_segments(body, body_total, min_shot, max_shot)
    if not segments:
        raise ValueError("Le script ne contient pas de corps après le hook.")
    durations = plan_durations(segments, body_total, min_shot=min_shot, max_shot=max_shot)
    rounded = [round(d, 3) for d in durations]
    if rounded:
        rounded[-1] = round(rounded[-1] + body_total - sum(rounded), 3)

    shots: List[Shot] = []
    captions: List[CaptionLine] = []
    hook_source = sources[0] if sources else None
    hook_shot = Shot(
        id="hook",
        duration=round(hook_duration, 3),
        source=hook_source,
        motion={"kind": "kenburns-in", "start_scale": 1.0, "end_scale": 1.14},
        transition="flash",
    )
    shots.append(hook_shot)
    hook_cap_duration = max(0.3, min(hook_duration - 0.1, 2.8))
    captions.append(
        CaptionLine(
            text=hook_text,
            start=0.1,
            duration=hook_cap_duration,
            words=plan_words(hook_text, 0.1, hook_cap_duration),
            highlight="word",
            size=68,
            y=0.70,
        )
    )

    cursor = hook_duration
    for i, (segment, d) in enumerate(zip(segments, rounded)):
        src = sources[(i + 1) % len(sources)] if sources else None
        motion = motions[i % len(motions)] if motions else "kenburns-in"
        shot = Shot(
            id=f"s{i + 1}",
            duration=d,
            source=src,
            motion={"kind": motion},
            transition="cut",
        )
        shots.append(shot)
        captions.append(
            CaptionLine(
                text=segment,
                start=round(cursor, 3),
                duration=d,
                words=plan_words(segment, cursor, d),
                highlight="word",
                size=66,
                max_width=800,
                y=0.70,
            )
        )
        cursor += d

    if cta and cta_duration > 0:
        cta_text_for_caption = spoken_cta or ""
        shots.append(
            Shot(
                id="cta",
                duration=round(cta_duration, 3),
                source=sources[-1] if sources else None,
                motion={"kind": "kenburns-out", "start_scale": 1.14, "end_scale": 1.0},
                transition="flash",
            )
        )
        if cta_text_for_caption:
            start = max(0.0, duration - cta_duration)
            captions.append(
                CaptionLine(
                    text=cta_text_for_caption,
                    start=round(start, 3),
                    duration=round(cta_duration, 3),
                    words=plan_words(cta_text_for_caption, start, cta_duration),
                    highlight="word",
                    size=66,
                    max_width=800,
                    y=0.70,
                )
            )

    meta = {
        "hook_score": score_hook(hook_text),
        "sentences": len(sentences),
        "body_shots": len(segments),
        "cta_duration": cta_duration,
        "timeline": round(sum(shot.duration for shot in shots), 3),
    }
    hook = Hook(text=hook_text, subtext="", duration=hook_duration)
    return shots, captions, hook, meta


def cut_points(spec: ShortSpec) -> List[float]:
    """Temps de coupe (en secondes) du montage."""
    points: List[float] = []
    t = 0.0
    for shot in spec.shots:
        t += shot.duration
        points.append(round(t, 3))
    return points


def rhythm_metrics(spec: ShortSpec) -> dict:
    """Métriques de rythme du montage."""
    cuts = cut_points(spec)
    durations = [s.duration for s in spec.shots]
    internal = [c for c in cuts if c < spec.duration - 0.05]
    gaps = [round(cuts[i] - cuts[i - 1], 2) for i in range(1, len(cuts))]
    long_gaps = [g for g in gaps if g > 3.0]
    short_gaps = [g for g in gaps if g < 1.0]
    return {
        "cuts": len(cuts),
        "cuts_per_10s": round(len(cuts) / max(spec.duration, 0.1) * 10, 2),
        "mean_shot": round(sum(durations) / max(len(durations), 1), 2),
        "gaps": gaps,
        "long_gaps": long_gaps,
        "short_gaps": short_gaps,
        "cut_points": cuts,
    }
