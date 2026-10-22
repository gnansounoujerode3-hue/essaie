---
name: caption-hierarchy-styles
description: Hiérarchie de sous-titres façon refs (base blanche + un mot-clé en couleur/style par phrase, boîtes surlignées, serif italique, dégradé, glow, hook burst 3 s) + lint ASS qui détecte les chemins vectoriels rendus en texte et autres grilles cassées. Utiliser ce skill pour « sous-titres hiérarchisés », « mot-clé en couleur », « corriger un sous-titre cassé », « hook animé ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg (libass)
---

# Hiérarchie de sous-titres + lint ASS

Les 7 vidéos de référence traitent **un seul mot-clé par phrase** (couleur,
italique, boîte, glow) sur une base **blanche** : c'est cette hiérarchie qui
donne le rendu « propre » — pas le jaune uniforme.

## Quand l'utiliser

- P0 : passer d'un sous-titre monochrome à une base blanche + accent par phrase.
- P0 : vérifier un `.ass` avant burn (bug flèche/`m -8018 0 18` = chemin en texte).
- P2 : hook burst sur les 3 premières secondes (mots qui claquent 1 à 1).

## Démarrage rapide

```bash
python3 scripts/ass_lint.py montage.ass            # 0 = propre, 1 = grilles cassées
python3 scripts/ass_lint.py montage.ass --json
```

## Presets de hiérarchie (styles ASS)

| Ref | Style du mot-clé | StyleNames |
|-----|------------------|------------|
| v1 jaune + glow | `PrimaryColour=&H0000E5FF, Bold=1, BorderStyle=1, Outline=4, Shadow=1` | `KeyYellow` |
| v5 boîte rouge | événement avec `{\pos}` + rectangle `{\an5\1c&H2E34FF&}` de fond (boîte) | `BoxRed` |
| v7 highlight vert | `PrimaryColour=&H0080FF00, Bold=1` | `KeyGreen` |
| v2 serif italique violet | `Fontname=DejaVu Serif, Italic=1, PrimaryColour=&H00D98BFF` | `AccentViolet` |
| v4 script rouge | `Fontname=DejaVu Serif, Italic=1, PrimaryColour=&H003030F0` | `ScriptRed` |
| v6 dégradé bleu | deux passes : mot en `Bold=1` bleu clair, `\t(\fscx)` pop d'échelle | `AccentBlue` |
| base (tous) | blanc `&H00FFFFFF`, Outline 4, Shadow 1, Fontsize 74@1080 | `Base` |

Règle : **mot actif = accent, mots voisins = base blanche** ; jamais tout en accent.

## Hook burst (P2, 0-3 s)

```
Dialogue: 0,0:00:00.10,0:00:00.55,Base,,0,0,0,,{\fad(60,0)\fscx60\fscy60\t(0,120,\fscx110\fscy110)}LE
Dialogue: 0,0:00:00.45,0:00:00.95,Base,,0,0,0,,{\fad(60,0)\t(0,120,\fscx110\fscy110)}PLUS
```
(une fenêtre ~0,4 s par mot, recouvrement 0,1 s, scale 60→110 ; finir sur
`KeyYellow` pour le mot de tension.)

## Commandes des scripts

- `python3 scripts/ass_lint.py montage.ass` — détecte chemins rendus en texte, accolades déséquilibrées, événements anormaux
- `python3 scripts/ass_lint.py montage.ass --json` — rapport machine avant burn

## Vérification après burn

```bash
ffmpeg -ss 27.5 -i out.mp4 -frames:v 1 ctrl_text.png   # mot-clé seul en accent ?
```

Le lint tourne **avant** chaque incrustation (blocage P0) ; voir aussi
`animated-captions-generator` (styles pop/karaoké) et `motion-design-templates`
(titres cinétiques).
