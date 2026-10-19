"""Sound design : catalogue de SFX, détection de cues, génération et mixage FFmpeg."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Sequence

from .common import (SkillError, fmt_clock, normalize_text, read_json, skill_data,
                     write_json)
from .ffmpeg import ffmpeg, media_info

DEFAULT_CATALOG = skill_data("sound-effect-cue-automator", "sfx-catalog.json")

# id -> (arguments lavfi, filtre audio)
SYNTH = {
    "whoosh": (
        "anoisesrc=color=pink:duration=0.55:amplitude=0.6:seed=7",
        "highpass=f=350,lowpass=f=4200,afade=t=in:st=0:d=0.06,"
        "afade=t=out:st=0.10:d=0.45,volume=1.0",
    ),
    "pop": (
        "sine=frequency=950:duration=0.10,asetpts=PTS-STARTPTS",
        "afade=t=out:st=0.012:d=0.088,volume=0.9",
    ),
    "braam": (
        "sine=frequency=52:duration=1.5,asetpts=PTS-STARTPTS",
        "tremolo=f=9:d=0.35,aecho=0.8:0.6:120:0.4,"
        "afade=t=out:st=0.35:d=1.1,volume=1.3",
    ),
    "camera-click": (
        "anoisesrc=color=white:duration=0.12:amplitude=0.9:seed=3",
        "highpass=f=1200,afade=t=out:st=0.02:d=0.10,volume=0.8",
    ),
    "riser": (
        "anoisesrc=color=white:duration=1.8:amplitude=0.5:seed=11",
        "highpass=f=300,lowpass=f=8000,afade=t=in:st=0:d=1.55,"
        "afade=t=out:st=1.55:d=0.25,volume=0.8",
    ),
    "impact": (
        "sine=frequency=62:duration=0.55,asetpts=PTS-STARTPTS",
        "afade=t=out:st=0.04:d=0.5,volume=1.4",
    ),
    "tick": (
        "sine=frequency=2300:duration=0.035,asetpts=PTS-STARTPTS",
        "afade=t=out:st=0.004:d=0.03,volume=0.7",
    ),
    "swoosh": (
        "anoisesrc=color=pink:duration=0.35:amplitude=0.5:seed=19",
        "bandpass=f=1400:width_type=h:w=1200,afade=t=in:st=0:d=0.03,"
        "afade=t=out:st=0.08:d=0.25,volume=0.9",
    ),
}


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    data = read_json(Path(path) if path else DEFAULT_CATALOG)
    if "effects" not in data:
        raise SkillError("Catalogue SFX invalide (clé 'effects' absente).")
    return data


def catalog_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {effect["id"]: effect for effect in catalog["effects"]}


def generate_catalog(output_dir: str | Path, *, catalog_path: str | Path | None = None,
                     force: bool = False, dry_run: bool = False) -> list[Path]:
    """Fabrique des SFX libres de droits avec les synthétiseurs FFmpeg."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog(catalog_path)
    written = []
    for effect in catalog["effects"]:
        effect_id = effect["id"]
        target = output / effect["file"]
        if target.exists() and not force:
            written.append(target)
            continue
        if effect_id not in SYNTH:
            continue
        source, filters = SYNTH[effect_id]
        ffmpeg(["-f", "lavfi", "-i", source, "-af", filters,
                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(target)],
               dry_run=dry_run)
        written.append(target)
    return written


# --------------------------------------------------------------------------- cues


def _keyword_set(keywords: Sequence[str] | None) -> set[str]:
    return {normalize_text(word) for word in (keywords or []) if str(word).strip()}


def detect_cues(
    transcript: dict[str, Any],
    *,
    keywords: Sequence[str] | None = None,
    styles: dict[str, Any] | None = None,
    scenes: Sequence[dict[str, Any]] | None = None,
    captions: Sequence[dict[str, Any]] | None = None,
    interval: float = 6.0,
    min_spacing: float = 0.22,
    max_cues: int = 400,
) -> list[dict[str, Any]]:
    """Déduit les SFX des moments de montage (segments, mots-clés, plans)."""
    from .transcript import all_words, ensure_word_timings

    styles = styles or {}
    keyword_set = _keyword_set(keywords)
    cues: list[dict[str, Any]] = []

    def add(time: float, effect: str, reason: str, gain: float | None = None,
            priority: int = 1) -> None:
        cues.append({
            "time": round(max(0.0, time), 3),
            "sfx": effect,
            "reason": reason,
            "gain_db": gain,
            "priority": priority,
        })

    segments = ensure_word_timings(transcript.get("segments", []))
    if not segments:
        raise SkillError("Transcription vide : impossible de placer des SFX.")
    add(0.0, styles.get("intro", "whoosh"), "ouverture de la vidéo", priority=3)
    previous_end = None
    for index, segment in enumerate(segments):
        if index > 0 and previous_end is not None:
            gap = float(segment["start"]) - previous_end
            if gap > 0.30:
                add(float(segment["start"]) - 0.04, styles.get("transition", "whoosh"),
                    f"reprise après {gap:.1f}s de silence", priority=2)
        previous_end = max(previous_end or 0.0, float(segment["end"]))
        text = str(segment.get("text", ""))
        if re.search(r"\?$", text.strip()):
            add(float(segment["end"]) - 0.1, styles.get("question", "tick"),
                "fin de question", priority=1)
        if index > 0 and index % max(1, int(interval / 2)) == 0:
            add(float(segment["start"]), styles.get("rhythm", "swoosh"),
                "respiration rythmique", priority=1)

    if keyword_set:
        for word in all_words(transcript):
            token = normalize_text(re.sub(r"[^\w'’-]", "", str(word["word"])))
            if token in keyword_set:
                add(float(word["start"]), styles.get("keyword", "pop"),
                    f"mot-clé « {word['word']} »", priority=2)

    if scenes:
        for scene in scenes:
            time = float(scene.get("time", 0))
            if time > 0.1:
                add(time, styles.get("cut", "whoosh"), "changement de plan", priority=2)

    if captions:
        for index, event in enumerate(captions):
            if index % 3 == 0:
                add(float(event["start"]), styles.get("caption", "pop"),
                    "apparition de sous-titre", priority=1)

    # déduplication : garde la priorité la plus haute dans une fenêtre courte
    cues.sort(key=lambda cue: (cue["time"], -cue["priority"]))
    selected: list[dict[str, Any]] = []
    for cue in cues:
        if any(abs(cue["time"] - other["time"]) < min_spacing for other in selected):
            continue
        selected.append(cue)
        if len(selected) >= max_cues:
            break
    return sorted(selected, key=lambda cue: cue["time"])


