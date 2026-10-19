---
name: silence-removal-automation
description: Détecte et supprime ou accélère automatiquement les silences et hésitations d'une vidéo, avec remapping exact des sous-titres et rendu multi-coupes en une passe. Utiliser ce skill pour « couper les blancs », « auto-cut », « accélérer les silences » ou « donner du rythme » à un montage.
license: MIT
metadata:
  version: 1.0.0
  category: montage
  requires: ffmpeg
---

# Auto-cut des silences

Supprime le vide sans casser la parole : chaque phrase garde une respiration de
quelques dizaines de millisecondes.

## Quand l'utiliser

- Resserer un podcast ou un tuto plein d'hésitations et de blancs.
- Accélérer les silences d'un vlog plutôt que les supprimer (mode `speed`).
- Dérusher un rush avant transcription pour réduire le temps de calcul.
- Garder les sous-titres parfaitement synchronisés après les coupes.

## Deux modes

| Mode | Résultat | Usage |
|------|----------|-------|
| `remove` (défaut) | les silences sont **supprimés** | Shorts/Reels nerveux, podcast resserré |
| `speed` | les silences sont **accélérés** (×N) | time-lapse de blancs, transitions douces |

```bash
# Suppression avec rendu final
python3 scripts/cut_silences.py --media interview.mp4 --render interview-cut.mp4 \
  --transcript interview.transcript.json --srt interview-cut.srt \
  --json plan.json --md plan.md

# Accélération ×8 des blancs (garde la continuité temporelle)
python3 scripts/cut_silences.py --media vlog.mp4 --mode speed --speed 8 --render vlog-fast.mp4

# Simuler sans rendre
python3 scripts/cut_silences.py --media talk.mp4 --dry-run --json plan.json
```

## Pourquoi ce n'est pas un simple `-af silenceremove`

1. **Détection visuelle + audio** : `silencedetect` renvoie les bornes exactes.
2. **Marge de respiration** (`--margin 0.08`) autour de chaque phrase.
3. **Rendu multi-plages en une seule passe** avec `trim`/`atrim` + `concat`
   (précision à la frame, pas de dérive du concat demuxer).
4. **Remapping des sous-titres** : un `TimeMap` projette chaque mot du montage
   source vers le montage final, y compris quand une phrase est coupée en deux.

## Options

- `--noise-db -35` : seuil de silence (dB).
- `--min-silence 0.35` : ne traite que les blancs plus longs.
- `--margin 0.08` : respiration conservée autour de la parole.
- `--speed 6` : facteur d'accélération en mode `speed` (atempo chaîné si > 2).
- `--crf 18 --preset medium` : qualité/rapidité du rendu H.264.

## Sorties

- `plan.json` : plages source → montage, durée finale, gain en secondes/%.
- `plan.md` : tableau des coupes et des silences les plus longs.
- `*cut.srt` : sous-titres recalés sur le montage final.
- `--render` : MP4 H.264 + AAC, audio rééchantillonné à 48 kHz.

## Limites

- Un seuil trop haut mange les fins de phrases ; un seuil trop bas laisse passer le souffle.
  Toujours vérifier 20 secondes de rendu avant de lancer 1 h.
- L'ambiance (musique de fond) empêche `silencedetect` de voir les blancs : nettoyer
  l'audio ou baisser le seuil (`--noise-db -25`).
- Les coupes sont des coupes franches : ajouter un `whoosh` (sound-effect-cue-automator)
  ou un léger crossfade si le rendu sonne sec.

## Suite logique

`highlight-detector-ai` pour choisir les meilleurs extraits, puis
`animated-captions-generator` avec le SRT remappé.
