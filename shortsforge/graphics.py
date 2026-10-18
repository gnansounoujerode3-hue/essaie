"""Production des couches graphiques (PIL) : titres, autocollants, emoji, fonds.

Tout ce qui est du texte ou un autocollant est rendu une fois en PNG avec
alpha par Pillow, puis composé par ffmpeg (rapide, net, animable).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fonts

Color = Tuple[int, int, int, int]


# --------------------------------------------------------------------------- #
# Couleurs
# --------------------------------------------------------------------------- #
def hex_to_rgba(value: str, alpha: int = 255) -> Color:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) == 6:
        v += "ff"
    if len(v) != 8:
        raise ValueError(f"Couleur invalide: {value!r}")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), int(v[6:8], 16))


def rgba_to_hex(color: Color, with_alpha: bool = True) -> str:
    r, g, b, a = color
    base = f"#{r:02X}{g:02X}{b:02X}"
    return base + f"{a:02X}" if with_alpha else base


def mix(c1: str, c2: str, t: float = 0.5) -> str:
    a, b = hex_to_rgba(c1), hex_to_rgba(c2)
    return rgba_to_hex(
        (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
            255,
        ),
        with_alpha=False,
    )


# --------------------------------------------------------------------------- #
# Utilitaires texte
# --------------------------------------------------------------------------- #
def _emoji_font(size: int) -> ImageFont.FreeTypeFont:
    path = fonts.FONT_DIR / "NotoColorEmoji.ttf"
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return fonts.pil_font("inter-800", size)


def _draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Color,
    stroke_width: int = 0,
    stroke_fill: Color = (0, 0, 0, 255),
    anchor: Optional[str] = None,
) -> None:
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill, anchor=anchor)


def _split_highlights(text: str, highlights: Sequence[str]) -> List[Tuple[str, bool]]:
    """Découpe un texte en segments (mot, est_surligné)."""
    if not highlights:
        return [(text, False)]
    pattern = "(" + "|".join(re.escape(h) for h in sorted(highlights, key=len, reverse=True)) + ")"
    parts = re.split(pattern, text)
    out: List[Tuple[str, bool]] = []
    for part in parts:
        if part:
            out.append((part, part in highlights))
    return out


@dataclass
class TextLayer:
    """Couche texte prête à être composée."""

    image: Image.Image
    path: Optional[Path] = None
    width: int = 0
    height: int = 0

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(path)
        self.path = path
        self.width, self.height = self.image.size
        return path


def render_text_layer(
    text: str,
    *,
    font: str = "anton",
    size: int = 96,
    color: str = "#FFFFFF",
    accent: Optional[str] = None,
    highlights: Sequence[str] = (),
    max_width: int = 940,
    stroke: int = 0,
    stroke_color: str = "#000000",
    shadow: int = 0,
    shadow_color: str = "#000000",
    background: Optional[str] = None,
    background_opacity: float = 0.0,
    uppercase: bool = True,
    line_spacing: float = 1.12,
    align: str = "center",
    padding: int = 24,
    gradient: Optional[Tuple[str, str]] = None,
    letter_spacing: float = 0.0,
) -> TextLayer:
    """Rend un titre/accroche en PNG transparent."""
    if uppercase:
        text = text.upper()
    pil_font = fonts.pil_font(font, size)
    # On réserve la marge (contour + ombre) dans la largeur maximale.
    usable = max(120, max_width - 2 * (padding + stroke + shadow))
    lines = fonts.wrap_text(text, pil_font, usable) if text else []

    line_h = int(size * line_spacing)
    ascent, descent = pil_font.getmetrics()
    text_w = max((int(fonts.text_width(l, pil_font)) for l in lines), default=0)
    pad = padding + stroke + shadow
    # Hauteur nécessaire : ascent + descendante réelles, lignes empilées.
    content_h = max(0, len(lines) - 1) * line_h + ascent + descent
    width = text_w + pad * 2
    height = content_h + pad * 2

    def baseline(i: int) -> float:
        return float(pad + i * line_h + ascent)

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # --- fond (boîte)
    if background and background_opacity > 0:
        bg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        d = ImageDraw.Draw(bg)
        box = hex_to_rgba(background, int(255 * background_opacity))
        radius = int(size * 0.28)
        d.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=box)
        layer.alpha_composite(bg)

    # --- ombre portée
    if shadow > 0:
        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ds = ImageDraw.Draw(shadow_layer)
        for i, line in enumerate(lines):
            _draw_text_with_stroke(
                ds,
                (pad + shadow * 0.4, baseline(i) + shadow * 0.6),
                line,
                pil_font,
                hex_to_rgba(shadow_color, 190),
                stroke_width=stroke,
                stroke_fill=(0, 0, 0, 0),
                anchor="ls",
            )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(max(1, shadow * 0.7)))
        layer.alpha_composite(shadow_layer)

    # --- texte (couleur unie ou dégradé, avec mots surlignés)
    text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dt = ImageDraw.Draw(text_layer)
    for i, line in enumerate(lines):
        y = baseline(i)
        segments = _split_highlights(line, [h.upper() for h in highlights])
        if len(segments) == 1:
            _draw_text_with_stroke(
                dt,
                (pad, y),
                line,
                pil_font,
                hex_to_rgba(color),
                stroke_width=stroke,
                stroke_fill=hex_to_rgba(stroke_color),
                anchor="ls",
            )
            continue
        # segments colorés : on mesure et on place au pixel près
        x = float(pad)
        for seg, is_hi in segments:
            w = fonts.text_width(seg, pil_font)
            fill = hex_to_rgba(accent or color) if is_hi else hex_to_rgba(color)
            _draw_text_with_stroke(
                dt,
                (x, y),
                seg,
                pil_font,
                fill,
                stroke_width=stroke,
                stroke_fill=hex_to_rgba(stroke_color),
                anchor="ls",
            )
            x += w + letter_spacing
    layer.alpha_composite(text_layer)

    # --- dégradé appliqué sur le masque du texte
    if gradient:
        grad = Image.new("RGBA", (width, height))
        dg = ImageDraw.Draw(grad)
        c1 = hex_to_rgba(gradient[0])
        c2 = hex_to_rgba(gradient[1])
        for y in range(height):
            t = y / max(height - 1, 1)
            dg.line([(0, y), (width, y)], fill=mix(rgba_to_hex(c1, False), rgba_to_hex(c2, False), t))
        mask = Image.new("L", (width, height), 0)
        dm = ImageDraw.Draw(mask)
        for i, line in enumerate(lines):
            _draw_text_with_stroke(dm, (pad, baseline(i)), line, pil_font, 255, stroke_width=stroke, stroke_fill=255, anchor="ls")
        grad.putalpha(mask)
        layer.alpha_composite(grad)

    return TextLayer(layer)


def render_sticker(
    text: str,
    *,
    font: str = "inter-900",
    size: int = 64,
    fg: str = "#0B0B0F",
    bg: str = "#FFD400",
    border: Optional[str] = "#000000",
    border_width: int = 6,
    padding: int = 28,
    max_width: int = 900,
    radius: int = 26,
    rotate: float = 0.0,
    uppercase: bool = True,
    shadow: bool = True,
) -> TextLayer:
    """Autocollant texte (badge) — style « stamp » marketing."""
    if uppercase:
        text = text.upper()
    pil_font = fonts.pil_font(font, size)
    content_width = max(80, max_width - 2 * padding - 2 * border_width)
    lines = fonts.wrap_text(text, pil_font, content_width)
    line_h = int(size * 1.1)
    ascent, descent = pil_font.getmetrics()
    text_w = max(int(fonts.text_width(l, pil_font)) for l in lines)
    content_h = max(0, len(lines) - 1) * line_h + ascent + descent
    width = text_w + padding * 2 + border_width * 2
    height = content_h + padding * 2 + border_width * 2

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = [border_width, border_width, width - 1 - border_width, height - 1 - border_width]
    if shadow:
        sh = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dsh = ImageDraw.Draw(sh)
        dsh.rounded_rectangle([box[0] + 6, box[1] + 8, box[2] + 6, box[3] + 8], radius=radius, fill=(0, 0, 0, 150))
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))

    d.rounded_rectangle(box, radius=radius, fill=hex_to_rgba(bg))
    if border and border_width > 0:
        d.rounded_rectangle(box, radius=radius, outline=hex_to_rgba(border), width=border_width)

    for i, line in enumerate(lines):
        x = width / 2
        y = padding + border_width + i * line_h + ascent
        d.text((x, y), line, font=pil_font, fill=hex_to_rgba(fg), anchor="ms")

    if rotate:
        layer = layer.rotate(rotate, resample=Image.BICUBIC, expand=True)
    return TextLayer(layer)


def render_emoji(char: str, size: int = 160) -> TextLayer:
    """Rend un emoji en PNG (couleur via Noto Color Emoji)."""
    f = _emoji_font(109)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        d.text((size / 2, size / 2), char, font=f, embedded_color=True, anchor="mm")
    except Exception:
        d.text((size / 2, size / 2), char, font=f, anchor="mm")
    return TextLayer(img)


def render_icon(text: str, *, size: int = 160, color: str = "#FFFFFF", stroke_color: str = "#000000", stroke: int = 0) -> TextLayer:
    """Glyphe simple (flèche, symbole) rendu en PNG transparent."""
    pil_font = fonts.pil_font("inter-900", int(size * 0.8))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text(
        (size / 2, size / 2),
        text,
        font=pil_font,
        fill=hex_to_rgba(color),
        anchor="mm",
        stroke_width=stroke,
        stroke_fill=hex_to_rgba(stroke_color),
    )
    return TextLayer(img)


def gradient_background(width: int, height: int, colors: Sequence[str], angle: float = 135.0) -> Image.Image:
    """Fond dégradé (ou aplat si une seule couleur)."""
    import numpy as np

    if len(colors) == 1:
        return Image.new("RGBA", (width, height), hex_to_rgba(colors[0]))

    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    xs = np.arange(width, dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    proj = (np.add.outer(ys, 0) * dy)[..., None] + (xs * dx)[None, ...]
    proj = proj - proj.min()
    if proj.max() > 0:
        proj = proj / proj.max()
    # On interpole entre les couleurs successives.
    stops = np.array([hex_to_rgba(c, False)[:3] for c in colors], dtype=np.float32)
    seg = len(stops) - 1
    t = proj * seg
    idx = np.clip(np.floor(t).astype(np.int32), 0, seg - 1)
    frac = (t - idx)[..., None]
    arr = stops[idx] * (1 - frac) + stops[idx + 1] * frac
    out = np.concatenate([arr, np.full(arr.shape[:2] + (1,), 255.0, dtype=np.float32)], axis=2)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def noise_texture(width: int, height: int, opacity: int = 18, seed: int = 3) -> Image.Image:
    """Grain léger (évite l'aspect « plastique » des aplats)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, size=(height // 4, width // 4, 3), dtype=np.uint8)
    small = Image.fromarray(arr, "RGB").resize((width, height), Image.BILINEAR)
    noise = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    noise.putalpha(small.convert("L").point(lambda v: int(abs(v - 128) / 128 * opacity)))
    return noise


def rounded_image(source: str | Path, width: int, height: Optional[int] = None, radius: int = 28, border: int = 0, border_color: str = "#FFFFFF") -> Image.Image:
    """Recadre une image au format demandé avec coins arrondis (B-roll)."""
    with Image.open(source) as im:
        im = im.convert("RGB")
        target_h = height or int(width * im.height / max(im.width, 1))
        scale = max(width / im.width, target_h / im.height)
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
        left = (im.width - width) // 2
        top = (im.height - target_h) // 2
        im = im.crop((left, top, left + width, top + target_h)).convert("RGBA")
    if radius > 0:
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
        im.putalpha(mask)
    if border > 0:
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle(
            [border // 2, border // 2, im.width - 1 - border // 2, im.height - 1 - border // 2],
            radius=radius,
            outline=hex_to_rgba(border_color),
            width=border,
        )
    return im


def vignette(size: Tuple[int, int], strength: int = 70) -> Image.Image:
    """Vignettage radial (donne du relief aux photos)."""
    w, h = size
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    d.ellipse([-w * 0.25, -h * 0.1, w * 1.25, h * 1.1], fill=255)
    img = img.filter(ImageFilter.GaussianBlur(w * 0.12))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.putalpha(img.point(lambda v: int((255 - v) * strength / 255)))
    return out
