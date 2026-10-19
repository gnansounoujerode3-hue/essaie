"""Utilitaires communs : erreurs, JSON, temps, timecodes, exécution de commandes."""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Sequence


def _configure_stdio() -> None:
    """Évite les UnicodeEncodeError des consoles Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


_configure_stdio()


def env_flag(name: str) -> bool:
    """Lit un drapeau d'environnement (1/true/yes/on)."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


class SkillError(RuntimeError):
    """Erreur utilisateur : message clair, sans stacktrace."""


def info(message: str) -> None:
    print(message, file=sys.stderr)


def warn(message: str) -> None:
    print(f"⚠️  {message}", file=sys.stderr)


def die(message: str, code: int = 2) -> "None":
    raise SkillError(message)


def run(
    cmd: Sequence[str] | str,
    *,
    check: bool = True,
    capture: bool = True,
    cwd: str | Path | None = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Exécute une commande. En mode ``dry_run``, l'affiche sans l'exécuter."""
    if isinstance(cmd, str):
        display = cmd
        argv: list[str] = shlex.split(cmd)
    else:
        argv = [str(part) for part in cmd]
        display = " ".join(shlex.quote(part) for part in argv)
    if dry_run:
        info(f"[dry-run] {display}")
        return subprocess.CompletedProcess(argv, 0, "", "")
    if not quiet and not env_flag("VESK_QUIET"):
        info(f"$ {display}")
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            capture_output=capture,
            text=True,
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise SkillError(f"Commande introuvable : {argv[0]} ({exc})") from exc
    if check and proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        tail = "\n".join(stderr.splitlines()[-12:])
        raise SkillError(f"Échec de la commande ({proc.returncode}) : {display}\n{tail}")
    return proc


def sanitize_json(value: Any) -> Any:
    """Remplace NaN/Infinity (invalides en JSON strict) par ``None``."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json(item) for item in value]
    return value


def write_json(path: str | Path, data: Any, *, indent: int = 2) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(sanitize_json(data), ensure_ascii=False, indent=indent, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return target


def read_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        raise SkillError(f"Fichier JSON introuvable : {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SkillError(f"JSON invalide dans {p} : {exc}") from exc


def read_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise SkillError(f"Fichier introuvable : {p}")
    return p.read_text(encoding="utf-8-sig", errors="replace")


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_time(value: str | float | int) -> float:
    """Convertit ``83.4``, ``01:23.400`` ou ``1:02:03,000`` en secondes."""
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(",", ".")
    if not raw:
        raise SkillError("Temps vide.")
    if ":" not in raw:
        try:
            return float(raw)
        except ValueError as exc:
            raise SkillError(f"Temps invalide : {value!r}") from exc
    parts = raw.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise SkillError(f"Temps invalide : {value!r}")
    try:
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError as exc:
        raise SkillError(f"Temps invalide : {value!r}") from exc


def fmt_srt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    millis = int(round(seconds * 1000))
    h, rem = divmod(millis, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_vtt_time(seconds: float) -> str:
    return fmt_srt_time(seconds).replace(",", ".")


def fmt_timecode(seconds: float, fps: float = 30.0) -> str:
    """Timecode SMPTE non-drop ``HH:MM:SS:FF``."""
    fps = max(1.0, float(fps))
    total_frames = int(round(max(0.0, seconds) * fps))
    frames_per_second = int(round(fps))
    frames = total_frames % frames_per_second
    total_seconds = total_frames // frames_per_second
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}:{frames:02d}"


def fmt_clock(seconds: float) -> str:
    """``1:23`` ou ``1:02:03`` lisible pour les rapports."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_ass_time(seconds: float) -> str:
    centis = int(round(max(0.0, seconds) * 100))
    h, rem = divmod(centis, 360_000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def slugify(value: str, *, max_length: int = 60) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "sans-titre")[:max_length].strip("-")


def strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def normalize_text(value: str) -> str:
    value = strip_accents(str(value)).lower()
    value = re.sub(r"[’']", " ", value)
    value = re.sub(r"[^a-z0-9\s-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def which(name: str) -> str | None:
    return shutil.which(name)


def human_size(path: str | Path) -> str:
    size = float(Path(path).stat().st_size)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if size < 1024 or unit == "To":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"


def safe_filename(value: str, default: str = "asset") -> str:
    stem = slugify(Path(value).stem, max_length=48)
    suffix = Path(value).suffix.lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{1,5}", suffix):
        return f"{stem}{suffix}"
    return f"{stem or default}"


def chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def skill_data(skill: str, filename: str, *, override: str | Path | None = None) -> Path:
    """Localise un fichier de données d'un skill, en dépôt comme après installation.

    - dépôt : ``<repo>/skills/<skill>/<fichier>``
    - installé : ``<skill>/<fichier>`` (à côté du dossier ``_shared``)
    """
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "skills" / skill / filename,          # dépôt
        root / filename,                             # skill installé (même skill)
        root / "_shared" / "data" / skill / filename,  # installation : données partagées
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


