---
name: auto-framing-916
description: Recadre intelligemment une vidéo horizontale 16:9 en vertical 9:16 en suivant le visage du locuteur (OpenCV), avec repli centré ou fond flou. Utiliser ce skill pour « passer en vertical », « recadrer en 9:16 », « format Shorts/Reels/TikTok » ou « suivi de visage ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg, opencv-python-headless (suivi de visage)
---

# Recadrage 16:9 → 9:16

Trois stratégies, une seule commande.

| Mode | Principe | Quand |
|------|----------|-------|
| `face` (défaut) | suivi du visage → keyframes → expression de recadrage | interview, talking head |
| `center` | coupe centrée puis upscale | plan large, sujet centré |
| `blur` | fond flouté + vidéo centrée | quand le recadrage coupe trop |

```bash
# Suivi de visage + rendu
python3 scripts/reframe.py --media interview.mp4 --out interview-916.mp4

# Fond flou
python3 scripts/reframe.py --media podcast.mp4 --out podcast-916.mp4 --mode blur

# Batch + export des keyframes pour réutilisation
python3 scripts/reframe.py --batch ./rushes --outdir ./vertical \
  --mode face --analyze faces.json
```

## Quand l'utiliser

- Transformer une interview 16:9 en Short/Reel 9:16 sans perdre le visage.
- Recadrer un plan à deux personnes ou un plan large où le sujet bouge.
- Produire une version verticale « fond flou » quand le suivi est impossible.
- Décliner une même vidéo en 9:16, 1:1 et 4:5 pour plusieurs plateformes.

## Comment le suivi fonctionne

1. Échantillonnage d'une frame toutes les `--interval` secondes (0,5 s par défaut),
   plafonné à 180 échantillons.
2. Détection Haar (face + profil) sur une image égalisée.
3. Lissage par médiane glissante, interpolation des trous.
4. Génération d'une **expression FFmpeg** `if(lt(t,…), …)` interpolant linéairement
   le centre du visage entre keyframes (limitée à 90 points pour rester rapide).
5. Recadrage `crop=…:x='<expression>'` puis scale Lanczos 1080x1920.

Si aucun visage n'est trouvé, le script bascule automatiquement en `center` et le dit.

## Options

- `--mode auto|center|blur|face`
- `--keyframes faces.json` : réutilise des keyframes existantes (rendu sans OpenCV)
- `--analyze faces.json` : écrit les keyframes détectées
- `--width 1080 --height 1920`, `--crf`, `--preset`
- `--batch DOSSIER --outdir DOSSIER`

## Limites

- Haar est rapide mais moins précis que des modèles de segmentation : sur des visages
  de profil ou très petits, préférer `blur` ou un recadrage manuel.
- Les scènes à plusieurs visages suivent le plus grand détecté (pas de sélection).
- Le recadrage ne réinvente pas l'image : un plan 16:9 avec deux personnes côte à côte
  perdra l'une des deux. Découper le plan en amont.
- Le fichier source 1080p vertical reste 1080p : pas de gain de définition.

## Suite logique

`animated-captions-generator` (canvas 1080x1920 par défaut), `motion-design-templates`.
