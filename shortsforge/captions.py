"""Sous-titres dynamiques (style « mot par mot » à la TikTok).

Le layout est calculé en Python (métriques Pillow) puis écrit en ASS avec des
positions absolues : chaque mot est positionné au pixel près, ce qui permet de
changer sa couleur au mot actif sans provoquer de reflow de la ligne.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import ImageFont

from . import fonts
from .graphics import hex_to_rgba
from .spec import CaptionLine, CaptionWord, ShortSpec


# --------------------------------------------------------------------------- #
# Outils ASS
# --------------------------------------------------------------------------- #
def ass_color(hex_value: str, alpha: float = 1.0) -> str:
    """#RRGGBB + opacité (0..1) -> &HAABBGGRR (ASS : alpha inversé)."""
    r, g, b, a = hex_to_rgba(hex_value)
    inv = int(round((1.0 - max(0.0, min(1.0, alpha))) * 255))
    return f"&H{inv:02X}{b:02X}{g:02X}{r:02X}"


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


# --------------------------------------------------------------------------- #
# Découpage & layout
# --------------------------------------------------------------------------- #
def plan_words(text: str, start: float, duration: float) -> List[CaptionWord]:
    """Répartit les mots sur la durée en tenant compte de la longueur.

    Les ponctuations (« , » « . » « ? ») ajoutent une micro-pause.
    """
    tokens = [t for t in re.split(r"(\s+)", text) if t.strip()]
    if not tokens:
        return []
    weights: List[float] = []
    for token in tokens:
        word = token.strip()
        base = max(len(word), 1)
        pause = 0.0
        if word.endswith((",", ";", ":")):
            pause = 0.35
        elif word.endswith((".", "!", "?")):
            pause = 0.6
        weights.append(base + pause * 6)
    total = sum(weights)
    out: List[CaptionWord] = []
    cursor = start
    for token, w in zip(tokens, weights):
        span = (w / total) * duration
        end = cursor + span
        out.append(CaptionWord(word=token.strip(), start=cursor, end=end))
        cursor = end
    if out:
        out[-1].end = start + duration
    return out


def layout_words(words: Sequence[str], font: ImageFont.FreeTypeFont, max_width: float) -> List[List[str]]:
    """Découpe une liste de mots en lignes (retour à la ligne mot par mot)."""
    lines: List[List[str]] = []
    current: List[str] = []
    width = 0.0
    space = float(font.getlength(" "))
    for word in words:
        ww = fonts.text_width(word, font)
        add = ww if not current else space + ww
        if current and width + add > max_width:
            lines.append(current)
            current = [word]
            width = ww
        else:
            current.append(word)
            width += add
    if current:
        lines.append(current)
    return lines


@dataclass
class CaptionBox:
    """Boîte de placement d'une ligne de sous-titre (pour la QA)."""

    top: float
    bottom: float
    left: float
    right: float
    words: List[Tuple[str, float, float]]


