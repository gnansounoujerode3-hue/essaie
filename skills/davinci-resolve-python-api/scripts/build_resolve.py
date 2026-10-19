#!/usr/bin/env python3
"""Prépare un job DaVinci Resolve : FCPXML + script Python (timeline, markers, rendu, LUT)."""

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

from vesk.cli import base_parser, main_guard  # noqa: E402
from vesk.common import SkillError, read_json, write_json  # noqa: E402
from vesk.davinci import (build_color_script, build_resolve_script,  # noqa: E402
                          describe_workflow, write_resolve_script)
from vesk.nle_premiere import (normalize_plan, plan_summary, to_fcpxml,  # noqa: E402
                               write_outputs)


def run() -> int:
    parser = base_parser(
        "Génère un script Python Resolve + FCPXML pour automatiser timeline, markers et rendu.",
        epilog="Exemples :\n"
               "  build_resolve.py --plan edit.json --out-prefix resolve/short01 --render-dir ~/Renders\n"
               "  build_resolve.py --media clip.mp4 --clips highlights.json --lut LUTs/look.cube\n"
               "  build_resolve.py --plan edit.json --color --contrast 1.08 --saturation 1.1",
    )
    parser.add_argument("--plan")
    parser.add_argument("--media")
    parser.add_argument("--clips")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--out-prefix", "-o", default="resolve/job")
    parser.add_argument("--timeline", help="Nom de la timeline")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--markers")
    parser.add_argument("--lut")
    parser.add_argument("--render-dir", help="Active le rendu vers ce dossier")
    parser.add_argument("--render-name")
    parser.add_argument("--preset", help="Preset de rendu Resolve (.xml)")
    parser.add_argument("--format", help="Format de rendu (mp4, mov…)")
    parser.add_argument("--codec", default="H264")
    parser.add_argument("--color", action="store_true", help="Génère aussi le script d'étalonnage")
    parser.add_argument("--contrast", type=float)
    parser.add_argument("--saturation", type=float)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.plan:
        plan = normalize_plan(read_json(args.plan), default_source=args.media,
                              fps=args.fps, width=args.width, height=args.height,
                              name=args.timeline)
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
                              width=args.width, height=args.height, name=args.timeline)
    else:
        parser.error("indique --plan ou --media")

    prefix = Path(args.out_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    stem = prefix.name
    fcpxml_path = prefix.parent / f"{stem}.fcpxml"
    script_path = prefix.parent / f"{stem}-resolve.py"
    color_path = prefix.parent / f"{stem}-color.py"

    markers = []
    if args.markers:
        data = read_json(args.markers)
        markers = data.get("markers", data) if isinstance(data, dict) else data
    for clip in plan["clips"]:
        markers.append({"time": clip["start"], "name": clip["name"],
                        "note": f"in {clip['in']:.2f}s → out {clip['out']:.2f}s",
                        "duration": 0.0, "color": "Blue"})

    print(plan_summary(plan))
    if args.dry_run:
        print("--- FCPXML ---\n" + to_fcpxml(plan))
        print("--- RESOLVE ---\n" + build_resolve_script(plan, timeline_name=args.timeline,
                                                         fcpxml_path=str(fcpxml_path),
                                                         markers=markers,
                                                         lut_path=args.lut))
        return 0
    fcpxml_path.write_text(to_fcpxml(plan), encoding="utf-8")
    print(f"✅ FCPXML : {fcpxml_path}")
    render = None
    if args.render_dir:
        render = {"output_dir": args.render_dir, "name": args.render_name or plan["name"],
                  "preset": args.preset, "format": args.format, "codec": args.codec}
    script = build_resolve_script(plan, timeline_name=args.timeline,
                                  fcpxml_path=str(fcpxml_path), markers=markers,
                                  render=render, lut_path=args.lut)
    try:
        compile(script, str(script_path), "exec")
    except SyntaxError as exc:  # garde-fou : le script doit être exécutable dans Resolve
        raise SkillError(f"Script Resolve invalide : {exc}") from exc
    write_resolve_script(script_path, script)
    print(f"✅ Script Resolve : {script_path}")
    if args.color:
        color = build_color_script(args.lut, contrast=args.contrast,
                                   saturation=args.saturation,
                                   temperature=args.temperature)
        write_resolve_script(color_path, color)
        print(f"✅ Script couleur : {color_path}")
    summary = {"plan": plan, "fcpxml": str(fcpxml_path), "script": str(script_path),
               "render": render, "markers": markers}
    write_json(prefix.parent / f"{stem}-job.json", summary)
    print("\n" + describe_workflow())
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
