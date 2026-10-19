#!/usr/bin/env python3
"""Dérushage : transcription enrichie, silences, tics de langage, débit, mots-clés."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

for _parent in Path(__file__).resolve().parents:
    _found = False
    for _name in ("shared", "_shared"):
        if (_parent / _name / "vesk").is_dir():
            sys.path.insert(0, str(_parent / _name))
            _found = True
            break
    if _found:
        break

from vesk.cli import (base_parser, load_or_transcribe, main_guard,  # noqa: E402
                      read_optional_json, save_or_print_json, save_text)
from vesk.common import SkillError, fmt_clock, normalize_text, write_json  # noqa: E402
from vesk.ffmpeg import detect_silences, media_info  # noqa: E402
from vesk.transcript import (all_words, ensure_word_timings, split_words,  # noqa: E402
                             text_of, to_srt, to_vtt)

STOPWORDS = set("""le la les un une des du de d dans sur pour avec sans que qui quoi est sont
être avoir mais donc alors comme plus moins très tout tous toute toutes cette ces son sa ses
leur leurs nous vous ils elles je tu il elle on et ou à au aux en par ce cet mon ton notre
votre mes tes nos vos leurs y a été était ai as avons avez ont avait étaient sera seront
the and of to in is are you your it this that for with on as at be been was were i we they
he she his her their our not no so but if or from by an""".split())

FILLERS = [
    "euh", "eu", "heu", "hum", "hmm", "bah", "ben", "bon", "bref", "genre",
    "voilà", "voila", "quoi", "en fait", "du coup", "tu vois", "vous voyez",
    "je veux dire", "comment dire", "on va dire", "en quelque sorte", "au niveau",
    "like", "you know", "i mean", "actually", "basically", "so yeah", "right",
    "kind of", "sort of",
]


def _gaps_from_transcript(segments: list[dict[str, Any]], duration: float) -> list[dict[str, float]]:
    silences = []
    previous_end = 0.0
    for segment in segments:
        start = float(segment["start"])
        if start - previous_end > 0.25:
            silences.append({"start": round(previous_end, 3), "end": round(start, 3),
                             "duration": round(start - previous_end, 3)})
        previous_end = max(previous_end, float(segment["end"]))
    if duration - previous_end > 0.25:
        silences.append({"start": round(previous_end, 3), "end": round(duration, 3),
                         "duration": round(duration - previous_end, 3)})
    return silences


def _find_fillers(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    words = all_words(transcript)
    normalized = [normalize_text(re.sub(r"[^\w'’-]", "", str(w["word"]))) for w in words]
    patterns = [pattern.split() for pattern in FILLERS]
    counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    index = 0
    while index < len(words):
        matched = None
        for pattern in sorted(patterns, key=len, reverse=True):
            size = len(pattern)
            if normalized[index:index + size] == pattern:
                matched = (" ".join(pattern), size)
                break
        if matched:
            label, size = matched
            counts[label] += 1
            examples.append({
                "filler": label,
                "start": round(float(words[index]["start"]), 3),
                "end": round(float(words[index + size - 1]["end"]), 3),
                "context": " ".join(str(w["word"]) for w in
                                    words[max(0, index - 4):index + size + 4]),
            })
            index += size
        else:
            index += 1
    return [
        {"filler": filler, "count": count,
         "examples": [e for e in examples if e["filler"] == filler][:5]}
        for filler, count in counts.most_common()
    ]


def _find_tics(transcript: dict[str, Any], *, min_count: int = 3) -> list[dict[str, Any]]:
    words = all_words(transcript)
    tokens = [normalize_text(re.sub(r"[^\w'’-]", "", str(w["word"]))) for w in words]
    tokens = [token for token in tokens if token]
    grams: Counter[tuple[str, ...]] = Counter()
    occurrences: dict[tuple[str, ...], list[float]] = {}
    for size in (2, 3, 4):
        for index in range(len(tokens) - size + 1):
            gram = tuple(tokens[index:index + size])
            if all(token in STOPWORDS for token in gram):
                continue
            if len(set(gram)) == 1:
                continue
            grams[gram] += 1
            occurrences.setdefault(gram, []).append(float(words[index]["start"]))
    results = []
    for gram, count in grams.most_common(60):
        if count < min_count:
            continue
        if any(set(gram).issubset(set(other)) and gram != other and grams[other] == count
               for other in grams if len(other) > len(gram)):
            continue
        results.append({
            "phrase": " ".join(gram),
            "count": count,
            "times": [round(time, 2) for time in occurrences[gram][:10]],
            "score": count * len(gram),
        })
    return sorted(results, key=lambda item: item["score"], reverse=True)[:12]


def analyze(args) -> dict[str, Any]:
    from vesk.transcript import load_transcript, normalize_transcript
    from vesk.speech import transcribe

    if args.transcript:
        transcript = normalize_transcript(load_transcript(args.transcript))
    elif args.media:
        transcript = normalize_transcript(transcribe(
            args.media, provider=args.provider, model=args.model,
            language=args.language, dry_run=args.dry_run,
        ))
        if args.json and not args.dry_run:
            write_json(args.json, transcript)
    else:
        raise SkillError("Fournis --transcript FICHIER ou --media VIDEO.")

    segments = ensure_word_timings(transcript.get("segments", []))
    words = all_words({"segments": segments})
    if not words:
        raise SkillError("Transcription vide.")
    duration = float(transcript.get("duration") or segments[-1]["end"])
    if args.media:
        info = media_info(args.media)
        duration = duration or info["duration"]
        try:
            silences = detect_silences(args.media, noise_db=args.noise_db,
                                       min_duration=args.min_silence)
        except SkillError:
            silences = _gaps_from_transcript(segments, duration)
    else:
        silences = _gaps_from_transcript(segments, duration)

    total_silence = sum(s["duration"] for s in silences)
    word_count = len(words)
    content_tokens = [
        normalize_text(re.sub(r"[^\w'’-]", "", str(w["word"])))
        for w in words
    ]
    content_tokens = [t for t in content_tokens if t and t not in STOPWORDS and len(t) > 2]
    top_words = [{"word": w, "count": c} for w, c in Counter(content_tokens).most_common(args.top_words)]

    fillers = _find_fillers(transcript)
    tics = _find_tics(transcript)
    questions = [
        {"start": s["start"], "end": s["end"], "text": s["text"]}
        for s in segments if str(s.get("text", "")).strip().endswith("?")
    ]
    slow = []
    for segment in segments:
        length = float(segment["end"]) - float(segment["start"])
        wpm = len(split_words(str(segment.get("text", "")))) / max(0.1, length) * 60
        if wpm < args.slow_wpm:
            slow.append({"start": segment["start"], "end": segment["end"],
                         "wpm": round(wpm, 1), "text": segment["text"]})

    stats = {
        "duration": round(duration, 2),
        "segments": len(segments),
        "words": word_count,
        "words_per_minute": round(word_count / max(0.1, duration) * 60, 1),
        "speech_seconds": round(duration - total_silence, 2),
        "silence_seconds": round(total_silence, 2),
        "silence_ratio": round(total_silence / max(0.1, duration), 3),
        "silence_count": len(silences),
        "longest_silence": round(max((s["duration"] for s in silences), default=0), 2),
        "questions": len(questions),
        "filler_count": sum(item["count"] for item in fillers),
        "tics_count": len(tics),
        "unique_content_words": len(set(content_tokens)),
    }
    threshold = max(1.0, duration * 0.015)
    long_silences = sorted(
        [s for s in silences if s["duration"] >= min(threshold, 2.0)],
        key=lambda s: s["duration"], reverse=True,
    )[:12]
    recommendations = _recommendations(stats, fillers, tics, long_silences)
    return {
        "version": 1,
        "source": str(Path(args.media).resolve()) if args.media else None,
        "language": transcript.get("language"),
        "stats": stats,
        "silences": silences,
        "long_silences": long_silences,
        "fillers": fillers,
        "tics": tics,
        "top_words": top_words,
        "questions": questions[:20],
        "slow_segments": slow[:20],
        "recommendations": recommendations,
        "transcript": {
            "segments": segments,
            "text": text_of(transcript),
        },
    }


def _recommendations(stats: dict[str, Any], fillers: list[dict[str, Any]],
                     tics: list[dict[str, Any]],
                     silences: list[dict[str, Any]]) -> list[str]:
    tips = []
    if stats["silence_ratio"] > 0.12:
        tips.append(
            f"{stats['silence_ratio'] * 100:.0f} % de la vidéo est silencieuse "
            f"({stats['silence_seconds']:.0f}s). Passe par silence-removal-automation "
            "en mode remove ou speed."
        )
    if stats["filler_count"]:
        top = ", ".join(f"« {f['filler']} » ×{f['count']}" for f in fillers[:3])
        tips.append(f"Tics de langage à couper : {top}. Coupe-les au montage ou atténue-les.")
    if tics:
        tips.append(
            f"Répétitions récurrentes : « {tics[0]['phrase']} » ({tics[0]['count']}×). "
            "Varie les formulations ou coupe les redites."
        )
    if stats["words_per_minute"] < 110:
        tips.append("Débit lent (< 110 mots/min) : accélère légèrement (1,05–1,15×) "
                    "ou coupe les hésitations.")
    elif stats["words_per_minute"] > 190:
        tips.append("Débit très rapide : ajoute des respirations visuelles (B-roll, cartes) "
                    "pour laisser le spectateur suivre.")
    if silences:
        tips.append(
            f"Silence le plus long : {silences[0]['duration']:.1f}s à "
            f"{fmt_clock(silences[0]['start'])} — candidat prioritaire à la coupe."
        )
    if stats["questions"] == 0:
        tips.append("Aucune question détectée : ajoute une question dans les 3 premières "
                    "secondes pour ouvrir une boucle.")
    return tips


def markdown(analysis: dict[str, Any]) -> str:
    stats = analysis["stats"]
    lines = [
        "# Dérushage & analyse de transcription",
        "",
        f"- **Durée** : {fmt_clock(stats['duration'])}",
        f"- **Mots** : {stats['words']} · **Débit** : {stats['words_per_minute']} mots/min",
        f"- **Silences** : {stats['silence_count']} ({stats['silence_seconds']}s, "
        f"{stats['silence_ratio'] * 100:.0f} % du total)",
        f"- **Tics de langage** : {stats['filler_count']} occurrence(s)",
        f"- **Questions** : {stats['questions']}",
        "",
        "## Silences les plus longs",
        "",
    ]
    if analysis["long_silences"]:
        lines += ["| Timecode | Durée |", "|----------|-------|"]
        for silence in analysis["long_silences"]:
            lines.append(f"| {fmt_clock(silence['start'])} | {silence['duration']:.2f}s |")
    else:
        lines.append("Aucun silence significatif.")
    lines += ["", "## Tics de langage", ""]
    if analysis["fillers"]:
        for filler in analysis["fillers"]:
            times = ", ".join(fmt_clock(e["start"]) for e in filler["examples"][:4])
            lines.append(f"- « **{filler['filler']}** » ×{filler['count']} — {times}")
    else:
        lines.append("Aucun tic détecté.")
    lines += ["", "## Répétitions / tics de structure", ""]
    if analysis["tics"]:
        for tic in analysis["tics"][:8]:
            lines.append(f"- « {tic['phrase']} » ×{tic['count']}")
    else:
        lines.append("Aucune répétition marquante.")
    lines += ["", "## Mots-clés dominants", ""]
    lines.append(", ".join(f"**{w['word']}** ({w['count']})" for w in analysis["top_words"]) or "—")
    if analysis["slow_segments"]:
        lines += ["", "## Segments lents (< seuil)", ""]
        for segment in analysis["slow_segments"][:8]:
            lines.append(f"- {fmt_clock(segment['start'])} · {segment['wpm']} mots/min — "
                         f"{segment['text'][:120]}")
    lines += ["", "## Recommandations", ""]
    for tip in analysis["recommendations"]:
        lines.append(f"- {tip}")
    lines += ["", "## Structure", ""]
    for segment in analysis["transcript"]["segments"][:60]:
        lines.append(f"- `{fmt_clock(segment['start'])}` {segment['text']}")
    if len(analysis["transcript"]["segments"]) > 60:
        lines.append(f"- … {len(analysis['transcript']['segments']) - 60} segment(s) supplémentaire(s)")
    lines.append("")
    return "\n".join(lines)


def run() -> int:
    parser = base_parser("Analyse une transcription : silences, tics, débit, mots-clés.")
    parser.add_argument("--transcript", "-t", help="Transcription JSON/SRT/VTT/TXT")
    parser.add_argument("--media", "-m", help="Vidéo/audio (transcrit si besoin)")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--json", help="Sortie JSON complète")
    parser.add_argument("--md", help="Rapport Markdown")
    parser.add_argument("--srt", help="Export SRT")
    parser.add_argument("--vtt", help="Export VTT")
    parser.add_argument("--txt", help="Export texte brut")
    parser.add_argument("--noise-db", type=float, default=-35.0)
    parser.add_argument("--min-silence", type=float, default=0.35)
    parser.add_argument("--slow-wpm", type=float, default=95.0)
    parser.add_argument("--top-words", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    analysis = analyze(args)
    if args.json:
        write_json(args.json, analysis)
        print(f"✅ JSON : {args.json}")
    if args.md:
        save_text(markdown(analysis), args.md)
    if args.srt:
        save_text(to_srt(analysis["transcript"]["segments"]), args.srt)
    if args.vtt:
        save_text(to_vtt(analysis["transcript"]["segments"]), args.vtt)
    if args.txt:
        save_text(analysis["transcript"]["text"] + "\n", args.txt)
    if not any([args.json, args.md, args.srt, args.vtt, args.txt]):
        print(json.dumps({k: v for k, v in analysis.items() if k != "transcript"},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
