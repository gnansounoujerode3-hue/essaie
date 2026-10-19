---
name: retention-chart-analyzer
description: Analyse les courbes de rétention YouTube exportées en CSV (ou un dossier d'exports) — décrochages, pics, zones faibles, croisement avec la transcription — et produit des recommandations de montage. Utiliser ce skill pour « analyser la rétention », « pourquoi les gens partent », « courbe YouTube » ou « optimiser une vidéo existante ».
license: MIT
metadata:
  version: 1.0.0
  category: optimisation
  requires: rien
---

# Analyse de rétention

## Quand l'utiliser

- Comprendre où et pourquoi les spectateurs quittent une vidéo.
- Croiser un décrochage avec la phrase prononcée à ce moment précis.
- Comparer deux vidéos ou plusieurs épisodes d'une série.
- Décider quoi couper avant de remonter une vidéo qui performe mal.

## Export CSV attendu

Depuis YouTube Studio → Analytics → Rétention → Exporter (CSV).
Colonnes reconnues (insensibles à la casse) :

- temps : `elapsed_video_time_seconds`, `video_time`, `time`, `position`…
- rétention : `audience_watch_ratio`, `watch_ratio`, `retention`…
- vues : `views`, `audience`…

Les formats `mm:ss` et `1:02:03` sont acceptés ; les pourcentages avec virgule aussi.

```bash
python3 scripts/analyze_retention.py --csv retention.csv --md rapport.md --json data.json

# Comparer plusieurs vidéos (courbe moyenne par position relative)
python3 scripts/analyze_retention.py --all exports/ --json compare.json --md compare.md

# Croiser les décrochages avec ce qui est dit
python3 scripts/analyze_retention.py --csv retention.csv --transcript t.json --md croise.md
```

## Ce que le rapport calcule

- Rétention au départ, à 5 %, à 50 %, à la fin.
- **Décrochages** sur une fenêtre glissante (`--window 5`) au-delà de `--min-drop 3` points,
  fusionnés et triés par gravité.
- **Pics** de rétention (ce qui retient).
- Recommandations contextuelles : chute dans les 15 premières secondes → hook ;
  chute en fin → outro trop long, etc.
- En mode `--all` : courbe moyenne par tranche de 5 % et zones faibles communes.

## Options

- `--window 5` : fenêtre d'analyse (s).
- `--step 1` : rééchantillonnage (s).
- `--min-drop 3` : seuil de détection (points de %).
- `--transcript` : associe chaque drop à la phrase prononcée.

## Limites

- Les exports varient selon les versions de YouTube Studio : si les colonnes ne sont pas
  reconnues, le fichier est ignoré avec un message explicite (et non une erreur bloquante).
- La rétention mélange souvent plusieurs audiences (abonnés, suggestions) : comparer
  des vidéos de même durée et même format.
- Corrélation ≠ causalité : un drop n'est pas forcément causé par la phrase affichée.

## Suite logique

`viral-hooks-library` (nouveau hook), `highlight-detector-ai` (couper les passages faibles),
`silence-removal-automation` (rythme).
