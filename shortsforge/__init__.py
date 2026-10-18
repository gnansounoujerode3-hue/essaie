"""ShortsForge — pipeline de production de Shorts marketing verticale.

Modules :
    spec        : modèle de données d'un Short (+ validation)
    planner     : transformation script -> plan de montage
    aligner     : alignement voix / sous-titres
    captions    : sous-titres dynamiques mot par mot (ASS)
    graphics    : couches graphiques (titres, stickers, emoji, fonds)
    renderer    : pipeline ffmpeg de rendu final
    audio_synth : génération de musique et de bruitages
    qa          : contrôle qualité & score de performance
    skills      : bibliothèque de skills (charge, composition, brief)
    cli         : interface en ligne de commande
"""

__version__ = "1.0.0"

from .spec import ShortSpec  # noqa: F401

__all__ = ["ShortSpec", "__version__"]
