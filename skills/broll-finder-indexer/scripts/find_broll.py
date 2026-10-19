#!/usr/bin/env python3
"""Sélectionne des B-rolls pour une transcription (recherche lexicale ou CLIP)."""

from __future__ import annotations

import csv
import sys
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

from vesk.assets import (ensure_manifest, filter_assets, plan_broll,  # noqa: E402
                         search)
from vesk.cli import base_parser, load_or_transcribe, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, fmt_clock, write_json  # noqa: E402


def markdown(plan: list[dict]) -> str:
    lines = [
        "# Plan B-roll",
        "",
        f"{len(plan)} illustration(s) sélectionnée(s).",
        "",
        "| # | Séquence | Proposition | B-roll | Score |",
        "|---|----------|-------------|--------|-------|",
    ]
    for index, item in enumerate(plan, start=1):
        name = Path(item["asset"]["path"]).name
        text = item["text"].replace("|", "\\|")
        if len(text) > 90:
            text = text[:87] + "…"
        lines.append(
            f"| {index} | {fmt_clock(item['start'])} → {fmt_clock(item['end'])} "
            f"| {text} | `{name}` | {item['score']} |"
        )
    lines += ["", "## Détail des choix", ""]
    for index, item in enumerate(plan, start=1):
        lines += [
            f"### {index}. {fmt_clock(item['start'])} — {Path(item['asset']['path']).name}",
            "",
            f"- **Requête** : `{item['query']}`",
            f"- **Extrait** : {item['clip_in']:.2f}s → {item['clip_out']:.2f}s",
            f"- **Score de pertinence** : {item['score']}",
            f"- **Texte** : {item['text']}",
            "",
        ]
    return "\n".join(lines)


def run() -> int:
    parser = base_parser(
        "Trouve les B-rolls les plus pertinents pour chaque phrase d'une transcription.",
        epilog="Exemples :\n"
               "  find_broll.py --manifest library.json --transcript t.json --out broll.json --md broll.md\n"
               "  find_broll.py --manifest library.json --query \"café matin\" --top 10\n"
               "  find_broll.py --manifest library.json --transcript t.json --semantic",
    )
    parser.add_argument("--library", "-l", action="append", help="Dossier de B-rolls")
    parser.add_argument("--manifest", help="Index JSON (index_library.py)")
    parser.add_argument("--transcript", "-t")
    parser.add_argument("--media", "-m")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--query", help="Recherche simple (sans transcription)")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--semantic", action="store_true",
                        help="Recherche CLIP (torch + transformers requis)")
    parser.add_argument("--cache", default=".vesk-index.json")
    parser.add_argument("--min-clip", type=float, default=2.0)
    parser.add_argument("--max-clip", type=float, default=5.0)
    parser.add_argument("--min-duration", type=float)
    parser.add_argument("--orientation", choices=["vertical", "horizontal", "square"])
    parser.add_argument("--no-reuse", action="store_true", default=True)
    parser.add_argument("--reuse", dest="no_reuse", action="store_false")
    parser.add_argument("--csv", help="Liste pour monteur (CSV)")
    parser.add_argument("--out", help="Plan JSON")
    parser.add_argument("--md", help="Plan Markdown")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    assets = ensure_manifest(args.library, args.manifest,
                             include_images=True)
    assets = filter_assets(assets, min_duration=args.min_duration,
                           orientation=args.orientation)
    if not assets:
        raise SkillError("Bibliothèque vide après filtrage.")

    if args.query:
        results = search(assets, args.query, semantic=args.semantic, top_k=args.top,
                         cache_path=args.cache)
        print(f"🔎 « {args.query} » — {len(results)} résultat(s)")
        for index, result in enumerate(results, start=1):
            asset = result["asset"]
            print(f"  {index:2d}. {result['score']:.3f}  {Path(asset['path']).name} "
                  f"({asset.get('duration', 0):.1f}s, {asset.get('width')}x{asset.get('height')})")
        if args.out:
            write_json(args.out, {"version": 1, "query": args.query, "results": results})
        return 0

    if not args.transcript and not args.media:
        parser.error("indique --query, ou --transcript/--media")
    transcript = load_or_transcribe(args, download=Path("transcript.json"))
    plan = plan_broll(
        transcript, assets, semantic=args.semantic, min_clip=args.min_clip,
        max_clip=args.max_clip, top_k=args.top, reuse=not args.no_reuse,
        cache_path=args.cache,
    )
    matched = sum(1 for item in plan if item["score"] > 0)
    print(f"🎞️  {len(plan)} B-roll(s) sélectionné(s) · {matched} correspondance(s) réelle(s)")
    if plan and matched == 0:
        print("⚠️  Aucune correspondance lexicale : sélection par rotation. Nomme tes rushes "
              "avec des mots-clés (ex: 'cafe-matin-01.mp4'), ajoute des sidecars .txt, "
              "ou utilise --semantic (CLIP).")
    if args.out:
        write_json(args.out, {"version": 1, "source": args.media, "plan": plan})
        print(f"✅ Plan : {args.out}")
    if args.md:
        save_text(markdown(plan), args.md)
    if args.csv:
        target = Path(args.csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Timeline start", "Timeline end", "Asset", "Clip in", "Clip out", "Query"])
            for item in plan:
                writer.writerow([item["start"], item["end"], item["asset"]["path"],
                                 item["clip_in"], item["clip_out"], item["query"]])
        print(f"✅ CSV : {target}")
    if not any([args.out, args.md, args.csv]):
        print(markdown(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
