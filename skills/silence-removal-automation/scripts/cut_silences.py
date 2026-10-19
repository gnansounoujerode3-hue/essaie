#!/usr/bin/env python3
"""Auto-cut des silences : suppression ou accélération, avec remapping des sous-titres."""

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
from vesk.common import SkillError, fmt_clock, write_json  # noqa: E402
from vesk.ffmpeg import detect_silences, media_info  # noqa: E402
from vesk.media import (TimeMap, merge_ranges, render_cut, speech_ranges,  # noqa: E402
                        total_speed_aware_duration)
from vesk.transcript import (ensure_word_timings, load_transcript,  # noqa: E402
                             normalize_transcript, to_srt)


def build_plan(duration: float, silences: list[dict], args) -> tuple[list[dict], list[dict]]:
    if args.mode == "speed":
        plan: list[dict] = []
        speech: list[dict] = []
        cursor = 0.0
        for silence in sorted(silences, key=lambda s: s["start"]):
            start, end = float(silence["start"]), float(silence["end"])
            if start > cursor:
                plan.append({"start": cursor, "end": start, "speed": 1.0})
                speech.append({"start": cursor, "end": start})
            middle = (start + end) / 2
            # on garde une respiration de margin de chaque côté
            keep_start = min(middle, start + args.margin)
            keep_end = max(middle, end - args.margin)
            if keep_start > start:
                plan.append({"start": start, "end": keep_start, "speed": 1.0})
                speech.append({"start": start, "end": keep_start})
            if keep_end - keep_start >= 0.05:
                plan.append({"start": keep_start, "end": keep_end, "speed": args.speed})
            if end > keep_end:
                plan.append({"start": keep_end, "end": end, "speed": 1.0})
                speech.append({"start": keep_end, "end": end})
            cursor = end
        if duration > cursor:
            plan.append({"start": cursor, "end": duration, "speed": 1.0})
            speech.append({"start": cursor, "end": duration})
        return merge_ranges(plan), speech
    # mode remove (défaut)
    speech = speech_ranges(duration, silences, pad=args.margin, min_speech=0.08)
    plan = [{"start": r["start"], "end": r["end"], "speed": 1.0} for r in speech]
    return plan, speech


def report(plan: dict) -> str:
    lines = [
        "# Auto-cut des silences",
        "",
        f"- **Source** : `{plan['source']}`",
        f"- **Mode** : {plan['mode']}",
        f"- **Durée source** : {fmt_clock(plan['duration'])}",
        f"- **Durée finale** : {fmt_clock(plan['output_duration'])}",
        f"- **Gain** : {plan['saved_seconds']:.1f}s "
        f"({plan['saved_ratio'] * 100:.1f} %)",
        f"- **Silences détectés** : {plan['silence_count']} "
        f"({plan['silence_total']:.1f}s)",
        f"- **Coupes** : {plan['cut_count']}",
        "",
        "## Silences les plus longs",
        "",
        "| Timecode | Durée | Action |",
        "|----------|-------|--------|",
    ]
    for silence in sorted(plan["silences"], key=lambda s: s["duration"], reverse=True)[:10]:
        action = (f"accéléré ×{plan['speed']}" if plan["mode"] == "speed"
                  else "supprimé")
        lines.append(f"| {fmt_clock(silence['start'])} | {silence['duration']:.2f}s | {action} |")
    lines += [
        "",
        "## Plan de montage",
        "",
        "| # | Source | Sortie | Durée | Vitesse |",
        "|---|--------|--------|-------|---------|",
    ]
    for index, r in enumerate(plan["ranges"], start=1):
        lines.append(
            f"| {index} | {fmt_clock(r['start'])} → {fmt_clock(r['end'])} "
            f"| {fmt_clock(r['out_start'])} → {fmt_clock(r['out_end'])} "
            f"| {r['out_end'] - r['out_start']:.2f}s | ×{r['speed']:g} |"
        )
    lines += [
        "",
        "> Astuce : garde 60–120 ms de respiration autour de chaque phrase. Un montage sans "
        "aucun silence sonne mécanique ; l'objectif est un rythme, pas du vide.",
        "",
    ]
    return "\n".join(lines)


