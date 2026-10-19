#!/usr/bin/env python3
"""Analyse tempo/beats d'une musique et cale les coupes ou accents visuels dessus."""

from __future__ import annotations

import json
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
from vesk.ffmpeg import media_info  # noqa: E402
from vesk.music import analyze, plan_cuts, render_accent, snap_times  # noqa: E402


def report(analysis: dict, snapped: list[dict] | None = None) -> str:
    lines = [
        "# Analyse rythmique",
        "",
        f"- **Fichier** : `{analysis['file']}`",
        f"- **Extrait** : {fmt_clock(analysis['start'])} → {fmt_clock(analysis['end'])}",
        f"- **BPM estimé** : **{analysis['bpm']}**",
        f"- **Période** : {analysis['period']:.3f}s",
        f"- **Confiance** : {analysis['confidence'] * 100:.0f} %",
        f"- **Beats détectés** : {analysis['beat_count']}",
        "",
        "## Candidats BPM",
        "",
        "| BPM | Score |",
        "|-----|-------|",
    ]
    for candidate in analysis.get("candidates", []):
        lines.append(f"| {candidate['bpm']} | {candidate['score']} |")
    lines += ["", "## Premiers beats", "",
              ", ".join(fmt_clock(beat) for beat in analysis["beats"][:24]) or "—"]
    if snapped:
        lines += ["", "## Coupes recalées", "", "| Original | Recalé | Décalage | Beat |",
                  "|----------|--------|----------|------|"]
        for item in snapped:
            lines.append(
                f"| {fmt_clock(item['original'])} | {fmt_clock(item['snapped'])} "
                f"| {item['delta']:+.2f}s | {'oui' if item['snapped_to_beat'] else 'non'} |"
            )
    lines += [
        "",
        "## Comment utiliser",
        "",
        "- Coupe sur les beats **1 et 3** pour un montage pop, sur tous les beats pour du très rapide.",
        "- Évite de caler chaque coupe : alterne coupes sur beat et respirations pour ne pas lasser.",
        "- Un BPM estimé à 2× la réalité (ex. 150 au lieu de 75) est fréquent : vérifie à l'oreille.",
        "",
    ]
    return "\n".join(lines)


def _load_times(path: str) -> list[float]:
    data = read_json(path)
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return [float(item.get("start", item.get("time", 0))) for item in data]
        return [float(value) for value in data]
    if isinstance(data, dict):
        if "clips" in data:
            return [float(item.get("start", 0)) for item in data["clips"]]
        if "times" in data:
            return [float(value) for value in data["times"]]
    raise SkillError("Format de times invalide (liste de secondes ou {'clips': [...]})")


def run() -> int:
    parser = base_parser(
        "Détecte le tempo et synchronise coupes, accents et transitions sur les beats.",
        epilog="Exemples :\n"
               "  beat_sync.py --media clip.mp4 --json beats.json --md beats.md\n"
               "  beat_sync.py --media clip.mp4 --accent clip-beat.mp4 --style flash\n"
               "  beat_sync.py --media clip.mp4 --snap-times clips.json --snapped-out clips-synced.json",
    )
    parser.add_argument("--media", "-m", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--json", help="Analyse JSON")
    parser.add_argument("--md", help="Rapport Markdown")
    parser.add_argument("--every", type=int, default=4, help="Coupe tous les N beats")
    parser.add_argument("--cuts-json", help="Plan de coupes régulier JSON")
    parser.add_argument("--snap-times", help="Temps à recaler sur les beats")
    parser.add_argument("--snapped-out", help="Sortie des temps recalés")
    parser.add_argument("--tolerance", type=float, default=0.25)
    parser.add_argument("--accent", help="Vidéo avec accents visuels sur les beats")
    parser.add_argument("--style", choices=["flash", "bars", "pulse"], default="flash")
    parser.add_argument("--strength", type=float, default=0.16)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    analysis = analyze(args.media, start=args.start, end=args.end)
    duration = media_info(args.media)["duration"]
    print(f"🥁 {analysis['bpm']} BPM · confiance {analysis['confidence'] * 100:.0f} % · "
          f"{analysis['beat_count']} beats")
    if args.json:
        write_json(args.json, analysis)
        print(f"✅ Analyse : {args.json}")
    if args.cuts_json:
        cuts = plan_cuts(min(duration, args.end or duration), analysis["bpm"],
                         every=args.every, start=args.start)
        write_json(args.cuts_json, {"bpm": analysis["bpm"], "every": args.every, "cuts": cuts})
        print(f"✅ Coupes : {args.cuts_json} ({len(cuts)} points)")
    snapped = None
    if args.snap_times:
        times = _load_times(args.snap_times)
        snapped = snap_times(times, analysis["beats"], tolerance=args.tolerance)
        if args.snapped_out:
            write_json(args.snapped_out, {"version": 1, "bpm": analysis["bpm"],
                                          "times": snapped})
            print(f"✅ Temps recalés : {args.snapped_out}")
    if args.md:
        save_text(report(analysis, snapped), args.md)
    if args.accent:
        render_accent(args.media, args.accent, analysis["beats"], style=args.style,
                      strength=args.strength, crf=args.crf, preset=args.preset,
                      dry_run=args.dry_run)
        print(f"✅ Accents : {args.accent}")
    if not any([args.json, args.md, args.cuts_json, args.snap_times, args.accent]):
        print(report(analysis, snapped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
