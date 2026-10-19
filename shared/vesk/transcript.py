"""Modèle de transcription, parsing SRT/VTT et répartition des mots dans le temps."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import SkillError, clamp, fmt_srt_time, fmt_vtt_time, read_text

_TS = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?P<sep>[,.])(?P<ms>\d{1,3})"
)
_WORD = re.compile(r"[^\s]+")
_TAG = re.compile(r"<[^>]+>")
_PUNCT_END = re.compile(r"[.!?…]+[\"'»)]*$")
_PUNCT_SOFT = re.compile(r"[,;:…]+[\"'»)]*$")


def _ts_to_seconds(match: re.Match[str]) -> float:
    ms = match.group("ms").ljust(3, "0")
    return (
        int(match.group("h")) * 3600
        + int(match.group("m")) * 60
        + int(match.group("s"))
        + int(ms) / 1000
    )


def split_words(text: str) -> list[str]:
    return [token for token in _WORD.findall(text.strip()) if token]


def parse_srt(content: str) -> list[dict[str, Any]]:
    content = content.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff \n")
    blocks = re.split(r"\n{2,}", content)
    segments: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        start_raw, end_raw = [part.strip() for part in lines[time_index].split("-->", 1)]
        start_match = _TS.search(start_raw)
        end_match = _TS.search(end_raw)
        if not start_match or not end_match:
            continue
        text = " ".join(_TAG.sub("", line).strip() for line in lines[time_index + 1 :]).strip()
        if not text:
            continue
        segments.append({
            "start": round(_ts_to_seconds(start_match), 3),
            "end": round(_ts_to_seconds(end_match), 3),
            "text": re.sub(r"\s+", " ", text),
        })
    return _finalize(segments)


def parse_vtt(content: str) -> list[dict[str, Any]]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    cleaned: list[str] = []
    for line in lines:
        if line.strip().upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        cleaned.append(line)
    return parse_srt("\n".join(cleaned))


def parse_txt(content: str, *, duration: float | None = None,
              words_per_minute: float = 150.0) -> list[dict[str, Any]]:
    """Script sans timings : répartit les phrases à ~150 mots/minute."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", content) if s.strip()]
    if not sentences:
        return []
    total_words = sum(len(split_words(s)) for s in sentences) or 1
    estimated = duration or total_words / words_per_minute * 60
    cursor = 0.0
    segments = []
    for sentence in sentences:
        share = len(split_words(sentence)) / total_words * estimated
        segments.append({"start": round(cursor, 3), "end": round(cursor + share, 3),
                         "text": sentence})
        cursor += share
    return _finalize(segments)


