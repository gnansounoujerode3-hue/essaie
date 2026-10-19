"""Génération de sous-titres ASS animés (pop, karaoké, boîte, néon…)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from .common import SkillError, fmt_ass_time, normalize_text, read_json, skill_data

DEFAULT_STYLES_PATH = skill_data("animated-captions-generator", "styles.json")


# --------------------------------------------------------------------------- styles


def load_styles(path: str | Path | None = None) -> dict[str, Any]:
    styles_path = Path(path) if path else DEFAULT_STYLES_PATH
    data = read_json(styles_path)
    if "styles" not in data:
        raise SkillError(f"Fichier de styles invalide : {styles_path}")
    return data["styles"]


def get_style(name: str, *, path: str | Path | None = None) -> dict[str, Any]:
    styles = load_styles(path)
    if name not in styles:
        raise SkillError(
            f"Style inconnu : {name}. Disponibles : {', '.join(sorted(styles))}"
        )
    style = dict(styles[name])
    style["name"] = name
    return style


def merge_overrides(style: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    merged = dict(style)
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    return merged


# --------------------------------------------------------------------------- couleurs


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    raw = str(value).strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raise SkillError(f"Couleur hexadécimale invalide : {value}")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def ass_color(value: str, alpha: float = 0.0) -> str:
    """``#RRGGBB`` → ``&HAABBGGRR`` (alpha ASS : 00 opaque, FF transparent)."""
    r, g, b = hex_to_rgb(value)
    a = max(0, min(255, int(round(alpha * 255))))
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


# --------------------------------------------------------------------------- texte


def escape_ass(text: str) -> str:
    text = str(text).replace("\\", "\\\\")
    text = text.replace("{", "\\{").replace("}", "\\}")
    text = re.sub(r"\r?\n", " ", text)
    return text.strip()


def wrap_text(text: str, max_chars: int) -> str:
    words = text.split()
    if len(text) <= max_chars or len(words) == 1:
        return text
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
    return "\\N".join(lines[:3])


def _keyword_set(keywords: Iterable[str] | None) -> set[str]:
    if not keywords:
        return set()
    return {normalize_text(word) for word in keywords if str(word).strip()}


def _lookup_emoji(emoji_map: dict[str, Any] | None, word: str) -> str | None:
    if not emoji_map:
        return None
    table = emoji_map.get("map", emoji_map)
    if not isinstance(table, dict):
        return None
    key = normalize_text(re.sub(r"[^\w'’-]", "", word))
    value = table.get(key)
    if isinstance(value, list):
        return str(value[0]) if value else None
    if isinstance(value, str):
        return value
    return None


# --------------------------------------------------------------------------- cues


def group_words(
    words: Sequence[dict[str, Any]],
    *,
    max_words: int = 3,
    max_chars: int = 28,
    max_duration: float = 2.8,
    gap_break: float = 0.65,
) -> list[list[dict[str, Any]]]:
    cues: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for index, word in enumerate(words):
        start, end = float(word["start"]), float(word["end"])
        if current:
            previous = current[-1]
            gap = start - float(previous["end"])
            candidate_len = len(" ".join(str(w["word"]) for w in current + [word]))
            if (
                len(current) >= max_words
                or candidate_len > max_chars
                or end - float(current[0]["start"]) > max_duration
                or gap > gap_break
            ):
                cues.append(current)
                current = []
        current.append(word)
        if re.search(r"[.!?…]$", str(word["word"])):
            cues.append(current)
            current = []
    if current:
        cues.append(current)
    # durée minimale + pas de chevauchement
    for index, cue in enumerate(cues):
        for word_index, word in enumerate(cue):
            if float(word["end"]) <= float(word["start"]):
                word["end"] = float(word["start"]) + 0.12
        next_start = float(cues[index + 1][0]["start"]) if index + 1 < len(cues) else None
        cue_end = float(cue[-1]["end"])
        if next_start is not None and cue_end > next_start:
            cue_end = next_start - 0.01
        if cue_end - float(cue[0]["start"]) < 0.16:
            cue_end = float(cue[0]["start"]) + 0.16
        cue[0]["_cue_start"] = float(cue[0]["start"])
        cue[0]["_cue_end"] = cue_end
    return cues


def _cue_times(cue: Sequence[dict[str, Any]]) -> tuple[float, float]:
    return float(cue[0].get("_cue_start", cue[0]["start"])), float(
        cue[0].get("_cue_end", cue[-1]["end"])
    )


