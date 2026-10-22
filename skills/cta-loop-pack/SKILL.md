---
name: cta-loop-pack
description: Pack de fins façon refs — CTA follow surligné, CTA commentaire mot-clé, carte-question plein écran, abonnement pilule, boucle de re-regard — en templates ASS prêts à brûler à un horodatage donné. Utiliser ce skill pour « CTA de fin », « demande de commentaire », « carte question », « fin en boucle ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg (libass)
---

# Pack CTA + fin en boucle

Nous n'avons qu'une pilule « ABONNE-TOI » ; les refs terminent chacune
différemment : follow surligné (v5), **commentaire mot-clé** (v6 « Comment
Rhythm »), question carte (v4), highlight CTA (v7). Ce pack livre les 5 motifs.

## Quand l'utiliser

- P2 « multi-CTA » : poser follow + commentaire-mot-clé + question avant la fin.
- P2 « fin en boucle » : le dernier plan renvoie au hook (le Reels rejoue).

## Démarrage rapide

```bash
# 1. Générer un .ass de CTA à partir des templates (horodatages en secondes) :
python3 scripts/burn_cta.py --times follow=55.5,comment=57.0,loop=60.0 -o cta.ass
# 2. Vérifier puis brûler avec les sous-titres :
python3 ../caption-hierarchy-styles/scripts/ass_lint.py cta.ass
ffmpeg -i in.mp4 -vf "ass=cta.ass:fontsdir=/usr/share/fonts/truetype/dejavu" -c:a copy out.mp4
```

## Motifs du pack (`data/cta_templates.ass`)

| id | Motif | Fenêtre | Réf |
|----|-------|---------|-----|
| `follow` | « Ne rate rien » + boîte rouge surlignée sur **follow** | 2,0 s | v5 |
| `comment` | « Commente **MOT** » — mot-clé = sujet du clip | 2,0 s | v6 |
| `question` | carte plein cadre « Tu as aussi ce problème ? » | 1,8 s | v4 |
| `subscribe` | pilule arrondie **ABONNE-TOI** (déjà en place, version upscale) | 2,5 s | v8→refs |
| `loop` | micro-teaser 1 s qui reprend le hook (boucle) | 1,0 s | v7 |

Règles : un CTA principal + un secondaire max ; toujours **sur fond calme**
(dernier plan ou scène texte), accent couleur unique, 0,1 s de fondu.

## Commandes des scripts

- `python3 scripts/burn_cta.py --list` — liste les motifs disponibles
- `python3 scripts/burn_cta.py --times follow=55,comment=57 -o cta.ass` — génère le .ass
- `python3 scripts/burn_cta.py --times follow=55 --print-cmd` — commande FFmpeg directe

À coupler avec `viral-hooks-library` (texte du hook pour la boucle) et
`motion-design-templates` (end card générique).