def _finalize(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, segment in enumerate(segments, start=1):
        segment["id"] = index
        segment.setdefault("words", [])
        if segment["end"] < segment["start"]:
            segment["end"] = segment["start"]
    return segments


def load_transcript(path: str | Path, *, duration: float | None = None) -> dict[str, Any]:
    p = Path(path)
    suffix = p.suffix.lower()
    content = read_text(p)
    if suffix == ".json":
        data = json.loads(content)
        if isinstance(data, list):
            data = {"segments": data}
        if not isinstance(data, dict) or "segments" not in data:
            raise SkillError(
                "JSON de transcription attendu : {'segments': [{'start','end','text'}]} "
                "ou {'words': [{'word','start','end'}]}."
            )
        segments = data.get("segments") or segments_from_words(data.get("words") or [])
        data["segments"] = _finalize([
            {"start": float(s["start"]), "end": float(s["end"]), "text": str(s.get("text", "")).strip(),
             "words": s.get("words", [])}
            for s in segments
        ])
        data.setdefault("language", None)
        data.setdefault("duration", duration or (data["segments"][-1]["end"] if data["segments"] else 0))
        return data
    if suffix in {".srt", ".sbv"}:
        segments = parse_srt(content)
    elif suffix == ".vtt":
        segments = parse_vtt(content)
    elif suffix in {".txt", ".md"}:
        segments = parse_txt(content, duration=duration)
    else:
        raise SkillError(f"Format de transcription non supporté : {suffix} (JSON, SRT, VTT, TXT)")
    return {
        "language": None,
        "duration": duration or (segments[-1]["end"] if segments else 0.0),
        "segments": segments,
    }


def segments_from_words(words: Sequence[dict[str, Any]], *, max_chars: int = 72,
                        max_duration: float = 5.0, max_words: int = 16) -> list[dict[str, Any]]:
    """Regroupe des mots horodatés en segments lisibles."""
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        current.append(word)
        text = " ".join(str(w.get("word", w.get("text", ""))) for w in current).strip()
        gap_next = 0.0
        if len(current) > 1:
            gap_next = float(word["start"]) - float(current[-2]["end"])
        if (
            len(text) >= max_chars
            or len(current) >= max_words
            or float(word["end"]) - float(current[0]["start"]) >= max_duration
            or gap_next > 0.8
            or _PUNCT_END.search(str(word.get("word", "")))
        ):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    segments = []
    for group in groups:
        segments.append({
            "start": float(group[0]["start"]),
            "end": float(group[-1]["end"]),
            "text": " ".join(str(w.get("word", w.get("text", ""))) for w in group).strip(),
            "words": group,
        })
    return _finalize(segments)


def ensure_word_timings(segments: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Complète (ou recalcule) les timings mot à mot dans chaque segment."""
    output: list[dict[str, Any]] = []
    for segment in segments:
        words = segment.get("words") or []
        if not words:
            tokens = split_words(str(segment.get("text", "")))
            words = distribute_words(tokens, float(segment["start"]), float(segment["end"]))
        else:
            normalized = []
            for word in words:
                text = str(word.get("word", word.get("text", ""))).strip()
                if not text:
                    continue
                normalized.append({
                    "word": text,
                    "start": float(word.get("start", segment["start"])),
                    "end": float(word.get("end", word.get("start", segment["end"]))),
                })
            words = normalized or distribute_words(
                split_words(str(segment.get("text", ""))),
                float(segment["start"]), float(segment["end"]),
            )
        output.append({**segment, "words": words})
    return output


def distribute_words(tokens: Sequence[str], start: float, end: float) -> list[dict[str, Any]]:
    """Répartit des mots dans [start, end] proportionnellement à leur longueur."""
    if not tokens:
        return []
    span = max(0.001, end - start)
    weights = []
    for token in tokens:
        weight = max(2.0, len(token) + 1.0)
        if _PUNCT_END.search(token):
            weight += 2.5
        elif _PUNCT_SOFT.search(token):
            weight += 1.0
        weights.append(weight)
    total = sum(weights)
    words = []
    cursor = start
    for token, weight in zip(tokens, weights):
        duration = span * weight / total
        words.append({"word": token, "start": round(cursor, 3),
                      "end": round(min(end, cursor + duration), 3)})
        cursor += duration
    words[-1]["end"] = round(end, 3)
    return words


def all_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    segments = ensure_word_timings(transcript.get("segments", []))
    words: list[dict[str, Any]] = []
    for segment in segments:
        words.extend(segment["words"])
    return words


def text_of(transcript: dict[str, Any]) -> str:
    return " ".join(str(s.get("text", "")).strip() for s in transcript.get("segments", [])).strip()


def normalize_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    segments = ensure_word_timings(transcript.get("segments", []))
    return {
        "version": "1.0",
        "language": transcript.get("language"),
        "duration": float(transcript.get("duration") or (segments[-1]["end"] if segments else 0.0)),
        "source": transcript.get("source"),
        "segments": segments,
    }


def to_srt(segments: Sequence[dict[str, Any]], *, max_chars: int = 42) -> str:
    blocks = []
    index = 1
    for segment in segments:
        for chunk in wrap_segment(segment, max_chars=max_chars):
            blocks.append(
                f"{index}\n{fmt_srt_time(chunk['start'])} --> {fmt_srt_time(chunk['end'])}\n"
                f"{chunk['text']}\n"
            )
            index += 1
    return "\n".join(blocks)


def to_vtt(segments: Sequence[dict[str, Any]], *, max_chars: int = 42) -> str:
    blocks = ["WEBVTT\n"]
    for segment in segments:
        for chunk in wrap_segment(segment, max_chars=max_chars):
            blocks.append(
                f"{fmt_vtt_time(chunk['start'])} --> {fmt_vtt_time(chunk['end'])}\n"
                f"{chunk['text']}\n"
            )
    return "\n".join(blocks)


def wrap_segment(segment: dict[str, Any], *, max_chars: int = 42) -> list[dict[str, Any]]:
    """Découpe un segment trop long en respectant les timings des mots si dispo."""
    text = str(segment.get("text", "")).strip()
    if len(text) <= max_chars:
        return [{"start": float(segment["start"]), "end": float(segment["end"]), "text": text}]
    words = segment.get("words") or distribute_words(
        split_words(text), float(segment["start"]), float(segment["end"])
    )
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        current.append(word)
        if len(" ".join(str(w["word"]) for w in current)) >= max_chars * 0.75:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return [
        {
            "start": float(group[0]["start"]),
            "end": float(group[-1]["end"]),
            "text": " ".join(str(w["word"]) for w in group),
        }
        for group in chunks
    ]


def transcript_summary(transcript: dict[str, Any]) -> dict[str, Any]:
    segments = transcript.get("segments", [])
    words = all_words(transcript)
    return {
        "language": transcript.get("language"),
        "duration": transcript.get("duration"),
        "segments": len(segments),
        "words": len(words),
        "words_per_minute": round(
            len(words) / max(0.001, float(transcript.get("duration") or 1)) * 60, 1
        ) if words else 0,
    }


def trim_to_range(transcript: dict[str, Any], start: float, end: float) -> dict[str, Any]:
    segments = []
    for segment in ensure_word_timings(transcript.get("segments", [])):
        if segment["end"] <= start or segment["start"] >= end:
            continue
        words = [w for w in segment["words"] if w["end"] > start and w["start"] < end]
        if not words:
            continue
        segments.append({
            "start": clamp(float(words[0]["start"]) - start, 0, end - start),
            "end": clamp(float(words[-1]["end"]) - start, 0, end - start),
            "text": " ".join(str(w["word"]) for w in words),
            "words": [{"word": w["word"],
                       "start": clamp(float(w["start"]) - start, 0, end - start),
                       "end": clamp(float(w["end"]) - start, 0, end - start)} for w in words],
        })
    return {"language": transcript.get("language"), "duration": round(end - start, 3),
            "segments": _finalize(segments)}


def iter_sentences(transcript: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Concatène les segments en phrases (pour le scoring sémantique)."""
    buffer: list[str] = []
    start = None
    last_end = None
    for segment in transcript.get("segments", []):
        if start is None:
            start = segment["start"]
        buffer.append(str(segment.get("text", "")).strip())
        last_end = segment["end"]
        text = " ".join(buffer)
        if re.search(r"[.!?…]\s*$", text) and len(buffer) >= 1:
            yield {"start": float(start), "end": float(last_end), "text": text}
            buffer, start = [], None
    if buffer and start is not None:
        yield {"start": float(start), "end": float(last_end), "text": " ".join(buffer)}
