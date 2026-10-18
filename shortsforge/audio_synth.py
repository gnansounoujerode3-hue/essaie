"""Synthèse audio : nappe musicale « trending » + bibliothèque de bruitages.

Tout est généré en NumPy (48 kHz stéréo) : kick/snare/hats/basse/pad, ducking
sidechain sur le kick et banque de SFX (whoosh, pop, click, ding, impact,
riser). Les fichiers produits sont encodés en MP3 via FFmpeg.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .ffmpeg import ffmpeg_bin, run

SR = 48000


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def _midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def _env(n: int, attack: float, decay: float, sr: int = SR) -> np.ndarray:
    """Enveloppe ADSR simplifiée (attack linéaire puis decay exponentiel)."""
    t = np.arange(n) / sr
    a = max(int(attack * sr), 1)
    env = np.ones(n)
    if a < n:
        env[:a] = np.linspace(0.0, 1.0, a)
        env[a:] = np.exp(-np.linspace(0.0, 1.0, n - a) * decay * 6.0)
    else:
        env[:] = 1.0
    return env


def _lowpass(x: np.ndarray, cutoff, sr: int = SR) -> np.ndarray:
    """Filtre passe-bas à un pôle, calculé par FFT (rapide et exact).

    ``cutoff`` peut être un scalaire ou un tableau (balayage de fréquence).
    """
    cutoff_arr = np.asarray(cutoff, dtype=np.float64)
    if x.size == 0:
        return np.zeros_like(x)
    if cutoff_arr.size > 1:
        cutoff_arr = np.array([cutoff_arr.mean()])
    if np.all(cutoff_arr <= 0):
        return np.zeros_like(x)
    dt = 1.0 / sr
    rc = 1.0 / (2 * math.pi * np.clip(cutoff_arr, 1.0, sr * 0.49))
    alpha = dt / (rc + dt)
    w = 2.0 * math.pi * np.fft.rfftfreq(len(x), dt)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = alpha / (1.0 - (1.0 - alpha) * np.exp(-1j * w))
    h = np.nan_to_num(h)
    y = np.fft.irfft(np.fft.rfft(x) * h, n=len(x))
    return y


def _highpass(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    return x - _lowpass(x, cutoff, sr)


def _noise(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(n).astype(np.float64)


def _soft_clip(x: np.ndarray) -> np.ndarray:
    return np.tanh(x * 1.4) * 0.85


def _write_wav(path: Path, data: np.ndarray, sr: int = SR) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(data, -1.0, 1.0)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    pcm = (data * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def _to_mp3(wav: Path, mp3: Path, bitrate: str = "192k") -> Path:
    mp3.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", bitrate, str(mp3)])
    return mp3


# --------------------------------------------------------------------------- #
# Nappe musicale
# --------------------------------------------------------------------------- #
PROGRESSIONS: Dict[str, list] = {
    "upbeat_minor": [
        (57, [57, 60, 64]),  # Am
        (53, [53, 57, 60]),  # F
        (48, [48, 52, 55]),  # C
        (55, [55, 59, 62]),  # G
    ],
    "bright_pop": [
        (60, [60, 64, 67]),  # C
        (57, [57, 61, 64]),  # Am
        (55, [55, 59, 62]),  # G
        (53, [53, 57, 60]),  # F
    ],
    "dark_trap": [
        (45, [45, 48, 52]),  # Am low
        (41, [41, 45, 48]),  # F low
        (43, [43, 47, 50]),  # G low
        (40, [40, 44, 47]),  # E low
    ],
    "corporate_hop": [
        (48, [48, 52, 55]),
        (45, [45, 48, 52]),
        (43, [43, 47, 50]),
        (41, [41, 45, 48]),
    ],
}


def _kick(sr: int = SR) -> np.ndarray:
    n = int(0.32 * sr)
    t = np.arange(n) / sr
    freq = 120.0 * np.exp(-t * 26) + 42.0
    phase = 2 * math.pi * np.cumsum(freq) / sr
    body = np.sin(phase) * np.exp(-t * 9.0)
    click = _noise(n, np.random.default_rng(1)) * np.exp(-t * 180.0) * 0.25
    return (body + click) * 0.95


def _snare(sr: int = SR) -> np.ndarray:
    n = int(0.24 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(2)
    noise = _noise(n, rng)
    body = _highpass(noise, 1400.0, sr) * np.exp(-t * 26.0) * 0.55
    tone = np.sin(2 * math.pi * 190.0 * t) * np.exp(-t * 34.0) * 0.35
    return body + tone


def _hat(sr: int = SR, open_hat: bool = False) -> np.ndarray:
    n = int((0.16 if open_hat else 0.055) * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(3)
    x = _highpass(_noise(n, rng), 7200.0, sr)
    return x * np.exp(-t * (18.0 if open_hat else 62.0)) * 0.32


def _clap(sr: int = SR) -> np.ndarray:
    n = int(0.26 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(4)
    x = _highpass(_noise(n, rng), 1200.0, sr)
    env = np.exp(-t * 30.0)
    for off in (0.0, 0.011, 0.022):
        env += np.where(t > off, np.exp(-(t - off) * 34.0), 0.0) * 0.7
    return x * env * 0.5


def _synth_bass(freq: float, dur: float, sr: int = SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = np.linspace(freq * 0.985, freq, n)
    sig = np.sin(2 * math.pi * np.cumsum(f) / sr)
    sig += 0.35 * np.sin(4 * math.pi * np.cumsum(f) / sr)
    sig *= 0.32
    env = np.ones(n)
    a = int(0.005 * sr)
    env[:a] = np.linspace(0, 1, a)
    rel = int(0.05 * sr)
    if rel < n:
        env[-rel:] *= np.linspace(1, 0, rel)
    return sig * env


def _pad(freqs: list, dur: float, sr: int = SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    for f in freqs:
        for detune in (-0.16, 0.0, 0.17):
            ff = f * (1 + detune / 100.0)
            out += np.sin(2 * math.pi * ff * t + detune) * 0.09
    attack = int(0.12 * sr)
    env = np.ones(n)
    env[:attack] = np.linspace(0, 1, attack)
    return out * env * 0.5


def render_music(
    path: str | Path,
    duration: float = 30.0,
    bpm: int = 128,
    style: str = "upbeat_minor",
    seed: int = 7,
    loudness: float = 0.9,
) -> Path:
    """Génère une boucle musicale parfaite pour un Short."""
    rng = np.random.default_rng(seed)
    out_path = Path(path)
    total = int(duration * SR)
    beat = 60.0 / bpm
    bar = beat * 4
    mix = np.zeros(total)
    prog = PROGRESSIONS.get(style, PROGRESSIONS["upbeat_minor"])

    kick = _kick()
    snare = _snare()
    hat = _hat()
    open_hat = _hat(open_hat=True)
    clap = _clap()

    n_bars = int(math.ceil(duration / bar)) + 1
    for b in range(n_bars):
        bar_start = b * bar
        root, chord = prog[b % len(prog)]
        # --- percussions
        for beat_idx in range(4):
            pos = bar_start + beat_idx * beat
            i0 = int(pos * SR)
            if beat_idx in (0, 2):
                n = min(len(kick), total - i0)
                if n > 0:
                    mix[i0 : i0 + n] += kick[:n] * (1.0 if beat_idx == 0 else 0.92)
            if beat_idx in (1, 3) and style != "dark_trap":
                n = min(len(snare), total - i0)
                if n > 0:
                    mix[i0 : i0 + n] += snare[:n] * 0.85
            elif beat_idx == 3:
                n = min(len(clap), total - i0)
                if n > 0:
                    mix[i0 : i0 + n] += clap[:n] * 0.5
            # hats 8ths
            for half in (0, 0.5):
                hp = pos + half * beat
                i0 = int(hp * SR)
                src = open_hat if (half == 0.5 and beat_idx == 3) else hat
                amp = 0.75 if half == 0 else 0.5
                n = min(len(src), total - i0)
                if n > 0:
                    mix[i0 : i0 + n] += src[:n] * amp
        # --- basse
        for beat_idx in (0, 1.5, 2.5):
            pos = bar_start + beat_idx * beat
            i0 = int(pos * SR)
            dur = beat * 0.8
            seg = _synth_bass(_midi_to_hz(root - 12), dur)
            n = min(len(seg), total - i0)
            if n > 0:
                mix[i0 : i0 + n] += seg[:n] * 0.85
        # --- pad
        i0 = int(bar_start * SR)
        seg = _pad([_midi_to_hz(c) for c in chord], bar)
        n = min(len(seg), total - i0)
        if n > 0:
            mix[i0 : i0 + n] += seg[:n] * 0.5
        # --- riser avant la reprise de la boucle
        if b % 4 == 3 and style != "dark_trap":
            rp = bar_start + bar * 0.5
            i0 = int(rp * SR)
            dur = bar * 0.5
            n = int(dur * SR)
            t = np.arange(n) / SR
            x = _noise(n, rng)
            x *= (0.55 + 0.45 * np.sin(2 * math.pi * 32.0 * t))
            x = _highpass(x, 1200.0, SR)
            x *= (t / max(dur, 1e-6)) ** 2 * 0.30
            m = min(n, total - i0)
            if m > 0:
                mix[i0 : i0 + m] += x[:m]

    # Ducking sidechain simple sur les graves au rythme du kick
    env = np.ones(total)
    for b in range(n_bars):
        for beat_idx in (0, 2):
            i0 = int((b * bar + beat_idx * beat) * SR)
            length = int(0.22 * SR)
            seg = np.linspace(1.0, 0.72, length)
            end = min(i0 + length, total)
            env[i0:end] = np.minimum(env[i0:end], seg[: end - i0])
    low = _lowpass(mix, 180.0)
    mix = mix - low * 0.35 + low * 0.35 * env

    mix = _soft_clip(mix * loudness)

    # Léger « widening » stéréo + room
    left = mix
    right = np.roll(mix, int(0.006 * SR)) * 0.94
    stereo = np.stack([left, right], axis=1)
    stereo = np.clip(stereo, -0.98, 0.98)

    wav = _write_wav(out_path.with_suffix(".wav"), stereo)
    mp3 = _to_mp3(wav, out_path.with_suffix(".mp3"), "192k")
    wav.unlink(missing_ok=True)
    return mp3


# --------------------------------------------------------------------------- #
# Bruitages
# --------------------------------------------------------------------------- #
def _sfx_whoosh(sr: int = SR) -> np.ndarray:
    n = int(0.45 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(11)
    x = _noise(n, rng)
    sweep = _highpass(x, 400.0 + 5000.0 * (t / (n / sr)) ** 2, sr)
    env = np.sin(np.pi * (t / (n / sr))) ** 1.6
    return sweep * env * 0.6


def _sfx_pop(sr: int = SR) -> np.ndarray:
    n = int(0.12 * sr)
    t = np.arange(n) / sr
    f = 900.0 * np.exp(-t * 16) + 180.0
    sig = np.sin(2 * math.pi * np.cumsum(f) / sr)
    return sig * np.exp(-t * 26.0) * 0.75


def _sfx_click(sr: int = SR) -> np.ndarray:
    n = int(0.035 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(12)
    x = _highpass(_noise(n, rng), 2500.0, sr)
    return x * np.exp(-t * 190.0) * 0.55


def _sfx_ding(sr: int = SR) -> np.ndarray:
    n = int(0.7 * sr)
    t = np.arange(n) / sr
    sig = np.sin(2 * math.pi * 1180.0 * t) * np.exp(-t * 6.0)
    sig += 0.5 * np.sin(2 * math.pi * 1790.0 * t) * np.exp(-t * 9.0)
    sig += 0.25 * np.sin(2 * math.pi * 2640.0 * t) * np.exp(-t * 13.0)
    return sig * 0.45


def _sfx_impact(sr: int = SR) -> np.ndarray:
    n = int(0.6 * sr)
    t = np.arange(n) / sr
    f = 90.0 * np.exp(-t * 7) + 38.0
    body = np.sin(2 * math.pi * np.cumsum(f) / sr) * np.exp(-t * 7.0)
    rng = np.random.default_rng(13)
    air = _lowpass(_noise(n, rng), 2500.0, sr) * np.exp(-t * 18.0) * 0.35
    return (body * 0.8 + air) * 0.8


def _sfx_riser(sr: int = SR) -> np.ndarray:
    n = int(1.4 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(14)
    x = _highpass(_noise(n, rng), 600.0 + 6000.0 * (t / (n / sr)), sr)
    f = 220.0 * (1 + 5 * (t / (n / sr)) ** 2)
    tone = np.sin(2 * math.pi * np.cumsum(f) / sr) * 0.25
    env = (t / (n / sr)) ** 2.2
    return (x * 0.5 + tone) * env * 0.6


def _sfx_swoosh_up(sr: int = SR) -> np.ndarray:
    n = int(0.35 * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(15)
    x = _highpass(_noise(n, rng), 500.0 + 8000.0 * (t / (n / sr)) ** 1.5, sr)
    env = np.sin(np.pi * (t / (n / sr))) ** 1.2
    return x * env * 0.55


def _sfx_zoom(sr: int = SR) -> np.ndarray:
    n = int(0.3 * sr)
    t = np.arange(n) / sr
    f = 300.0 + 2400.0 * (t / (n / sr)) ** 2
    sig = np.sin(2 * math.pi * np.cumsum(f) / sr)
    env = np.exp(-t * 5.0)
    return sig * env * 0.4


SFX_BUILDERS = {
    "whoosh": _sfx_whoosh,
    "pop": _sfx_pop,
    "click": _sfx_click,
    "ding": _sfx_ding,
    "impact": _sfx_impact,
    "riser": _sfx_riser,
    "swoosh": _sfx_swoosh_up,
    "zoom": _sfx_zoom,
}


def render_sfx(path: str | Path, kind: str = "whoosh", gain: float = 1.0) -> Path:
    """Génère un bruitage isolé dans un fichier MP3."""
    builder = SFX_BUILDERS.get(kind)
    if builder is None:
        raise KeyError(f"Bruitage inconnu: {kind}. Disponibles: {sorted(SFX_BUILDERS)}")
    data = builder()
    data = data * gain
    out = Path(path)
    wav = _write_wav(out.with_suffix(".wav"), data)
    mp3 = _to_mp3(wav, out.with_suffix(".mp3"), "192k")
    wav.unlink(missing_ok=True)
    return mp3


def render_sfx_library(directory: str | Path, gain: float = 1.0) -> Dict[str, Path]:
    """Génère toute la bibliothèque de bruitages."""
    directory = Path(directory)
    out: Dict[str, Path] = {}
    for kind in SFX_BUILDERS:
        out[kind] = render_sfx(directory / f"{kind}.mp3", kind, gain)
    return out
