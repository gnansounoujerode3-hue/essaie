"""Modèle de données d'un Short (spec) + validation.

Un ``ShortSpec`` est la source de vérité unique : le plan de montage, le
script, l'audio et le design y sont décrits en JSON/YAML, puis compilés par
le renderer.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields as dataclass_fields
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


# --------------------------------------------------------------------------- #
# Format
# --------------------------------------------------------------------------- #
@dataclass
class Brand:
    name: str = "Ma marque"
    primary: str = "#FF2E63"
    accent: str = "#25F4EE"
    ink: str = "#FFFFFF"
    paper: str = "#0B0B0F"
    font_title: str = "anton"
    font_caption: str = "inter-800"
    font_sticker: str = "inter-900"
    logo: Optional[str] = None


@dataclass
class SafeZone:
    """Zones réservées par les interfaces (TikTok / Reels / Shorts)."""

    top: int = 220
    bottom: int = 320
    right: int = 140
    left: int = 60


@dataclass
class Motion:
    """Mouvement de caméra appliqué à un plan."""

    kind: str = "kenburns-in"  # kenburns-in|out|left|right|static|shake|zoom-out
    start_scale: float = 1.0
    end_scale: float = 1.12
    fps: int = 30


@dataclass
class Sticker:
    """Autocollant (emoji, texte, badge) posé sur l'image."""

    text: str = ""
    image: Optional[str] = None
    position: str = "top-right"  # top-left|top-right|center|bottom-left|bottom-right|middle-left|middle-right
    scale: float = 1.0
    at: Optional[float] = None
    duration: Optional[float] = None
    rotation: float = 0.0
    opacity: float = 1.0


@dataclass
class TextOverlay:
    """Titre à l'écran (hook, liste ou CTA) — style typographique fort."""

    text: str = ""
    subtext: str = ""
    position: str = "center"  # top|upper|center|lower|bottom
    size: int = 96
    color: Optional[str] = None
    accent: Optional[str] = None
    at: float = 0.0
    duration: float = 3.0
    effect: str = "pop"  # pop|slide|fade|type|shake
    background: bool = False
    rotation: float = 0.0
    font: Optional[str] = None
    max_width: int = 940
    highlights: List[str] = field(default_factory=list)


@dataclass
class Broll:
    """B-roll / overlay vidéo posé au-dessus du plan principal."""

    source: str = ""
    position: str = "top-right"  # top-left|top-right|bottom-left|bottom-right|center
    width: int = 420
    height: Optional[int] = None
    radius: int = 28
    at: Optional[float] = None
    duration: Optional[float] = None
    opacity: float = 1.0
    border: bool = True


@dataclass
class Shot:
    """Un plan du montage (unité de coupe)."""

    id: str = ""
    duration: float = 3.0
    source: Optional[str] = None
    fallback_color: str = "#12121A"
    motion: Motion = field(default_factory=Motion)
    stickers: List[Sticker] = field(default_factory=list)
    broll: List[Broll] = field(default_factory=list)
    texts: List[TextOverlay] = field(default_factory=list)
    transition: str = "cut"  # cut|fade|whip|flash|zoom|glitch|dip
    sfx: List[str] = field(default_factory=list)
    music_sfx_at: Optional[float] = None
    source_in: float = 0.0
    source_loop: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.motion, dict):
            self.motion = sub_motion(self.motion)


@dataclass
class CaptionWord:
    word: str
    start: float
    end: float


@dataclass
class CaptionLine:
    """Ligne de sous-titre dynamique."""

    text: str = ""
    start: float = 0.0
    duration: float = 2.0
    words: List[CaptionWord] = field(default_factory=list)
    highlight: str = "word"  # word|phrase|none
    style: str = "bold"  # bold|box|outline|karaoke
    y: Optional[float] = None  # position verticale en % de la hauteur
    color: Optional[str] = None
    highlight_color: Optional[str] = None
    size: int = 68
    max_width: int = 800
    uppercase: bool = True


@dataclass
class Sfx:
    path: str = ""
    at: float = 0.0
    gain_db: float = -12.0
    duration: Optional[float] = None


@dataclass
class Music:
    path: Optional[str] = None
    gain_db: float = -20.0
    duck: bool = True
    fade_in: float = 0.4
    fade_out: float = 0.8
    bpm: Optional[int] = None


