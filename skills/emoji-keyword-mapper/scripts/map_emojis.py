#!/usr/bin/env python3
"""Détecte les mots-clés d'une transcription et leur associe emojis + timings."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

for _parent in Path(__file__).resolve().parents:
    _found = False
    for _name in ("shared", "_shared"):
        if (_parent / _name / "vesk").is_dir():
            sys.path.insert(0, str(_parent / _name))
            _found = True
            break
    if _found:
        break

from vesk.cli import base_parser, load_or_transcribe, main_guard, save_text  # noqa: E402
from vesk.common import (SkillError, fmt_clock, normalize_text, read_json,  # noqa: E402
                         skill_data, write_json)
from vesk.transcript import all_words, ensure_word_timings  # noqa: E402

STOPWORDS = set("""le la les un une des du de d dans sur pour avec sans que qui quoi est sont
etre avoir mais donc alors comme plus moins tres tout tous toute toutes cette ces son sa ses
leur leurs nous vous ils elles je tu il elle on et ou a au aux en par ce cet mon ton notre
votre mes tes nos vos leurs y a ete etait ai as avons avez ont avait etaient sera seront
the and of to in is are you your it this that for with on as at be been was were i we they
he she his her their our not no so but if or from by an vais veux peux fait faire dire dis
salut aujourd hui allez voici voila genre vraiment juste aussi encore autre autres""".split())

POWER = set("""secret astuce methode strategie systeme erreur argent gratuit resultat preuve
verite mythe business client clients vente croissance opportunite attention danger urgent
meilleur pire rapide simple facile""".split())


def _config(path: str | None) -> dict:
    return read_json(skill_data("emoji-keyword-mapper", "emojis.json", override=path))


def _word_key(word: str) -> str:
    raw = re.sub(r"[^\w'’-]", "", str(word)).replace("'", "").replace("’", "")
    return normalize_text(raw).replace(" ", "")


def detect_keywords(transcript: dict, config: dict, *, max_keywords: int = 30,
                    min_count: int = 1) -> list[dict]:
    words = all_words(transcript)
    tokens = [_word_key(w["word"]) for w in words]
    tokens = [token for token in tokens if token and token not in STOPWORDS and len(token) > 2]
    freq = Counter(tokens)
    times: dict[str, list[float]] = {}
    for word in words:
        token = _word_key(word["word"])
        if token:
            times.setdefault(token, []).append(float(word["start"]))
    results = []
    for token, count in freq.items():
        if count < min_count:
            continue
        score = count * (1 + min(len(token), 12) * 0.06)
        if token in POWER:
            score *= 1.4
        if " " in token:
            continue
        emoji = config["emojis"].get(token)
        # on garde les mots illustrables, les mots forts et les mots répétés
        if not emoji and token not in POWER and count < 2:
            continue
        results.append({
            "word": token,
            "count": count,
            "score": round(score, 2),
            "emoji": emoji,
            "times": [round(t, 2) for t in times.get(token, [])[:8]],
        })
    results.sort(key=lambda item: (item["emoji"] is not None, item["score"]), reverse=True)
    selected = results[:max_keywords]
    if not any(item["emoji"] for item in selected):
        fallback = config.get("fallback", "✨")
        for item in selected:
            item["emoji"] = fallback
    return selected


def build_timeline(transcript: dict, keywords: list[dict]) -> list[dict]:
    mapping = {item["word"]: item["emoji"] for item in keywords if item.get("emoji")}
    events = []
    for word in all_words(transcript):
        token = _word_key(word["word"])
        emoji = mapping.get(token)
        if emoji:
            events.append({
                "time": round(float(word["start"]), 3),
                "end": round(float(word["end"]), 3),
                "word": word["word"],
                "emoji": emoji,
                "position": "top-right" if len(events) % 2 == 0 else "top-left",
            })
    return events


def annotated_markdown(transcript: dict, keywords: list[dict]) -> str:
    mapping = {item["word"]: item["emoji"] for item in keywords if item.get("emoji")}
    lines = ["# Transcription annotée", "", "| Timecode | Texte |", "|----------|-------|"]
    for segment in ensure_word_timings(transcript["segments"]):
        rendered = []
        for word in segment["words"]:
            token = _word_key(word["word"])
            emoji = mapping.get(token)
            rendered.append(f"{word['word']} {emoji}" if emoji else str(word["word"]))
        lines.append(f"| {fmt_clock(segment['start'])} | {' '.join(rendered)} |")
    lines += ["", "## Mots-clés", "", "| Mot | × | Emoji | Timecodes |", "|-----|---|-------|-----------|"]
    for item in keywords:
        times = ", ".join(fmt_clock(t) for t in item["times"][:4])
        lines.append(f"| **{item['word']}** | {item['count']} | {item.get('emoji', '')} | {times} |")
    lines.append("")
    return "\n".join(lines)


def run() -> int:
    parser = base_parser(
        "Associe automatiquement des emojis aux mots-clés d'une transcription.",
        epilog="Exemples :\n"
               "  map_emojis.py --transcript t.json --out emoji-map.json --keywords-out keywords.json\n"
               "  map_emojis.py --media clip.mp4 --md annotated.md --timeline emoji-events.json",
    )
    parser.add_argument("--transcript", "-t")
    parser.add_argument("--media", "-m")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--config", help="Dictionnaire d'emojis JSON")
    parser.add_argument("--out", default="emoji-map.json", help="JSON consommé par les captions")
    parser.add_argument("--keywords-out", help="JSON des mots-clés scorés")
    parser.add_argument("--timeline", help="JSON des emojis horodatés")
    parser.add_argument("--md", help="Transcription annotée en Markdown")
    parser.add_argument("--max-keywords", type=int, default=20)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.transcript and not args.media:
        parser.error("indique --transcript ou --media")
    config = _config(args.config)
    transcript = load_or_transcribe(args, download=Path("transcript.json"))
    keywords = detect_keywords(transcript, config, max_keywords=args.max_keywords,
                               min_count=args.min_count)
    if not keywords:
        raise SkillError("Aucun mot-clé détecté.")
    emoji_map = {
        "version": 1,
        "map": {item["word"]: item["emoji"] for item in keywords if item.get("emoji")},
    }
    timeline = build_timeline(transcript, keywords)
    print(f"✨ {len(keywords)} mot(s)-clé(s) · {len(emoji_map['map'])} emoji(s) · "
          f"{len(timeline)} occurrence(s)")
    if args.dry_run:
        for item in keywords[:15]:
            print(f"   {item.get('emoji', '')} {item['word']} ×{item['count']}")
        return 0
    write_json(args.out, emoji_map)
    print(f"✅ Emoji map : {args.out}")
    if args.keywords_out:
        write_json(args.keywords_out, {"version": 1, "keywords": keywords})
        print(f"✅ Mots-clés : {args.keywords_out}")
    if args.timeline:
        write_json(args.timeline, {"version": 1, "events": timeline})
        print(f"✅ Timeline : {args.timeline}")
    if args.md:
        save_text(annotated_markdown(transcript, keywords), args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
