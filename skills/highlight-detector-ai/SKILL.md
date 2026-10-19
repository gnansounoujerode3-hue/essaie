---
name: highlight-detector-ai
description: Détecte automatiquement les hooks et moments forts d'une vidéo en combinant contenu (questions, contrase, chiffres, mots forts) et énergie vocale, puis sort des clips prêts à publier avec sous-titres optionnels. Utiliser ce skill pour « trouver les meilleurs moments », « extraire des clips », « détecter les hooks » ou « faire des Shorts/Reels ».
license: MIT
metadata:
  version: 1.0.0
  category: analyse
  requires: ffmpeg
---

# Détection de hooks & moments forts

Scoring 0–100 par phrase, puis assemblage de **clips non chevauchants** de 18 à 45 s.

## Quand l'utiliser

- Extraire 5 à 20 clips courts d'un podcast ou d'un live de plusieurs heures.
- Trouver le meilleur hook d'une vidéo avant de publier.
- Prioriser le montage quand le temps est limité (les 3 meilleurs moments d'abord).
- Alimenter `auto-framing-916` puis `animated-captions-generator` pour un Short complet.

## Score = 4 signaux + 1 bonus

```
score = 100 × (0.42·sémantique + 0.24·énergie vocale + 0.16·débit + 0.12·richesse
                + 0.06·durée) + bonus de position
```

- **Sémantique** : question, contraste (`mais`, `pourtant`, `jamais`), chiffres,
  mots forts (secret, erreur, argent, preuve…), promesse, interpellation.
- **Énergie vocale** : RMS moyen + pic, mesurés avec FFmpeg sur chaque phrase.
  Si aucun média n'est fourni, une valeur neutre est utilisée.
- **Débit** : mots/seconde (le dynamisme retient).
- **Richesse** : proportion de mots rares (évite le remplissage).

Chaque phrase est typée : `question`, `contrarian`, `promesse`, `valeur`,
`resultat`, `story`.

## Démarrage rapide

```bash
# Rapport seul
python3 scripts/detect.py --media podcast.mp4 --language fr \
  --clips 6 --min 18 --max 45 --json clips.json --md clips.md

# Rendu des clips + sous-titres Hormozi incrustés
python3 scripts/detect.py --transcript podcast.transcript.json --media podcast.mp4 \
  --render-dir clips/ --captions hormozi
```

## Options

- `--clips N` : nombre maximum de clips.
- `--min` / `--max` : durée cible (rallonge avec les phrases voisines).
- `--padding 0.12` : marge avant/après.
- `--captions STYLE` : incruste les sous-titres (`hormozi`, `ali`, `karaoke-pop`…).
- `--crf`, `--preset` : réglages d'encodage.

## Sorties

- `clips.json` : phrases scorées, top hooks, clips (timecodes source), chemins rendus.
- `clips.md` : rapport lisible avec tableau des clips et explication des signaux.
- `clips/clip-01-….mp4` : extraits rendus (–captioned si demandé).

## Limites

- Le scoring est **lexical + énergétique**, pas un modèle de langage : il ne comprend pas
  le sens profond. Relire les clips proposés, surtout le début (le hook doit tenir en 1,5 s).
- Sans audio exploitable (musique seule), l'énergie est neutre : le classement repose
  sur le texte.
- Les clips peuvent se chevaucher si `--min` est très grand : le script les écarte.

## Suite logique

`animated-captions-generator` (style), `auto-framing-916` (recadrage),
`viral-hooks-library` (variantes d'accroche), `premiere-pro-extendscript-generator`
(pour retravailler les clips dans le NLE).
