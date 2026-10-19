"""Découverte et wrappers FFmpeg/ffprobe (aucune dépendance Python)."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from .common import SkillError, info, run, warn

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".m2ts", ".mpg", ".mpeg",
}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    candidate = os.environ.get("FFMPEG_BIN")
    if candidate and Path(candidate).exists():
        return str(Path(candidate))
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # roue PyPI très pratique en CI / environnements sans apt
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    for path in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/snap/bin/ffmpeg"):
        if Path(path).exists():
            return path
    raise SkillError(
        "FFmpeg introuvable. Installe-le puis relance :\n"
        "  macOS : brew install ffmpeg\n"
        "  Ubuntu/Debian : sudo apt install ffmpeg\n"
        "  Windows : winget install Gyan.FFmpeg\n"
        "  Sans admin : pip install imageio-ffmpeg (binaire embarqué)"
    )


@lru_cache(maxsize=1)
def ffprobe_bin() -> str | None:
    candidate = os.environ.get("FFPROBE_BIN")
    if candidate and Path(candidate).exists():
        return str(Path(candidate))
    found = shutil.which("ffprobe")
    if found:
        return found
    sibling = Path(ffmpeg_bin()).with_name("ffprobe")
    if sibling.exists():
        return str(sibling)
    # imageio-ffmpeg ne livre pas ffprobe : on retombe sur ffmpeg -i.
    return None


def version() -> str:
    proc = run([ffmpeg_bin(), "-version"], capture=True)
    return (proc.stdout or "").splitlines()[0] if proc.stdout else "ffmpeg"


def require() -> str:
    """Vérifie FFmpeg et renvoie sa version."""
    bin_path = ffmpeg_bin()
    proc = run([bin_path, "-version"], check=False, capture=True)
    if proc.returncode != 0:
        raise SkillError(f"FFmpeg ne fonctionne pas : {bin_path}")
    return (proc.stdout or "ffmpeg").splitlines()[0]


@lru_cache(maxsize=1)
def filter_list() -> set[str]:
    proc = run([ffmpeg_bin(), "-hide_banner", "-filters"], check=False, capture=True,
               quiet=True)
    filters: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        # FFmpeg 9 a fait évoluer la largeur des colonnes : on reste tolérant.
        match = re.match(r"\s*[A-Z.]{3}\s+(\S+)\s+", line)
        if match:
            filters.add(match.group(1))
    return filters


@lru_cache(maxsize=None)
def has_filter(name: str) -> bool:
    """Vrai si le filtre existe réellement dans ce build.

    ``-h filter=NAME`` est stable entre versions (contrairement au format de
    ``-filters``), et répond « Unknown filter » quand le filtre manque.
    """
    proc = run([ffmpeg_bin(), "-hide_banner", "-h", f"filter={name}"],
               check=False, capture=True, quiet=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    # FFmpeg répond « Unknown filter 'x'. » quand le filtre n'est pas compilé.
    # Le libellé d'aide, lui, varie selon les versions : on ne l'analyse pas.
    lowered = output.lower()
    if any(marker in lowered for marker in ("unknown filter", "no such filter",
                                            "filter not found")):
        return False
    if output.strip():
        return True
    return name in filter_list()


def escape_filter_path(path: str | Path) -> str:
    """Échappe un chemin pour l'option ``filename`` d'un filtre FFmpeg.

    Gère les deux pièges : les deux-points de lecteur Windows (``C:\…``) et les
    caractères spéciaux du parseur de filtergraph (``'``, ``,``, ``[``, ``]``).
    """
    raw = Path(path).expanduser()
    try:
        if raw.exists():
            raw = raw.resolve()
    except OSError:
        pass
    text = raw.as_posix()
    for char in ("\\", ":", "'", "[", "]", ",", ";"):
        text = text.replace(char, "\\" + char)
    return text


def subtitle_filter(path: str | Path) -> str:
    """Expression ``-vf`` pour incruster un SRT/ASS, compatible FFmpeg 7 → 9."""
    escaped = escape_filter_path(path)
    for name in ("subtitles", "ass"):
        if has_filter(name):
            return f"{name}=filename='{escaped}'"
    raise SkillError(
        "Ce FFmpeg n'a pas le rendu de sous-titres (libass). Installe un build complet "
        "(brew install ffmpeg / apt install ffmpeg) ou utilise le fichier ASS dans un NLE."
    )


def ffmpeg(args: Sequence[str], *, check: bool = True, dry_run: bool = False,
           quiet: bool = False):
    return run([ffmpeg_bin(), "-hide_banner", "-y", *[str(a) for a in args]],
               check=check, dry_run=dry_run, quiet=quiet)


def ffprobe(path: str | Path, *, extra: Sequence[str] = ()) -> dict[str, Any]:
    binary = ffprobe_bin()
    if not binary:
        return _probe_with_ffmpeg(path)
    args = [binary, "-v", "error", "-print_format", "json", "-show_format",
            "-show_streams", *extra, str(path)]
    proc = run(args, check=False, capture=True)
    if proc.returncode != 0:
        # ffprobe peut être absent ou être un simple lien vers ffmpeg : repli robuste
        fallback = _probe_with_ffmpeg(path)
        if fallback.get("format", {}).get("duration"):
            return fallback
        raise SkillError(f"Fichier média illisible : {path}\n{(proc.stderr or '').strip()}")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return _probe_with_ffmpeg(path)


def _probe_with_ffmpeg(path: str | Path) -> dict[str, Any]:
    proc = run([ffmpeg_bin(), "-hide_banner", "-i", str(path)], check=False, capture=True)
    stderr = proc.stderr or ""
    duration = 0.0
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if match:
        h, m, s = match.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)
    width, height, fps = None, None, None
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", stderr)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
    if match:
        fps = float(match.group(1))
    has_audio = bool(re.search(r"Audio:", stderr))
    has_video = bool(re.search(r"Video:", stderr))
    codec_match = re.search(r"Video:\s*([a-zA-Z0-9_-]+)", stderr)
    return {
        "format": {"duration": str(duration), "size": str(Path(path).stat().st_size) if Path(path).exists() else "0"},
        "streams": [],
        "_fallback": True,
        "_width": width,
        "_height": height,
        "_fps": fps,
        "_has_video": has_video,
        "_has_audio": has_audio,
        "_vcodec": codec_match.group(1) if codec_match else None,
    }


def media_info(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise SkillError(f"Fichier introuvable : {p}")
    data = ffprobe(p)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = 0.0
    try:
        duration = float(data.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if not duration:
        for stream in (video, audio):
            if stream and stream.get("duration"):
                try:
                    duration = float(stream["duration"])
                    break
                except (TypeError, ValueError):
                    pass
    fps = None
    if video:
        raw_fps = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        try:
            num, den = raw_fps.split("/")
            fps = float(num) / float(den) if float(den) else None
        except (ValueError, ZeroDivisionError):
            fps = None
    elif data.get("_fps"):
        fps = data["_fps"]
    width_value = (video or {}).get("width") or data.get("_width")
    height_value = (video or {}).get("height") or data.get("_height")
    width = int(width_value) if width_value else None
    height = int(height_value) if height_value else None
    return {
        "path": str(p.resolve()),
        "filename": p.name,
        "duration": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(fps, 4) if fps else None,
        "has_video": bool(video) if streams else bool(data.get("_has_video")),
        "has_audio": bool(audio) if streams else bool(data.get("_has_audio")),
        "vcodec": (video or {}).get("codec_name") or data.get("_vcodec"),
        "acodec": (audio or {}).get("codec_name"),
        "size_bytes": p.stat().st_size,
        "bitrate": int(float(data.get("format", {}).get("bit_rate") or 0)),
    }


def duration(path: str | Path) -> float:
    return float(media_info(path)["duration"])


def extract_audio(
    src: str | Path,
    dst: str | Path,
    *,
    sample_rate: int = 16_000,
    channels: int = 1,
    dry_run: bool = False,
) -> Path:
    out = Path(dst)
    out.parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(src), "-vn", "-sn", "-dn", "-ac", str(channels),
            "-ar", str(sample_rate), "-acodec", "pcm_s16le", str(out)]
    ffmpeg(args, dry_run=dry_run)
    return out


def extract_frame(src: str | Path, dst: str | Path, time: float = 0.0,
                  width: int | None = None) -> Path:
    out = Path(dst)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={width}:-2" if width else "null"
    ffmpeg(["-ss", str(max(0, time)), "-i", str(src), "-frames:v", "1",
            "-vf", vf, "-q:v", "2", str(out)])
    return out


def detect_silences(
    src: str | Path,
    *,
    noise_db: float = -35.0,
    min_duration: float = 0.35,
    dry_run: bool = False,
) -> list[dict[str, float]]:
    """Silences via le filtre ``silencedetect`` (garde les blancs + durées)."""
    if not media_info(src)["has_audio"]:
        raise SkillError(f"Aucune piste audio dans {src}")
    args = ["-i", str(src), "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
            "-f", "null", "-"]
    if dry_run:
        ffmpeg(args, dry_run=True)
        return []
    proc = run([ffmpeg_bin(), "-hide_banner", "-y", *[str(a) for a in args]],
               check=False, capture=True)
    stderr = proc.stderr or ""
    silences: list[dict[str, float]] = []
    pending: float | None = None
    for line in stderr.splitlines():
        start_match = re.search(r"silence_start:\s*(-?\d+(?:\.\d+)?)", line)
        if start_match:
            pending = max(0.0, float(start_match.group(1)))
        end_match = re.search(
            r"silence_end:\s*(-?\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(\d+(?:\.\d+)?)",
            line,
        )
        if end_match and pending is not None:
            end = float(end_match.group(1))
            silences.append({
                "start": round(pending, 3),
                "end": round(end, 3),
                "duration": round(end - pending, 3),
            })
            pending = None
    if pending is not None:
        total = duration(src)
        silences.append({"start": round(pending, 3), "end": round(total, 3),
                         "duration": round(total - pending, 3)})
    return silences


def burn_subtitles(
    video: str | Path,
    ass_path: str | Path,
    out: str | Path,
    *,
    crf: int = 18,
    preset: str = "medium",
    audio_bitrate: str = "192k",
    dry_run: bool = False,
) -> Path:
    """Incruste un fichier ASS (libass requis)."""
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vesk-subs-") as tmp:
        simple = Path(tmp) / "captions.ass"
        shutil.copyfile(ass_path, simple)
        vf = "subtitles=filename=captions.ass" if dry_run else subtitle_filter(simple)
        info("Incrustation des sous-titres…")
        ffmpeg(["-i", str(video), "-vf", vf, "-c:v", "libx264", "-crf", str(crf),
                "-preset", preset, "-c:a", "aac", "-b:a", audio_bitrate,
                "-movflags", "+faststart", str(out_path)], dry_run=dry_run)
    return out_path


def mux_audio(video: str | Path, audio: str | Path, out: str | Path,
              *, replace: bool = False, audio_gain_db: float = 0.0,
              dry_run: bool = False) -> Path:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    filters = []
    if audio_gain_db:
        filters.append(f"volume={audio_gain_db}dB")
    if replace:
        args = ["-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
    else:
        args = ["-i", str(video), "-i", str(audio),
                "-filter_complex", "[1:a]volume=1.0[sfx];[0:a][sfx]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v:0", "-map", "[a]"]
    if filters and replace:
        args += ["-af", ",".join(filters)]
    args += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)]
    ffmpeg(args, dry_run=dry_run)
    return out_path


def concat_files(files: Sequence[str | Path], out: str | Path,
                 *, dry_run: bool = False) -> Path:
    if not files:
        raise SkillError("Aucun fichier à concaténer.")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vesk-concat-") as tmp:
        list_file = Path(tmp) / "concat.txt"
        list_file.write_text(
            "".join(f"file '{Path(f).resolve().as_posix()}'\n" for f in files),
            encoding="utf-8",
        )
        ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy",
                str(out_path)], dry_run=dry_run)
    return out_path


def audio_loudness(path: str | Path, *, dry_run: bool = False) -> dict[str, float]:
    """Mesure loudness (LUFS intégré) via ``loudnorm`` en mode analyse."""
    args = ["-i", str(path), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"]
    if dry_run:
        ffmpeg(args, dry_run=True)
        return {}
    proc = run([ffmpeg_bin(), "-hide_banner", "-nostats", *[str(a) for a in args]],
               check=False, capture=True)
    stderr = proc.stderr or ""
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return {key: float(value) for key, value in data.items()
            if isinstance(value, (int, float, str)) and _is_number(value)}


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_media(path: str | Path, *, need_audio: bool = False,
                   need_video: bool = False) -> dict[str, Any]:
    info_ = media_info(path)
    if need_audio and not info_["has_audio"]:
        raise SkillError(f"{path} ne contient pas de piste audio.")
    if need_video and not info_["has_video"]:
        raise SkillError(f"{path} ne contient pas de piste vidéo.")
    return info_