@dataclass
class Voiceover:
    path: Optional[str] = None
    gain_db: float = 0.0
    start: float = 0.0
    speed: float = 1.06
    target_lufs: float = -14.0


@dataclass
class Cta:
    text: str = ""
    subtext: str = ""
    at: float = 0.0
    duration: float = 3.0
    style: str = "loop"  # loop|cta|both
    position: str = "center"


@dataclass
class Hook:
    text: str = ""
    subtext: str = ""
    badge: str = ""
    duration: float = 3.0


@dataclass
class ShortSpec:
    """Description complète d'un Short."""

    title: str = "Short sans titre"
    slug: str = "short"
    brand: Brand = field(default_factory=Brand)
    safe_zone: SafeZone = field(default_factory=SafeZone)
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 30.0
    hook: Hook = field(default_factory=Hook)
    shots: List[Shot] = field(default_factory=list)
    captions: List[CaptionLine] = field(default_factory=list)
    music: Music = field(default_factory=Music)
    voiceover: Voiceover = field(default_factory=Voiceover)
    sfx: List[Sfx] = field(default_factory=list)
    cta: Optional[Cta] = None
    loop: bool = True
    grade: str = "standard"  # standard|punch|soft|none
    output: str = "output/{slug}.mp4"
    notes: str = ""
    seed: int = 7

    # ------------------------------------------------------------------ #
    # (De)serialisation
    # ------------------------------------------------------------------ #
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShortSpec":
        data = dict(data or {})

        def sub(key, klass, factory):
            raw = data.pop(key, None)
            if raw is None:
                return factory()
            if isinstance(raw, dict):
                known = {f for f in klass.__dataclass_fields__}
                return klass(**{k: v for k, v in raw.items() if k in known})
            return factory()

        brand = sub("brand", Brand, Brand)
        safe = sub("safe_zone", SafeZone, SafeZone)
        hook = sub("hook", Hook, Hook)
        music = sub("music", Music, Music)
        vo = sub("voiceover", Voiceover, Voiceover)
        cta_raw = data.pop("cta", None)
        cta = None
        if isinstance(cta_raw, dict):
            known = {f for f in Cta.__dataclass_fields__}
            cta = Cta(**{k: v for k, v in cta_raw.items() if k in known})
        elif isinstance(cta_raw, str):
            cta = Cta(text=cta_raw)

        shots: List[Shot] = []
        for raw_shot in data.pop("shots", []) or []:
            raw_shot = dict(raw_shot or {})
            motion = sub_motion(raw_shot)
            stickers = [Sticker(**st) for st in raw_shot.pop("stickers", []) or []]
            brolls = [Broll(**b) for b in raw_shot.pop("broll", []) or []]
            texts = [TextOverlay(**t) for t in raw_shot.pop("texts", []) or []]
            known = {f for f in Shot.__dataclass_fields__ if f not in {"motion", "stickers", "broll", "texts"}}
            shots.append(
                Shot(
                    motion=motion,
                    stickers=stickers,
                    broll=brolls,
                    texts=texts,
                    **{k: v for k, v in raw_shot.items() if k in known},
                )
            )

        captions: List[CaptionLine] = []
        for raw_cap in data.pop("captions", []) or []:
            raw_cap = dict(raw_cap or {})
            words = [
                CaptionWord(**{"word": w["word"], "start": float(w["start"]), "end": float(w["end"])})
                for w in raw_cap.pop("words", []) or []
            ]
            known = {f for f in CaptionLine.__dataclass_fields__ if f != "words"}
            captions.append(CaptionLine(words=words, **{k: v for k, v in raw_cap.items() if k in known}))

        sfx = [Sfx(**s) for s in data.pop("sfx", []) or []]

        known = {f for f in cls.__dataclass_fields__ if f not in {
            "brand", "safe_zone", "hook", "shots", "captions", "music", "voiceover", "sfx", "cta"}}
        spec = cls(
            brand=brand,
            safe_zone=safe,
            hook=hook,
            shots=shots,
            captions=captions,
            music=music,
            voiceover=vo,
            sfx=sfx,
            cta=cta,
            **{k: v for k, v in data.items() if k in known},
        )
        return spec

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_compact_dict(self) -> Dict[str, Any]:
        """Version allégée : uniquement les champs qui diffèrent des défauts.

        Les specs sont versionnés : on veut des fichiers lisibles et des
        diffs courts.
        """
        default = ShortSpec()
        out: Dict[str, Any] = {}
        for f in (x.name for x in dataclass_fields(self)):
            value = getattr(self, f)
            ref = getattr(default, f)
            if isinstance(value, list):
                if not value:
                    continue
                out[f] = [_compact_value(v, ref) for v in value]
            elif isinstance(value, (Brand, SafeZone, Hook, Music, Voiceover, Cta)):
                sub = _compact_value(value, ref)
                if sub:
                    out[f] = sub
            elif value != ref:
                out[f] = value
        return out

    def save(self, path: str | Path, *, compact: bool = True) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_compact_dict() if compact else self.to_dict()
        if path.suffix in {".yaml", ".yml"} and yaml is not None:
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "ShortSpec":
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix in {".yaml", ".yml"} and yaml is not None:
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return cls.from_dict(data)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def validate(self, root: Optional[Path] = None) -> List[str]:
        """Retourne la liste des problèmes (vide = spec conforme)."""
        root = Path(root) if root else Path.cwd()
        issues: List[str] = []
        if self.width * 16 != self.height * 9:
            issues.append(f"Format non vertical 9:16 ({self.width}x{self.height}).")
        if self.duration <= 0:
            issues.append("Durée <= 0.")
        if not self.shots:
            issues.append("Aucun plan défini.")
        total = sum(s.duration for s in self.shots)
        if self.shots and abs(total - self.duration) > 0.75:
            issues.append(f"Somme des plans ({total:.2f}s) != durée annoncée ({self.duration:.2f}s).")
        if self.duration > 60:
            issues.append(f"Durée {self.duration:.1f}s > 60s (format court décrié).")

        for shot in self.shots:
            if shot.source:
                p = Path(shot.source)
                if not p.is_absolute():
                    p = root / p
                if not p.exists():
                    issues.append(f"Source introuvable: {shot.source} (plan {shot.id})")
            if shot.duration < 0.4:
                issues.append(f"Plan {shot.id} trop court ({shot.duration:.2f}s) — coupe invisible.")
            for br in shot.broll:
                p = Path(br.source)
                if not p.is_absolute():
                    p = root / p
                if not p.exists():
                    issues.append(f"B-roll introuvable: {br.source}")
        for cap in self.captions:
            if cap.start < 0 or cap.start + cap.duration > self.duration + 0.5:
                issues.append(f"Légende hors timeline: '{cap.text[:24]}' [{cap.start:.2f}s]")
        for s in self.sfx:
            if s.at < 0 or s.at > self.duration:
                issues.append(f"SFX hors timeline à {s.at:.2f}s ({s.path})")
        if self.voiceover.path:
            p = Path(self.voiceover.path)
            if not p.is_absolute():
                p = root / p
            if not p.exists():
                issues.append(f"Voice-over introuvable: {self.voiceover.path}")
        if self.music.path:
            p = Path(self.music.path)
            if not p.is_absolute():
                p = root / p
            if not p.exists():
                issues.append(f"Musique introuvable: {self.music.path}")
        return issues


def _compact_value(value: Any, ref: Any) -> Any:
    """Allège un sous-objet : on ne garde que ce qui diffère du défaut."""
    if isinstance(value, dict):
        return {k: _compact_value(v, getattr(ref, k, None)) for k, v in value.items()}
    if isinstance(value, list):
        return [_compact_value(v, None) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        if not hasattr(ref, "__dataclass_fields__"):
            try:
                ref = type(value)()
            except Exception:
                ref = None
        out: Dict[str, Any] = {}
        for f in (x.name for x in dataclass_fields(value)):
            v = getattr(value, f)
            r = getattr(ref, f, None) if hasattr(ref, "__dataclass_fields__") else None
            if v != r:
                out[f] = _compact_value(v, r)
        return out
    return value


def sub_motion(raw: Dict[str, Any]) -> Motion:
    m = raw.pop("motion", None)
    if isinstance(m, str):
        m = {"kind": m}
    raw.update(m or {})
    known = {f for f in Motion.__dataclass_fields__}
    return Motion(**{k: v for k, v in raw.items() if k in known})
