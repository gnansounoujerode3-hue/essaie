---
name: broll-finder-indexer
description: Indexe une bibliothèque de rushes, cherche les B-rolls correspondant à chaque phrase d'une transcription (recherche lexicale ou sémantique CLIP), télécharge des séquences libres de droits (Pexels/Pixabay) et produit un plan de montage. Utiliser ce skill pour « trouver des B-rolls », « illustrer un texte », « chercher des images libres de droits » ou « indexer mes rushes ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg
---

# B-rolls : index, recherche, téléchargement

## Quand l'utiliser

- Retrouver un B-roll pertinent dans des milliers de rushes mal nommés.
- Habiller chaque phrase d'une interview avec un plan d'illustration.
- Compléter une bibliothèque avec des séquences libres de droits (Pexels/Pixabay).
- Sortir un plan de B-rolls importable dans Premiere, Resolve ou After Effects.

## 1. Indexer

```bash
python3 scripts/index_library.py --library ~/Footage --library ~/Downloads/broll \
  --out library.json
```

L'index contient : chemin, type (vidéo/image), durée, résolution, fps, tags déduits
du nom de fichier, description issue d'un sidecar `.txt`/`meta.json`.

**Nommer les rushes proprement est le levier n°1** :
`cafe-matin-pluie-01.mp4` sera trouvé pour « café pluvieux », `VID_20240112.mp4` non.

## 2. Chercher pour une transcription

```bash
python3 scripts/find_broll.py --manifest library.json --transcript interview.json \
  --out broll-plan.json --md broll-plan.md --csv broll.csv
```

Chaque phrase reçoit un B-roll, une fenêtre (`clip_in` → `clip_out`) et un score.
La sélection évite les répétitions et alterne les assets si aucune correspondance
n'existe.

### Recherche sémantique (CLIP)

```bash
pip install torch transformers pillow
python3 scripts/index_library.py --library ~/Footage --out library.json --semantic
python3 scripts/find_broll.py --manifest library.json --transcript t.json --semantic
```

CLIP compare le **sens** d'une phrase au contenu visuel (images et frames vidéo
échantillonnées à 12 %, 50 %, 88 %). Le cache `.vesk-index.json` évite de recalculer.

## 3. Télécharger des séquences libres de droits

```bash
export PEXELS_API_KEY=…      # https://www.pexels.com/api/ (gratuit)
python3 scripts/fetch_stock.py --query "cafe matin" --count 8 --out ./broll

export PIXABAY_API_KEY=…     # https://pixabay.com/api/docs/
python3 scripts/fetch_stock.py --query "city night" --provider pixabay --orientation portrait
```

`licenses.json` conserve l'auteur, la page et la licence de chaque fichier : à garder
avec le montage.

## Recherche rapide sans transcription

```bash
python3 scripts/find_broll.py --manifest library.json --query "bureau nuit" --top 10
```

## Options

- `--min-duration`, `--orientation vertical|horizontal|square`
- `--min-clip 2 --max-clip 5` : durée d'insertion (bornée par le rush)
- `--top 8` : candidats évalués par phrase
- `--reuse` : autorise la réutilisation d'un asset
- `--semantic`, `--cache .vesk-index.json`

## Limites

- Recherche lexicale = correspondance de mots, pas de synonymes : fournir des sidecars
  (`cafe-matin.txt` contenant « café, matin, pluie, fenêtre ») améliore nettement le résultat.
- CLIP nécessite torch (téléchargement lourd) et reste approximatif sur les concepts abstraits.
- Les banques gratuites imposent parfois une attribution : `licenses.json` la fournit.
- Aucune génération d'image ici : voir `ai-image-video-generator`.

## Suite logique

`ai-image-video-generator` quand la banque ne suffit pas, puis
`premiere-pro-extendscript-generator` ou `davinci-resolve-python-api` pour placer les B-rolls.
