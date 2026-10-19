#!/usr/bin/env python3
"""Détecte les hooks et moments forts, puis sort des clips prêts à publier."""

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

from vesk.analyze import analyze_highlights, highlights_markdown  # noqa: E402
from vesk.cli import base_parser, load_or_transcribe, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, fmt_clock, slugify, write_json  # noqa: E402
from vesk.ffmpeg import burn_subtitles, media_info  # noqa: E402
from vesk.media import render_cut  # noqa: E402
from vesk.transcript import trim_to_range  # noqa: E402


def _render_clip(args, transcript, clip: dict, index: int, out_dir: Path) -> Path:
    if not args.media:
        raise SkillError("--render nécessite --media.")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"clip-{index:02d}-{slugify(clip['hook'], max_length=32)}.mp4"
    target = out_dir / name
    render_cut(args.media, target, [{"start": clip["start"], "end": clip["end"], "speed": 1.0}],
               crf=args.crf, preset=args.preset, dry_run=args.dry_run)
    if args.captions and not args.dry_run:
        from vesk.captions import generate, parse_canvas, write_ass

        info = media_info(target)
        trimmed = trim_to_range(transcript, clip["start"], clip["end"])
        canvas = parse_canvas("auto", info)
        result = generate(trimmed, style_name=args.captions, canvas=canvas)
        ass_path = target.with_suffix(".ass")
        write_ass(ass_path, result["ass"])
        burned = target.with_name(target.stem + "-captioned.mp4")
        burn_subtitles(target, ass_path, burned, crf=args.crf, preset=args.preset)
        target.unlink()
        target = burned
    return target


def run() -> int:
    parser = base_parser(
        "Extrait les hooks et moments forts d'une vidéo (scoring sémantique + énergie).",
        epilog="Exemples :\n"
               "  detect.py --media podcast.mp4 --language fr --clips 6 --json clips.json --md report.md\n"
               "  detect.py --transcript interview.json --render-dir clips/ --captions hormozi\n",
    )
    parser.add_argument("--transcript", "-t")
    parser.add_argument("--media", "-m")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--clips", type=int, default=8, help="Nombre de clips à extraire")
    parser.add_argument("--min", dest="min_duration", type=float, default=18.0)
    parser.add_argument("--max", dest="max_duration", type=float, default=45.0)
    parser.add_argument("--padding", type=float, default=0.12)
    parser.add_argument("--json", help="Analyse JSON")
    parser.add_argument("--md", help="Rapport Markdown")
    parser.add_argument("--render-dir", help="Dossier des clips rendus")
    parser.add_argument("--captions", help="Style de sous-titres à incruster (hormozi, ali…)")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    transcript = load_or_transcribe(args, download=Path("transcript.json"))
    print(f"🧠 Scoring de {len(transcript['segments'])} segments…")
    analysis = analyze_highlights(
        transcript,
        media=args.media,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        max_clips=args.clips,
        padding=args.padding,
    )
    analysis["source"] = args.media
    if args.json:
        write_json(args.json, analysis)
        print(f"✅ JSON : {args.json}")
    if args.md:
        save_text(highlights_markdown(analysis, source=args.media), args.md)
    if not args.json and not args.md:
        print(highlights_markdown(analysis, source=args.media))
    if args.render_dir:
        rendered = []
        for index, clip in enumerate(analysis["clips"], start=1):
            target = _render_clip(args, transcript, clip, index, Path(args.render_dir))
            clip["rendered"] = str(target)
            rendered.append(target)
            print(f"🎬 {target} ({fmt_clock(clip['start'])} → {fmt_clock(clip['end'])})")
        if args.json and not args.dry_run:
            write_json(args.json, analysis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
