"""Manifeste média, plages de montage, rendu multi-coupes accéléré et mapping temporel."""

from __future__ import annotations

import bisect
import math
from pathlib import Path
from typing import Any, Sequence

from .common import SkillError, info, warn
from .ffmpeg import ffmpeg, media_info


# --------------------------------------------------------------------------- plages


def merge_ranges(ranges: Sequence[dict[str, Any]],
                 *, gap: float = 0.0) -> list[dict[str, Any]]:
    """Fusionne des plages qui se chevauchent (garde la clé ``speed`` si identique)."""
    cleaned = sorted(
        ({"start": float(r["start"]), "end": float(r["end"]),
          "speed": float(r.get("speed", 1.0))} for r in ranges if float(r["end"]) > float(r["start"])),
        key=lambda r: r["start"],
    )
    merged: list[dict[str, Any]] = []
    for current in cleaned:
        if not merged:
            merged.append(current)
            continue
        last = merged[-1]
        same_speed = abs(last["speed"] - current["speed"]) < 1e-6
        if current["start"] <= last["end"] + gap and same_speed:
            last["end"] = max(last["end"], current["end"])
        else:
            merged.append(current)
    return merged


def speech_ranges(duration: float, silences: Sequence[dict[str, Any]],
                  *, pad: float = 0.06, min_speech: float = 0.12) -> list[dict[str, float]]:
    """Complément des silences = plages de parole."""
    ranges: list[dict[str, float]] = []
    cursor = 0.0
    for silence in sorted(silences, key=lambda s: s["start"]):
        start = max(0.0, float(silence["start"]) + pad)
        end = min(duration, float(silence["end"]) - pad)
        if start - cursor >= min_speech:
            ranges.append({"start": cursor, "end": start})
        cursor = max(cursor, end)
    if duration - cursor >= min_speech:
        ranges.append({"start": cursor, "end": duration})
    return [r for r in ranges if r["end"] - r["start"] > 0.04]


def invert_speech(ranges: Sequence[dict[str, float]], duration: float) -> list[dict[str, float]]:
    cuts = []
    cursor = 0.0
    for r in ranges:
        if r["start"] > cursor:
            cuts.append({"start": cursor, "end": r["start"]})
        cursor = max(cursor, r["end"])
    if cursor < duration:
        cuts.append({"start": cursor, "end": duration})
    return cuts


def total_speed_aware_duration(ranges: Sequence[dict[str, Any]]) -> float:
    return sum((float(r["end"]) - float(r["start"])) / float(r.get("speed", 1.0)) for r in ranges)


# --------------------------------------------------------------------------- time map


