---
name: overlay-card-templates
description: Génère en PNG les cartes manquantes des refs — scènes texte plein cadre (blanc/noir/couleur de marque), cartes statistiques chiffrées, mockups UI (message DM, cadre téléphone, badges pill) — prêtes à overlay FFmpeg en 1080x1920. Utiliser ce skill pour « scène texte », « carte chiffre », « mockup chat/DM », « badge pill ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: Pillow (optionnel), ffmpeg
---

# Cartes overlay : scènes texte, stats, mockups UI

0 sur 7 références manquent ces cartes : **5/7** ont des scènes texte plein
cadre, **4/7** des chiffres géants ($1 288, $15 000, 90 %, #1), **3/7** des
mockups UI (DM, téléphone, chat). Ce skill les produit en PNG sans réseau.

## Quand l'utiliser

- P1 « scène texte » : respirations blanches/noires avec un seul mot (v3, v5, v7).
- P1 « carte chiffre » : sortir le chiffre clé du script en carte stat (v3, v5, v7).
- P1 « mockup UI » : message DM qui prouve la douleur client (v2, v4, v6).

## Démarrage rapide

```bash
python3 scripts/make_card.py scene --bg blanc --text "go viral" --accent 1DB954 -o scene1.png
python3 scripts/make_card.py stat  --number "1 500 $" --label "de dettes" --accent FF3B30 -o stat1.png
python3 scripts/make_card.py chat  --name "David J." --msg "Je suis intéressé…" --badge "En attente" -o dm.png
python3 scripts/make_card.py pill  --text "3 types" --accent 7C3AED -o pill.png
python3 scripts/make_card.py phone --shot exemple.png -o phone.png
# overlay 1,2 s :
ffmpeg -i in.mp4 -i dm.png -filter_complex "[1:v]fade=t=in:d=0.12[a];[0:v][a]overlay=x=(W-w)/2:y=H*0.30:enable='between(t,10,11.2)'" out.mp4
```

## Commandes des scripts

- `python3 scripts/make_card.py scene …` — scène texte plein cadre
- `python3 scripts/make_card.py stat …` — carte statistique
- `python3 scripts/make_card.py chat …` — mockup message DM
- `python3 scripts/make_card.py pill …` — badge pill arrondi
- `python3 scripts/make_card.py phone …` — cadre téléphone autour d'une capture

## Spécifications (calques des refs)

- Canvas 1080×1920, marge de sécurité 96 px, texte centré `an5`.
- Scène : fond uni (blanc `FAFAFA` / noir `0B0B10` / marque), 1 phrase max,
  mot d'accent en couleur, respiration ≈ 1,5-2,5 s.
- Stat : nombre ≥ 260 px bold, label 64 px, accent unique.
- DM : carte arrondie r=36, ombre douce, badge pill en haut à droite.
- Overlay **sans fondu long** (0,1 s) pour coller au rythme 2-3 s des refs.

Voir aussi `motion-design-templates` (titres animés ASS) et
`chart-animation` (data-viz animée, import Remotion).
