#!/usr/bin/env python3
"""Analyse les courbes de rétention YouTube pour identifier les décrochages."""

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

from vesk.cli import base_parser, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, fmt_clock, read_json, write_json  # noqa: E402
from vesk.retention import (analyze_file, analyze_many, correlate,  # noqa: E402
                            retention_markdown)


def aggregate_markdown(data: dict) -> str:
    lines = [
        "# Rétention comparée",
        "",
        f"{data['count']} vidéo(s) analysée(s).",
        "",
        "## Vidéos",
        "",
        "| Vidéo | Durée | Rétention moyenne | Départ |",
        "|-------|-------|-------------------|--------|",
    ]
    for video in data["videos"]:
        lines.append(f"| {Path(video['file']).name} | {fmt_clock(video['duration'])} "
                     f"| {video['average_retention']:.1f} % | {video['start_retention']:.1f} % |")
    lines += ["", "## Courbe moyenne par position", "",
              "| Position | Rétention moyenne | Décrochages |", "|----------|-------------------|-------------|"]
    for point in data["average_curve"]:
        lines.append(f"| {point['position']} % | {point['retention']:.1f} % | {point['drops']} |")
    lines += ["", "## Zones faibles", ""]
    for zone in data["weakest_zones"]:
        lines.append(f"- **{zone['position']} %** de la vidéo : rétention moyenne "
                     f"{zone['retention']:.1f} % sur {zone['videos']} vidéo(s).")
    lines += ["", "## Lecture", "",
              "- Si la baisse est concentrée au même endroit sur plusieurs vidéos, "
              "c'est un problème de structure, pas de hasard.",
              "- Croise chaque zone faible avec la transcription correspondante "
              "(`--transcript`) pour identifier la phrase ou la séquence responsable.",
              "- Les pics indiquent ce qui retient : réutilise ces patterns.", ""]
    return "\n".join(lines)


def run() -> int:
    parser = base_parser(
        "Analyse un export CSV de rétention YouTube (ou un dossier d'exports).",
        epilog="Exemples :\n"
               "  analyze_retention.py --csv retention-video.csv --md rapport.md\n"
               "  analyze_retention.py --all exports/ --json retention.json --md compare.md\n"
               "  analyze_retention.py --csv r.csv --transcript t.json --md croise.md",
    )
    parser.add_argument("--csv", action="append", help="Export CSV (répétable)")
    parser.add_argument("--all", help="Dossier contenant plusieurs CSV")
    parser.add_argument("--transcript", "-t", help="Transcription pour croiser les drops")
    parser.add_argument("--json")
    parser.add_argument("--md")
    parser.add_argument("--window", type=float, default=5.0,
                        help="Fenêtre de calcul des drops (s)")
    parser.add_argument("--step", type=float, default=1.0, help="Rééchantillonnage (s)")
    parser.add_argument("--min-drop", type=float, default=3.0,
                        help="Perte minimale pour signaler un drop (points)")
    args = parser.parse_args()

    paths = []
    if args.csv:
        paths.extend(Path(item) for item in args.csv)
    if args.all:
        root = Path(args.all)
        if not root.is_dir():
            raise SkillError(f"Dossier introuvable : {root}")
        paths.extend(sorted(root.glob("*.csv")))
    if not paths:
        parser.error("indique --csv FICHIER ou --all DOSSIER")

    transcript = None
    if args.transcript:
        from vesk.transcript import load_transcript, normalize_transcript

        transcript = normalize_transcript(load_transcript(args.transcript))

    if len(paths) == 1:
        analysis = analyze_file(paths[0], window=args.window, step=args.step,
                                min_drop=args.min_drop)
        correlation = correlate(analysis, transcript) if transcript else None
        if correlation:
            analysis["correlation"] = correlation
        report = retention_markdown(analysis, source=str(paths[0]), correlation=correlation)
    else:
        analysis = analyze_many(paths, window=args.window, step=args.step)
        for result in analysis["per_video"]:
            if transcript:
                result["correlation"] = correlate(result, transcript)
        report = aggregate_markdown(analysis)
    print(report)
    if args.json:
        write_json(args.json, analysis)
        print(f"✅ JSON : {args.json}")
    if args.md:
        save_text(report, args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
