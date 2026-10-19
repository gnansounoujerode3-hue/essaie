"""Analyse de courbes de rétention (exports CSV YouTube Studio et formats proches)."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence

from .common import SkillError, fmt_clock, read_text

TIME_KEYS = (
    "elapsed_video_time_seconds", "elapsed_video_time", "video_time", "videotime",
    "position", "timestamp", "time", "secondes", "seconds", "sec", "start_time", "duration",
)
RETENTION_KEYS = (
    "audience_watch_ratio", "audience_watch_ratio_", "watch_ratio", "relative_retention",
    "retention", "retention_rate", "audience_retention", "percent", "percentage", "ratio",
)
VIEW_KEYS = ("views", "audience", "viewers", "vues", "impressions")


def _norm_header(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[%()]", "", value)
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def _parse_time(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace(",", ".").replace("\u202f", "").replace(" ", "")
    if not raw:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return float(raw)
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?", raw):
        parts = [float(p) for p in raw.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace("\u202f", "").replace(" ", "").replace("%", "")
    if not raw:
        return None
    raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def load_retention_csv(path: str | Path) -> list[dict[str, float]]:
    content = read_text(path)
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(content), dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise SkillError(f"CSV vide : {path}")
    header = [_norm_header(cell) for cell in rows[0]]
    time_index = next((header.index(key) for key in TIME_KEYS if key in header), None)
    retention_index = next((header.index(key) for key in RETENTION_KEYS if key in header), None)
    view_index = next((header.index(key) for key in VIEW_KEYS if key in header), None)
    data_start = 1
    if time_index is None or retention_index is None:
        # certains exports n'ont pas d'en-tête : on tente les deux premières colonnes
        first = [_parse_time(rows[0][0]), _parse_number(rows[0][1]) if len(rows[0]) > 1 else None]
        if first[0] is not None and first[1] is not None:
            time_index, retention_index, data_start = 0, 1, 0
            view_index = 2 if len(rows[0]) > 2 else None
        else:
            raise SkillError(
                f"Colonnes temps/rétention introuvables dans {Path(path).name}.\n"
                f"Colonnes vues : {header}\n"
                "Attendu : 'elapsed_video_time_seconds' + 'audience_watch_ratio' "
                "(YouTube Studio) ou 'time' + 'retention'."
            )
    points = []
    for row in rows[data_start:]:
        if len(row) <= max(time_index, retention_index):
            continue
        time = _parse_time(row[time_index])
        retention = _parse_number(row[retention_index])
        if time is None or retention is None:
            continue
        views = _parse_number(row[view_index]) if view_index is not None and len(row) > view_index else None
        points.append({"time": round(time, 3), "retention": retention,
                       "views": views if views is not None else 0.0})
    if not points:
        raise SkillError(f"Aucune donnée exploitable dans {path}")
    points.sort(key=lambda p: p["time"])
    if mean(p["retention"] for p in points) <= 1.5:
        for point in points:
            point["retention"] *= 100.0
    # dédoublonne les temps
    deduped = []
    for point in points:
        if deduped and abs(point["time"] - deduped[-1]["time"]) < 0.01:
            deduped[-1] = point
        else:
            deduped.append(point)
    return deduped


def resample(points: Sequence[dict[str, float]], step: float = 1.0) -> list[dict[str, float]]:
    if step <= 0:
        return list(points)
    end = points[-1]["time"]
    buckets: list[list[dict[str, float]]] = [[] for _ in range(int(end / step) + 1)]
    for point in points:
        index = min(len(buckets) - 1, int(point["time"] / step))
        buckets[index].append(point)
    samples = []
    for index, bucket in enumerate(buckets):
        if bucket:
            samples.append({
                "time": round(index * step, 3),
                "retention": round(mean(p["retention"] for p in bucket), 3),
                "views": mean(p["views"] for p in bucket),
            })
    return samples


def find_events(points: Sequence[dict[str, float]], *, window: float = 5.0,
                min_drop: float = 3.0, min_gain: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    if len(points) < 3:
        return {"drops": [], "spikes": []}
    times = [p["time"] for p in points]
    values = [p["retention"] for p in points]
    drops, spikes = [], []
    j = 0
    for i in range(len(points)):
        while times[i] - times[j] > window:
            j += 1
        if i - j < 1:
            continue
        delta = values[i] - values[j]
        seconds = max(0.1, times[i] - times[j])
        rate = delta / seconds
        if delta <= -min_drop:
            drops.append({"start": times[j], "end": times[i], "delta": round(delta, 2),
                          "rate": round(rate, 3), "from": values[j], "to": values[i]})
        elif delta >= min_gain:
            spikes.append({"start": times[j], "end": times[i], "delta": round(delta, 2),
                           "rate": round(rate, 3), "from": values[j], "to": values[i]})
    return {
        "drops": _merge_events(drops),
        "spikes": _merge_events(spikes, prefer_max=True),
    }


def _merge_events(events: list[dict[str, Any]], *, prefer_max: bool = False) -> list[dict[str, Any]]:
    if not events:
        return []
    events.sort(key=lambda e: e["start"])
    merged = [events[0]]
    for event in events[1:]:
        last = merged[-1]
        if event["start"] <= last["end"] + 0.5:
            if prefer_max:
                if abs(event["delta"]) > abs(last["delta"]):
                    last.update(event)
            else:
                last["end"] = event["end"]
                last["delta"] = min(last["delta"], event["delta"])
                last["rate"] = min(last["rate"], event["rate"])
                last["to"] = event["to"]
        else:
            merged.append(event)
    return merged


def analyze_file(path: str | Path, *, window: float = 5.0, step: float = 1.0,
                 min_drop: float = 3.0) -> dict[str, Any]:
    raw = load_retention_csv(path)
    points = resample(raw, step)
    duration = points[-1]["time"] if points else 0.0
    events = find_events(points, window=window, min_drop=min_drop)
    total_drop = points[0]["retention"] - points[-1]["retention"] if points else 0.0
    intro = _at_ratio(points, 0.05)
    mid = _at_ratio(points, 0.5)
    return {
        "file": str(Path(path).resolve()),
        "duration": round(duration, 2),
        "points": len(points),
        "start_retention": round(points[0]["retention"], 2) if points else 0,
        "end_retention": round(points[-1]["retention"], 2) if points else 0,
        "average_retention": round(mean(p["retention"] for p in points), 2) if points else 0,
        "intro_retention": intro,
        "mid_retention": mid,
        "total_drop": round(total_drop, 2),
        "samples": points,
        "drops": events["drops"],
        "spikes": events["spikes"],
        "recommendations": recommendations(points, events),
    }


def _at_ratio(points: Sequence[dict[str, float]], ratio: float) -> float:
    if not points:
        return 0.0
    target = points[-1]["time"] * ratio
    return round(min(points, key=lambda p: abs(p["time"] - target))["retention"], 2)


def recommendations(points: Sequence[dict[str, float]],
                    events: dict[str, list[dict[str, Any]]]) -> list[str]:
    tips: list[str] = []
    if not points:
        return tips
    duration = points[-1]["time"]
    start = points[0]["retention"]
    first_15 = _at_ratio(points, 15 / duration) if duration > 15 else start
    if start - first_15 > 8:
        tips.append(
            f"Chute de {start - first_15:.1f} pts dans les 15 premières secondes : "
            "le hook arrive trop tard. Ouvre sur la promesse ou le résultat, coupe toute intro."
        )
    for drop in events["drops"][:5]:
        ratio = drop["start"] / max(0.1, duration)
        if ratio < 0.12:
            tips.append(
                f"Drop fort à {fmt_clock(drop['start'])} ({drop['delta']:.1f} pts) en ouverture : "
                "teste un cold open, un plan plus dynamique ou une question directe."
            )
        elif ratio > 0.8:
            tips.append(
                f"Drop à {fmt_clock(drop['start'])} en fin de vidéo : raccourcis l'outro, "
                "place le CTA plus tôt ou coupe la récapitulation."
            )
        else:
            tips.append(
                f"Drop à {fmt_clock(drop['start'])} ({drop['delta']:.1f} pts) : "
                "zone à retravailler — raccourcis les silences, ajoute un B-roll ou un changement de plan."
            )
    if events["spikes"]:
        best = max(events["spikes"], key=lambda e: e["delta"])
        tips.append(
            f"Pic de rétention à {fmt_clock(best['start'])} (+{best['delta']:.1f} pts) : "
            "identifie ce qui a retenu (question, visuel, révélation) et réutilise ce pattern."
        )
    if not tips:
        tips.append("Courbe stable : pas de décrochage majeur détecté sur cet export.")
    tips.append(
        "Les courbes YouTube mélangent souvent plusieurs formats d'audience : compare toujours "
        "des vidéos de même durée et de même style."
    )
    return tips


def analyze_many(paths: Iterable[str | Path], *, window: float = 5.0,
                 step: float = 1.0) -> dict[str, Any]:
    from .common import warn

    results = []
    skipped = []
    for path in paths:
        try:
            results.append(analyze_file(path, window=window, step=step))
        except SkillError as exc:
            skipped.append({"file": str(path), "reason": str(exc).splitlines()[0]})
            warn(f"CSV ignoré : {Path(path).name} ({str(exc).splitlines()[0]})")
    if not results:
        raise SkillError("Aucun CSV de rétention exploitable.")
    if skipped:
        warn(f"{len(skipped)} fichier(s) ignoré(s) : colonnes temps/rétention absentes.")
    # rétention moyenne par position relative (bins de 5 %)
    bins: list[list[float]] = [[] for _ in range(20)]
    drop_bins = [0] * 20
    for result in results:
        duration = max(0.1, result["duration"])
        for point in result["samples"]:
            index = min(19, int(point["time"] / duration * 20))
            bins[index].append(point["retention"])
        for drop in result["drops"]:
            index = min(19, int(drop["start"] / duration * 20))
            drop_bins[index] += 1
    curve = []
    for index, values in enumerate(bins):
        if values:
            curve.append({
                "position": index * 5,
                "retention": round(mean(values), 2),
                "videos": len(values),
                "drops": drop_bins[index],
            })
    weakest = sorted(
        [point for point in curve if point["videos"] >= max(1, len(results) // 2)],
        key=lambda point: point["retention"],
    )[:3]
    return {
        "count": len(results),
        "skipped": skipped,
        "videos": [
            {"file": r["file"], "duration": r["duration"],
             "average_retention": r["average_retention"],
             "start_retention": r["start_retention"]}
            for r in results
        ],
        "average_curve": curve,
        "weakest_zones": weakest,
        "per_video": results,
    }


def correlate(analysis: dict[str, Any], transcript: dict[str, Any],
              *, max_items: int = 8) -> list[dict[str, Any]]:
    """Associe les drops à ce qui est dit au même moment."""
    from .transcript import ensure_word_timings

    segments = ensure_word_timings(transcript.get("segments", []))
    notes = []
    for drop in analysis.get("drops", [])[:max_items]:
        midpoint = (drop["start"] + drop["end"]) / 2
        segment = next((s for s in segments if s["start"] <= midpoint <= s["end"]), None)
        notes.append({
            "time": round(drop["start"], 2),
            "drop": drop["delta"],
            "text": segment["text"] if segment else None,
            "segment_start": segment["start"] if segment else None,
        })
    return notes


def retention_markdown(analysis: dict[str, Any], *, source: str | None = None,
                       correlation: Sequence[dict[str, Any]] | None = None) -> str:
    lines = ["# Analyse de rétention", ""]
    if source:
        lines += [f"**Source** : `{source}`", ""]
    lines += [
        f"- Durée analysée : **{fmt_clock(analysis['duration'])}**",
        f"- Rétention au départ : **{analysis['start_retention']:.1f} %**",
        f"- Rétention moyenne : **{analysis['average_retention']:.1f} %**",
        f"- Rétention à mi-parcours : **{analysis['mid_retention']:.1f} %**",
        f"- Rétention finale : **{analysis['end_retention']:.1f} %**",
        "",
        "## Décrochages",
        "",
    ]
    if analysis["drops"]:
        lines += ["| Timecode | Fenêtre | Perte | Vitesse |", "|----------|---------|-------|---------|"]
        for drop in analysis["drops"][:10]:
            lines.append(
                f"| {fmt_clock(drop['start'])} | {fmt_clock(drop['start'])} → "
                f"{fmt_clock(drop['end'])} | {drop['delta']:.1f} pts | {drop['rate']:.2f} pts/s |"
            )
    else:
        lines.append("Aucun décrochage significatif détecté.")
    lines += ["", "## Pics", ""]
    if analysis["spikes"]:
        for spike in analysis["spikes"][:5]:
            lines.append(
                f"- **{fmt_clock(spike['start'])}** : +{spike['delta']:.1f} pts "
                f"(fenêtre {fmt_clock(spike['start'])} → {fmt_clock(spike['end'])})"
            )
    else:
        lines.append("Aucun pic notable.")
    if correlation:
        lines += ["", "## Ce qui est dit au moment des drops", ""]
        for note in correlation:
            text = note.get("text") or "*(pas de transcription à cet instant)*"
            lines.append(f"- **{fmt_clock(note['time'])}** ({note['drop']:.1f} pts) — {text}")
    lines += ["", "## Recommandations", ""]
    for tip in analysis["recommendations"]:
        lines.append(f"- {tip}")
    lines += [
        "",
        "## Comment lire ce rapport",
        "",
        "- Une chute **dans les 5 premières secondes** = problème de hook ou d'intro.",
        "- Une chute **au milieu** = rythme, promesse non tenue ou passage trop long.",
        "- Un **pic** = moment à réutiliser comme pattern (question, preuve, visuel fort).",
        "- Compare plusieurs vidéos de même format avec `--all DOSSIER` pour fiabiliser.",
        "",
    ]
    return "\n".join(lines)
