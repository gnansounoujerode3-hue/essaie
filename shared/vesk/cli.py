"""Helpers CLI partagés : parsing, chargement transcription, sorties, erreurs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .common import SkillError, read_json, write_json
from .ffmpeg import media_info


def base_parser(description: str, *, epilog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="VESK 1.0.0")
    return parser


def add_transcript_args(parser: argparse.ArgumentParser, *,
                        media_option: bool = True) -> None:
    parser.add_argument("--transcript", "-t", help="Transcription JSON / SRT / VTT / TXT")
    if media_option:
        parser.add_argument("--media", "-m", help="Média source (transcrit si --transcript absent)")
    parser.add_argument("--language", default=None, help="Langue (fr, en, auto)")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "faster-whisper", "whispercpp", "whisper", "openai", "groq"],
                        help="Moteur de transcription si --media est utilisé")
    parser.add_argument("--model", default="small", help="Modèle Whisper (tiny, base, small, medium, large-v3)")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les actions sans exécuter")


def load_or_transcribe(args: argparse.Namespace, *, download: Path | None = None) -> dict[str, Any]:
    from .transcript import load_transcript, normalize_transcript
    from .speech import transcribe

    transcript_path = getattr(args, "transcript", None)
    media = getattr(args, "media", None)
    if transcript_path:
        transcript = load_transcript(transcript_path)
        if media and not transcript.get("duration"):
            transcript["duration"] = media_info(media)["duration"]
        return normalize_transcript(transcript)
    if not media:
        raise SkillError("Fournis --transcript FICHIER ou --media VIDEO.")
    transcript = transcribe(
        media,
        provider=getattr(args, "provider", "auto"),
        model=getattr(args, "model", "small"),
        language=getattr(args, "language", None),
        dry_run=getattr(args, "dry_run", False),
    )
    if download and not getattr(args, "dry_run", False):
        write_json(download, transcript)
    return normalize_transcript(transcript)


def save_or_print_json(data: Any, path: str | Path | None) -> None:
    if path:
        write_json(path, data)
        print(f"✅ JSON écrit : {path}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def save_text(content: str, path: str | Path | None) -> None:
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"✅ Fichier écrit : {target}")
    else:
        print(content)


def read_optional_json(path: str | None) -> Any:
    return read_json(path) if path else None


def _safe_stderr(message: str) -> None:
    try:
        print(message, file=sys.stderr)
    except UnicodeEncodeError:  # console Windows en cp1252
        print(message.encode("ascii", "replace").decode("ascii"), file=sys.stderr)


def main_guard(fn: Callable[[], int | None]) -> int:
    try:
        return int(fn() or 0)
    except SkillError as exc:
        _safe_stderr(f"❌ {exc}")
        return 2
    except KeyboardInterrupt:
        _safe_stderr("\nInterrompu.")
        return 130
    except BrokenPipeError:
        return 0
    except Exception as exc:  # pragma: no cover - filet de sécurité CLI
        _safe_stderr(f"❌ Erreur inattendue : {type(exc).__name__}: {exc}")
        _safe_stderr("   Relance avec --help ou consulte docs/TROUBLESHOOTING.md")
        return 1


def require_media(path: str | None) -> str:
    if not path:
        raise SkillError("Option --media obligatoire pour cette commande.")
    return path


def describe_media(path: str) -> dict[str, Any]:
    info = media_info(path)
    print(
        f"🎬 {Path(path).name} — {info['duration']:.1f}s · "
        f"{info['width']}x{info['height']} · {info['fps'] or '?'} fps · "
        f"{'audio' if info['has_audio'] else 'sans audio'}"
    )
    return info
