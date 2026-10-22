#!/usr/bin/env python3
"""Nettoie et masterise une voix : denoise, EQ, compression, loudness broadcast."""

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

from vesk.clean import PRESETS, analyze, clean_audio, clean_report  # noqa: E402
from vesk.cli import base_parser, main_guard, save_text  # noqa: E402
from vesk.common import SkillError, write_json  # noqa: E402
from vesk.ffmpeg import MEDIA_EXTENSIONS  # noqa: E402


def run() -> int:
    parser = base_parser(
        "Nettoie une piste audio (voix) et la masterise aux normes broadcast/social.",
        epilog="Exemples :\n"
               "  clean.py --input interview.wav --out voix.wav --preset podcast\n"
               "  clean.py --input rushes/ --batch --outdir cleaned --preset social --md rapport.md\n"
               "  clean.py --input clip.mp4 --analyze",
    )
    parser.add_argument("--input", "-i")
    parser.add_argument("--batch", action="store_true", help="Traite tous les médias d'un dossier")
    parser.add_argument("--out", "-o", default="cleaned.wav")
    parser.add_argument("--outdir", help="Dossier de sortie en mode --batch")
    parser.add_argument("--preset", default="voice", choices=list(PRESETS))
    parser.add_argument("--denoise", type=float, help="Force la réduction de bruit (0-97)")
    parser.add_argument("--target", type=float, help="Loudness cible en LUFS (ex : -14, -16, -23)")
    parser.add_argument("--no-loudnorm", action="store_true")
    parser.add_argument("--single-pass", action="store_true")
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--stereo", action="store_true")
    parser.add_argument("--json", help="Rapport JSON")
    parser.add_argument("--md", help="Rapport Markdown")
    parser.add_argument("--analyze", action="store_true", help="Mesures seulement")
    parser.add_argument("--elevenlabs", action="store_true",
                        help="Isolation de la voix via l'API ElevenLabs (ELEVENLABS_API_KEY)")
    parser.add_argument("--elevenlabs-out", help="Fichier isolé (défaut : <sortie>-isolated.wav)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.input:
        parser.error("indique --input FICHIER (ou --batch)")
    root = Path(args.input)
    if args.batch:
        if not root.is_dir():
            raise SkillError(f"Dossier introuvable : {root}")
        files = sorted(p for p in root.rglob("*") if p.suffix.lower() in MEDIA_EXTENSIONS)
        if not files:
            raise SkillError("Aucun média dans ce dossier.")
        output = Path(args.outdir or "cleaned")
        results = []
        for media in files:
            target = output / f"{media.stem}-clean.wav"
            print(f"\n🎧 {media.name}")
            result = clean_audio(media, target, preset=args.preset, denoise=args.denoise,
                                 target_i=args.target, loudnorm=not args.no_loudnorm,
                                 two_pass=not args.single_pass,
                                 sample_rate=args.sample_rate,
                                 channels=2 if args.stereo else 1,
                                 dry_run=args.dry_run)
            results.append(result)
            print(f"   → {target}")
        if args.json:
            write_json(args.json, {"version": 1, "results": results})
        if args.md:
            save_text("\n\n".join(clean_report(result) for result in results), args.md)
        return 0

    if args.analyze:
        data = analyze(root)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        if args.json:
            write_json(args.json, data)
        return 0
    source = root
    if args.elevenlabs:
        from vesk.speech import elevenlabs_isolate

        isolated = Path(args.elevenlabs_out or "isolated.wav")
        elevenlabs_isolate(root, isolated, dry_run=args.dry_run)
        print(f"✅ Voix isolée : {isolated}")
        source = isolated
    result = clean_audio(source, args.out, preset=args.preset, denoise=args.denoise,
                         target_i=args.target, loudnorm=not args.no_loudnorm,
                         two_pass=not args.single_pass, sample_rate=args.sample_rate,
                         channels=2 if args.stereo else 1, dry_run=args.dry_run)
    print(f"✅ Sortie : {args.out}")
    if result.get("after"):
        print(f"   {result['before'].get('input_lufs', '?')} LUFS → "
              f"{result['after'].get('input_lufs', '?')} LUFS")
    if args.json:
        write_json(args.json, result)
    if args.md:
        save_text(clean_report(result), args.md)
    if not args.json and not args.md:
        print(clean_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
