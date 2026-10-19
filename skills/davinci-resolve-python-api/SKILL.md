---
name: davinci-resolve-python-api
description: Prépare un job DaVinci Resolve : FCPXML de timeline, script Python Resolve (import, marqueurs, LUT, réglages de rendu, lancement du rendu) et script de color grading CDL. Utiliser ce skill pour « automatiser Resolve », « script Python DaVinci », « étalonnage automatique » ou « rendu batch ».
license: MIT
metadata:
  version: 1.0.0
  category: nle
  requires: ffmpeg, DaVinci Resolve (Studio pour l'API scripting)
---

# DaVinci Resolve : timeline, étalonnage, rendu

## Quand l'utiliser

- Automatiser l'assemblage d'un montage dans Resolve (timeline exacte depuis un plan JSON).
- Poser des marqueurs de montage et lancer un rendu sans cliquer.
- Appliquer une LUT et un étalonnage CDL reproductible sur plusieurs épisodes.
- Préparer un job de rendu la nuit sur une machine dédiée.

## Générer le job

```bash
python3 scripts/build_resolve.py --plan edit.json --out-prefix resolve/short01 \
  --timeline "Short 01" --lut LUTs/look.cube --render-dir ~/Renders \
  --format mp4 --codec H264 --color --contrast 1.08 --saturation 1.1
```

Produit :

- `resolve/short01.fcpxml` — timeline exacte (positions, in/out).
- `resolve/short01-resolve.py` — import de la timeline, marqueurs, LUT, rendu.
- `resolve/short01-color.py` — LUT + CDL (slope/offset/power/sat) sur la piste 1.
- `resolve/short01-job.json` — résumé machine.

## Exécution dans Resolve

1. Copier `short01-resolve.py` dans le dossier Scripts de Resolve
   (macOS : `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit`).
2. Ouvrir Resolve avec un projet chargé.
3. **Workspace → Scripts → short01-resolve**.

Le script règle la fréquence/résolution du projet, importe le FCPXML, ajoute les
marqueurs (`AddMarker`), applique la LUT (`SetLUT`) et lance `AddRenderJob` +
`StartRendering`.

## Notes importantes

- L'API scripting est **gratuite** en version Studio ; en version gratuite, elle est
  limitée (vérifier la version de Resolve installée).
- Le script est généré puis **validé syntaxiquement** par le skill (`compile()`),
  pour éviter un échec silencieux dans Resolve.
- Sans FCPXML, le script fait un `AppendToTimeline` séquentiel : les positions exactes
  du plan ne sont pas garanties. Le FCPXML est la voie fiable.
- `SetCDL` attend une chaîne `"r g b"` : le script la construit depuis `--contrast`,
  `--saturation`, `--temperature`.

## Options

- `--plan` ou `--media` + `--clips`
- `--timeline "Nom"`, `--fps`, `--width`, `--height`
- `--lut chemin.cube`
- `--render-dir`, `--preset fichier.xml`, `--format mp4`, `--codec H264`
- `--color`, `--contrast`, `--saturation`, `--temperature`
- `--dry-run` : affiche FCPXML + script sans écrire.

## Limites

- Le rendu dépend d'un preset/codec installé dans Resolve.
- L'étalonnage CDL est global : pour un vrai grading par plan, générer un script
  par clip ou affiner dans Resolve.
- L'API n'expose pas les nœuds Fusion : les effets restent manuels.

## Suite logique

`ffmpeg-power-tools` pour les conversions finales, `retention-chart-analyzer` pour
mesurer le résultat.