def _word_text(word: dict[str, Any], keywords: set[str], emoji_map: dict[str, Any] | None,
               emoji_suffix: bool) -> str:
    text = str(word["word"])
    if emoji_suffix:
        emoji = _lookup_emoji(emoji_map, text)
        if emoji:
            text = f"{text}{emoji}"
    return text


def wrap_tagged(tagged: Sequence[str], plain: Sequence[str], max_chars: int) -> str:
    """Découpe en lignes en mesurant le texte visible, pas les balises ASS."""
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for tag, text in zip(tagged, plain):
        addition = len(text) + (1 if current else 0)
        if current and current_len + addition > max_chars:
            lines.append(" ".join(current))
            current, current_len = [], 0
            addition = len(text)
        current.append(tag)
        current_len += addition
    if current:
        lines.append(" ".join(current))
    return "\\N".join(lines[:3])


def _colorized_word(raw: str, color: str | None, primary: str) -> str:
    if not color:
        return raw
    return f"{{\\c{ass_color(color)}}}{raw}{{\\c{ass_color(primary)}}}"


def build_events(
    transcript: dict[str, Any],
    style: dict[str, Any],
    *,
    canvas: tuple[int, int] = (1080, 1920),
    keywords: Iterable[str] | None = None,
    emoji_map: dict[str, Any] | None = None,
    emoji_suffix: bool = True,
    max_words: int | None = None,
    font_size: int | None = None,
    position: str | None = None,
) -> list[dict[str, Any]]:
    """Construit la liste d'événements ASS à partir du transcript."""
    from .transcript import ensure_word_timings

    width, height = canvas
    scale = height / 1920.0
    base_font = float(font_size or style.get("font_size", 96)) * scale
    margin_h = float(style.get("margin_h", 80)) * (width / 1080.0)
    margin_v = float(style.get("margin_v", 400)) * scale
    align = int(style.get("alignment", 2))
    if position == "center":
        align = 5
    elif position == "top":
        align = 8
    x = width / 2.0
    if align in {1, 4, 7}:
        x = margin_h
    elif align in {3, 6, 9}:
        x = width - margin_h
    y = height - margin_v if align in {1, 2, 3} else (height / 2.0 if align in {4, 5, 6} else margin_v)

    # largeur utile estimée (la police réellement installée peut différer de celle
    # demandée : on adapte la taille de police par cue pour ne jamais déborder)
    usable_width = max(120.0, width - 2 * margin_h)
    style_max_chars = int(style.get("max_chars", 30))
    keyword_set = _keyword_set(keywords)
    highlight = style.get("highlight_color", "#FFD400")
    primary = style.get("primary", "#FFFFFF")
    uppercase = bool(style.get("uppercase", False))
    karaoke = bool(style.get("karaoke", False))
    animation = str(style.get("animation", "pop"))
    pop_scale = float(style.get("pop_scale", 108))
    fade_ms = int(style.get("fade_ms", 60))
    border_style = int(style.get("border_style", 1))
    back_opacity = float(style.get("back_opacity", 0.0))

    words = [dict(w) for w in ensure_word_timings(transcript.get("segments", []))]
    flat: list[dict[str, Any]] = []
    for segment in words:
        flat.extend(segment["words"])
    if not flat:
        raise SkillError("Transcription vide : aucun mot à animer.")
    flat.sort(key=lambda w: float(w["start"]))
    cues = group_words(
        flat,
        max_words=int(max_words or style.get("words_per_cue", 3)),
        max_chars=style_max_chars,
        max_duration=float(style.get("max_duration", 3.0)),
    )

    events: list[dict[str, Any]] = []
    for cue in cues:
        start, end = _cue_times(cue)
        if end <= start:
            continue
        header: list[str] = [f"\\an{align}"]
        header.append(f"\\fs{base_font:.1f}")
        if animation == "slide":
            header.append(f"\\move({x:.1f},{y + 40:.1f},{x:.1f},{y:.1f},0,180)")
        else:
            header.append(f"\\pos({x:.1f},{y:.1f})")
        if style.get("spacing"):
            header.append(f"\\fsp{float(style['spacing']) * scale:.1f}")
        if style.get("blur"):
            header.append(f"\\blur{float(style['blur']) * scale:.1f}")
        if fade_ms:
            header.append(f"\\fad({fade_ms},{max(20, fade_ms // 2)})")
        if border_style == 3 and back_opacity < 0.999:
            header.append(f"\\3a&H{int(round((1.0 - back_opacity) * 255)):02X}&")
        if animation == "pop":
            start_scale = max(70.0, 100.0 - (pop_scale - 100.0) * 1.6)
            header.append(
                f"\\fscx{start_scale:.0f}\\fscy{start_scale:.0f}"
                f"\\t(0,110,\\fscx{pop_scale:.0f}\\fscy{pop_scale:.0f})"
                f"\\t(110,200,\\fscx100\\fscy100)"
            )

        if karaoke:
            parts: list[str] = []
            cursor = start
            for word in cue:
                w_start, w_end = float(word["start"]), float(word["end"])
                gap = max(0.0, w_start - cursor)
                if gap >= 0.02:
                    parts.append(f"{{\\k{int(round(gap * 100))}}}")
                duration = max(0.08, w_end - w_start)
                token = _word_text(word, keyword_set, emoji_map, emoji_suffix)
                if uppercase:
                    token = token.upper()
                is_keyword = normalize_text(re.sub(r"[^\w'’-]", "", str(word["word"]))) in keyword_set
                color_tag = f"\\c{ass_color(highlight)}" if is_keyword else ""
                parts.append(f"{{\\kf{int(round(duration * 100))}{color_tag}}}{escape_ass(token)} ")
                cursor = max(cursor, w_end)
            raw_text = "".join(parts).rstrip()
            plain_text = " ".join(
                (_word_text(w, keyword_set, emoji_map, emoji_suffix).upper() if uppercase
                 else _word_text(w, keyword_set, emoji_map, emoji_suffix)) for w in cue
            )
        else:
            tagged_tokens = []
            plain_tokens = []
            for word in cue:
                token = _word_text(word, keyword_set, emoji_map, emoji_suffix)
                if uppercase:
                    token = token.upper()
                is_keyword = normalize_text(re.sub(r"[^\w'’-]", "", str(word["word"]))) in keyword_set
                plain_tokens.append(token)
                tagged_tokens.append(_colorized_word(escape_ass(token),
                                                     highlight if is_keyword else None,
                                                     primary))
            raw_tokens = tagged_tokens
            plain_text = " ".join(plain_tokens)

        size = base_font
        text = ""
        for attempt in range(9):
            size = max(base_font * 0.5, base_font * (0.9 ** attempt))
            chars_per_line = max(6, int(usable_width / (0.58 * size)))
            if karaoke:
                # le karaoké ne se découpe pas facilement : on réduit simplement la taille
                text = raw_text
                lines = [plain_text]
            else:
                text = wrap_tagged(raw_tokens, plain_tokens, chars_per_line)
                lines = text.replace("\\N", "\n").split("\n")
            longest = max((len(line) for line in lines), default=1)
            if len(lines) <= 2 and longest * 0.58 * size <= usable_width:
                break
        header_literal = "".join(header).replace(
            f"\\fs{base_font:.1f}", f"\\fs{size:.1f}"
        )
        events.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "text": "{" + header_literal + "}" + text,
            "style": "Default",
            "layer": 0,
            "font_size": round(size, 1),
        })
        if not karaoke and len(cue) > 1 and style.get("animation") == "pop":
            # petit rebond sur chaque mot intérieur pour un rendu plus vivant
            pass
    return events


