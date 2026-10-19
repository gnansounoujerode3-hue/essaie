---
name: audio-cleaning-enhancer
description: Nettoie et masterise une voix — réduction de bruit, coupe-bas, dé-esseur, EQ, compression, loudness EBU R128 en deux passes — avec isolation ElevenLabs optionnelle. Utiliser ce skill pour « nettoyer l'audio », « supprimer le bruit de fond », « niveau YouTube/Reels » ou « voix de studio ».
license: MIT
metadata:
  version: 1.0.0
  category: audio
  requires: ffmpeg
---

# Nettoyage & mastering audio

Une chaîne unique, mesurée avant/après, avec quatre presets.

## Quand l'utiliser

- Voix enregistrée dans une pièce réverbérante ou avec un bruit de fond constant.
- Podcast ou voix off à livrer au niveau standard des plateformes (−16 LUFS).
- Rush téléphonique à sauver avant montage (preset `aggressive`).
- Voix noyée dans une musique : isolation ElevenLabs quand la clé est disponible.

## Presets

| Preset | Cible | Usage |
|--------|-------|-------|
| `voice` | −16 LUFS, TP −1,5 | YouTube, voix off |
| `podcast` | −16 LUFS, LRA 9 | interview, podcast |
| `social` | −14 LUFS | Reels/TikTok (plus fort) |
| `light` | −16 LUFS | son déjà propre |

## Chaîne appliquée

```
highpass 80 Hz → lowpass 13 kHz → gate → afftdn (denoise) → EQ (shelf + présence + air)
→ dé-esseur → compand (compression douce) → loudnorm 2 passes → alimiter
```

```bash
python3 scripts/clean.py --input interview.wav --out voix.wav --preset podcast \
  --json rapport.json --md rapport.md

python3 scripts/clean.py --input rushes/ --batch --outdir cleaned --preset social
python3 scripts/clean.py --input clip.mp4 --analyze     # mesures seulement
```

## Mesure en deux passes (important)

La première passe mesure la loudness **après** la chaîne de traitement (pas sur le
fichier brut), puis la seconde applique `loudnorm` en mode linéaire. Sans cela,
la compression fausse la mesure et le niveau final dérive (bug classique).
Le rapport affiche LUFS/true peak/bruit de fond avant et après.

## Isolation de la voix (ElevenLabs)

```bash
export ELEVENLABS_API_KEY=…
python3 scripts/clean.py --input bruyant.mp4 --elevenlabs --elevenlabs-out voix.wav \
  --out voix-clean.wav
```

Adobe Podcast Enhance n'a pas d'API publique : `afftdn` local ou ElevenLabs
Audio Isolation sont les options automatisables.

## Options

- `--denoise 0…97` : force la réduction de bruit.
- `--target -14` : change la cible LUFS.
- `--no-loudnorm` : garde la dynamique d'origine.
- `--single-pass` : plus rapide, moins précis.
- `--stereo`, `--sample-rate 48000`.

## Limites

- `afftdn` est un débruiteur spectral : sur une voix très dégradée, il introduit des
  artefacts « métalliques ». Baisser `--denoise` (20–30) plutôt que monter.
- Le dé-esseur nécessite un FFmpeg récent (`deesser`).
- La musique de fond n'est pas séparée : utiliser l'isolation, puis remixer.
- Un limiteur final à 0,97 empêche l'écrêtage, pas une mauvaise prise.

## Suite logique

`sound-effect-cue-automator`, `music-beat-sync`, puis le rendu final.
