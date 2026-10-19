#!/usr/bin/env python3
"""Motion design sans plugin : titres, lower thirds, compteurs, barres, CTA en ASS."""

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

from vesk.captions import parse_canvas  # noqa: E402
from vesk.cli import base_parser, main_guard  # noqa: E402
from vesk.common import SkillError  # noqa: E402
from vesk.ffmpeg import burn_subtitles, has_filter, media_info  # noqa: E402
from vesk.motion import build_motion, list_templates, palettes, write_ass  # noqa: E402


def hex_color(value: str) -> str:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise SkillError(f"Couleur invalide : {value}")
    return "#" + raw.upper()


def run() -> int:
    parser = base_parser(
        "Applique un template de motion design (titre, lower third, compteur, CTA…).",
        epilog="Exemples :\n"
               "  motion.py --template lower-third --text \"Marie Dupont\" --subtitle \"Monteuse\" "
               "--burn interview.mp4 --out lower.mp4\n"
               "  motion.py --template counter --number 87 --text \"% de rétention\" "
               "--duration 2.5 --out counter.ass\n"
               "  motion.py --list-templates",
    )
    parser.add_argument("--template", default="title")
    parser.add_argument("--text", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--number", type=float)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--out", "-o", default="motion.ass")
    parser.add_argument("--burn", help="Vidéo source sur laquelle incruster")
    parser.add_argument("--video-out", help="Vidéo de sortie (défaut : motion.mp4)")
    parser.add_argument("--canvas", default="auto", help="auto, 1080x1920, 1920x1080…")
    parser.add_argument("--font", default="Montserrat ExtraBold")
    parser.add_argument("--primary", help="#RRGGBB")
    parser.add_argument("--accent", help="#RRGGBB")
    parser.add_argument("--palette", help="vesk, ocean, sunset, mono")
    parser.add_argument("--position", choices=["bottom-left", "center"], default="bottom-left")
    parser.add_argument("--uppercase", dest="uppercase", action="store_true", default=True)
    parser.add_argument("--no-uppercase", dest="uppercase", action="store_false")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--list-templates", action="store_true")
    parser.add_argument("--list-palettes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_templates:
        for template in list_templates():
            fields = ", ".join(template.get("fields", [])) or "—"
            print(f"{template['id']:<14} {template['label']:<24} champs : {fields}")
        return 0
    if args.list_palettes:
        for name, colors in palettes().items():
            print(f"{name:<8} {colors}")
        return 0

    video_info = media_info(args.burn) if args.burn else None
    canvas = parse_canvas(args.canvas, video_info)
    palette = palettes().get(args.palette) if args.palette else None
    if args.palette and not palette:
        raise SkillError(f"Palette inconnue : {args.palette}")
    primary = hex_color(args.primary or (palette or {}).get("primary", "#FFFFFF"))
    accent = hex_color(args.accent or (palette or {}).get("accent", "#FFD400"))

    if args.template in {"title", "lower-third", "chapter", "quote", "cta"} and not args.text:
        raise SkillError(f"--text est requis pour le template {args.template}.")
    if args.template == "counter" and args.number is None:
        raise SkillError("--number est requis pour le template counter.")

    content = build_motion(
        args.template,
        text=args.text,
        subtitle=args.subtitle,
        start=args.start,
        duration=args.duration,
        canvas=canvas,
        font=args.font,
        primary=primary,
        accent=accent,
        number=args.number,
        position=args.position,
        uppercase=args.uppercase,
    )
    if args.dry_run:
        print(content)
        return 0
    ass_path = write_ass(args.out, content)
    print(f"✅ ASS : {ass_path}")
    if args.burn:
        if not (has_filter("subtitles") or has_filter("ass")):
            raise SkillError("FFmpeg sans libass : installe un build complet.")
        output = Path(args.video_out or "motion.mp4")
        burn_subtitles(args.burn, ass_path, output, crf=args.crf, preset=args.preset)
        print(f"✅ Vidéo : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
