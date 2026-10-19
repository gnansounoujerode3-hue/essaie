#!/usr/bin/env python3
"""Génère un script After Effects : comp, placement des clips, marqueurs, sous-titres, BPM."""

from __future__ import annotations

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

from vesk.captions import generate, parse_canvas, write_ass  # noqa: E402
from vesk.cli import base_parser, main_guard  # noqa: E402
from vesk.common import SkillError, read_json, write_json  # noqa: E402
from vesk.nle_aftereffects import beat_reactive_expression, build_ae_jsx  # noqa: E402
from vesk.nle_premiere import normalize_plan, plan_summary, write_jsx  # noqa: E402


def run() -> int:
    parser = base_parser(
        "Automatise After Effects : composition, rushes, marqueurs, captions et expressions.",
        epilog="Exemples :\n"
               "  build_ae.py --plan edit.json --out ae.jsx --comp \"Short 01\"\n"
               "  build_ae.py --media clip.mp4 --captions captions-events.json --bpm 120 --out ae.jsx\n"
               "  build_ae.py --plan edit.json --transcript t.json --style hormozi --captions-out events.json",
    )
    parser.add_argument("--plan")
    parser.add_argument("--media")
    parser.add_argument("--clips", help="Highlights JSON (start/end)")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--comp", dest="comp_name")
    parser.add_argument("--markers", help="Marqueurs JSON")
    parser.add_argument("--transcript")
    parser.add_argument("--style", default="hormozi")
    parser.add_argument("--captions", help="Events JSON existants")
    parser.add_argument("--captions-out", help="Écrire les events générés")
    parser.add_argument("--ass", help="Écrire aussi les sous-titres ASS")
    parser.add_argument("--bpm", type=float, help="Ajoute un null « BEAT PULSE »")
    parser.add_argument("--out", "-o", default="after-effects.jsx")
    parser.add_argument("--save", help="Chemin .aep enregistré par le script")
    parser.add_argument("--expression", help="Affiche une expression beat-reactive et quitte")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.expression:
        print(beat_reactive_expression(args.bpm or 120, strength=6.0))
        return 0
    if args.plan:
        plan = normalize_plan(read_json(args.plan), default_source=args.media,
                              fps=args.fps, width=args.width, height=args.height)
    elif args.media:
        if args.clips:
            data = read_json(args.clips)
            clips = data.get("clips", data) if isinstance(data, dict) else data
            normalized = [{"source": args.media, "in": c["start"], "out": c["end"],
                           "name": f"{Path(args.media).stem} #{i + 1}"}
                          for i, c in enumerate(clips)]
        else:
            normalized = [{"source": args.media, "in": 0, "out": args.duration}]
        plan = normalize_plan({"clips": normalized}, fps=args.fps,
                              width=args.width, height=args.height)
    else:
        parser.error("indique --plan ou --media")

    print(plan_summary(plan))
    captions = []
    style = None
    if args.captions:
        data = read_json(args.captions)
        captions = data.get("events", data) if isinstance(data, dict) else data
    elif args.transcript:
        from vesk.transcript import load_transcript, normalize_transcript

        transcript = normalize_transcript(load_transcript(args.transcript))
        canvas = (plan["width"], plan["height"])
        result = generate(transcript, style_name=args.style, canvas=canvas)
        captions = result["events"]
        style = result["style"]
        if args.captions_out and not args.dry_run:
            write_json(args.captions_out, {"version": 1, "style": args.style,
                                           "canvas": result["canvas"], "events": captions})
            print(f"✅ Events captions : {args.captions_out}")
        if args.ass and not args.dry_run:
            write_ass(args.ass, result["ass"])
            print(f"✅ ASS : {args.ass}")
    markers = []
    if args.markers:
        data = read_json(args.markers)
        markers = data.get("markers", data) if isinstance(data, dict) else data

    jsx = build_ae_jsx(plan, comp_name=args.comp_name, markers=markers,
                       captions=captions, caption_style=style or {"font_size": 90},
                       beat_bpm=args.bpm, save_path=args.save)
    if args.dry_run:
        print(jsx)
        return 0
    write_jsx(args.out, jsx)
    print(f"✅ JSX After Effects : {args.out}")
    print("Dans After Effects : Fichier → Scripts → Exécuter un fichier de script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