class TimeMap:
    """Convertit un temps du montage final vers le média source."""

    def __init__(self, ranges: Sequence[dict[str, Any]]):
        self.entries: list[dict[str, float]] = []
        out_cursor = 0.0
        for r in ranges:
            src_start, src_end = float(r["start"]), float(r["end"])
            speed = float(r.get("speed", 1.0))
            out_duration = (src_end - src_start) / speed
            self.entries.append({
                "out_start": out_cursor,
                "out_end": out_cursor + out_duration,
                "src_start": src_start,
                "speed": speed,
            })
            out_cursor += out_duration
        self.duration = out_cursor
        self._starts = [entry["out_start"] for entry in self.entries]

    def to_source(self, t: float) -> float:
        if not self.entries:
            return 0.0
        t = max(0.0, min(float(t), max(0.0, self.duration - 1e-6)))
        index = bisect.bisect_right(self._starts, t) - 1
        index = max(0, min(index, len(self.entries) - 1))
        entry = self.entries[index]
        return entry["src_start"] + (t - entry["out_start"]) * entry["speed"]

    def to_output(self, src_time: float, *, prefer_end: bool = False) -> float:
        """Position d'un instant source dans le montage (approximation linéaire)."""
        for entry in self.entries:
            src_start = entry["src_start"]
            src_end = src_start + (entry["out_end"] - entry["out_start"]) * entry["speed"]
            if src_start <= src_time <= src_end:
                return entry["out_start"] + (src_time - src_start) / entry["speed"]
        if not self.entries:
            return 0.0
        if src_time < self.entries[0]["src_start"]:
            return 0.0
        return self.duration

    def map_segments(self, segments: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        """Projette des segments source sur le montage, en découpant aux frontières."""
        output = []
        for segment in segments:
            src_start, src_end = float(segment["start"]), float(segment["end"])
            pieces = []
            for entry in self.entries:
                entry_src_end = entry["src_start"] + (entry["out_end"] - entry["out_start"]) * entry["speed"]
                overlap_start = max(src_start, entry["src_start"])
                overlap_end = min(src_end, entry_src_end)
                if overlap_end - overlap_start <= 0.001:
                    continue
                pieces.append((overlap_start, overlap_end, entry))
            for index, (start, end, entry) in enumerate(pieces):
                out_start = entry["out_start"] + (start - entry["src_start"]) / entry["speed"]
                out_end = entry["out_start"] + (end - entry["src_start"]) / entry["speed"]
                text = str(segment.get("text", ""))
                words = []
                for word in segment.get("words", []) or []:
                    w_start, w_end = float(word["start"]), float(word["end"])
                    if w_end <= start or w_start >= end:
                        continue
                    words.append({
                        "word": word["word"],
                        "start": round(entry["out_start"] + (max(w_start, start) - entry["src_start"]) / entry["speed"], 3),
                        "end": round(entry["out_start"] + (min(w_end, end) - entry["src_start"]) / entry["speed"], 3),
                    })
                if not words:
                    words = _split_text_timing(text, out_start, out_end)
                output.append({
                    "start": round(out_start, 3),
                    "end": round(out_end, 3),
                    "text": text,
                    "words": words,
                    "part": index + 1 if len(pieces) > 1 else None,
                })
        return _renumber(output)


def _split_text_timing(text: str, start: float, end: float) -> list[dict[str, Any]]:
    from .transcript import distribute_words, split_words

    return distribute_words(split_words(text), start, end)


def _renumber(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, segment in enumerate(segments, start=1):
        segment["id"] = index
    return segments


# --------------------------------------------------------------------------- rendu


def _atempo_chain(speed: float) -> list[str]:
    """Découpe une vitesse en facteurs atempo valides [0.5, 2.0]."""
    factors: list[float] = []
    remaining = speed
    while remaining > 2.0 + 1e-9:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(round(remaining, 6))
    return [f"atempo={factor:g}" for factor in factors if abs(factor - 1.0) > 1e-6]


def render_cut(
    source: str | Path,
    out: str | Path,
    ranges: Sequence[dict[str, Any]],
    *,
    crf: int = 18,
    preset: str = "medium",
    audio_bitrate: str = "192k",
    audio: bool | None = None,
    dry_run: bool = False,
) -> Path:
    """Rend un montage multi-plages en UNE passe, avec vitesses variables.

    Contrairement au concat demuxer, ce rendu est précis à la frame et gère le
    rétime (accélération de silences, time-lapse…).
    """
    if not ranges:
        raise SkillError("Aucune plage à rendre.")
    source_info = media_info(source)
    has_audio = source_info["has_audio"] if audio is None else audio
    if audio and not source_info["has_audio"]:
        warn("Audio demandé mais absent de la source : rendu sans audio.")
        has_audio = False
    ranges = merge_ranges(ranges)
    parts: list[str] = []
    concat_inputs: list[str] = []
    for index, r in enumerate(ranges):
        start, end = float(r["start"]), float(r["end"])
        speed = float(r.get("speed", 1.0))
        if end - start < 0.02:
            continue
        video_filters = [
            f"trim=start={start:.6f}:end={end:.6f}",
            "setpts=(PTS-STARTPTS)/{speed}".format(speed=f"{speed:.6f}"),
            "setsar=1",
        ]
        parts.append(
            f"[0:v]{','.join(video_filters)}[v{index}]"
        )
        concat_inputs.append(f"[v{index}]")
        if has_audio:
            audio_filters = [
                f"atrim=start={start:.6f}:end={end:.6f}",
                "asetpts=PTS-STARTPTS",
                "aformat=sample_rates=48000:channel_layouts=stereo",
            ]
            audio_filters.extend(_atempo_chain(speed))
            parts.append(f"[0:a]{','.join(audio_filters)}[a{index}]")
            concat_inputs.append(f"[a{index}]")
    if not concat_inputs:
        raise SkillError("Toutes les plages sont trop courtes.")
    if has_audio:
        graph = ";".join(parts) + ";" + "".join(concat_inputs) + \
                f"concat=n={len(concat_inputs) // 2}:v=1:a=1[vout][aout]"
    else:
        graph = ";".join(parts) + ";" + "".join(concat_inputs) + \
                f"concat=n={len(concat_inputs)}:v=1:a=0[vout]"

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(source), "-filter_complex", graph, "-map", "[vout]"]
    if has_audio:
        args += ["-map", "[aout]"]
    args += [
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000"]
    args.append(str(out_path))
    expected = total_speed_aware_duration(ranges)
    info(f"Rendu de {len(ranges)} plage(s) → {out_path.name} (~{expected:.1f}s)")
    ffmpeg(args, dry_run=dry_run)
    return out_path


def smart_reframe(
    source: str | Path,
    out: str | Path,
    *,
    track: str = "auto",
    keyframes: Sequence[dict[str, float]] | None = None,
    width: int = 1080,
    height: int = 1920,
    crf: int = 18,
    preset: str = "medium",
    sample_interval: float = 0.5,
    dry_run: bool = False,
) -> Path:
    """Recadre en 9:16 : ``center``, ``blur`` (fond flou) ou ``track`` (suivi de visage)."""
    video_info = media_info(source)
    if not video_info["has_video"]:
        raise SkillError(f"{source} n'a pas de piste vidéo.")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    w, h = int(width), int(height)

    if track == "blur":
        graph = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"boxblur=40:2[bg2];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fg2];"
            f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2[v]"
        )
    elif track in {"center", "crop"}:
        graph = (
            f"[0:v]crop=w=trunc(ih*{w}/{h}/2)*2:h=ih:x=(iw-ow)/2:y=0,"
            f"scale={w}:{h}:flags=lanczos[v]"
        )
    elif track == "track":
        if not keyframes:
            raise SkillError("Le suivi de visage nécessite des keyframes.")
        expr = _crop_expression(keyframes, video_info, w, h)
        graph = (
            f"[0:v]crop=w=trunc(ih*{w}/{h}/2)*2:h=ih:x='{expr}':y=0,"
            f"scale={w}:{h}:flags=lanczos[v]"
        )
    else:
        raise SkillError(f"Mode de recadrage inconnu : {track}")

    args = ["-i", str(source), "-filter_complex", graph, "-map", "[v]"]
    if video_info["has_audio"]:
        args += ["-map", "0:a", "-c:a", "aac", "-b:a", "192k"]
    args += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
    info(f"Recadrage {track} → {w}x{h}")
    ffmpeg(args, dry_run=dry_run)
    return out_path


def _crop_expression(keyframes: Sequence[dict[str, float]], video_info: dict[str, Any],
                     width: int, height: int) -> str:
    """Expression FFmpeg d'interpolation linéaire entre keyframes de centre visage."""
    iw = float(video_info.get("width") or 1920)
    ih = float(video_info.get("height") or 1080)
    out_w = math.floor(ih * width / height / 2) * 2
    max_x = max(0.0, iw - out_w)
    points = sorted({round(float(k["time"]), 3): float(k.get("x", iw / 2))
                     for k in keyframes}.items())
    if not points:
        points = [(0.0, iw / 2)]
    if len(points) == 1:
        x = min(max(points[0][1] - out_w / 2, 0.0), max_x)
        return f"{x:.1f}"
    # limite la longueur de l'expression (les keyframes sont déjà sous-échantillonnées)
    if len(points) > 90:
        step = math.ceil(len(points) / 90)
        points = points[::step] + [points[-1]]
    expr = f"{min(max(points[-1][1] - out_w / 2, 0.0), max_x):.1f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(points[:-1], points[1:]))):
        x0_clamped = min(max(x0 - out_w / 2, 0.0), max_x)
        x1_clamped = min(max(x1 - out_w / 2, 0.0), max_x)
        span = max(1e-3, t1 - t0)
        expr = (
            f"if(lt(t,{t1:.3f}),"
            f"{x0_clamped:.1f}+({x1_clamped - x0_clamped:.1f})*(t-{t0:.3f})/{span:.3f},"
            f"{expr})"
        )
    return expr


def default_poster(source: str | Path, out: str | Path, *, time: float = 0.5,
                   width: int | None = 480) -> Path:
    from .ffmpeg import extract_frame

    return extract_frame(source, out, time=time, width=width)
