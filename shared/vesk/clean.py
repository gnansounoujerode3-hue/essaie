"""Nettoyage et mastering audio : denoise, EQ, compression, loudness EBU R128."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .common import SkillError, info, warn
from .ffmpeg import audio_loudness, ffmpeg, has_filter, media_info

PRESETS: dict[str, dict[str, Any]] = {
    "voice": {
        "label": "Voix parlée (YouTube / Reels)",
        "highpass": 80, "lowpass": 13000, "denoise": 35, "deess": 0.35,
        "eq": [("low_shelf", 180, -2.5), ("presence", 3200, 2.0), ("air", 9000, 1.0)],
        "compressor": True, "gate": True, "target_i": -16.0, "true_peak": -1.5, "lra": 11.0,
    },
    "podcast": {
        "label": "Podcast / interview",
        "highpass": 70, "lowpass": 15000, "denoise": 25, "deess": 0.3,
        "eq": [("low_shelf", 200, -2.0), ("presence", 2800, 1.5)],
        "compressor": True, "gate": True, "target_i": -16.0, "true_peak": -1.0, "lra": 9.0,
    },
    "social": {
        "label": "Réseaux sociaux (plus fort, plus dense)",
        "highpass": 90, "lowpass": 14000, "denoise": 40, "deess": 0.4,
        "eq": [("low_shelf", 160, -3.0), ("presence", 3500, 2.5), ("air", 10000, 1.5)],
        "compressor": True, "gate": True, "target_i": -14.0, "true_peak": -1.0, "lra": 7.0,
    },
    "light": {
        "label": "Nettoyage léger (son déjà propre)",
        "highpass": 60, "lowpass": 16000, "denoise": 12, "deess": 0.15,
        "eq": [], "compressor": False, "gate": False,
        "target_i": -16.0, "true_peak": -1.5, "lra": 11.0,
    },
}


def analyze(path: str | Path) -> dict[str, Any]:
    info_ = media_info(path)
    if not info_["has_audio"]:
        raise SkillError(f"Aucune piste audio dans {path}")
    loudness = audio_loudness(path)
    stats = _astats(path)
    return {
        "file": str(Path(path).resolve()),
        "duration": info_["duration"],
        "sample_rate": _sample_rate(path),
        "input_lufs": loudness.get("input_i"),
        "input_true_peak": loudness.get("input_tp"),
        "input_lra": loudness.get("input_lra"),
        "noise_floor_db": stats.get("noise_floor"),
        "peak_db": stats.get("peak"),
        "rms_db": stats.get("rms"),
    }


def _sample_rate(path: str | Path) -> int | None:
    from .ffmpeg import ffprobe

    try:
        data = ffprobe(path)
    except SkillError:
        return None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return int(stream.get("sample_rate") or 0) or None
    return None


def _astats(path: str | Path) -> dict[str, float]:
    proc = ffmpeg(["-i", str(path), "-af", "astats=metadata=1:reset=0", "-f", "null", "-"],
                  check=False, quiet=True)
    stderr = proc.stderr or ""
    stats: dict[str, float] = {}
    for line in stderr.splitlines():
        match = None
        for key, label in (("noise_floor", "Noise floor dB"), ("peak", "Peak level dB"),
                           ("rms", "RMS level dB")):
            marker = label + ":"
            if marker in line:
                match = (key, line.split(marker, 1)[1].strip())
        if match:
            try:
                number = float(match[1].split()[0])
            except (ValueError, IndexError):
                continue
            if math.isfinite(number):
                stats[match[0]] = number
    return stats


def build_filter_chain(*, preset: str = "voice", denoise: int | None = None,
                       target_i: float | None = None, loudnorm: bool = True,
                       measured: dict[str, float] | None = None,
                       gate: bool | None = None, compressor: bool | None = None,
                       eq: bool | None = None, deess: float | None = None) -> str:
    if preset not in PRESETS and preset != "custom":
        raise SkillError(f"Preset audio inconnu : {preset} (voice, podcast, social, light)")
    config = dict(PRESETS.get(preset, PRESETS["voice"]))
    if denoise is not None:
        config["denoise"] = float(denoise)
    if target_i is not None:
        config["target_i"] = float(target_i)
    if gate is not None:
        config["gate"] = gate
    if compressor is not None:
        config["compressor"] = compressor
    if eq is not None:
        config["eq"] = config["eq"] if eq else []
    if deess is not None:
        config["deess"] = float(deess)

    filters: list[str] = []
    if config["highpass"]:
        filters.append(f"highpass=f={config['highpass']}:poles=2")
    if config["lowpass"]:
        filters.append(f"lowpass=f={config['lowpass']}:poles=2")
    if config["gate"]:
        filters.append("agate=threshold=0.015:ratio=4:attack=8:release=180")
    if config["denoise"] and has_filter("afftdn"):
        nr = max(0.0, min(97.0, float(config["denoise"])))
        filters.append(f"afftdn=nr={nr:.1f}:nf=-32:tn=1")
    elif config["denoise"] and has_filter("anlmdn"):
        strength = max(0.00001, min(0.002, float(config["denoise"]) / 30000.0))
        filters.append(f"anlmdn=s={strength:.6f}:p=0.002:r=0.006")
        warn("afftdn indisponible : réduction de bruit via anlmdn (plus douce).")
    for name, freq, gain in config.get("eq", []):
        if name == "low_shelf":
            filters.append(f"equalizer=f={freq}:t=h:w=1:g={gain}")
        elif name == "presence":
            filters.append(f"equalizer=f={freq}:t=q:w=1.2:g={gain}")
        elif name == "air":
            filters.append(f"highshelf=f={freq}:g={gain}")
    if config.get("deess") and has_filter("deesser"):
        filters.append(
            f"deesser=i={float(config['deess']):.2f}:m=0.5:f=0.5"
        )
    if config["compressor"]:
        filters.append(
            "compand=attacks=0.008:decays=0.16:"
            "points=-70/-70|-45/-30|-30/-18|-20/-12|-12/-8|-6/-5|0/-4:"
            "soft-knee=6:gain=0"
        )
    if loudnorm:
        target_i = float(config["target_i"])
        true_peak = float(config["true_peak"])
        lra = float(config["lra"])
        if measured and measured.get("input_i") is not None:
            filters.append(
                "loudnorm=I={i}:TP={tp}:LRA={lra}:measured_I={mi}:measured_TP={mtp}:"
                "measured_LRA={mlra}:measured_thresh={mth}:offset={off}:linear=true".format(
                    i=target_i, tp=true_peak, lra=lra,
                    mi=measured.get("input_i", -23.0),
                    mtp=measured.get("input_tp", -2.0),
                    mlra=measured.get("input_lra", 7.0),
                    mth=measured.get("input_thresh", -33.0),
                    off=measured.get("target_offset", 0.0),
                )
            )
        else:
            filters.append(f"loudnorm=I={target_i}:TP={true_peak}:LRA={lra}")
    filters.append("alimiter=limit=0.97")
    return ",".join(filters)


def measure_after_chain(input_path: str | Path, chain_without_loudnorm: str,
                        target_i: float, *, true_peak: float, lra: float) -> dict[str, float]:
    """Mesure la loudness **après** la chaîne de traitement (2e passe fiable)."""
    loudnorm = (f"loudnorm=I={target_i}:TP={true_peak}:LRA={lra}:print_format=json")
    filters = ",".join(part for part in [chain_without_loudnorm, loudnorm] if part)
    proc = ffmpeg(["-i", str(input_path), "-af", filters, "-f", "null", "-"],
                  check=False, quiet=True)
    stderr = proc.stderr or ""
    import json as _json
    import re as _re

    match = _re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, _re.S)
    if not match:
        return {}
    try:
        data = _json.loads(match.group(0))
    except _json.JSONDecodeError:
        return {}
    measured = {}
    for key, value in data.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            measured[key] = number
    return measured


def clean_audio(input_path: str | Path, output_path: str | Path, *,
                preset: str = "voice", denoise: int | None = None,
                target_i: float | None = None, loudnorm: bool = True,
                sample_rate: int = 48000, channels: int = 1,
                bitrate: str = "256k", two_pass: bool = True,
                dry_run: bool = False) -> dict[str, Any]:
    info_ = media_info(input_path)
    if not info_["has_audio"]:
        raise SkillError(f"Aucune piste audio dans {input_path}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    before = analyze(input_path) if not dry_run else {}
    config = PRESETS.get(preset, PRESETS["voice"])
    effective_target = float(target_i if target_i is not None else config["target_i"])
    measured = None
    if loudnorm and two_pass and not dry_run:
        info("Mesure loudness après traitement (passe 1/2)…")
        base_chain = build_filter_chain(preset=preset, denoise=denoise,
                                        target_i=target_i, loudnorm=False)
        measured = measure_after_chain(
            input_path, base_chain, effective_target,
            true_peak=float(config["true_peak"]), lra=float(config["lra"]),
        )
        if not measured:
            warn("Mesure loudness indisponible : loudnorm en mode dynamique.")
    chain = build_filter_chain(preset=preset, denoise=denoise, target_i=target_i,
                               loudnorm=loudnorm, measured=measured)
    info(f"Traitement audio ({preset}) : {chain[:160]}…")
    audio_codec = ["-c:a", "pcm_s16le"] if out.suffix.lower() == ".wav" else ["-c:a", "aac", "-b:a", bitrate]
    ffmpeg(["-i", str(input_path), "-vn", "-af", chain, "-ar", str(sample_rate),
            "-ac", str(channels), *audio_codec, str(out)], dry_run=dry_run)
    after = analyze(out) if not dry_run and out.exists() else {}
    return {
        "input": str(Path(input_path).resolve()),
        "output": str(out.resolve()),
        "preset": preset,
        "filter_chain": chain,
        "before": before,
        "after": after,
        "gain_lufs": (round(after.get("input_lufs", 0) - before.get("input_lufs", 0), 2)
                      if before.get("input_lufs") and after.get("input_lufs") else None),
    }


def clean_report(result: dict[str, Any]) -> str:
    before = result.get("before") or {}
    after = result.get("after") or {}
    lines = [
        "# Nettoyage audio",
        "",
        f"- **Entrée** : `{result['input']}`",
        f"- **Sortie** : `{result['output']}`",
        f"- **Preset** : {result['preset']}",
        "",
        "| Mesure | Avant | Après |",
        "|--------|-------|-------|",
        f"| Loudness intégré | {before.get('input_lufs', '—')} LUFS | {after.get('input_lufs', '—')} LUFS |",
        f"| True peak | {before.get('input_true_peak', '—')} dBTP | {after.get('input_true_peak', '—')} dBTP |",
        f"| Bruit de fond | {before.get('noise_floor_db', '—')} dB | {after.get('noise_floor_db', '—')} dB |",
        f"| RMS | {before.get('rms_db', '—')} dB | {after.get('rms_db', '—')} dB |",
        "",
        "## Chaîne appliquée",
        "",
        "```",
        result.get("filter_chain", ""),
        "```",
        "",
        "> Le loudnorm en deux passes garantit un niveau constant sans pompage. "
        "Pour un rendu broadcast, cible -23 LUFS ; pour YouTube/Reels, -14 à -16 LUFS.",
        "",
    ]
    return "\n".join(lines)
