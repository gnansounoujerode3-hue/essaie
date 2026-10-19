---
name: ffmpeg-power-tools
description: Boîte à outils FFmpeg par lot — sonde, compression (CRF ou taille cible), conversion, découpe précise, concaténation, GIF optimisé, vignettes/planche contact, sous-titres incrustés, extraction audio, mesure LUFS et batch sur dossier. Utiliser ce skill pour « compresser une vidéo », « convertir », « découper », « faire un GIF » ou « traiter un dossier entier ».
license: MIT
metadata:
  version: 1.0.0
  category: technique
  requires: ffmpeg
---

# FFmpeg : traitement par lot

## Quand l'utiliser

- Compresser une vidéo pour Discord, WhatsApp ou un upload limité en taille.
- Découper, concaténer, convertir ou extraire l'audio sans ouvrir un NLE.
- Produire un GIF, une vignette ou une planche contact pour une miniature.
- Traiter un dossier entier (batch) avec les mêmes réglages.

## Commandes

| Commande | Rôle |
|----------|------|
| `probe` | métadonnées (durée, codecs, résolution, fps, audio) |
| `compress` | H.264 CRF **ou** taille cible (2 passes) |
| `convert` | remux sans perte ou transcodage |
| `cut` | découpe copie rapide ou réencodage exact |
| `merge` | concaténation |
| `audio` | extraction / remplacement / mixage, gain dB |
| `gif` | GIF palette optimisée |
| `thumbnail` | une ou plusieurs vignettes |
| `contact` | planche de vignettes (5×4 par défaut) |
| `hardsub` | incrustation SRT/ASS |
| `loudness` | mesure LUFS / true peak |
| `batch` | compress ou convert sur un dossier |

```bash
python3 scripts/ffmpeg_tool.py probe clip.mp4 --json
python3 scripts/ffmpeg_tool.py compress clip.mov -o clip.mp4 --target-size 25
python3 scripts/ffmpeg_tool.py compress clip.mov -o clip.mp4 --crf 23 --scale 1080:-2
python3 scripts/ffmpeg_tool.py cut clip.mp4 -o extract.mp4 --start 12 --duration 8 --reencode
python3 scripts/ffmpeg_tool.py merge a.mp4 b.mp4 -o ab.mp4
python3 scripts/ffmpeg_tool.py gif clip.mp4 -o anim.gif --start 1 --duration 3 --width 480
python3 scripts/ffmpeg_tool.py contact clip.mp4 -o planche.jpg --interval 2
python3 scripts/ffmpeg_tool.py hardsub clip.mp4 --subtitles subs.ass -o out.mp4
python3 scripts/ffmpeg_tool.py batch ./rushes --outdir ./compressed --crf 26 --scale 720:-2
```

## Choisir compression / taille cible

- **CRF** (qualité constante) : 18 quasi transparent, 23 bon compromis, 28 léger.
- **Taille cible** : calcule le bitrate vidéo = `taille×8×1024/durée − audio` puis
  encode en 2 passes. Plafonné par `--max-bitrate` et plancher à 120 kb/s.
- `--scale 1080:-2` conserve le ratio (hauteur paire).

## Découpe : copie ou réencodage

- Sans `--reencode` : instantané, mais la coupe tombe sur la keyframe précédente.
- Avec `--reencode` : précise à la frame, plus lente.

## Détection de FFmpeg

Ordre : `$FFMPEG_BIN` → `ffmpeg` du PATH → roue `imageio-ffmpeg` → chemins usuels.
`ffprobe` est optionnel : un repli lit `ffmpeg -i` (sans flux détaillés).

## Limites

- La concaténation suppose des codecs/paramètres identiques ; sinon réencoder d'abord.
- `hardsub` nécessite libass.
- Les noms de fichiers avec caractères spéciaux sont gérés, mais éviter les `:` sur Windows.
- Le batch ne parallélise pas (choix de stabilité) : lancer plusieurs processus à la main
  pour saturer un gros CPU.

## Suite logique

Tous les autres skills produisent des fichiers que celui-ci peut finaliser.
