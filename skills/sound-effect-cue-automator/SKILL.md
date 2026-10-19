---
name: sound-effect-cue-automator
description: Détecte les transitions, pop-ups, mots-clés et apparitions de sous-titres pour y placer automatiquement des effets sonores (whoosh, pop, braam, camera click, riser, impact) et mixe la piste SFX dans la vidéo. Utiliser ce skill pour « ajouter des effets sonores », « sound design automatique », « whoosh sur les transitions » ou « pop sur les mots ».
license: MIT
metadata:
  version: 1.0.0
  category: audio
  requires: ffmpeg
---

# Sound design automatique

## Quand l'utiliser

- Ajouter du rythme à un Short sans bibliothèque payante (SFX générés, libres de droits).
- Marquer les transitions, les questions et les mots-clés avec des sons.
- Poser une piste SFX complète mixée dans la vidéo, en une commande.
- Réutiliser le même catalogue pour une série, avec un rendu cohérent.

## 1. Fabriquer le pack de SFX (une fois)

```bash
python3 scripts/build_catalog.py --generate --out ./sfx
```

8 effets synthétisés par FFmpeg (lavfi), donc **libres de droits** : whoosh, pop,
braam, camera click, riser, impact, tick, swoosh.

## 2. Détecter les cues

```bash
python3 scripts/plan_cues.py --transcript interview.json --media interview.mp4 \
  --keywords keywords.json --caption-events events.json --detect-scenes \
  --sfx-dir ./sfx --out cues.json --md cues.md --csv cues.csv
```

Règles appliquées :

| Moment détecté | SFX |
|----------------|-----|
| Début de vidéo | whoosh (ou braam) |
| Reprise après un silence > 0,3 s | whoosh |
| Fin de question | tick |
| Mot-clé (emoji/keywords) | pop |
| Changement de plan (OpenCV) | whoosh |
| Apparition de sous-titre (1 sur 3) | pop |
| Respiration rythmique toutes ~3 s | swoosh |

Déduplication par fenêtre (`--min-spacing 0.22`) et priorité : un mot-clé et une
coupe au même instant ne produisent qu'un son.

## 3. Rendre et mixer

```bash
python3 scripts/plan_cues.py --transcript t.json --media clip.mp4 \
  --keywords keywords.json --wav sfx.wav --mix clip-sfx.mp4 \
  --sfx-gain 0 --original-gain 0 --sfx-dir ./sfx
```

Le mix utilise `amix` avec `normalize=0` : la voix garde son niveau, les SFX sont
ajoutés. Gains par effet dans `sfx-catalog.json` (whoosh −10 dB, pop −14 dB…).

## Personnaliser

```bash
python3 scripts/plan_cues.py --styles '{"intro":"braam","transition":"swoosh",
  "question":"pop","keyword":"impact","cut":"whoosh"}' …
```

Remplacer un WAV dans `./sfx` par un son de meilleure qualité (même nom) est
immédiatement pris en compte.

## Sorties

- `cues.json` / `cues.csv` : timecodes, effet, gain, raison.
- `cues.md` : tableau lisible.
- `sfx.wav` : piste 48 kHz prête à importer dans un NLE.
- `clip-sfx.mp4` : vidéo finale mixée.

## Limites

- La détection de plans (OpenCV) est optionnelle et rapide/approximative.
- Un placement automatique doit être **écouté** : trop de « pop » fatigue.
  Commencer avec `--max-cues 80` sur une vidéo d'une minute.
- Sans pack SFX généré, les cues pointent vers des fichiers absents (le script prévient).

## Suite logique

`audio-cleaning-enhancer` (voix propre), `music-beat-sync` (musique calée),
`ffmpeg-power-tools` (export final).
