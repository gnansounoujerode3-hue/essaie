#!/usr/bin/env python3
"""Prompts et payloads pour Midjourney, Runway, Luma, Sora, Kling, FLUX…"""

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
from vesk.common import SkillError, write_json  # noqa: E402
from vesk.imagegen import (build_prompt, build_request, execute,  # noqa: E402
                           load_providers, provider_guide, shot_plan,
                           shot_plan_markdown)


def run() -> int:
    parser = base_parser(
        "Génère des prompts et payloads API pour les modèles images/vidéos IA.",
        epilog="Exemples :\n"
               "  generate.py prompt --subject \"bureau de nuit, monteur devant sa timeline\" "
               "--provider runway --out prompt.json\n"
               "  generate.py request --provider luma --prompt \"...\" --out request.json\n"
               "  generate.py plan --media podcast.mp4 --provider runway --md shots.md\n"
               "  generate.py guide",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prompt_parser = sub.add_parser("prompt", help="Construire un prompt")
    prompt_parser.add_argument("--subject", required=True)
    prompt_parser.add_argument("--provider", default="midjourney",
                               choices=list(load_providers()["providers"]))
    prompt_parser.add_argument("--action", default="")
    prompt_parser.add_argument("--setting", default="")
    prompt_parser.add_argument("--camera", default="plan rapproché, léger push-in")
    prompt_parser.add_argument("--lighting", default="lumière naturelle douce")
    prompt_parser.add_argument("--style", default="cinématographique, réaliste, contraste élevé")
    prompt_parser.add_argument("--palette", default="tons chauds, jaune et noir")
    prompt_parser.add_argument("--mood", default="intense et motivant")
    prompt_parser.add_argument("--shot-type", default="broll",
                               choices=list(load_providers()["shot_types"]))
    prompt_parser.add_argument("--aspect", default="9:16")
    prompt_parser.add_argument("--negative", default="texte illisible, mains déformées, "
                                                    "visage déformé, logo, watermark")
    prompt_parser.add_argument("--duration", type=float, default=5.0)
    prompt_parser.add_argument("--out")

    request_parser = sub.add_parser("request", help="Payload API + curl")
    request_parser.add_argument("--provider", required=True,
                                choices=list(load_providers()["providers"]))
    request_parser.add_argument("--prompt", required=True)
    request_parser.add_argument("--aspect", default="9:16")
    request_parser.add_argument("--duration", type=float, default=5.0)
    request_parser.add_argument("--image", help="Image de départ (image-to-video)")
    request_parser.add_argument("--out")
    request_parser.add_argument("--execute", action="store_true",
                                help="Envoie réellement la requête (clé API requise)")
    request_parser.add_argument("--download", action="store_true",
                                help="Télécharge le rendu terminé")
    request_parser.add_argument("--output-dir", default="ai-assets")
    request_parser.add_argument("--timeout", type=float, default=600.0)

    plan_parser = sub.add_parser("plan", help="Plan de shots IA depuis une transcription")
    plan_parser.add_argument("--transcript", "-t")
    plan_parser.add_argument("--media", "-m")
    plan_parser.add_argument("--provider", default="runway",
                             choices=list(load_providers()["providers"]))
    plan_parser.add_argument("--every", type=float, default=8.0)
    plan_parser.add_argument("--max-shots", type=int, default=20)
    plan_parser.add_argument("--style", default="cinématographique, réaliste")
    plan_parser.add_argument("--aspect", default="9:16")
    plan_parser.add_argument("--duration", type=float, default=5.0)
    plan_parser.add_argument("--out")
    plan_parser.add_argument("--md")

    sub.add_parser("guide", help="Comparatif des providers")
    args = parser.parse_args()

    if args.command == "guide":
        print(provider_guide())
        return 0

    if args.command == "prompt":
        result = build_prompt(
            args.subject, provider=args.provider, action=args.action,
            setting=args.setting, camera=args.camera, lighting=args.lighting,
            style=args.style, palette=args.palette, mood=args.mood,
            shot_type=args.shot_type, aspect=args.aspect, negative=args.negative,
            duration=args.duration,
        )
        print(result["prompt"])
        if args.out:
            write_json(args.out, result)
            print(f"\n✅ {args.out}")
        return 0

    if args.command == "request":
        result = build_request(args.provider, args.prompt, aspect=args.aspect,
                               duration=args.duration, image_path=args.image)
        if args.out:
            write_json(args.out, result)
            print(f"✅ {args.out}")
        if args.execute:
            outcome = execute(result, download=args.download,
                              output_dir=args.output_dir, timeout=args.timeout)
            print(json.dumps(outcome, ensure_ascii=False, indent=2))
            return 0
        print(result["curl"])
        print(f"\n# Polling : {result['polling']}")
        print("# Ajoute --execute pour lancer la génération (clé API requise).")
        return 0

    if args.command == "plan":
        transcript = load_or_transcribe(args, download=Path("transcript.json"))
        plan = shot_plan(transcript, provider=args.provider, every=args.every,
                         max_shots=args.max_shots, style=args.style,
                         aspect=args.aspect, duration=args.duration)
        print(f"🎨 {len(plan)} shot(s) proposé(s)")
        if args.out:
            write_json(args.out, {"version": 1, "source": args.media, "shots": plan})
            print(f"✅ {args.out}")
        if args.md:
            save_text(shot_plan_markdown(plan), args.md)
        if not args.out and not args.md:
            print(shot_plan_markdown(plan))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