def build_ass(
    spec: ShortSpec,
    *,
    default_font: Optional[str] = None,
    default_size: int = 74,
    default_color: str = "#FFFFFF",
    highlight_color: str = "#FFD400",
    bg_color: str = "#000000",
) -> Tuple[str, List[CaptionBox]]:
    """Construit le fichier ASS + les boîtes de placement (contrôle zone de sécurité)."""
    font_name = default_font or spec.brand.font_caption
    base_color = default_color
    hi_color = highlight_color

    styles: Dict[str, Dict] = {}
    events: List[str] = []
    boxes: List[CaptionBox] = []

    for idx, cap in enumerate(spec.captions):
        text = cap.text
        if cap.uppercase:
            text = text.upper()
        if not text.strip():
            continue
        cap_font = cap.size or default_size
        pil_font = fonts.pil_font(font_name, cap_font)
        ascent, descent = pil_font.getmetrics()

        words = cap.words or plan_words(text, cap.start, cap.duration)
        if not words:
            continue
        tokens = [w.word for w in words]
        max_w = cap.max_width or int(spec.width * 0.84)
        lines = layout_words(tokens, pil_font, max_w)
        # On repartit les mots dans l'ordre sur les lignes
        flat = [w for w in words]
        line_words: List[List[CaptionWord]] = []
        i = 0
        for line in lines:
            chunk = flat[i : i + len(line)]
            line_words.append(chunk)
            i += len(line)
        while len(line_words) < len(lines):
            line_words.append([])

        line_h = int(cap_font * 1.18)
        block_h = line_h * len(lines)
        y_frac = cap.y if cap.y is not None else 0.68
        block_top = y_frac * spec.height - block_h / 2
        # On garde le bloc dans la zone sûre
        safe = spec.safe_zone
        block_top = max(block_top, safe.top + line_h * 0.2)
        block_top = min(block_top, spec.height - safe.bottom - block_h - line_h * 0.2)

        style_name = f"C{idx}"
        styles[style_name] = {
            "font": font_name,
            "size": cap_font,
            "color": cap.color or base_color,
            "highlight": cap.highlight_color or hi_color,
            "style": cap.style,
            "bg": bg_color,
        }

        space = float(pil_font.getlength(" "))
        for li, chunk in enumerate(line_words):
            if not chunk:
                continue
            baseline = block_top + li * line_h + ascent
            # largeur de la ligne et position x de chaque mot
            widths = [fonts.text_width(w.word, pil_font) for w in chunk]
            line_w = sum(widths) + space * (len(chunk) - 1)
            x = (spec.width - line_w) / 2.0
            centers: List[float] = []
            for w_width in widths:
                centers.append(x + w_width / 2.0)
                x += w_width + space
            boxes.append(
                CaptionBox(
                    top=baseline - ascent,
                    bottom=baseline + descent,
                    left=(spec.width - line_w) / 2.0,
                    right=(spec.width + line_w) / 2.0,
                    words=[(c.word, c.start, c.end) for c in chunk],
                )
            )

            # Un event par mot actif : on affiche toute la phrase, le mot actif en couleur
            if cap.highlight == "word" and len(chunk) > 1:
                for wi, active in enumerate(chunk):
                    start_t = active.start
                    end_t = chunk[wi + 1].start if wi + 1 < len(chunk) else cap.start + cap.duration
                    end_t = max(end_t, start_t + 0.06)
                    parts = []
                    for cj, c in enumerate(chunk):
                        col = styles[style_name]["highlight"] if cj == wi else styles[style_name]["color"]
                        parts.append(
                            f"{{\\pos({centers[cj]:.1f},{baseline:.1f})\\an2\\c{ass_color(col)}\\1c{ass_color(col)}"
                            + (f"\\fscx{105}\\fscy{105}" if cj == wi else "")
                            + "}"
                            + ass_escape(c.word)
                        )
                    events.append(
                        f"Dialogue: 0,{ass_time(start_t)},{ass_time(end_t)},{style_name},,0,0,0,,"
                        + " ".join(parts)
                    )
            else:
                start_t = cap.start
                end_t = cap.start + cap.duration
                parts = []
                for cj, c in enumerate(chunk):
                    col = styles[style_name]["color"]
                    parts.append(
                        f"{{\\pos({centers[cj]:.1f},{baseline:.1f})\\an2\\c{ass_color(col)}\\1c{ass_color(col)}}}"
                        + ass_escape(c.word)
                    )
                events.append(
                    f"Dialogue: 0,{ass_time(start_t)},{ass_time(end_t)},{style_name},,0,0,0,,"
                    + " ".join(parts)
                )

    header = [
        "[Script Info]",
        "; Généré par ShortsForge",
        "ScriptType: v4.00+",
        f"PlayResX: {spec.width}",
        f"PlayResY: {spec.height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for name, s in styles.items():
        size = s["size"]
        style_kind = s["style"]
        if style_kind == "box":
            border_style, outline, shadow = 3, int(size * 0.28), 0
            back = ass_color(s["bg"], 0.55)
        elif style_kind == "outline":
            border_style, outline, shadow = 1, int(size * 0.14), 0
            back = ass_color(s["bg"], 1.0)
        else:  # bold / karaoke
            border_style, outline, shadow = 1, max(3, int(size * 0.09)), int(size * 0.05)
            back = ass_color(s["bg"], 0.85)
        font_family = fonts.resolve(s["font"]).family
        header.append(
            "Style: {name},{font},{size},{primary},{secondary},{outline_col},{back},-1,0,0,0,100,100,0,0,"
            "{bs},{ol},{sh},5,60,60,60,1".format(
                name=name,
                font=font_family,
                size=size,
                primary=ass_color(s["color"]),
                secondary=ass_color(s["highlight"]),
                outline_col=ass_color(s["bg"], 1.0),
                back=back,
                bs=border_style,
                ol=outline,
                sh=shadow,
            )
        )

    body = [
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *events,
        "",
    ]
    return "\n".join(header + body), boxes


def write_ass(path: str | Path, content: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def coverage(spec: ShortSpec) -> float:
    """% de la durée couverte par des sous-titres."""
    if not spec.duration:
        return 0.0
    covered = 0.0
    for cap in spec.captions:
        covered += min(cap.duration, spec.duration - cap.start)
    return min(1.0, covered / spec.duration)
