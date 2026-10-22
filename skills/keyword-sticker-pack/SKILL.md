---
name: keyword-sticker-pack
description: Planificateur de stickers synchronisés sur les mots — pop d'objet (clé, cerveau, potion, ampoule…) et bulles d'icônes en cercle près du visage, en sortie JSON + commande FFmpeg prête, aliments par Twemoji 72px agrandis. Utiliser ce skill pour « sticker sur un mot », « bulle icône près du visage », « emoji contextuel ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg, Twemoji (PNG fetch via gh api)
---

# Stickers de mots-clés : pops d'objets + bulles-contexte

Les refs placent un **objet illustrant le mot** (v7 : 🔑 sur « The Secrets »,
🧠 sur « Execution ») et des **bulles d'icônes rondes près du visage** (v6 :
megaphone à « about », poignée de main à « closing »). Nous n'avons que des
emojis d'angle : ce skill industrialise les deux patterns.

## Quand l'utiliser

- P1 « sticker objet » : illustrer un mot-clé par un objet 3D/emoji géant (1,1 s).
- P1 « bulle-contexte » : icône ronde en cercle blanc à côté du visage, timing = mot.
- Remplacer les pops d'angle fixes par des positions variées (near-face, center, corner).

## Démarrage rapide

```bash
# 1. PNG Twemoji (si absents) — 5s, via l'API GitHub :
gh api -H "Accept: application/vnd.github.raw" \
  repos/jdecked/twemoji/contents/assets/72x72/1f511.png > twemoji/1f511.png
# 2. Plan à partir d'un JSON de mots horodatés :
python3 scripts/plan_stickers.py events.json --style bubble --size 240 -o plan.json
# 3. Aperçu de la commande FFmpeg :
python3 scripts/plan_stickers.py events.json --style pop --print-cmd
```

`events.json` : `[{"t": 11.5, "word": "clé", "dur": 1.1}, …]`

## Dictionnaire objet par défaut (extrait)

clé→1f511, cerveau→1f9e0, potion→1f9ea, ampoule→1f4a1, argent→1f4b0,
feu→1f525, flèche haut→2b06, warning→26a0, cochon→1f437, maison→1f3e0,
coup de sifflet→1f4ef, poignée→1f91d, message→1f4ac, horloge→23f0.

## Styles de placement

| Style | Géométrie | Usage |
|-------|-----------|-------|
| `pop` | coin haut-droite, 216 px, bump `sin(PI·t/0.4)` | pops actuels, mots-args |
| `bubble` | x = visage+180 px, y ≈ 38 % H, cercle blanc 260 px + icône 150 px | icône-contexte v6 |
| `center` | centre haut, 320 px, fade+scale | objet-clé v7 (🔑🧠) |

## Commandes des scripts

- `python3 scripts/plan_stickers.py events.json --style pop` — plan JSON (coin)
- `python3 scripts/plan_stickers.py events.json --style bubble --face-x 540` — bulles près du visage
- `python3 scripts/plan_stickers.py events.json --print-cmd` — commande FFmpeg collage des enables

## Positionnement exact

`overlay=x=…:y=…:enable='between(t,S,S+DUR)'` avec fenêtres **1,0-1,2 s**,
position recalculée par phrase (les refs ne répètent jamais 3 fois le même coin).
Voir `emoji-keyword-mapper` (sélection mot→emoji) et
`caption-hierarchy-styles` (le sous-titre reste en hiérarchie blanche+accent).