# --------------------------------------------------------------------------- ASS


def _style_line(style: dict[str, Any], canvas_height: int) -> str:
    scale = canvas_height / 1920.0
    font = style.get("font", "Arial")
    size = float(style.get("font_size", 96)) * scale
    bold = int(style.get("bold", -1))
    italic = int(style.get("italic", 0))
    primary = ass_color(style.get("primary", "#FFFFFF"))
    secondary = ass_color(style.get("secondary", "#FFFFFF"))
    outline = ass_color(style.get("outline_color", "#000000"))
    back_alpha = 1.0 - float(style.get("back_opacity", 0.0))
    back = ass_color(style.get("shadow_color", "#000000"), alpha=back_alpha)
    border_style = int(style.get("border_style", 1))
    outline_width = float(style.get("outline", 4)) * scale
    shadow = float(style.get("shadow", 0)) * scale
    scale_x = 100
    scale_y = 100
    spacing = float(style.get("spacing", 0)) * scale
    angle = 0
    align = int(style.get("alignment", 2))
    margin_l = int(float(style.get("margin_h", 80)) * 0.6)
    margin_r = margin_l
    margin_v = int(float(style.get("margin_v", 400)) * scale)
    return (
        "Style: Default,{font},{size:.1f},{primary},{secondary},{outline_color},{back},"
        "{bold},{italic},0,0,{sx},{sy},{spacing:.1f},{angle},{border},{outline_width:.1f},"
        "{shadow:.1f},{align},{ml},{mr},{mv},1"
    ).format(
        font=font, size=size, primary=primary, secondary=secondary,
        outline_color=outline, back=back, bold=bold, italic=italic, sx=scale_x,
        sy=scale_y, spacing=spacing, angle=angle, border=border_style,
        outline_width=outline_width, shadow=shadow, align=align, ml=margin_l,
        mr=margin_r, mv=margin_v,
    )


