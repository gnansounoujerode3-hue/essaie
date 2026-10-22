#!/usr/bin/env python3
"""Bar chart race animé 1080x1920 en MP4 — fallback PIL/FFmpeg sans Remotion/Chromium.

Données : JSON [{"label": "Crédit", "from": 10, "to": 42}, ...] ou --demo.
Classement re-ordonné chaque frame, interpolation ease-in-out, barres horizontales.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)
    print("Pillow requis : pip install pillow", file=sys.stderr)
    sys.exit(3)

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEMO = [
    {"label": "Hypothèque", "from": 38, "to": 74},
    {"label": "Carte crédit", "from": 24, "to": 61},
    {"label": "LOC", "from": 18, "to": 39},
    {"label": "Prêt auto", "from": 12, "to": 27},
    {"label": "Découvert", "from": 6, "to": 15},
]


def font(sz):
    return ImageFont.truetype(FONT, sz) if Path(FONT).is_file() else ImageFont.load_default()


def ease(p):
    return p * p * (3 - 2 * p)


def hex_rgb(s):
    s = (s or "FF3B30").lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def frame_at(rows, t, dur, accent, bg):
    p = ease(min(max(t / dur, 0.0), 1.0))
    vals = [(r["label"], r["from"] + (r["to"] - r["from"]) * p) for r in rows]
    vals.sort(key=lambda x: -x[1])
    vmax = max(v for _, v in vals) or 1
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    title_f, lab_f, val_f = font(86), font(56), font(52)
    d.text((72, 110), "EN HAUSSE", font=title_f, fill=accent)
    top, bar_h, gap = 340, 150, 64
    for i, (label, v) in enumerate(vals):
        y = top + i * (bar_h + gap)
        bw = int((W - 420) * (v / vmax))
        d.rounded_rectangle((72, y, 72 + max(bw, 40), y + bar_h), 28, fill=accent)
        d.text((110, y + bar_h // 2 - 34), label, font=lab_f, fill=(255, 255, 255))
        d.text((W - 300, y + bar_h // 2 - 32), f"{v:.0f}", font=val_f,
               fill=(250, 250, 252))
    # progression
    d.rounded_rectangle((72, H - 190, 72 + int((W - 144) * min(t / dur, 1)),
                         H - 160), 15, fill=accent)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", help="JSON [{label,from,to}]")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--dur", type=float, default=4.0)
    ap.add_argument("--accent", default="FF3B30")
    ap.add_argument("--bg", default="0B0B10")
    ap.add_argument("-o", default="race.mp4")
    a = ap.parse_args()
    if a.demo or not a.data:
        rows = DEMO
    else:
        rows = json.loads(Path(a.data).read_text(encoding="utf-8"))
    accent, bg = hex_rgb(a.accent), hex_rgb(a.bg)

    import imageio_ffmpeg
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel",
           "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", a.o]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(a.dur * FPS)
    for k in range(n):
        proc.stdin.write(frame_at(rows, k / FPS, a.dur, accent, bg).tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit("ffmpeg échec")
    print(f"écrit : {a.o} ({a.dur}s, {len(rows)} séries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
