"""Motion design en ASS : titres, lower thirds, chapitres, compteurs, barres, CTA."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Sequence

from .captions import ass_color, escape_ass
from .common import SkillError, fmt_ass_time, read_json, skill_data

DEFAULT_TEMPLATES = skill_data("motion-design-templates", "templates.json")


def load_templates(path: str | Path | None = None) -> dict[str, Any]:
    data = read_json(Path(path) if path else DEFAULT_TEMPLATES)
    if "templates" not in data:
        raise SkillError("Fichier de templates motion invalide.")
    return data


def _event(start: float, end: float, text: str, *, layer: int = 0,
           style: str = "Motion") -> str:
    return (f"Dialogue: {layer},{fmt_ass_time(start)},{fmt_ass_time(end)},"
            f"{style},,0,0,0,,{text}")


def _header(width: int, height: int, *, font: str, primary: str, accent: str) -> str:
    primary_c = ass_color(primary)
    accent_c = ass_color(accent)
    black = ass_color("#000000")
    return "\n".join([
        "[Script Info]",
        "Title: VESK motion",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Motion,{font},96,{primary_c},{primary_c},{black},{black},-1,0,0,0,100,100,0,0,1,5,0,5,60,60,60,1",
        f"Style: Accent,{font},96,{accent_c},{accent_c},{black},{black},-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: Dark,{font},96,{black},{black},{black},{black},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: Small,{font},36,{primary_c},{primary_c},{black},{black},0,0,0,0,100,100,0,0,1,2,0,5,60,60,60,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


def _scaled(value: float, height: int) -> float:
    return value * height / 1920.0


def _rect(w: float, h: float) -> str:
    """Rectangle ASS (dessin ``\\p1``) ancré en haut à gauche."""
    return f"m 0 0 l {w:.1f} 0 l {w:.1f} {h:.1f} l 0 {h:.1f}"


def _wrap(text: str, max_chars: int) -> str:
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\\N".join(lines)


def build_motion(
    template: str,
    *,
    text: str = "",
    subtitle: str = "",
    start: float = 0.0,
    duration: float = 3.0,
    canvas: tuple[int, int] = (1080, 1920),
    font: str = "Montserrat ExtraBold",
    primary: str = "#FFFFFF",
    accent: str = "#FFD400",
    number: float | None = None,
    position: str = "bottom-left",
    uppercase: bool = True,
) -> str:
    width, height = canvas
    if duration <= 0:
        raise SkillError("La durée doit être positive.")
    if template not in {"title", "lower-third", "chapter", "quote", "counter",
                        "progress", "callout", "cta"}:
        raise SkillError(f"Template inconnu : {template}")
    display = text.upper() if uppercase else text
    end = start + duration
    events: list[str] = []

    if template == "title":
        size = _scaled(150, height)
        y = height * 0.44
        events.append(_event(start, end, (
            f"{{\\an5\\pos({width / 2:.0f},{y:.0f})\\fs{size:.0f}\\fad(120,120)"
            f"\\fscx78\\fscy78\\t(0,180,\\fscx103\\fscy103)\\t(180,300,\\fscx100\\fscy100)"
            f"\\blur1}}{escape_ass(_wrap(display, 18))}"
        )))
        line_w = min(width * 0.55, 720)
        line_y = y + _scaled(130, height)
        events.append(_event(start + 0.25, end, (
            f"{{\\an5\\pos({width / 2:.0f},{line_y:.0f})\\p1\\1c{ass_color(accent)}"
            f"\\fscx0\\t(0,500,\\fscx100)}}{_rect(line_w, _scaled(9, height))}"
        ), layer=1, style="Accent"))
        if subtitle:
            events.append(_event(start + 0.4, end, (
                f"{{\\an5\\pos({width / 2:.0f},{line_y + _scaled(80, height):.0f})"
                f"\\fs{_scaled(50, height):.0f}\\alpha&HFF&\\t(0,420,\\alpha&H00&)\\fsp2}}"
                f"{escape_ass(_wrap(subtitle, 32))}"
            ), layer=2, style="Small"))

    elif template == "lower-third":
        margin = _scaled(90, width)
        box_w = min(width - 2 * margin, _scaled(820, width))
        box_h = _scaled(150, height)
        x = margin
        y = height - margin - box_h
        enter = f"\\move({x - 70:.1f},{y:.1f},{x:.1f},{y:.1f},0,240)\\fad(180,120)"
        events.append(_event(start, end, (
            f"{{\\an7{enter}\\p1\\1c{ass_color('#000000')}\\1a&H42&}}"
            f"{_rect(box_w, box_h)}"
        ), layer=0, style="Accent"))
        events.append(_event(start + 0.05, end, (
            f"{{\\an7\\move({x + 18:.1f},{y:.1f},{x + 18:.1f},{y:.1f},0,1)"
            f"\\p1\\1c{ass_color(accent)}}}{_rect(_scaled(10, width), box_h)}"
        ), layer=1, style="Accent"))
        events.append(_event(start + 0.12, end, (
            f"{{\\an7\\pos({x + 48:.1f},{y + 28:.1f})\\fs{_scaled(62, height):.0f}"
            f"\\fad(220,100)}}{escape_ass(display)}"
        ), layer=2))
        if subtitle:
            events.append(_event(start + 0.2, end, (
                f"{{\\an7\\pos({x + 50:.1f},{y + 100:.1f})\\fs{_scaled(34, height):.0f}"
                f"\\fsp2\\alpha&H20&}}{escape_ass(subtitle.upper())}"
            ), layer=3, style="Small"))

    elif template == "chapter":
        number_text = "" if number is None else f"{int(round(number)):02d}"
        events.append(_event(start, end, (
            f"{{\\an7\\pos(0,0)\\p1\\1c{ass_color('#000000')}\\1a&HAA&}}"
            f"{_rect(width, height)}"
        ), layer=0, style="Accent"))
        if number_text:
            events.append(_event(start + 0.1, end, (
                f"{{\\an7\\pos({_scaled(100, width):.0f},{height * 0.22:.0f})"
                f"\\fs{_scaled(260, height):.0f}\\1c{ass_color(accent)}\\fad(150,100)"
                f"\\fscx80\\fscy80\\t(0,220,\\fscx100\\fscy100)}}{number_text}"
            ), layer=2, style="Accent"))
        events.append(_event(start + 0.25, end, (
            f"{{\\an7\\pos({_scaled(100, width):.0f},{height * 0.47:.0f})"
            f"\\fs{_scaled(84, height):.0f}\\fad(250,100)"
            f"\\fscx95\\fscy95\\t(0,300,\\fscx100\\fscy100)}}{escape_ass(_wrap(display, 26))}"
        ), layer=2))
        if subtitle:
            events.append(_event(start + 0.45, end, (
                f"{{\\an7\\pos({_scaled(104, width):.0f},{height * 0.47 + _scaled(210, height):.0f})"
                f"\\fs{_scaled(40, height):.0f}\\alpha&HFF&\\t(0,400,\\alpha&H00&)\\fsp1}}"
                f"{escape_ass(subtitle)}"
            ), layer=2, style="Small"))

    elif template == "quote":
        mark_size = _scaled(200, height)
        events.append(_event(start, end, (
            f"{{\\an7\\pos({_scaled(110, width):.0f},{height * 0.28:.0f})"
            f"\\fs{mark_size:.0f}\\1c{ass_color(accent)}\\fad(180,120)}}\u201c"
        ), layer=1, style="Accent"))
        events.append(_event(start + 0.1, end, (
            f"{{\\an5\\pos({width / 2:.0f},{height * 0.48:.0f})\\fs{_scaled(72, height):.0f}"
            f"\\fn{font}\\i1\\fad(260,140)\\fsp1}}{escape_ass(_wrap(display, 30))}"
        ), layer=2))
        if subtitle:
            events.append(_event(start + 0.35, end, (
                f"{{\\an5\\pos({width / 2:.0f},{height * 0.68:.0f})\\fs{_scaled(38, height):.0f}"
                f"\\fsp3\\1c{ass_color(accent)}\\alpha&HFF&\\t(0,450,\\alpha&H00&)}}— "
                f"{escape_ass(subtitle)}"
            ), layer=2, style="Small"))

    elif template == "counter":
        target = float(number if number is not None else 0.0)
        steps = 30
        suffix = ""
        match = re.match(r"^\s*([\d\s.,]+)(.*)$", str(text or target))
        if text and match:
            suffix = match.group(2).strip()
        for step in range(steps):
            ratio = step / (steps - 1)
            eased = 1 - math.pow(1 - ratio, 3)
            value = target * eased
            if abs(target - round(target)) < 0.01:
                shown = f"{int(round(value)):,}".replace(",", " ")
            else:
                shown = f"{value:.1f}".replace(".", ",")
            step_time = start + duration * ratio
            step_end = min(end, step_time + duration / steps + 0.05)
            events.append(_event(step_time, step_end, (
                f"{{\\an5\\pos({width / 2:.0f},{height * 0.42:.0f})"
                f"\\fs{_scaled(230, height):.0f}\\1c{ass_color(accent)}\\bord{_scaled(4, height):.0f}"
                f"\\blur1\\fad(0,0)}}{escape_ass(shown)}{escape_ass(suffix)}"
            ), layer=2, style="Accent"))
        if text and not match:
            events.append(_event(start, end, (
                f"{{\\an5\\pos({width / 2:.0f},{height * 0.58:.0f})\\fs{_scaled(44, height):.0f}"
                f"\\fsp1\\fad(200,100)}}{escape_ass(text)}"
            ), layer=2, style="Small"))

    elif template == "progress":
        margin = _scaled(90, width)
        bar_w = width - margin * 2
        bar_h = _scaled(14, height)
        y = height - _scaled(110, height)
        events.append(_event(start, end, (
            f"{{\\an7\\pos({margin:.0f},{y:.0f})\\p1\\1c{ass_color('#FFFFFF')}\\1a&H70&}}"
            f"{_rect(bar_w, bar_h)}"
        ), layer=1, style="Accent"))
        events.append(_event(start, end, (
            f"{{\\an7\\pos({margin:.0f},{y:.0f})\\p1\\1c{ass_color(accent)}"
            f"\\org({margin:.0f},{y + bar_h / 2:.0f})\\fscx0"
            f"\\t(0,{int(duration * 1000)},\\fscx100)}}{_rect(bar_w, bar_h)}"
        ), layer=2, style="Accent"))

    elif template == "callout":
        size = _scaled(46, height)
        box_w = min(width - _scaled(160, width), _scaled(700, width))
        x = width * 0.5 if position == "center" else _scaled(140, width)
        y = height * (0.35 if position == "center" else 0.62)
        events.append(_event(start, end, (
            f"{{\\an5\\pos({x:.0f},{y:.0f})\\move({x - 50:.0f},{y:.0f},{x:.0f},{y:.0f},0,220)"
            f"\\fs{size:.0f}\\fad(180,120)\\bord{_scaled(18, height):.0f}"
            f"\\3c{ass_color(accent)}\\1c{ass_color('#0A0A0A')}\\b1}}"
            f"{escape_ass(_wrap(display, 26))}"
        ), layer=2, style="Motion"))
        tri_y = y + size * 1.5
        events.append(_event(start + 0.12, end, (
            f"{{\\an5\\pos({x - box_w * 0.25:.0f},{tri_y:.0f})\\p1"
            f"\\1c{ass_color(accent)}\\alpha&HFF&\\t(0,300,\\alpha&H00&)}}m 0 0 l 26 0 l 13 22"
        ), layer=1, style="Accent"))

    elif template == "cta":
        events.append(_event(start, end, (
            f"{{\\an7\\pos(0,0)\\p1\\1c{ass_color('#000000')}\\1a&H60&}}"
            f"{_rect(width, height)}"
        ), layer=0, style="Accent"))
        events.append(_event(start + 0.1, end, (
            f"{{\\an5\\pos({width / 2:.0f},{height * 0.36:.0f})\\fs{_scaled(110, height):.0f}"
            f"\\fad(200,150)\\fscx70\\fscy70\\t(0,260,\\fscx103\\fscy103)"
            f"\\t(260,360,\\fscx100\\fscy100)}}{escape_ass(display or 'ABONNE-TOI')}"
        ), layer=2))
        arrow_y = height * 0.52
        events.append(_event(start + 0.25, end, (
            f"{{\\an5\\pos({width / 2:.0f},{arrow_y:.0f})\\fs{_scaled(120, height):.0f}"
            f"\\1c{ass_color(accent)}\\fad(200,120)}}\u2193"
        ), layer=2, style="Accent"))
        if subtitle:
            events.append(_event(start + 0.35, end, (
                f"{{\\an5\\pos({width / 2:.0f},{height * 0.64:.0f})\\fs{_scaled(46, height):.0f}"
                f"\\fsp2\\alpha&HFF&\\t(0,400,\\alpha&H00&)}}{escape_ass(subtitle)}"
            ), layer=2, style="Small"))

    return _header(width, height, font=font, primary=primary, accent=accent) + \
        "\n" + "\n".join(events) + "\n"


def write_ass(path: str | Path, content: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def list_templates(path: str | Path | None = None) -> list[dict[str, Any]]:
    data = load_templates(path)
    return [{"id": key, **value} for key, value in data["templates"].items()]


def palettes(path: str | Path | None = None) -> dict[str, dict[str, str]]:
    return dict(load_templates(path).get("palettes", {}))
