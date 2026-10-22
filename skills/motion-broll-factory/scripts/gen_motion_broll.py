#!/usr/bin/env python3
"""B-roll animés 1080x1920 en MP4 (PIL + ffmpeg) : money, marquee, orbit, particles."""
import argparse
import math
import os
import random
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    if "--help" in sys.argv:
        print(__doc__ or "usage: gen_motion_broll.py {money,marquee,orbit,particles}")
        sys.exit(0)
    print("Pillow requis : pip install pillow", file=sys.stderr)
    sys.exit(3)

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size):
    if Path(FONT).is_file():
        return ImageFont.truetype(FONT, size)
    return ImageFont.load_default()


def hex_rgb(s):
    s = (s or "2E6BFF").lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def render(frames_iter, dur, out):
    n = int(dur * FPS)
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i, img in enumerate(frames_iter(n)):
        p.stdin.write(img.tobytes())
    p.stdin.close()
    rc = p.wait()
    if rc:
        sys.exit(f"ffmpeg rc={rc}")
    print(f"écrit : {out} ({dur}s @ {FPS}fps)")


def frames_money(n, accent, bg):
    rnd = random.Random(7)
    bills = [dict(x=rnd.randint(-80, W - 120), y=rnd.randint(-H, -60),
                  v=rnd.uniform(700, 1100), r=rnd.uniform(-18, 18),
                  ph=rnd.uniform(0, 6.28)) for _ in range(14)]
    accent = hex_rgb(accent) if accent else (46, 200, 90)
    bg = hex_rgb(bg) if bg else (13, 78, 70)
    for k in range(n):
        t = k / FPS
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        for b in bills:
            y = b["y"] + b["v"] * t
            y = ((y + 260) % (H + 520)) - 260
            x = b["x"] + 40 * math.sin(2 * t + b["ph"])
            bill = Image.new("RGBA", (210, 105), accent + (255,))
            bd = ImageDraw.Draw(bill)
            bd.rectangle((8, 8, 201, 96), outline=(255, 255, 255, 255), width=4)
            bd.text((84, 26), "$", font=font(48), fill=(255, 255, 255, 255))
            bill = bill.rotate(b["r"] + 8 * math.sin(t * 2 + b["ph"]),
                               expand=True, resample=Image.BILINEAR)
            img.paste(bill, (int(x), int(y)), bill)
        yield img


def frames_marquee(n, text, accent, bg):
    accent = hex_rgb(accent) if accent else (255, 107, 0)
    bg = hex_rgb(bg) if bg else (16, 16, 22)
    fnt = font(420)
    letters = [c for c in text.upper() if c.isalnum()] or ["V", "I", "R", "A", "L"]
    col_w = 520
    x = (W - col_w) // 2
    total = len(letters) * 460
    for k in range(n):
        t = k / FPS
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        off = (t * 380) % total
        for i, ch in enumerate(letters):
            y = -200 + i * 460 + off
            for wrap_y in (y - total, y, y + total):
                if -500 < wrap_y < H + 100:
                    d.text((x + 30, wrap_y), ch, font=fnt, fill=accent)
        yield img


def frames_orbit(n, accent, bg):
    accent = hex_rgb(accent) if accent else (46, 107, 255)
    bg = hex_rgb(bg) if bg else (8, 12, 34)
    cx, cy, R = W // 2, H // 2, 330
    icons = ["1", "2", "3", "4"]
    fnt_big, fnt_ic = font(220), font(96)
    for k in range(n):
        t = k / FPS
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        # anneau pointillé qui tourne
        for a in range(0, 360, 9):
            ang = math.radians(a + t * 12)
            x1 = cx + (R - 14) * math.cos(ang)
            y1 = cy + (R - 14) * math.sin(ang)
            x2 = cx + (R + 14) * math.cos(ang)
            y2 = cy + (R + 14) * math.sin(ang)
            d.line((x1, y1, x2, y2), fill=accent, width=6)
        d.ellipse((cx - 150, cy - 150, cx + 150, cy + 150), fill=accent)
        d.text((cx - 60, cy - 90), "$", font=fnt_big, fill=(255, 255, 255))
        # icônes qui apparaissent progressivement
        for i, lab in enumerate(icons):
            start = i * 0.7
            if t >= start:
                ang = math.radians(-90 + i * 90 + t * 12)
                ix = cx + R * math.cos(ang)
                iy = cy + R * math.sin(ang)
                pop = min(1.0, (t - start) / 0.3)
                r = int(70 * (0.6 + 0.4 * pop))
                d.ellipse((ix - r, iy - r, ix + r, iy + r),
                          fill=(250, 250, 255))
                d.text((ix - 24, iy - 44), lab, font=fnt_ic, fill=accent)
        yield img


def frames_particles(n, accent, bg):
    rnd = random.Random(11)
    accent = hex_rgb(accent) if accent else (64, 224, 208)
    bg = hex_rgb(bg) if bg else (8, 8, 14)
    pts = [dict(x=rnd.uniform(0, W), y=rnd.uniform(0, H),
                vx=rnd.uniform(-26, 26), vy=rnd.uniform(-40, -8),
                r=rnd.randint(2, 5), ph=rnd.uniform(0, 6.28)) for _ in range(90)]
    for k in range(n):
        t = k / FPS
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        for p in pts:
            x = (p["x"] + p["vx"] * t) % W
            y = (p["y"] + p["vy"] * t) % H
            tw = 0.55 + 0.45 * math.sin(3 * t + p["ph"])
            col = tuple(int(c * tw) for c in accent)
            d.ellipse((x - p["r"], y - p["r"], x + p["r"], y + p["r"]), fill=col)
        yield img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["money", "marquee", "orbit", "particles"])
    ap.add_argument("--text", default="CANADA")
    ap.add_argument("--accent")
    ap.add_argument("--bg")
    ap.add_argument("--dur", type=float, default=4.0)
    ap.add_argument("-o", default="broll.mp4")
    a = ap.parse_args()
    gens = {
        "money": lambda n: frames_money(n, a.accent, a.bg),
        "marquee": lambda n: frames_marquee(n, a.text, a.accent, a.bg),
        "orbit": lambda n: frames_orbit(n, a.accent, a.bg),
        "particles": lambda n: frames_particles(n, a.accent, a.bg),
    }
    render(gens[a.mode], a.dur, a.o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
