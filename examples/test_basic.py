"""Test rapide du pipeline de rendu (sans média externe)."""
from __future__ import annotations

from pathlib import Path

from shortsforge.spec import (
    Brand, Cta, Hook, Music, ShortSpec, Shot, Sfx, TextOverlay, Voiceover,
)

ROOT = Path(__file__).resolve().parent.parent


def build() -> ShortSpec:
    spec = ShortSpec(
        title="Test pipeline",
        slug="test_pipeline",
        brand=Brand(name="Test", primary="#FF2E63", accent="#25F4EE", paper="#0B0B0F"),
        duration=12.0,
        hook=Hook(text="POURQUOI ton short flop", subtext="3 erreurs", duration=2.6),
        shots=[
            Shot(id="s1", duration=3.0, fallback_color="#1B1035", motion={"kind": "kenburns-in"}),
            Shot(id="s2", duration=3.0, fallback_color="#0E2A47", motion={"kind": "kenburns-out"}, transition="flash"),
            Shot(id="s3", duration=3.0, fallback_color="#3A1128", motion={"kind": "kenburns-in"}),
            Shot(id="s4", duration=3.0, fallback_color="#0B2E1F", motion={"kind": "shake"}),
        ],
        captions=[],
        music=Music(path="assets/music/beat_upbeat_minor.mp3", gain_db=-20),
        voiceover=Voiceover(path=None),
        cta=Cta(text="ABONNE-TOI", subtext="1 astuce par jour", at=9.0, duration=3.0),
        output="output/test_pipeline.mp4",
    )
    return spec


if __name__ == "__main__":
    from shortsforge.captions import plan_words
    from shortsforge.renderer import render_spec

    spec = build()
    lines = [
        ("Ton short flop ?", 0.3, 2.2),
        ("Regarde ces 3 erreurs", 2.6, 2.4),
        ("Pas de hook fort", 5.2, 2.0),
        ("Trop de plans morts", 7.4, 2.2),
        ("Aucun appel à l'action", 9.8, 2.0),
    ]
    from shortsforge.spec import CaptionLine

    spec.captions = [
        CaptionLine(text=t, start=s, duration=d, words=plan_words(t, s, d), highlight="word", size=72, y=0.70)
        for t, s, d in lines
    ]
    spec.sfx = [
        Sfx(path="assets/sfx/whoosh.mp3", at=2.95, gain_db=-14),
        Sfx(path="assets/sfx/ding.mp3", at=9.0, gain_db=-14),
    ]
    res = render_spec(spec, root=ROOT, verbose=True)
    print(res.to_dict())