def run() -> int:
    parser = base_parser(
        "Détecte et supprime/accélère les silences pour un rythme rapide.",
        epilog="Exemples :\n"
               "  cut_silences.py --media interview.mp4 --render out.mp4 --mode remove\n"
               "  cut_silences.py --media vlog.mp4 --mode speed --speed 8 --render vlog-fast.mp4\n"
               "  cut_silences.py --media talk.mp4 --json plan.json --md plan.md --dry-run",
    )
    parser.add_argument("--media", "-m", required=True)
    parser.add_argument("--mode", choices=["remove", "speed"], default="remove")
    parser.add_argument("--speed", type=float, default=6.0,
                        help="Vitesse appliquée aux silences en mode speed (défaut 6)")
    parser.add_argument("--noise-db", type=float, default=-35.0,
                        help="Seuil de silence (dB, défaut -35)")
    parser.add_argument("--min-silence", type=float, default=0.35,
                        help="Durée minimale d'un silence à traiter")
    parser.add_argument("--margin", type=float, default=0.08,
                        help="Respiration conservée autour de la parole (s)")
    parser.add_argument("--transcript", "-t", help="Transcription à remapper sur le montage")
    parser.add_argument("--render", help="Vidéo de sortie")
    parser.add_argument("--json", help="Plan JSON")
    parser.add_argument("--md", help="Rapport Markdown")
    parser.add_argument("--srt", help="Sous-titres remappés")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.speed <= 1.0 and args.mode == "speed":
        raise SkillError("--speed doit être > 1 en mode speed.")
    info = media_info(args.media)
    if not info["has_audio"]:
        raise SkillError("Aucune piste audio à analyser.")
    print(f"🔍 Détection des silences ({info['duration']:.1f}s)…")
    silences = detect_silences(args.media, noise_db=args.noise_db,
                              min_duration=args.min_silence, dry_run=args.dry_run)
    ranges, speech = build_plan(info["duration"], silences, args)
    if not ranges:
        raise SkillError("Aucune plage de parole détectée : vérifie --noise-db.")
    time_map = TimeMap(ranges)
    plan_ranges = []
    for r in ranges:
        entry = time_map.entries[len(plan_ranges)]
        plan_ranges.append({
            **r,
            "out_start": round(entry["out_start"], 3),
            "out_end": round(entry["out_end"], 3),
        })
    saved = info["duration"] - time_map.duration
    plan = {
        "version": 1,
        "source": str(Path(args.media).resolve()),
        "mode": args.mode,
        "speed": args.speed,
        "duration": round(info["duration"], 3),
        "output_duration": round(time_map.duration, 3),
        "saved_seconds": round(saved, 3),
        "saved_ratio": round(saved / max(0.1, info["duration"]), 3),
        "silence_count": len(silences),
        "silence_total": round(sum(s["duration"] for s in silences), 3),
        "cut_count": max(0, len(ranges) - 1),
        "silences": silences,
        "speech_ranges": speech,
        "ranges": plan_ranges,
        "transcript": None,
    }
    if args.transcript:
        transcript = normalize_transcript(load_transcript(args.transcript))
        mapped = time_map.map_segments(ensure_word_timings(transcript["segments"]))
        plan["transcript"] = {"segments": mapped, "duration": time_map.duration,
                              "language": transcript.get("language")}
        if args.srt and not args.dry_run:
            save_text(to_srt(mapped), args.srt)
    if args.json:
        write_json(args.json, plan)
        print(f"✅ Plan JSON : {args.json}")
    if args.md:
        save_text(report(plan), args.md)
    if args.render:
        render_cut(args.media, args.render, ranges, crf=args.crf,
                   preset=args.preset, dry_run=args.dry_run)
        print(f"✅ Montage : {args.render} ({time_map.duration:.1f}s)")
        if args.srt and plan["transcript"] and not Path(args.srt).exists():
            save_text(to_srt(plan["transcript"]["segments"]), args.srt)
    if not any([args.json, args.md, args.render]):
        print(report(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
