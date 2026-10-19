"""Suivi de visage (OpenCV Haar) et détection de plans — utilisé par auto-framing 9:16."""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any, Sequence

from .common import SkillError, info
from .ffmpeg import media_info

FACE_CASCADE = "haarcascade_frontalface_default.xml"
PROFILE_CASCADE = "haarcascade_profileface.xml"


def require_cv2():
    try:
        import cv2  # type: ignore

        return cv2
    except Exception as exc:  # pragma: no cover
        raise SkillError(
            "Le suivi de visage nécessite OpenCV :\n"
            "  pip install opencv-python-headless\n"
            f"(détail : {exc})"
        ) from exc


def _cascades(cv2) -> list[Any]:
    base = Path(cv2.data.haarcascades)
    cascades = []
    for name in (FACE_CASCADE, PROFILE_CASCADE):
        path = base / name
        if path.exists():
            cascade = cv2.CascadeClassifier(str(path))
            if not cascade.empty():
                cascades.append(cascade)
    if not cascades:
        raise SkillError("Cascades Haar introuvables dans l'installation OpenCV.")
    return cascades


def sample_times(duration: float, interval: float, max_samples: int = 180) -> list[float]:
    interval = max(0.1, float(interval))
    count = max(1, int(duration / interval) + 1)
    if count > max_samples:
        interval = duration / max_samples
        count = max_samples + 1
    return [round(i * interval, 3) for i in range(count) if i * interval < duration]


def detect_faces(
    path: str | Path,
    *,
    interval: float = 0.5,
    min_face_ratio: float = 0.045,
    smooth: bool = True,
) -> dict[str, Any]:
    """Renvoie ``keyframes`` (temps, x du centre visage) + statistiques."""
    cv2 = require_cv2()
    info_ = media_info(path)
    if not info_["has_video"]:
        raise SkillError("Pas de piste vidéo pour la détection de visages.")
    width, height = int(info_["width"] or 0), int(info_["height"] or 0)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SkillError(f"OpenCV n'arrive pas à ouvrir {path}")
    times = sample_times(float(info_["duration"]), interval)
    cascades = _cascades(cv2)
    raw: list[dict[str, Any]] = []
    try:
        for time in times:
            capture.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            best = None
            height_px, width_px = gray.shape[:2]
            for cascade in cascades:
                faces = cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5,
                    minSize=(int(width_px * min_face_ratio), int(width_px * min_face_ratio)),
                )
                for (x, y, w, h) in faces:
                    area = float(w * h)
                    if best is None or area > best[4]:
                        best = (float(x), float(y), float(w), float(h), area)
            if best is not None:
                cx = best[0] + best[2] / 2.0
                raw.append({"time": time, "x": round(cx, 2), "face_width": round(best[2], 1),
                            "confidence": round(min(1.0, best[2] / (width_px * 0.35)), 2)})
            else:
                raw.append({"time": time, "x": None, "face_width": 0.0, "confidence": 0.0})
    finally:
        capture.release()

    detected = [f for f in raw if f["x"] is not None]
    if not detected:
        return {
            "video": {"width": width, "height": height, "duration": info_["duration"]},
            "keyframes": [{"time": 0.0, "x": width / 2.0}],
            "face_ratio": 0.0,
            "samples": len(raw),
            "message": "Aucun visage détecté : recadrage centré par défaut.",
        }

    xs = [float(f["x"]) for f in raw if f["x"] is not None]
    if smooth and len(xs) > 2:
        radius = 2
        filled: list[float] = []
        for index, frame in enumerate(raw):
            window = [float(f["x"]) for f in raw[max(0, index - radius): index + radius + 1]
                      if f["x"] is not None]
            filled.append(round(median(window), 2) if window else None)
        for index, frame in enumerate(raw):
            if frame["x"] is None:
                frame["x"] = filled[index]
            elif filled[index] is not None:
                frame["x"] = filled[index]
    # interpolation des trous
    known = [(i, float(f["x"])) for i, f in enumerate(raw) if f["x"] is not None]
    for i, frame in enumerate(raw):
        if frame["x"] is not None:
            continue
        before = [(j, x) for j, x in known if j < i]
        after = [(j, x) for j, x in known if j > i]
        if before and after:
            (j0, x0), (j1, x1) = before[-1], after[0]
            ratio = (i - j0) / max(1, j1 - j0)
            frame["x"] = round(x0 + (x1 - x0) * ratio, 2)
        elif before:
            frame["x"] = before[-1][1]
        elif after:
            frame["x"] = after[0][1]
        else:
            frame["x"] = width / 2.0
    keyframes = [{"time": float(f["time"]), "x": float(f["x"])}
                 for f in raw if f["x"] is not None]
    return {
        "video": {"width": width, "height": height, "duration": info_["duration"]},
        "keyframes": keyframes,
        "face_ratio": round(len(detected) / max(1, len(raw)), 3),
        "samples": len(raw),
    }


def detect_scenes(path: str | Path, *, threshold: float = 0.32,
                  max_samples: int = 600) -> list[dict[str, float]]:
    """Détection de coupes par différence de luminance (échantillonnage adaptatif)."""
    cv2 = require_cv2()
    info_ = media_info(path)
    duration = float(info_["duration"])
    interval = max(0.08, duration / max_samples)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SkillError(f"OpenCV n'arrive pas à ouvrir {path}")
    scenes: list[dict[str, float]] = [{"time": 0.0, "score": 0.0}]
    previous = None
    try:
        for time in sample_times(duration, interval, max_samples=max_samples):
            capture.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (160, 90))
            if previous is not None:
                diff = float(cv2.absdiff(small, previous).mean()) / 255.0
                if diff >= threshold:
                    scenes.append({"time": round(time, 3), "score": round(diff, 3)})
            previous = small
    finally:
        capture.release()
    return scenes


def motion_curve(path: str | Path, *, interval: float = 0.2) -> list[dict[str, float]]:
    """Énergie de mouvement par échantillon (0→1), utile pour les hooks visuels."""
    cv2 = require_cv2()
    info_ = media_info(path)
    duration = float(info_["duration"])
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SkillError(f"OpenCV n'arrive pas à ouvrir {path}")
    curve: list[dict[str, float]] = []
    previous = None
    try:
        for time in sample_times(duration, interval, max_samples=400):
            capture.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (96, 54))
            score = 0.0
            if previous is not None:
                score = float(cv2.absdiff(small, previous).mean()) / 255.0
            curve.append({"time": round(time, 3), "motion": round(score, 4)})
            previous = small
    finally:
        capture.release()
    return curve
