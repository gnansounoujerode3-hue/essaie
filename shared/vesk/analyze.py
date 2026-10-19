"""Scoring des moments forts : hooks, énergie vocale, densité sémantique, plans de clips."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import SkillError, fmt_clock, normalize_text
from .transcript import iter_sentences, split_words

HOOK_PATTERNS: list[tuple[str, float, str]] = [
    (r"\b(comment|pourquoi|combien|quand|quel(?:le|s)?|qui|quoi)\b", 1.6, "question"),
    (r"\b(est-ce que|savez-vous|tu savais|vous saviez|as-tu|avez-vous)\b", 1.5, "interpellation"),
    (r"\b(secret|astuce|methode|technique|systeme|formule|strategie)\b", 1.4, "secret/méthode"),
    (r"\b(erreur|faux|mythe|mensonge|piege|jamais|personne|rien)\b", 1.6, "erreur/contraste"),
    (r"\b(mais|pourtant|sauf que|en fait|contrairement|au lieu de)\b", 1.0, "rupture"),
    (r"\b(regarde|ecoute|arrete|fais|essaie|prends|note|retiens)\b", 1.2, "injonction"),
    (r"\b(tu|vous|ton|ta|tes|votre|vos)\b", 1.0, "adresse directe"),
    (r"\b(incroyable|fou|dingue|choquant|surprenant|hallucinant|genial)\b", 1.3, "émotion"),
    (r"\b(meilleur|pire|plus grand|plus rapide|ultime|number one|n°1)\b", 1.2, "superlatif"),
    (r"\b(argent|euros?|dollars?|revenus?|gagner|gratuit|prix|cout|benefice|chiffre)\b", 1.1, "argent/résultat"),
    (r"\b(millions?|milliers?|personnes|clients|abonnes|vues|resultats?)\b", 0.9, "preuve sociale"),
    (r"\b(maintenant|aujourd'hui|avant|apres|demain|derniere|urgent)\b", 0.7, "urgence"),
    (r"\b(voici|voila|decouvre|decouvrez|je vais te montrer|on va voir)\b", 1.2, "promesse"),
    (r"\b(premiere|deuxieme|troisieme|etape|point)\b", 0.8, "structure"),
]

POWER_WORDS = {
    "secret", "erreur", "argent", "gratuit", "jamais", "personne", "meilleur",
    "pire", "rapide", "simple", "facile", "resultat", "preuve", "verite", "mythe",
    "astuce", "methode", "systeme", "strategie", "exemple", "attention", "danger",
    "opportunite", "chance", "incroyable", "fou", "test", "essai",
}

STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "dans", "sur", "pour",
    "avec", "sans", "que", "qui", "quoi", "est", "sont", "etre", "avoir", "mais",
    "donc", "alors", "comme", "plus", "moins", "tres", "tout", "tous", "toute",
    "cette", "ces", "son", "sa", "ses", "leur", "leurs", "nous", "vous", "ils",
    "elles", "je", "tu", "il", "elle", "on", "et", "ou", "a", "au", "aux", "en",
    "par", "ce", "cet", "mon", "ton", "notre", "votre", "the", "and", "of", "to",
    "in", "is", "are", "you", "your", "it", "this", "that", "for", "with",
}


def text_features(text: str, *, word_freq: Counter | None = None) -> dict[str, Any]:
    normalized = normalize_text(text)
    reasons: list[str] = []
    score = 0.0
    for pattern, weight, label in HOOK_PATTERNS:
        hits = len(re.findall(pattern, normalized))
        if hits:
            score += weight * min(2, hits)
            reasons.append(label)
    words = split_words(normalized)
    if re.search(r"\d", normalized):
        score += 1.0
        reasons.append("chiffre concret")
    power_hits = [word for word in words if word in POWER_WORDS]
    score += 0.45 * len(power_hits)
    if power_hits:
        reasons.append("mots forts : " + ", ".join(sorted(set(power_hits))[:3]))
    rare_ratio = 0.0
    if word_freq and words:
        content = [word for word in words if word not in STOPWORDS and len(word) > 3]
        if content:
            rare_ratio = sum(1 for word in content if word_freq[word] <= 1) / len(content)
    length = len(words)
    if 6 <= length <= 32:
        score += 1.0
    elif length < 4:
        score -= 0.5
    elif length > 45:
        score -= 0.8
    if text.strip().endswith("?"):
        score += 0.6
    return {
        "score": round(score, 3),
        "reasons": sorted(set(reasons)),
        "words": length,
        "rare_ratio": round(rare_ratio, 3),
        "power_words": sorted(set(power_hits)),
    }


def classify_hook(text: str) -> str:
    normalized = normalize_text(text)
    if re.search(r"\b(comment|pourquoi|combien|quel|qui|quoi|est-ce que)\b", normalized):
        return "question"
    if re.search(r"\b(erreur|faux|mythe|mensonge|jamais|personne|mais|pourtant|sauf)\b", normalized):
        return "contrarian"
    if re.search(r"\b(voici|decouvre|je vais te montrer|regarde|ecoute)\b", normalized):
        return "promesse"
    if re.search(r"\b(secret|astuce|methode|systeme|formule|technique)\b", normalized):
        return "valeur"
    if re.search(r"\b(argent|euros?|dollars?|resultats?|clients|millions?)\b", normalized):
        return "resultat"
    return "story"


def _sentence_energy(media: str | Path | None,
                     sentences: Sequence[dict[str, Any]]) -> list[dict[str, float]]:
    if not media:
        return [{"mean": 0.5, "peak": 0.5} for _ in sentences]
    try:
        from .music import segment_energy

        return segment_energy(media, sentences)
    except Exception:
        return [{"mean": 0.5, "peak": 0.5} for _ in sentences]


def score_sentences(transcript: dict[str, Any], *, media: str | Path | None = None) -> list[dict[str, Any]]:
    sentences = list(iter_sentences(transcript))
    if not sentences:
        raise SkillError("Transcription vide ou sans phrase exploitable.")
    tokens = [word for sentence in sentences for word in split_words(normalize_text(sentence["text"]))]
    word_freq = Counter(tokens)
    energies = _sentence_energy(media, sentences)
    duration = max(0.001, float(transcript.get("duration") or sentences[-1]["end"]))
    scored = []
    for sentence, energy in zip(sentences, energies):
        features = text_features(sentence["text"], word_freq=word_freq)
        length = max(0.1, float(sentence["end"]) - float(sentence["start"]))
        words_per_second = features["words"] / length
        pace = min(1.0, words_per_second / 3.2)
        semantic = min(1.0, features["score"] / 8.0)
        richness = min(1.0, features["rare_ratio"] * 2.2)
        audio = 0.5 * float(energy.get("mean", 0.5)) + 0.5 * float(energy.get("peak", 0.5))
        start_ratio = float(sentence["start"]) / duration
        position_bonus = 0.06 if start_ratio < 0.18 else 0.0
        score = 100 * (
            0.42 * semantic + 0.24 * audio + 0.16 * pace + 0.12 * richness + 0.06 * min(1.0, length / 8)
        ) + position_bonus * 100
        reasons = list(features["reasons"])
        if audio > 0.7:
            reasons.append("voix énergique")
        if pace > 0.85:
            reasons.append("débit rapide")
        if length < 2.0:
            reasons.append("phrase très courte")
        scored.append({
            "start": round(float(sentence["start"]), 3),
            "end": round(float(sentence["end"]), 3),
            "duration": round(length, 3),
            "text": sentence["text"],
            "score": round(min(100.0, score), 1),
            "hook_type": classify_hook(sentence["text"]),
            "energy": round(audio, 3),
            "words_per_second": round(words_per_second, 2),
            "reasons": sorted(set(reasons)),
            "features": features,
        })
    return scored


def build_clips(
    scored: Sequence[dict[str, Any]],
    *,
    min_duration: float = 18.0,
    max_duration: float = 45.0,
    max_clips: int = 8,
    padding: float = 0.12,
    total_duration: float | None = None,
) -> list[dict[str, Any]]:
    """Assemble des clips non chevauchants autour des meilleures phrases."""
    if not scored:
        return []
    by_score = sorted(scored, key=lambda s: s["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    for seed in by_score:
        if len(selected) >= max_clips:
            break
        if any(not (seed["end"] <= clip["start"] or seed["start"] >= clip["end"])
               for clip in selected):
            continue
        index = next(i for i, s in enumerate(scored) if s is seed)
        start_index = end_index = index
        start, end = float(seed["start"]), float(seed["end"])
        while end - start < min_duration:
            can_prev = start_index > 0
            can_next = end_index < len(scored) - 1
            if not can_prev and not can_next:
                break
            # ajoute le voisin qui prolonge le plus équilibré
            prev_gain = float(seed["start"]) - float(scored[start_index - 1]["start"]) if can_prev else -1
            next_gain = float(scored[end_index + 1]["end"]) - float(seed["end"]) if can_next else -1
            if can_next and (not can_prev or next_gain <= prev_gain):
                end_index += 1
                end = float(scored[end_index]["end"])
            else:
                start_index -= 1
                start = float(scored[start_index]["start"])
            if end - start >= max_duration:
                break
        if end - start > max_duration:
            end = start + max_duration
        start = max(0.0, start - padding)
        end = end + padding
        if total_duration:
            end = min(total_duration, end)
        if end <= start:
            continue
        if any(not (end <= clip["start"] or start >= clip["end"]) for clip in selected):
            continue
        members = [s for s in scored if s["start"] >= start and s["end"] <= end]
        average = sum(s["score"] for s in members) / max(1, len(members))
        clip_score = 0.6 * float(seed["score"]) + 0.4 * average
        selected.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "score": round(clip_score, 1),
            "hook": seed["text"],
            "hook_type": seed["hook_type"],
            "text": " ".join(member["text"] for member in members),
            "reasons": seed["reasons"],
            "seed_start": seed["start"],
        })
    selected.sort(key=lambda clip: clip["start"])
    for rank, clip in enumerate(sorted(selected, key=lambda c: c["score"], reverse=True), start=1):
        clip["rank"] = rank
    return sorted(selected, key=lambda clip: clip["start"])


def analyze_highlights(
    transcript: dict[str, Any],
    *,
    media: str | Path | None = None,
    min_duration: float = 18.0,
    max_duration: float = 45.0,
    max_clips: int = 8,
    padding: float = 0.12,
) -> dict[str, Any]:
    scored = score_sentences(transcript, media=media)
    clips = build_clips(scored, min_duration=min_duration, max_duration=max_duration,
                        max_clips=max_clips, padding=padding,
                        total_duration=float(transcript.get("duration") or 0) or None)
    best_hook = max(scored, key=lambda s: s["score"]) if scored else None
    return {
        "duration": transcript.get("duration"),
        "sentences_scored": len(scored),
        "clips": clips,
        "best_hook": best_hook,
        "top_sentences": sorted(scored, key=lambda s: s["score"], reverse=True)[:12],
        "stats": {
            "average_score": round(sum(s["score"] for s in scored) / max(1, len(scored)), 1),
            "max_score": round(max((s["score"] for s in scored), default=0), 1),
            "words_per_minute": round(
                sum(s["words_per_second"] for s in scored) / max(1, len(scored)) * 60, 1
            ),
        },
    }


def highlights_markdown(analysis: dict[str, Any], *, source: str | None = None) -> str:
    lines = [
        "# Moments forts détectés",
        "",
    ]
    if source:
        lines += [f"**Source** : `{source}`", ""]
    best = analysis.get("best_hook")
    if best:
        lines += [
            "## Meilleur hook",
            "",
            f"> {best['text']}",
            "",
            f"- **Timecode** : {fmt_clock(best['start'])} → {fmt_clock(best['end'])}",
            f"- **Score** : {best['score']}/100 · type *{best['hook_type']}*",
            f"- **Signaux** : {', '.join(best['reasons']) or '—'}",
            "",
        ]
    lines += [
        "## Clips recommandés",
        "",
        "| # | Timecode | Durée | Score | Type | Hook |",
        "|---|----------|-------|-------|------|------|",
    ]
    for clip in analysis.get("clips", []):
        hook = clip["hook"].replace("|", "\\|")
        if len(hook) > 95:
            hook = hook[:92] + "…"
        lines.append(
            f"| {clip['rank']} | {fmt_clock(clip['start'])} → {fmt_clock(clip['end'])} "
            f"| {clip['duration']:.0f}s | {clip['score']:.0f} | {clip['hook_type']} | {hook} |"
        )
    lines += [
        "",
        "## Phrases les plus fortes",
        "",
    ]
    for sentence in analysis.get("top_sentences", [])[:10]:
        hook = sentence["text"].replace("\n", " ")
        if len(hook) > 140:
            hook = hook[:137] + "…"
        lines.append(
            f"- **{sentence['score']:.0f}/100** · `{fmt_clock(sentence['start'])}` · "
            f"{sentence['hook_type']} — {hook}"
        )
    lines += [
        "",
        "## Lecture des signaux",
        "",
        "- **Score** : combinaison du potentiel sémantique (question, contraste, chiffres, mots forts), "
        "de l'énergie vocale, du débit et de la richesse lexicale.",
        "- Les clips sont non chevauchants et rallongés avec les phrases voisines pour atteindre "
        "une durée exploitable en Shorts/Reels.",
        "- Vérifie toujours le début du clip : le hook doit tenir dans les 1,5 premières secondes.",
        "",
    ]
    return "\n".join(lines)
