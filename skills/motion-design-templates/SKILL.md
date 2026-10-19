---
name: motion-design-templates
description: Applique des templates de motion design sans plug-in (titre cinétique, lower third, carte de chapitre, citation, compteur animé, barre de progression, callout, end card CTA) en ASS, incrustables par FFmpeg. Utiliser ce skill pour « ajouter un titre animé », « lower third », « carte de chapitre », « compteur animé » ou « CTA de fin ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg (libass)
---

# Motion design en ASS

8 templates vectoriels, animés par les transformations ASS (`\move`, `\t`, `\fscx`,
`\fad`, dessins `\p1`). Aucun After Effects, aucun plug-in, rendu en secondes.

## Quand l'utiliser

- Ajouter un titre, un lower third ou une carte de chapitre sans After Effects.
- Animer un compteur (chiffre qui monte) ou une barre de progression.
- Insérer une citation ou un callout sur un plan existant.
- Terminer par une end card CTA, en une commande.

## Templates

| ID | Rendu | Champs |
|----|-------|--------|
| `title` | titre plein écran + ligne d'accent + sous-titre | `text`, `subtitle` |
| `lower-third` | bandeau nom/fonction en bas à gauche | `text`, `subtitle` |
| `chapter` | grand numéro + titre sur fond assombri | `text`, `subtitle`, `number` |
| `quote` | citation centrée + auteur | `text`, `subtitle` |
| `counter` | chiffre qui monte de 0 à N avec easing | `number`, `text` |
| `progress` | barre de progression sur la durée | — |
| `callout` | boîte d'annotation avec pointeur | `text` |
| `cta` | end card + flèche animée | `text`, `subtitle` |

```bash
python3 scripts/motion.py --list-templates
python3 scripts/motion.py --list-palettes

# Lower third incrusté
python3 scripts/motion.py --template lower-third --text "Marie Dupont" \
  --subtitle "Monteuse" --duration 4 --burn interview.mp4 --video-out lower.mp4

# Compteur animé (chiffre + libellé)
python3 scripts/motion.py --template counter --number 87 --text "de rétention" \
  --duration 2.5 --out counter.ass

# Titre avec palette
python3 scripts/motion.py --template title --text "3 astuces de montage" \
  --subtitle "pour doubler ta rétention" --palette ocean --out title.ass
```

## Palettes

`vesk` (blanc/jaune/noir), `ocean` (cyan), `sunset` (orange), `mono`.
Toutes surchargeables avec `--primary` / `--accent`.

## Réglages

- `--canvas auto|1080x1920|1920x1080|1080x1080`
- `--font`, `--uppercase/--no-uppercase`
- `--start`, `--duration`
- `--crf`, `--preset` pour l'incrustation

## Comment c'est construit

- Un en-tête ASS avec les styles `Motion`, `Accent`, `Small`.
- Des événements `Dialogue` avec positions calculées depuis le canvas.
- Les formes sont des dessins `\p1` (rectangles, triangle du callout, barre).
- Le compteur génère 30 keyframes avec easing cubique.

## Limites

- Ce n'est pas du vrai 3D : pas de titres extrudés ni de particules. Pour cela, exporter
  le JSX After Effects (`after-effects-scripting`) et animer dans AE.
- Le rendu dépend des polices installées ; vérifier avec `--font "DejaVu Sans"` en cas de doute.
- Les animations sont en 2D, calées sur une durée fixe (pas de détection de beat) :
  utiliser `music-beat-sync` pour choisir `--start`/`--duration` sur les temps.

## Suite logique

`music-beat-sync` pour caler les apparitions, `sound-effect-cue-automator` pour les « pop ».
