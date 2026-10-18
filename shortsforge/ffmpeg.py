"""Accès au binaire ffmpeg/ffprobe embarqué et exécution des commandes.

Le package ``imageio-ffmpeg`` fournit un binaire statique (x264 + libass +
freetype). Si le système dispose déjà de ffmpeg, celui-ci est prioritaire.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ENV_FFMPEG = "SHORTSFORGE_FFMPEG"


class FFmpegError(RuntimeError):
    """Échec d'une commande ffmpeg."""


def _system_ffmpeg(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    return None


def _bundled_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover - dépend de l'environnement
        return None


def ffmpeg_bin() -> str:
    """Chemin du binaire ffmpeg à utiliser."""
    env = os.environ.get(ENV_FFMPEG)
    if env and Path(env).exists():
        return env
    return _system_ffmpeg("ffmpeg") or _bundled_ffmpeg() or "ffmpeg"


def ffprobe_bin() -> str | None:
    env = os.environ.get("SHORTSFORGE_FFPROBE")
    if env and Path(env).exists():
        return env
    return _system_ffmpeg("ffprobe")


@dataclass
class MediaInfo:
    """Métadonnées minimales d'un média."""

    duration: float
    width: int
    height: int
    has_audio: bool
    has_video: bool
    fps: float
    kind: str  # "video" | "audio" | "image"

    @property
    def aspect(self) -> float:
        return (self.width / self.height) if self.height else 0.0


def run(args: Sequence[str], *, capture: bool = True, quiet: bool = True) -> str:
    """Exécute ffmpeg (ou ffprobe) et renvoie la sortie texte."""
    cmd = list(args)
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )
    if proc.returncode != 0:
        tail = ""
        if proc.stderr:
            tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise FFmpegError(f"Commande échouée ({proc.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return (proc.stdout or "").strip()


def probe(path: str | Path) -> MediaInfo:
    """Inspecte un média (vidéo, image ou audio)."""
    path = str(path)
    if not Path(path).exists():
        raise FileNotFoundError(path)

    # Cas particulier des images : ffprobe peut échouer sur certains formats.
    if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
        from PIL import Image

        with Image.open(path) as im:
            w, h = im.size
        return MediaInfo(duration=0.0, width=w, height=h, has_audio=False, has_video=True, fps=0.0, kind="image")

    probe_bin = ffprobe_bin()
    if probe_bin:
        raw = run(
            [
                probe_bin,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ]
        )
        data = json.loads(raw or "{}")
        return _media_from_probe(data)

    # Repli sans ffprobe : on parse la sortie de ffmpeg (durée + streams).
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    text = (proc.stderr or "") + (proc.stdout or "")
    return _media_from_ffmpeg_banner(text)


def _media_from_ffmpeg_banner(text: str) -> MediaInfo:
    import re

    duration = 0.0
    m = re.search(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)", text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    has_video = "Video:" in text
    has_audio = "Audio:" in text
    width = height = 0
    fps = 0.0
    mv = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text, re.S)
    if mv:
        width, height = int(mv.group(1)), int(mv.group(2))
    mf = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if mf:
        fps = float(mf.group(1))
    kind = "video" if has_video else "audio"
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        has_audio=has_audio,
        has_video=has_video,
        fps=fps,
        kind=kind,
    )


def _media_from_probe(data: dict) -> MediaInfo:
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or 0.0)
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = 0.0
    if v and v.get("avg_frame_rate") and "/" in v["avg_frame_rate"]:
        num, den = v["avg_frame_rate"].split("/")
        try:
            fps = float(num) / float(den) if float(den) else 0.0
        except ValueError:
            fps = 0.0
    kind = "video" if v else "audio"
    if v and duration == 0:
        duration = float(v.get("duration") or 0.0)
    return MediaInfo(
        duration=duration,
        width=int(v.get("width") or 0) if v else 0,
        height=int(v.get("height") or 0) if v else 0,
        has_audio=a is not None,
        has_video=v is not None,
        fps=fps,
        kind=kind,
    )


def escape_filter_path(path: str | Path) -> str:
    """Échappe un chemin pour l'utiliser dans un filtre ffmpeg (Windows + POSIX)."""
    p = str(path)
    p = p.replace("\\", "/")
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def escape_concat_path(path: str | Path) -> str:
    """Échappe un chemin pour un fichier de liste concat."""
    return str(path).replace("'", "'\\''")


def concat_demuxer_list(paths: Iterable[str | Path], dest: Path) -> Path:
    """Écrit une liste concat demuxer (chemins absolus)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for p in paths:
        ap = os.path.abspath(str(p))
        lines.append(f"file '{escape_concat_path(ap)}'")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
