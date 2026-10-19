"""Transcription audio : faster-whisper / openai-whisper en local, ou API distante.

Providers :
  * ``faster-whisper`` : local, rapide, recommandé (``pip install faster-whisper``)
  * ``whisper``        : local, référence OpenAI (``pip install openai-whisper``)
  * ``openai``         : API OpenAI Whisper (``OPENAI_API_KEY``)
  * ``groq``           : API Groq Whisper large-v3, très rapide (``GROQ_API_KEY``)
  * ``auto``           : premier provider disponible
"""

from __future__ import annotations

import json
import mimetypes
import os
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Sequence

from .common import SkillError, info, warn
from .ffmpeg import extract_audio, media_info


def _has_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def available_providers() -> list[str]:
    providers = []
    if _has_module("faster_whisper"):
        providers.append("faster-whisper")
    if _has_module("whisper"):
        providers.append("whisper")
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    if os.environ.get("GROQ_API_KEY"):
        providers.append("groq")
    return providers


def transcribe(
    media: str | Path,
    *,
    model: str = "small",
    language: str | None = None,
    provider: str = "auto",
    word_timestamps: bool = True,
    vad: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    media_path = Path(media)
    if not media_path.exists():
        raise SkillError(f"Fichier média introuvable : {media_path}")
    if dry_run:
        info(f"[dry-run] transcription {media_path} via {provider} (modèle {model})")
        return {"language": language, "duration": media_info(media_path)["duration"],
                "segments": [], "source": {"provider": provider, "model": model}}
    if provider == "auto":
        candidates = available_providers()
        if not candidates:
            raise SkillError(_missing_provider_message())
        provider = candidates[0]
        info(f"Provider de transcription sélectionné : {provider}")

    if provider in {"faster-whisper", "whisper"}:
        result = _local_transcribe(media_path, provider, model, language,
                                   word_timestamps=word_timestamps, vad=vad)
    elif provider in {"openai", "groq"}:
        result = _api_transcribe(media_path, provider, model, language)
    else:
        raise SkillError(f"Provider inconnu : {provider} "
                         f"(choix : auto, faster-whisper, whisper, openai, groq)")

    info_ = media_info(media_path)
    duration = info_["duration"]
    result.setdefault("duration", duration)
    result["source"] = {"provider": provider, "model": model, "file": str(media_path.resolve())}
    return result


def _missing_provider_message() -> str:
    return (
        "Aucun moteur de transcription disponible.\n\n"
        "Option recommandée (locale, gratuite, hors-ligne) :\n"
        "  pip install faster-whisper\n\n"
        "Autres options :\n"
        "  pip install openai-whisper            # Whisper OpenAI local\n"
        "  export OPENAI_API_KEY=...             # API OpenAI (payante)\n"
        "  export GROQ_API_KEY=...               # API Groq (rapide, offre gratuite)\n"
    )


def _local_transcribe(
    media: Path,
    provider: str,
    model_name: str,
    language: str | None,
    *,
    word_timestamps: bool,
    vad: bool,
) -> dict[str, Any]:
    language = _normalize_language(language)
    if provider == "faster-whisper":
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # pragma: no cover - dépend de l'installation
            raise SkillError(f"faster-whisper non importable : {exc}") from exc
        info(f"Chargement de faster-whisper « {model_name} » (téléchargement au 1er usage)…")
        try:
            model = WhisperModel(model_name, device="auto", compute_type="int8")
        except Exception:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments_iter, transcription_info = model.transcribe(
            str(media),
            language=language,
            vad_filter=vad,
            word_timestamps=word_timestamps,
            beam_size=5,
        )
        segments: list[dict[str, Any]] = []
        for index, segment in enumerate(segments_iter, start=1):
            words = []
            for word in getattr(segment, "words", None) or []:
                words.append({
                    "word": str(word.word).strip(),
                    "start": round(float(word.start), 3),
                    "end": round(float(word.end), 3),
                })
            segments.append({
                "id": index,
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": str(segment.text).strip(),
                "words": words,
            })
        return {
            "language": getattr(transcription_info, "language", language),
            "language_probability": round(
                float(getattr(transcription_info, "language_probability", 0.0) or 0.0), 3
            ),
            "duration": round(
                float(getattr(transcription_info, "duration", 0.0) or 0.0), 3
            ) or None,
            "segments": segments,
        }
    try:
        import whisper  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SkillError(f"openai-whisper non importable : {exc}") from exc
    info(f"Chargement de whisper « {model_name} »…")
    model = whisper.load_model(model_name)
    result = model.transcribe(str(media), language=language,
                              word_timestamps=word_timestamps, verbose=False)
    segments = []
    for index, segment in enumerate(result.get("segments", []), start=1):
        words = []
        for word in segment.get("words", []) or []:
            words.append({
                "word": str(word.get("word", "")).strip(),
                "start": round(float(word.get("start", segment["start"])), 3),
                "end": round(float(word.get("end", segment["end"])), 3),
            })
        segments.append({
            "id": index,
            "start": round(float(segment["start"]), 3),
            "end": round(float(segment["end"]), 3),
            "text": str(segment.get("text", "")).strip(),
            "words": words,
        })
    return {"language": result.get("language") or language,
            "duration": None, "segments": segments}


def _normalize_language(language: str | None) -> str | None:
    if not language or language.lower() in {"auto", "none", ""}:
        return None
    mapping = {
        "fr": "fr", "francais": "fr", "français": "fr",
        "en": "en", "anglais": "en", "english": "en",
        "es": "es", "pt": "pt", "de": "de", "it": "it", "ar": "ar",
    }
    return mapping.get(language.strip().lower(), language.strip().lower()[:2])


def _api_transcribe(media: Path, provider: str, model: str,
                    language: str | None) -> dict[str, Any]:
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        endpoint = f"{base}/audio/transcriptions"
        if not model or model in {"small", "medium", "large", "large-v3"}:
            model = "whisper-1"
    else:
        api_key = os.environ.get("GROQ_API_KEY")
        endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"
        if not model or model in {"small", "medium", "large", "large-v3"}:
            model = "whisper-large-v3"
    if not api_key:
        raise SkillError(f"Variable d'environnement manquante pour le provider {provider}.")

    with tempfile.TemporaryDirectory(prefix="vesk-asr-") as tmp:
        info("Extraction audio 16 kHz mono pour l'API…")
        audio = extract_audio(media, Path(tmp) / "audio.mp3", sample_rate=16000)
        size_mb = audio.stat().st_size / (1024 * 1024)
        if size_mb > 24:
            raise SkillError(
                f"Audio de {size_mb:.1f} Mo : au-delà de la limite API (~25 Mo). "
                "Découpe la vidéo ou utilise un moteur local."
            )
        fields = {
            "model": model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
        }
        if language and language.lower() not in {"auto", "none"}:
            fields["language"] = _normalize_language(language) or ""
        data = _post_multipart(endpoint, api_key, fields, audio)
    segments = []
    for index, segment in enumerate(data.get("segments", []), start=1):
        segments.append({
            "id": index,
            "start": round(float(segment.get("start", 0)), 3),
            "end": round(float(segment.get("end", 0)), 3),
            "text": str(segment.get("text", "")).strip(),
            "words": [],
        })
    words = [
        {"word": str(w.get("word", "")).strip(),
         "start": round(float(w.get("start", 0)), 3),
         "end": round(float(w.get("end", 0)), 3)}
        for w in data.get("words", []) or []
    ]
    if words and not any(s["words"] for s in segments):
        from .transcript import segments_from_words

        segments = segments_from_words(words)
    return {"language": data.get("language") or language,
            "duration": round(float(data.get("duration", 0) or 0), 3) or None,
            "segments": segments}


def _post_multipart(url: str, api_key: str, fields: dict[str, str],
                    file_path: Path) -> dict[str, Any]:
    boundary = f"----vesk{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    mime = mimetypes.guess_type(file_path.name)[0] or "audio/mpeg"
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
    body.extend(file_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        url, data=bytes(body), method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "vesk/1.0",
        },
    )
    info(f"Envoi à l'API de transcription ({file_path.stat().st_size // 1024} Ko)…")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise SkillError(f"Erreur API transcription ({exc.code}) : {detail}") from exc
    except urllib.error.URLError as exc:
        raise SkillError(f"API de transcription injoignable : {exc.reason}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SkillError(f"Réponse API non-JSON : {payload[:300]}") from exc


def describe_setup() -> dict[str, Any]:
    providers = available_providers()
    return {
        "available_providers": providers,
        "recommended": providers[0] if providers else None,
        "advice": None if providers else _missing_provider_message(),
    }


def elevenlabs_isolate(source: str | Path, output: str | Path, *,
                       api_key: str | None = None,
                       dry_run: bool = False) -> Path:
    """Isolation de la voix via l'API ElevenLabs Audio Isolation.

    ``POST https://api.elevenlabs.io/v1/audio-isolation`` avec un fichier audio.
    Adobe Podcast Enhance n'expose pas d'API publique : ce service (ou afftdn
    en local) est l'alternative automatisable.
    """
    key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SkillError(
            "Clé ELEVENLABS_API_KEY manquante. Crée-la sur "
            "https://elevenlabs.io/app/settings/api-keys puis exporte-la "
            "(ne colle jamais de clé dans le chat)."
        )
    src = Path(source)
    if not src.exists():
        raise SkillError(f"Fichier introuvable : {src}")
    if dry_run:
        info(f"[dry-run] isolation ElevenLabs de {src} → {output}")
        return Path(output)
    with tempfile.TemporaryDirectory(prefix="vesk-iso-") as tmp:
        wav = extract_audio(src, Path(tmp) / "input.wav", sample_rate=44100, channels=1)
        size_mb = wav.stat().st_size / (1024 * 1024)
        if size_mb > 50:
            raise SkillError(f"Audio de {size_mb:.1f} Mo : au-delà de la limite API ElevenLabs.")
        boundary = f"----vesk{uuid.uuid4().hex}"
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="audio"; filename="input.wav"\r\n')
        body.extend(b"Content-Type: audio/wav\r\n\r\n")
        body.extend(wav.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            "https://api.elevenlabs.io/v1/audio-isolation",
            data=bytes(body), method="POST",
            headers={
                "xi-api-key": key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "vesk/1.0",
            },
        )
        info("Isolation de la voix via ElevenLabs…")
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SkillError(f"Erreur ElevenLabs ({exc.code}) : {detail}") from exc
        except urllib.error.URLError as exc:
            raise SkillError(f"API ElevenLabs injoignable : {exc.reason}") from exc
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target