def resolve_cues(cues: Sequence[dict[str, Any]], catalog: dict[str, Any],
                 sfx_dir: str | Path) -> list[dict[str, Any]]:
    index = catalog_index(catalog)
    directory = Path(sfx_dir)
    resolved = []
    for cue in cues:
        effect = index.get(cue["sfx"])
        if not effect:
            continue
        path = directory / effect["file"]
        resolved.append({
            **cue,
            "label": effect.get("label", cue["sfx"]),
            "file": str(path),
            "gain_db": cue.get("gain_db") if cue.get("gain_db") is not None
            else effect.get("default_gain_db", -12),
            "exists": path.exists(),
        })
    return resolved


def cues_to_csv(cues: Sequence[dict[str, Any]], path: str | Path) -> Path:
    import csv

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Timecode", "Seconds", "SFX", "Gain dB", "Reason", "File"])
        for cue in cues:
            writer.writerow([fmt_clock(cue["time"]), cue["time"], cue["sfx"],
                             cue.get("gain_db", ""), cue.get("reason", ""), cue.get("file", "")])
    return target


def render_sfx_track(cues: Sequence[dict[str, Any]], out: str | Path, *,
                     duration: float, sample_rate: int = 48000,
                     master_gain_db: float = -2.0,
                     dry_run: bool = False) -> Path:
    available = [cue for cue in cues if cue.get("exists", Path(cue.get("file", "")).exists())]
    if not available:
        raise SkillError("Aucun fichier SFX disponible. Lance build_catalog.py --generate.")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    inputs = []
    filters = []
    labels = []
    for index, cue in enumerate(available):
        inputs += ["-i", cue["file"]]
        delay = int(round(cue["time"] * 1000))
        gain = float(cue.get("gain_db", -12))
        chain = f"[{index}:a]adelay={delay}:all=1,volume={gain}dB,"
        chain += f"aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]"
        filters.append(chain)
        labels.append(f"[a{index}]")
    filters.append(
        "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"alimiter=limit=0.95,volume={master_gain_db}dB[out]"
    )
    args = [*inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
            "-t", f"{duration:.3f}", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(out_path)]
    ffmpeg(args, dry_run=dry_run)
    return out_path


def mix_into_video(video: str | Path, sfx_track: str | Path, out: str | Path, *,
                   sfx_gain_db: float = 0.0, original_gain_db: float = 0.0,
                   dry_run: bool = False) -> Path:
    info_ = media_info(video)
    if not info_["has_audio"]:
        from .ffmpeg import mux_audio

        return mux_audio(video, sfx_track, out, replace=True,
                         audio_gain_db=sfx_gain_db, dry_run=dry_run)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    graph = (
        f"[0:a]volume={original_gain_db}dB[voice];"
        f"[1:a]volume={sfx_gain_db}dB[sfx];"
        "[voice][sfx]amix=inputs=2:duration=first:normalize=0[a]"
    )
    ffmpeg(["-i", str(video), "-i", str(sfx_track), "-filter_complex", graph,
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "256k", "-movflags", "+faststart", str(out_path)], dry_run=dry_run)
    return out_path


def cues_markdown(cues: Sequence[dict[str, Any]]) -> str:
    lines = ["# Cues d'effets sonores", "",
             f"{len(cues)} effet(s) placé(s).", "",
             "| Timecode | Effet | Gain | Raison |", "|----------|-------|------|--------|"]
    for cue in cues:
        lines.append(f"| {fmt_clock(cue['time'])} | {cue.get('sfx')} | "
                     f"{cue.get('gain_db', '')} dB | {cue.get('reason', '')} |")
    lines += ["", "Mixer avec `mix_into_video` ou importer le WAV dans le NLE.", ""]
    return "\n".join(lines)