def build_ass(events: Sequence[dict[str, Any]], style: dict[str, Any],
              *, canvas: tuple[int, int] = (1080, 1920),
              title: str = "VESK captions") -> str:
    width, height = canvas
    lines = [
        "[Script Info]",
        f"Title: {title}",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        _style_line(style, height),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for event in events:
        text = str(event["text"]).replace("\n", "\\N")
        lines.append(
            "Dialogue: {layer},{start},{end},{style},,0,0,0,,{text}".format(
                layer=event.get("layer", 0),
                start=fmt_ass_time(float(event["start"])),
                end=fmt_ass_time(float(event["end"])),
                style=event.get("style", "Default"),
                text=text,
            )
        )
    return "\n".join(lines) + "\n"


def generate(
    transcript: dict[str, Any],
    *,
    style_name: str = "hormozi",
    styles_path: str | Path | None = None,
    canvas: tuple[int, int] = (1080, 1920),
    keywords: Iterable[str] | None = None,
    emoji_map: dict[str, Any] | None = None,
    emoji_suffix: bool = True,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    style = get_style(style_name, path=styles_path)
    if overrides:
        style = merge_overrides(style, **overrides)
    events = build_events(
        transcript, style, canvas=canvas, keywords=keywords,
        emoji_map=emoji_map, emoji_suffix=emoji_suffix,
        max_words=style.get("words_per_cue"), font_size=style.get("font_size_override"),
        position=style.get("position_override"),
    )
    ass = build_ass(events, style, canvas=canvas)
    return {"style": style, "events": events, "ass": ass,
            "canvas": {"width": canvas[0], "height": canvas[1]}}


def write_ass(path: str | Path, content: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def events_to_srt(events: Sequence[dict[str, Any]]) -> str:
    from .common import fmt_srt_time

    blocks = []
    for index, event in enumerate(events, start=1):
        text = re.sub(r"\{[^}]*\}", "", str(event["text"]))
        text = text.replace("\\N", "\n").strip()
        blocks.append(
            f"{index}\n{fmt_srt_time(float(event['start']))} --> "
            f"{fmt_srt_time(float(event['end']))}\n{text}\n"
        )
    return "\n".join(blocks)


def parse_canvas(value: str, video: dict[str, Any] | None = None,
                 style: dict[str, Any] | None = None) -> tuple[int, int]:
    if not value or value == "auto":
        if video and video.get("width") and video.get("height"):
            width, height = int(video["width"]), int(video["height"])
            # résolutions verticales/horizontales standardisées
            if height > width:
                return (1080, 1920)
            if height == width:
                return (1080, 1080)
            return (1920, 1080)
        return (1080, 1920)
    match = re.fullmatch(r"(\d{2,5})[xX](\d{2,5})", value.strip())
    if not match:
        raise SkillError(f"Canvas invalide : {value} (attendu : auto, 1080x1920, 1920x1080…)")
    return int(match.group(1)), int(match.group(2))


def describe_styles(path: str | Path | None = None) -> list[dict[str, str]]:
    styles = load_styles(path)
    return [{"name": key, "label": value.get("label", key)} for key, value in styles.items()]


def font_available(name: str) -> bool | None:
    """Vérifie la présence d'une police via fc-list (``None`` si indisponible)."""
    import shutil
    import subprocess

    if not shutil.which("fc-list"):
        return None
    family = str(name).split()[0]
    try:
        proc = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True,
                              timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    families = proc.stdout.lower()
    return family.lower() in families


def missing_font_warning(style: dict[str, Any]) -> str | None:
    name = style.get("font", "")
    available = font_available(name)
    if available is False:
        return (f"Police « {name} » introuvable : FFmpeg utilisera une police de secours. "
                "Installe-la (fonts.google.com) ou passe --font \"DejaVu Sans\".")
    return None
