---
name: premiere-pro-extendscript-generator
description: Convertit un plan de montage JSON en FCPXML/XMEML/EDL et en scripts ExtendScript (JSX) pour Adobe Premiere Pro : import des rushes, création de séquence, placement des clips, marqueurs et export. Utiliser ce skill pour « automatiser Premiere Pro », « importer un montage », « script ExtendScript » ou « échanger avec un monteur ».
license: MIT
metadata:
  version: 1.0.0
  category: nle
  requires: ffmpeg
---

# Premiere Pro : plans, XML et scripts

## Quand l'utiliser

- Livrer un montage à un monteur Premiere depuis un plan JSON.
- Générer une timeline exacte (FCPXML) plutôt qu'un simple EDL approximatif.
- Automatiser l'import des rushes, le placement et l'export via JSX.
- Ajouter des marqueurs de brief (hook, CTA, relance) dans la timeline.

## Plan de montage (format pivot)

```json
{
  "name": "Short 01",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "clips": [
    {"source": "rushes/demo.mp4", "in": 0.2, "out": 3.8},
    {"source": "broll/cafe.mp4", "in": 0, "out": 2.5},
    {"source": "rushes/demo.mp4", "in": 8.0, "out": 12.0}
  ]
}
```

`in`/`out` sont des timecodes **source** ; la position sur la timeline est calculée
en séquence (ou fournie via `timeline_start`).

## Générer les échanges

```bash
python3 scripts/build_premiere.py --plan edit.json --out-prefix premiere/edit \
  --jsx premiere/import.jsx --jsx-markers premiere/markers.jsx \
  --jsx-export premiere/export.jsx --preset h264-1080p.epr
```

Sorties : `.fcpxml` (import natif Premiere 2020+), `.xml` (XMEML legacy),
`.edl` (conform conformé), `-markers.csv`, et les JSX.

## Les scripts ExtendScript

- `import.jsx` : importe les rushes, crée/retrouve la séquence, place les clips
  (positions absolues, chemins absolus), ajoute les marqueurs.
- `markers.jsx` : ajoute uniquement les marqueurs à la séquence active.
- `export.jsx` : lance l'encodage via `app.encoder.encodeSequence` avec un preset `.epr`.

Exécution : **Premiere Pro → Fichier → Scripts → Exécuter un script**.

## Options

- `--media` + `--clips highlights.json` : construit le plan depuis les moments forts.
- `--formats fcpxml,xml,edl,markers`
- `--fps`, `--width`, `--height`, `--name`
- `--summary-json` : exporte le plan normalisé.
- `--dry-run` : affiche le FCPXML sans écrire.

## Limites et pièges

- Les API ExtendScript de Premiere dépendent de la version : le placement utilise
  `overwriteClip` (2020+) avec repli sur `insertClip`.
- Les chemins doivent exister sur la machine du monteur : le FCPXML utilise des
  `file://localhost/…` absolus.
- Un `.fcpxml` importé dans Premiere peut demander de relier les médias si les fichiers
  ont été déplacés.
- Les effets/transitions ne sont pas générés (pas d'API ExtendScript stable) : les
  appliquer dans Premiere ou passer par After Effects.

## Suite logique

`after-effects-scripting` pour les animations, `davinci-resolve-python-api` pour
l'étalonnage et le rendu.
