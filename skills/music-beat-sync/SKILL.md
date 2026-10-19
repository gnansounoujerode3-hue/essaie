---
name: music-beat-sync
description: Analyse le tempo (BPM), la grille de beats et l'énergie d'une musique sans dépendance lourde, cale les coupes/transition dessus, génère un plan de coupes et des accents visuels sur les temps. Utiliser ce skill pour « synchroniser sur la musique », « trouver le BPM », « caler les coupes sur le beat » ou « montage rythmé ».
license: MIT
metadata:
  version: 1.0.0
  category: audio
  requires: ffmpeg
---

# Beat sync

Décodage FFmpeg → enveloppe RMS → flux d'onsets → autocorrélation → grille de beats
à phase optimisée. Pas de librosa, pas de numpy.

## Quand l'utiliser

- Caler des coupes de montage sur la musique, sans écouter beat par beat.
- Vérifier le BPM d'un morceau avant d'acheter une licence ou de choisir un preset.
- Ajouter des accents visuels (flash, scale) sur les temps forts.
- Détecter les zones d'énergie pour placer les moments calmes et les drops.

## Démarrage rapide

```bash
# Analyse complète
python3 scripts/beat_sync.py --media clip.mp4 --json beats.json --md beats.md

# Plan de coupes toutes les 4 temps + accents visuels flash
python3 scripts/beat_sync.py --media clip.mp4 --cuts-json cuts.json \
  --accent clip-bpm.mp4 --style flash

# Recaler des coupes existantes sur les beats
python3 scripts/beat_sync.py --media clip.mp4 --snap-times cuts.json \
  --snapped-out cuts-synced.json --tolerance 0.25
```

## Ce que renvoie l'analyse

```json
{
  "bpm": 120.19, "period": 0.4992, "confidence": 0.67,
  "beats": [0.697, 1.184, 1.672, …],
  "candidates": [{"bpm": 120.19, "score": …}, …],
  "energy_curve": [{"time": 0.0, "rms": 0.12}, …]
}
```

- **BPM replié** entre 75 et 170 (évite 240 ou 60 pour un même morceau).
- **Phase** choisie en maximisant l'énergie d'onset sur la grille.
- **Confiance** : périodicité de l'autocorrélation + pulse sur la grille (< 12 % = alerte).

## Accents visuels

| Style | Effet |
|-------|-------|
| `flash` | flash blanc 90 ms à chaque beat |
| `bars` | barres noires qui apparaissent |
| `pulse` | micro-zoom/oscillation |

```bash
python3 scripts/beat_sync.py --media clip.mp4 --accent out.mp4 --style pulse --strength 0.2
```

## Options

- `--start` / `--end` : analyser un extrait (utile sur un long morceau).
- `--every 4` : coupe tous les N beats.
- `--tolerance 0.25` : tolérance de recalage (s).
- `--max-accents` (interne) : limite le nombre de beats accentués pour rester fluide.

## Limites

- Le tempo est estimé : vérifier à l'oreille, surtout sur du rubato ou du free tempo.
- Les morceaux à tempo variable (live) donnent une grille moyenne.
- Un morceau sans percussion franche baisse la confiance : utiliser les coupes textuelles
  (`silence-removal-automation`) plutôt que le beat.
- L'accent `flash` sur 200 beats consécutifs est agressif : préférer un beat sur deux
  ou `bars`.

## Suite logique

`sound-effect-cue-automator` (impact sur les beats), `motion-design-templates`
(apparitions calées), `ffmpeg-power-tools`.
