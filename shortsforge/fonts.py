"""Gestion des polices (rendu PIL + rendu libass).

Chaque fichier TTF reçoit un nom de famille unique via un fichier fontconfig
généré à la volée : la famille "Inter" existe en 4 graisses, on veut pouvoir
demander précisément "Inter ExtraBold" sans que fontconfig ne les confonde.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from PIL import ImageFont

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
_PROJECT_FONTS = ROOT / "assets" / "fonts"
_BUNDLED_FONTS = PACKAGE_DIR / "bundled_assets" / "fonts"
FONT_DIR = _PROJECT_FONTS if _PROJECT_FONTS.exists() else _BUNDLED_FONTS


@dataclass(frozen=True)
class FontEntry:
    """Une police du registre interne.

    key      : identifiant logique ("inter-800")
    family   : famille unique exposée à libass ("SF Inter ExtraBold")
    path     : chemin du fichier TTF
    style    : style interne rapporté par FreeType
    weight   : indice de graisse (400 = normal ... 900 = black)
    category : "sans" | "display" | "mono"
    """

    key: str
    family: str
    path: Path
    style: str
    weight: int
    category: str

    @property
    def display(self) -> str:
        return f"{self.family} ({self.weight})"


_WEIGHT_TOKENS = {
    "thin": 100,
    "extralight": 200,
    "light": 300,
    "regular": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "extrabold": 800,
    "black": 900,
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@lru_cache(maxsize=1)
def _scan() -> Dict[str, FontEntry]:
    entries: Dict[str, FontEntry] = {}
    if not FONT_DIR.exists():
        return entries
    for ttf in sorted(FONT_DIR.glob("*.ttf")):
        stem = ttf.stem  # Inter_800ExtraBold
        family_raw, _, style_raw = stem.partition("_")
        if not style_raw:
            family_raw, style_raw = stem, "Regular"
        style_raw = style_raw.replace("Regular", "Regular")
        weight = 400
        for token, w in _WEIGHT_TOKENS.items():
            if token in style_raw.lower():
                weight = w
                break
        style = style_raw
        unique_family = f"SF {family_raw}" + (f" {style_raw}" if weight != 400 else "")
        key = f"{_slug(family_raw)}-{weight}"
        try:
            with ImageFont.truetype(str(ttf), 20) as f:
                internal = f.getname()
        except Exception:
            internal = (family_raw, style_raw)
        category = "display" if family_raw in {"Anton", "BebasNeue", "ArchivoBlack", "LilitaOne", "Fredoka", "Oswald"} else "sans"
        entries[key] = FontEntry(
            key=key,
            family=unique_family,
            path=ttf,
            style=style,
            weight=weight,
            category=category,
        )
    return entries


def all_fonts() -> List[FontEntry]:
    return sorted(_scan().values(), key=lambda e: (e.category, e.weight, e.family))


def resolve(name: str) -> FontEntry:
    """Résout un nom de police ("anton", "Inter ExtraBold", "inter-800")."""
    entries = _scan()
    if not entries:
        raise FileNotFoundError(f"Aucune police dans {FONT_DIR}")
    n = name.strip()
    low = n.lower()

    if low in entries:
        return entries[low]

    # Correspondance directe sur le nom de famille unique.
    for e in entries.values():
        if e.family.lower() == low:
            return e
        if e.family.lower().replace("sf ", "") == low:
            return e

    # Correspondance partielle : "inter" -> graisse 800 par défaut, "anton" -> Anton.
    fam = re.sub(r"[\s_-]+", "", low)
    fam = fam.replace("800", "").replace("700", "").replace("900", "")
    candidates = [e for e in entries.values() if re.sub(r"[\s_-]+", "", e.family.lower().replace("sf ", "")) == fam]
    if not candidates:
        candidates = [e for e in entries.values() if fam in re.sub(r"[\s_-]+", "", e.family.lower())]
    if candidates:
        weight_hint = 800
        for token, w in _WEIGHT_TOKENS.items():
            if token in low:
                weight_hint = w
        candidates.sort(key=lambda e: abs(e.weight - weight_hint))
        return candidates[0]
    raise KeyError(f"Police inconnue: {name!r}. Disponibles: {sorted(entries)}")


def pil_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Charge une police TrueType pour Pillow."""
    entry = resolve(name)
    return ImageFont.truetype(str(entry.path), size)


def text_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    """Largeur du texte en pixels (via bbox de la police)."""
    if not text:
        return 0.0
    try:
        bbox = font.getbbox(text)
        return float(bbox[2] - bbox[0])
    except Exception:
        return float(font.getlength(text))


def text_height(font: ImageFont.FreeTypeFont) -> float:
    try:
        bbox = font.getbbox("Ag")
        return float(bbox[3] - bbox[1])
    except Exception:
        return float(font.size * 1.2)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> List[str]:
    """Découpe un texte en lignes tenant dans max_width (coupe par mot)."""
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_width(candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


@lru_cache(maxsize=1)
def fontconfig_file() -> Path:
    """Génère (et met en cache) le fichier fontconfig qui fixe les familles uniques."""
    entries = _scan()
    cache_root = Path(os.environ.get("SHORTSFORGE_CACHE", tempfile.gettempdir())) / "shortsforge"
    cache_root.mkdir(parents=True, exist_ok=True)
    conf = cache_root / "fonts.conf"
    lines = [
        '<?xml version="1.0"?>',
        '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">',
        "<fontconfig>",
        f"  <dir>{FONT_DIR}</dir>",
        "  <cachedir>/tmp/shortsforge-fontcache</cachedir>",
    ]
    for e in entries.values():
        lines += [
            '  <match target="pattern">',
            f'    <test name="file"><string>{e.path}</string></test>',
            '    <edit name="family" mode="assign"><string>' + e.family + "</string></edit>",
            f'    <edit name="weight" mode="assign"><const>{"bold" if e.weight >= 700 else "regular"}</const></edit>',
            '    <edit name="style" mode="assign"><string>Regular</string></edit>',
            "  </match>",
        ]
    lines.append("</fontconfig>")
    conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return conf


def summary() -> str:
    rows = ["| Clé | Famille ASS | Graisse | Usage |", "| --- | --- | --- | --- |"]
    for e in all_fonts():
        rows.append(f"| `{e.key}` | {e.family} | {e.weight} | {e.category} |")
    return "\n".join(rows)
