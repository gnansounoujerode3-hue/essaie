#!/usr/bin/env python3
"""Génère FCPXML/XMEML/EDL + scripts ExtendScript pour Adobe Premiere Pro."""

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
from vesk.nle_premiere import (jsx_export, jsx_import_plan,  # noqa: E402
                               jsx_markers, normalize_plan, plan_summary,
                               to_fcpxml, write_jsx, write_outputs)


def build_plan(args) -> dict:
    if args.plan:
        data = read_json(args.plan)
        return normalize_plan(data, default_source=args.media, fps=args.fps,
                              width=args.width, height=args.height, name=args.name)
    if not args.media:
        raise SkillError("Fournis --plan JSON ou --media + --clips (highlights).")
    if args.clips:
        data = read_json(args.clips)
        clips = data.get("clips", data) if isinstance(data, dict) else data
        # highlights : start/end = plage source
        normalized = [
            {"source": args.media, "in": c["start"], "out": c["end"],
             "name": f"{Path(args.media).stem} #{c.get('rank', i + 1)}"}
            for i, c in enumerate(clips)
        ]
        return normalize_plan({"clips": normalized}, fps=args.fps, width=args.width,
                              height=args.height, name=args.name)
    return normalize_plan({"clips": [{"source": args.media, "in": 0,
                                      "out": args.duration or 5.0}]},
                          fps=args.fps, width=args.width, height=args.height,
                          name=args.name)


def run() -> int:
    parser = base_parser(
        "Prépare un montage pour Premiere Pro : FCPXML, XMEML, EDL, marqueurs et JSX.",
        epilog="Exemples :\n"
               "  build_premiere.py --plan edit.json --out-prefix edit --jsx import.jsx\n"
               "  build_premiere.py --media interview.mp4 --clips highlights.json "
               "--out-prefix selects --formats fcpxml,xml,edl,markers\n"
               "  build_premiere.py --plan edit.json --jsx-markers markers.jsx --jsx-export export.jsx "
               "--preset h264.epr",
    )
    parser.add_argument("--plan", help="Plan JSON {fps, width, height, clips:[{source,in,out}]}")
    parser.add_argument("--media", help="Source unique")
    parser.add_argument("--clips", help="Highlights JSON (start/end)")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--out-prefix", "-o", default="premiere/edit")
    parser.add_argument("--name", help="Nom de séquence")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--formats", default="fcpxml,xml,edl,markers",
                        help="fcpxml,xml,edl,markers")
    parser.add_argument("--markers", help="JSON de marqueurs additionnels")
    parser.add_argument("--jsx", help="Script JSX d'import/placement")
    parser.add_argument("--jsx-markers", help="Script JSX de marqueurs")
    parser.add_argument("--jsx-export", help="Script JSX d'export")
    parser.add_argument("--preset", help="Preset .epr pour l'export")
    parser.add_argument("--summary-json", help="Résumé du plan en JSON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = build_plan(args)
    markers = list(plan.get("markers") or [])
    if args.markers:
        data = read_json(args.markers)
        markers.extend(data.get("markers", data) if isinstance(data, dict) else data)
    for clip in plan["clips"]:
        markers.append({
            "time": clip["start"],
            "name": clip["name"],
            "note": f"in {clip['in']:.2f}s · out {clip['out']:.2f}s",
            "duration": 0.0,
            "color": "Violet",
        })
    formats = [fmt.strip() for fmt in args.formats.split(",") if fmt.strip()]
    print(plan_summary(plan))
    if args.summary_json:
        write_json(args.summary_json, plan)
    if args.dry_run:
        if "fcpxml" in formats:
            print("\n--- FCPXML ---\n" + to_fcpxml(plan))
        return 0
    outputs = write_outputs(plan, args.out_prefix, formats=formats, markers=markers)
    for fmt, path in outputs.items():
        print(f"✅ {fmt.upper():<8} {path}")
    if args.jsx:
        write_jsx(args.jsx, jsx_import_plan(plan))
        print(f"✅ JSX import {args.jsx}")
    if args.jsx_markers:
        write_jsx(args.jsx_markers, jsx_markers(markers))
        print(f"✅ JSX marqueurs {args.jsx_markers}")
    if args.jsx_export:
        write_jsx(args.jsx_export, jsx_export(plan["name"], "/tmp/vesk-export.mp4",
                                              preset_path=args.preset))
        print(f"✅ JSX export {args.jsx_export}")
    print("\nImport Premiere : Fichier → Importer → sélectionne le .fcpxml "
          "(ou .xml), puis relance les scripts JSX depuis Fichier → Scripts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
