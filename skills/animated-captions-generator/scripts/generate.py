#!/usr/bin/env python3
"""Sous-titres animés (Hormozi, Ali Abdaal, karaoké…) en ASS, incrustés par FFmpeg."""

from __future__ import annotations

import json
import sys
import tempfile
import shutil
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

from vesk.captions import (describe_styles, events_to_srt, generate,  # noqa: E402
                           missing_font_warning, parse_canvas, write_ass)
from vesk.cli import base_parser, load_or_transcribe, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, read_json, write_json  # noqa: E402
from vesk.ffmpeg import burn_subtitles, has_filter, media_info  # noqa: E402


def _load_keywords(value: str | None) -> list[str] | None:
    if not value:
        return None
    if Path(value).exists():
        data = read_json(value)
        if isinstance(data, list):
            return [str(item) for item in data]
        if isinstance(data, dict):
            items = data.get("keywords", [])
            if isinstance(items, dict):
                return [str(key) for key in items]
            words = [str(item.get("word", "")) if isinstance(item, dict) else str(item)
                     for item in items]
            illustrated = [str(item["word"]) for item in items
                           if isinstance(item, dict) and item.get("emoji")]
            return illustrated or words
    return [word.strip() for word in value.split(",") if word.strip()]


def _load_emoji(value: str | None) -> dict | None:
    if not value:
        return None
    return read_json(value)


def _preview(video: str, ass_path: Path, out: Path, time: float) -> None:
    from vesk.ffmpeg import ffmpeg, subtitle_filter

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vesk-preview-") as tmp:
        simple = Path(tmp) / "captions.ass"
        shutil.copyfile(ass_path, simple)
        ffmpeg(["-ss", f"{time:.3f}", "-i", video, "-vf", subtitle_filter(simple),
                "-frames:v", "1", str(out)])


def run() -> int:
    parser = base_parser(
        "Génère des sous-titres animés style Hormozi / Ali Abdaal, avec emojis optionnels.",
        epilog="Exemples :\n"
               "  generate.py --media clip.mp4 --style hormozi --burn clip-captions.mp4\n"
               "  generate.py --transcript t.json --style ali --out subs.ass --srt subs.srt\n"
               "  generate.py --list-styles",
    )
    parser.add_argument("--transcript", "-t")
    parser.add_argument("--media", "-m", help="Vidéo/audio ; transcrit si --transcript absent")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--style", default="hormozi")
    parser.add_argument("--styles-file")
    parser.add_argument("--canvas", default="auto", help="auto, 1080x1920, 1920x1080, 1080x1080")
    parser.add_argument("--out", default="captions.ass", help="Fichier ASS de sortie")
    parser.add_argument("--burn", help="Vidéo de sortie avec sous-titres incrustés")
    parser.add_argument("--srt", help="Export SRT synchronisé")
    parser.add_argument("--events-json", help="Événements (pour After Effects / Resolve)")
    parser.add_argument("--emoji-map", help="JSON {mot: emoji} (emoji-keyword-mapper)")
    parser.add_argument("--keywords", help="Liste de mots à surligner (JSON ou a,b,c)")
    parser.add_argument("--font", help="Force la police (Montserrat, Inter, DejaVu Sans…)")
    parser.add_argument("--font-size", type=float)
    parser.add_argument("--max-words", type=int)
    parser.add_argument("--position", choices=["bottom", "center", "top"])
    parser.add_argument("--primary", help="Couleur principale #RRGGBB")
    parser.add_argument("--highlight", help="Couleur des mots-clés #RRGGBB")
    parser.add_argument("--outline-color")
    parser.add_argument("--border-style", type=int, choices=[1, 3])
    parser.add_argument("--uppercase", dest="uppercase", action="store_true", default=None)
    parser.add_argument("--no-uppercase", dest="uppercase", action="store_false")
    parser.add_argument("--preview", help="PNG d'aperçu")
    parser.add_argument("--preview-time", type=float)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--list-styles", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_styles:
        for style in describe_styles(args.styles_file):
            print(f"{style['name']:<14} {style['label']}")
        return 0
    if not args.transcript and not args.media:
        parser.error("indique --transcript ou --media")

    transcript = load_or_transcribe(args, download=Path("transcript.json"))
    video_info = media_info(args.media) if args.media else None
    canvas = parse_canvas(args.canvas, video_info)

    overrides: dict = {}
    for key in ("font", "font_size", "primary", "outline_color", "border_style", "uppercase"):
        value = getattr(args, key, None)
        if value is not None:
            overrides[key] = value
    if args.highlight:
        overrides["highlight_color"] = args.highlight
    if args.font_size:
        overrides["font_size_override"] = args.font_size
    if args.position:
        overrides["position_override"] = args.position
    if args.max_words:
        overrides["words_per_cue"] = args.max_words

    result = generate(
        transcript,
        style_name=args.style,
        styles_path=args.styles_file,
        canvas=canvas,
        keywords=_load_keywords(args.keywords),
        emoji_map=_load_emoji(args.emoji_map),
        overrides=overrides,
    )
    warning = missing_font_warning(result["style"])
    if warning:
        print(f"⚠️  {warning}")
    print(f"💬 {len(result['events'])} événement(s) · style {args.style} · "
          f"canvas {canvas[0]}x{canvas[1]}")
    if args.dry_run:
        print(result["ass"])
        return 0
    ass_path = write_ass(args.out, result["ass"])
    print(f"✅ ASS : {ass_path}")
    if args.srt:
        save_text(events_to_srt(result["events"]), args.srt)
    if args.events_json:
        write_json(args.events_json, {
            "version": 1, "style": args.style, "canvas": result["canvas"],
            "events": result["events"],
        })
    if args.burn:
        if not args.media:
            raise SkillError("--burn nécessite --media.")
        if not (has_filter("subtitles") or has_filter("ass")):
            raise SkillError("FFmpeg sans libass : installe un build complet ou utilise le fichier ASS.")
        burn_subtitles(args.media, ass_path, args.burn, crf=args.crf, preset=args.preset)
        print(f"✅ Vidéo : {args.burn}")
    if args.preview:
        if not args.media:
            raise SkillError("--preview nécessite --media.")
        duration = video_info["duration"] if video_info else 0
        time = args.preview_time if args.preview_time is not None else duration * 0.35
        _preview(args.media, ass_path, Path(args.preview), time)
        print(f"✅ Aperçu : {args.preview}")
    if not args.burn and not args.srt and not args.events_json and not args.preview:
        print(json.dumps({"style": args.style, "events": len(result["events"]),
                          "canvas": result["canvas"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
