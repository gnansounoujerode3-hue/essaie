#!/usr/bin/env python3
"""Place automatiquement des SFX sur les transitions, mots-clés et apparitions de texte."""

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

from vesk.cli import base_parser, load_or_transcribe, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, read_json, write_json  # noqa: E402
from vesk.ffmpeg import media_info  # noqa: E402
from vesk.sfx import (cues_markdown, cues_to_csv, detect_cues, load_catalog,  # noqa: E402
                      mix_into_video, render_sfx_track, resolve_cues)


def _keywords(value: str | None) -> list[str] | None:
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
            return [str(item.get("word", item)) if isinstance(item, dict) else str(item)
                    for item in items]
    return [word.strip() for word in value.split(",") if word.strip()]


def run() -> int:
    parser = base_parser(
        "Détecte les moments de montage et y place automatiquement des SFX.",
        epilog="Exemples :\n"
               "  plan_cues.py --media clip.mp4 --keywords-out keywords.json --wav sfx.wav --mix clip-sfx.mp4\n"
               "  plan_cues.py --transcript t.json --styles '{\"intro\":\"braam\"}' --csv cues.csv\n"
               "  plan_cues.py --list",
    )
    parser.add_argument("--transcript", "-t")
    parser.add_argument("--media", "-m")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--keywords", help="Fichier keywords.json ou liste a,b,c")
    parser.add_argument("--caption-events", help="events JSON des sous-titres")
    parser.add_argument("--scenes", help="Scènes JSON (ou --detect-scenes)")
    parser.add_argument("--detect-scenes", action="store_true",
                        help="Détection de plans via OpenCV")
    parser.add_argument("--interval", type=float, default=6.0,
                        help="Fréquence des swooshes rythmiques (s)")
    parser.add_argument("--min-spacing", type=float, default=0.22)
    parser.add_argument("--max-cues", type=int, default=400)
    parser.add_argument("--styles", help="JSON de mapping (intro, transition, question, keyword…)")
    parser.add_argument("--sfx-dir", default="sfx")
    parser.add_argument("--catalog", help="Catalogue SFX alternatif")
    parser.add_argument("--wav", help="Piste SFX WAV de sortie")
    parser.add_argument("--mix", help="Vidéo finale avec SFX mixés")
    parser.add_argument("--sfx-gain", type=float, default=0.0)
    parser.add_argument("--original-gain", type=float, default=0.0)
    parser.add_argument("--out", help="Cues JSON")
    parser.add_argument("--md", help="Rapport Markdown")
    parser.add_argument("--csv", help="Cues CSV")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    if args.list:
        for effect in catalog["effects"]:
            print(f"{effect['id']:<14} {effect.get('default_gain_db', 0):>5} dB  "
                  f"{effect['label']} — {effect['usage']}")
        return 0
    if not args.transcript and not args.media:
        parser.error("indique --transcript ou --media")
    styles = json.loads(args.styles) if args.styles else {}
    transcript = load_or_transcribe(args, download=Path("transcript.json"))
    captions = read_json(args.caption_events) if args.caption_events else None
    if captions and isinstance(captions, dict):
        captions = captions.get("events", [])
    scenes = read_json(args.scenes) if args.scenes else None
    if args.detect_scenes and args.media:
        try:
            from vesk.faces import detect_scenes

            scenes = detect_scenes(args.media, max_samples=400)
            print(f"🎬 {len(scenes)} plan(s) détecté(s)")
        except SkillError as exc:
            print(f"⚠️  Détection de scènes ignorée : {exc}")
    cues = detect_cues(transcript, keywords=_keywords(args.keywords), styles=styles,
                       scenes=scenes, captions=captions, interval=args.interval,
                       min_spacing=args.min_spacing, max_cues=args.max_cues)
    resolved = resolve_cues(cues, catalog, args.sfx_dir)
    missing = [cue for cue in resolved if not cue["exists"]]
    if missing:
        print(f"⚠️  {len(missing)} SFX manquant(s) dans {args.sfx_dir} — "
              "lance build_catalog.py --generate")
    print(f"🔊 {len(resolved)} cue(s) SFX")
    if args.out:
        write_json(args.out, {"version": 1, "source": args.media, "cues": resolved})
        print(f"✅ JSON : {args.out}")
    if args.md:
        save_text(cues_markdown(resolved), args.md)
    if args.csv:
        cues_to_csv(resolved, args.csv)
        print(f"✅ CSV : {args.csv}")
    if args.wav:
        if not args.media:
            raise SkillError("--wav nécessite --media pour connaître la durée.")
        duration = media_info(args.media)["duration"]
        render_sfx_track(resolved, args.wav, duration=duration, dry_run=args.dry_run)
        print(f"✅ Piste SFX : {args.wav}")
        if args.mix:
            mix_into_video(args.media, args.wav, args.mix,
                           sfx_gain_db=args.sfx_gain,
                           original_gain_db=args.original_gain,
                           dry_run=args.dry_run)
            print(f"✅ Mix : {args.mix}")
    if not any([args.out, args.md, args.csv, args.wav]):
        print(cues_markdown(resolved))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
