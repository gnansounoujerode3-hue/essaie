#!/usr/bin/env python3
"""Transcription ultra-précise avec timestamps (Whisper local ou API OpenAI/Groq)."""

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
from vesk.ffmpeg import MEDIA_EXTENSIONS, require, validate_media  # noqa: E402
from vesk.speech import available_providers, describe_setup, transcribe  # noqa: E402
from vesk.transcript import (normalize_transcript, to_srt, to_vtt,  # noqa: E402
                             transcript_summary)


def _markdown(transcript: dict) -> str:
    summary = transcript_summary(transcript)
    lines = [
        "# Transcription",
        "",
        f"- **Langue** : {summary['language'] or 'auto'}",
        f"- **Durée** : {fmt_clock(summary['duration'])}",
        f"- **Segments** : {summary['segments']} · **Mots** : {summary['words']}",
        f"- **Débit** : {summary['words_per_minute']} mots/min",
        "",
        "| Timecode | Texte |",
        "|----------|-------|",
    ]
    for segment in transcript["segments"]:
        text = str(segment["text"]).replace("|", "\\|")
        lines.append(f"| {fmt_clock(segment['start'])} | {text} |")
    lines.append("")
    return "\n".join(lines)


def _collect_inputs(value: str) -> list[Path]:
    path = Path(value)
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.suffix.lower() in MEDIA_EXTENSIONS)
        if not files:
            raise SkillError(f"Aucun média dans {path}")
        return files
    return [path]


def run() -> int:
    parser = base_parser(
        "Transcrit un média avec timestamps (faster-whisper, whisper, OpenAI, Groq).",
        epilog="Exemples :\n"
               "  transcribe.py interview.mp4 --language fr --formats json,srt,vtt,md\n"
               "  transcribe.py rushes/ --provider groq --model whisper-large-v3\n"
               "  transcribe.py --list-providers",
    )
    parser.add_argument("input", nargs="?", help="Fichier média ou dossier")
    parser.add_argument("--out-prefix", help="Préfixe des fichiers de sortie")
    parser.add_argument("--formats", default="json,srt,vtt,md",
                        help="Formats : json,srt,vtt,txt,md")
    parser.add_argument("--language", default=None, help="fr, en, auto…")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "faster-whisper", "whisper", "openai", "groq"])
    parser.add_argument("--model", default="small",
                        help="tiny, base, small, medium, large-v3 (ou whisper-1 / whisper-large-v3 en API)")
    parser.add_argument("--no-word-timestamps", action="store_true",
                        help="Segments seulement (plus rapide)")
    parser.add_argument("--no-vad", action="store_true", help="Désactive la détection de voix")
    parser.add_argument("--srt-max-chars", type=int, default=42)
    parser.add_argument("--list-providers", action="store_true")
    parser.add_argument("--doctor", action="store_true", help="Diagnostic de l'installation")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_providers or args.doctor:
        setup = describe_setup()
        print("Moteurs disponibles :", ", ".join(setup["available_providers"]) or "aucun")
        if setup["advice"]:
            print("\n" + setup["advice"])
        else:
            print("Recommandé :", setup["recommended"])
        if args.doctor:
            print("FFmpeg :", require())
        return 0
    if not args.input:
        parser.error("indique un fichier média ou un dossier (ou --list-providers)")

    formats = {fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()}
    unknown = formats - {"json", "srt", "vtt", "txt", "md"}
    if unknown:
        raise SkillError(f"Formats inconnus : {', '.join(sorted(unknown))}")

    inputs = _collect_inputs(args.input)
    for media in inputs:
        validate_media(media, need_audio=True)
        print(f"\n🎙️  {media.name}")
        raw = transcribe(
            media,
            provider=args.provider,
            model=args.model,
            language=args.language,
            word_timestamps=not args.no_word_timestamps,
            vad=not args.no_vad,
            dry_run=args.dry_run,
        )
        transcript = normalize_transcript(raw)
        summary = transcript_summary(transcript)
        print(f"   {summary['segments']} segments · {summary['words']} mots · "
              f"{summary['words_per_minute']} mots/min · langue {summary['language'] or '?'}")
        if args.dry_run:
            continue
        if args.out_prefix and len(inputs) == 1:
            base = Path(args.out_prefix)
        elif args.out_prefix:
            base = Path(args.out_prefix).with_name(
                f"{Path(args.out_prefix).name}-{media.stem}")
        else:
            base = media.with_suffix("")
        base.parent.mkdir(parents=True, exist_ok=True)
        if "json" in formats:
            write_json(base.with_suffix(".transcript.json"), transcript)
        if "srt" in formats:
            save_text(to_srt(transcript["segments"], max_chars=args.srt_max_chars),
                      base.with_suffix(".srt"))
        if "vtt" in formats:
            save_text(to_vtt(transcript["segments"], max_chars=args.srt_max_chars),
                      base.with_suffix(".vtt"))
        if "txt" in formats:
            text = "\n".join(f"[{fmt_clock(s['start'])}] {s['text']}"
                             for s in transcript["segments"])
            save_text(text + "\n", base.with_suffix(".txt"))
        if "md" in formats:
            save_text(_markdown(transcript), base.with_suffix(".transcript.md"))
        print(f"   → {base.with_suffix('.transcript.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(run))
