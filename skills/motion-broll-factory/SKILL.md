---
name: motion-broll-factory
description: Fabrique de B-roll animés locaux (aucun réseau) — billets qui tombent, marquee vertical géant, diagramme en orbite qui se construit, particules — en MP4 9:16 injectables en overlay FFmpeg. Utiliser ce skill pour « B-roll animé », « billets qui tombent », « texte marquee », « diagramme orbite », « fond particules ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: Pillow, imageio-ffmpeg (ou ffmpeg)
---

# Usine de B-roll animés (PIL → MP4)

Nos 4 B-rolls sont des **images plates** ; les refs tournent des **animations**
(billets v3, marquee « LONDON » v1, orbite-icônes v4, particules v6). Ce skill
les génère en local, sans dépendance réseau.

## Quand l'utiliser

- P1 « money » : billets/pièces qui tombent derrière un chiffre (v3).
- P1 « marquee » : nom/keyword géant vertical qui défile (v1 LONDON).
- P1 « orbit » : cercle pointillé + icônes qui apparaissent en rotation (v4).
- P1 « particles » : champ de particules sur fond sombre de marque (v6).

## Démarrage rapide

```bash
python3 scripts/gen_motion_broll.py money    --dur 3 -o broll_money.mp4
python3 scripts/gen_motion_broll.py marquee --text CANADA --accent FF6B00 -o broll_marq.mp4
python3 scripts/gen_motion_broll.py orbit   --accent 2E6BFF -o broll_orbit.mp4
python3 scripts/gen_motion_broll.py particles --accent 40E0D0 --bg 0B0B10 -o broll_part.mp4
# usage (fenêtre identique à un B-roll fixe) :
ffmpeg -i base.mp4 -i broll_money.mp4 -filter_complex \
  "[1:v]setsar=1[b];[0:v][b]overlay=0:0:enable='between(t,25,27.9)'" out.mp4
```

## Spécifications

- 1080×1920, 30 i/s, 2-4 s en boucle, fond = couleur de marque unique.
- Marquee : lettres 480 px empilées verticalement, défilement ≈ 380 px/s.
- Orbit : anneau pointillé tournant 12°/s, 4 icônes qui apparaissent à 0/0,7/1,4/2,1 s.
- Money : 14 « billets » 210×105 px (bord + « $ »), chute 700-1100 px/s, rotation ±18°.
- Particules : 90 points 2-5 px, dérive lente + scintillement.

## Commandes des scripts

- `python3 scripts/gen_motion_broll.py money -o out.mp4` — billets qui tombent
- `python3 scripts/gen_motion_broll.py marquee --text MOT -o out.mp4` — marquee vertical
- `python3 scripts/gen_motion_broll.py orbit -o out.mp4` — diagramme orbite construit
- `python3 scripts/gen_motion_broll.py particles -o out.mp4` — fond particules

Complète `broll-finder-indexer` (B-réels libres, réseau requis) et
`overlay-card-templates` (cartes stat posées SUR ce fond animé).

## Scripts de ce skill

- `scripts/gen_motion_broll.py` — B-roll procédural (money, marquee, orbit, particles) pur PIL → mp4.
- `scripts/cutaway.py` — plan serré + lente poussée sur UNE fenêtre du propre rush (aucun réseau, licence clean) : `python3 scripts/cutaway.py rush.mp4 --t0 64.7 --t1 68.2 --zoom 1.7 --focus 0.5,0.35 -o cutaway.mp4`. Voir `python3 scripts/cutaway.py --help`.
- `assets/photoreal/` — 4 photogrammes 1024x1536 IA (banque, argent, Toronto, cles) directement insérables : les boucler en `loop=1,enable=between(t,a,b)`.
