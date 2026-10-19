---
name: after-effects-scripting
description: Génère des scripts JSX pour After Effects : composition au bon format, import et placement des rushes, marqueurs, calques de sous-titres animés par keyframes, null de pulsation BPM et sauvegarde du projet. Utiliser ce skill pour « automatiser After Effects », « script JSX AE », « sous-titres animés dans AE » ou « comp depuis un plan ».
license: MIT
metadata:
  version: 1.0.0
  category: nle
  requires: ffmpeg
---

# After Effects : compositions et animations

## Quand l'utiliser

- Monter une composition 1080×1920 (ou autre format) depuis un plan de montage JSON.
- Livrer un `.jsx` autonome à un motion designer qui n'utilise pas le pack.
- Générer des sous-titres keyframés et un pulse audio-réactif sans écrire d'expression à la main.
- Rejouer le même montage sur plusieurs épisodes (le script reste paramétré).

## Générer un script complet

```bash
python3 scripts/build_ae.py --plan edit.json --comp "Short 01" \
  --out ae/assembly.jsx --bpm 120 --save ae/short01.aep

python3 scripts/build_ae.py --media clip.mp4 --transcript t.json --style hormozi \
  --captions-out ae/captions.json --ass ae/captions.ass --out ae/captions.jsx
```

## Ce que fait le JSX

1. Ouvre/crée le projet et la composition (`1080×1920`, fps et durée du plan).
2. Importe chaque rush (`ImportOptions`) et crée un calque par clip.
3. Positionne `startTime`, `inPoint`, `outPoint` avec les timecodes du plan.
4. Ajoute les marqueurs (`MarkerValue`) sur la composition.
5. Crée un calque texte `CAPTIONS` avec une paire de keyframes par événement.
6. Optionnel : null `BEAT PULSE` avec expression de pulsation BPM.
7. Sauvegarde le `.aep` si `--save` est fourni.

Exécution : **After Effects → Fichier → Scripts → Exécuter un fichier de script**.

## Options

- `--plan` ou `--media` (+ `--clips highlights.json`)
- `--comp "Nom"`
- `--transcript` + `--style` : génère les captions ASS + events
- `--captions events.json` : réutilise des événements existants
- `--bpm 120` : ajoute la pulsation rythmique
- `--expression` : affiche une expression beat-reactive à copier-coller

## Expressions fournies

```javascript
var bpmPeriod = 0.5;
var phase = (time % bpmPeriod) / bpmPeriod;
var bump = Math.max(0, 1 - phase * 6);
[100 + bump * 6, 100 + bump * 6];
```

À coller sur l'échelle d'un calque pour un « pump » sur chaque temps.

## Limites

- Le JSX suppose des rushes déjà accessibles sur le disque local.
- Les sous-titres sont des keyframes de texte : le style riche (couleur par mot) doit
  être appliqué dans AE ou via les fichiers ASS (importés par un script tiers).
- Pas de rendu : AE doit être ouvert pour exécuter le script.
- Les marqueurs de composition ne sont pas transférés dans Premiere (utiliser le skill
  Premiere pour cela).

## Suite logique

`premiere-pro-extendscript-generator` pour le montage, `davinci-resolve-python-api`
pour l'étalonnage.
