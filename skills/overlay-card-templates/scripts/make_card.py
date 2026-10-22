#!/usr/bin/env python3
"""Cartes PNG 1080x1920 pour overlay : scene texte, stat, chat DM, pill, phone."""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    if "--help" in sys.argv:
        print(__doc__ or "usage: make_card.py {scene,stat,chat,pill,phone} --help")
        sys.exit(0)
    print("Pillow requis : pip install pillow", file=sys.stderr)
    sys.exit(3)

W, H = 1080, 1920
FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_DIRS:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def hex_rgb(s: str) -> tuple:
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def wrap(draw, text: str, fnt, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def centered_text(img, text: str, fnt, color, y_ratio=0.5, accent=None):
    """Motifs **ACCENT** dans le texte = segment coloré en `accent` (hex)."""
    accent_color = hex_rgb(accent) if accent else color
    d = ImageDraw.Draw(img)
    flat = text.replace("**", "")
    lines = wrap(d, flat, fnt, int(W * 0.82))
    lh = fnt.size * 1.25
    y = int(H * y_ratio - lh * len(lines) / 2)
    for line in lines:
        w = d.textbbox((0, 0), line, font=fnt)[2]
        x = (W - w) // 2
        # segmentuation **…** sur la ligne courante
        parts, in_acc = [], False
        for token in line.split(" "):
            n = token.count("**")
            t = token.replace("**", "")
            if n == 2:
                parts.append((t, True))
                continue
            if n == 1:
                in_acc = not in_acc
            parts.append((t, in_acc))
        for token, is_acc in parts:
            d.text((x, y), token + " ", font=fnt,
                   fill=accent_color if is_acc else color)
            x += d.textbbox((0, 0), token + " ", font=fnt)[2]
        y += int(lh)


def cmd_scene(a):
    bg = {"blanc": (250, 250, 250), "noir": (11, 11, 16)}.get(a.bg) or hex_rgb(a.bg)
    img = Image.new("RGB", (W, H), bg)
    fg = (17, 17, 20) if sum(bg) > 380 else (245, 245, 247)
    centered_text(img, a.text, font(a.size), fg, a.y, a.accent)
    img.save(a.o)


def cmd_stat(a):
    img = Image.new("RGB", (W, H), hex_rgb(a.bg) if a.bg else (11, 11, 16))
    d = ImageDraw.Draw(img)
    acc = hex_rgb(a.accent)
    nfont = font(a.size)
    w = d.textbbox((0, 0), a.number, font=nfont)[2]
    d.text(((W - w) // 2, int(H * 0.40)), a.number, font=nfont, fill=acc)
    lfont = font(64)
    w2 = d.textbbox((0, 0), a.label, font=lfont)[2]
    d.text(((W - w2) // 2, int(H * 0.40) + a.size + 40), a.label,
           font=lfont, fill=(245, 245, 247))
    img.save(a.o)


def cmd_chat(a):
    img = Image.new("RGB", (W, H), (11, 11, 16))
    d = ImageDraw.Draw(img)
    x0, y0, w, h = 90, int(H * 0.34), W - 180, 460
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 36, fill=(28, 28, 34),
                        outline=(60, 60, 70), width=2)
    d.ellipse((x0 + 36, y0 + 36, x0 + 132, y0 + 132), fill=(90, 90, 110))
    d.text((x0 + 156, y0 + 44), a.name, font=font(52), fill=(235, 235, 240))
    if a.badge:
        bfont = font(40)
        bw = d.textbbox((0, 0), a.badge, font=bfont)[2] + 48
        bx, by = x0 + w - bw - 32, y0 + 40
        d.rounded_rectangle((bx, by, bx + bw, by + 70), 35, fill=(46, 92, 255))
        d.text((bx + 24, by + 12), a.badge, font=bfont, fill=(255, 255, 255))
    d.multiline_text((x0 + 48, y0 + 170), a.msg, font=font(48),
                     fill=(210, 210, 218), spacing=14)
    img.save(a.o)


def cmd_pill(a):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fnt = font(a.size)
    tw = d.textbbox((0, 0), a.text, font=fnt)[2]
    pw, ph = tw + 96, fnt.size + 64
    x, y = (W - pw) // 2, (H - ph) // 2
    d.rounded_rectangle((x, y, x + pw, y + ph), ph // 2, fill=hex_rgb(a.accent))
    d.text((x + 48, y + 28), a.text, font=fnt, fill=(255, 255, 255))
    img.save(a.o)


def cmd_phone(a):
    shot = Image.open(a.shot).convert("RGB")
    scale = min((W - 200) / shot.width, (H - 400) / shot.height)
    shot = shot.resize((int(shot.width * scale), int(shot.height * scale)))
    img = Image.new("RGB", (W, H), (11, 11, 16))
    d = ImageDraw.Draw(img)
    bx0 = (W - shot.width) // 2 - 24
    by0 = (H - shot.height) // 2 - 24
    d.rounded_rectangle((bx0, by0, bx0 + shot.width + 48,
                         by0 + shot.height + 48), 48, outline=(230, 230, 235), width=6)
    img.paste(shot, ((W - shot.width) // 2, (H - shot.height) // 2))
    img.save(a.o)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("scene"); g.add_argument("--bg", default="blanc")
    g.add_argument("--text", required=True); g.add_argument("--accent")
    g.add_argument("--size", type=int, default=150); g.add_argument("--y", type=float, default=0.5)
    g.add_argument("-o", default="scene.png")
    s = sub.add_parser("stat"); s.add_argument("--number", required=True)
    s.add_argument("--label", default=""); s.add_argument("--accent", default="FF3B30")
    s.add_argument("--bg"); s.add_argument("--size", type=int, default=300)
    s.add_argument("-o", default="stat.png")
    c = sub.add_parser("chat"); c.add_argument("--name", default="David J.")
    c.add_argument("--msg", required=True); c.add_argument("--badge")
    c.add_argument("-o", default="chat.png")
    p = sub.add_parser("pill"); p.add_argument("--text", required=True)
    p.add_argument("--accent", default="7C3AED"); p.add_argument("--size", type=int, default=88)
    p.add_argument("-o", default="pill.png")
    ph = sub.add_parser("phone"); ph.add_argument("--shot", required=True)
    ph.add_argument("-o", default="phone.png")
    a = ap.parse_args()
    globals()[f"cmd_{a.cmd}"](a)
    print(f"écrit : {a.o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
