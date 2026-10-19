---
name: animated-captions-generator
description: Génère des sous-titres animés style Alex Hormozi / Ali Abdaal (mot par mot, pop, karaoké, boîte jaune, néon) en ASS et les incruste via FFmpeg, avec surlignage de mots-clés et emojis. Utiliser ce skill pour « sous-titres animés », « captions dynamiques », « sous-titres Hormozi » ou « brûler les sous-titres ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg (libass)
---

# Sous-titres animés

Un moteur ASS complet : styles, animations, surlignage, emojis, auto-ajustement
pour ne jamais déborder de l'écran.

## Quand l'utiliser

- Un Short/Reel qui doit accrocher dès la première seconde (style Hormozi).
- Une vidéo pédagogique où le mot prononcé doit s'allumer (karaoké, style Ali Abdaal).
- Des sous-titres lisibles sur un fond complexe (boîte noire) ou un rendu néon.
- Brûler un SRT existant en `.ass` stylé, avec surlignage de mots-clés et emojis.

## Styles fournis (`styles.json`)

| Style | Rendu | Idéal pour |
|-------|-------|-----------|
| `hormozi` | capitales, boîte jaune, mots clés en rouge, pop | Shorts énergiques, hooks |
| `ali` | blanc net, karaoké vert mot par mot, sans fond | contenus pédagogiques |
| `karaoke-pop` | mot actif en jaune, gris pour le reste, zoom léger | talking head rapide |
| `boxed-black` | bloc noir 82 %, texte blanc | fonds complexes, extérieurs |
| `neon` | glow cyan/violet | gaming, tech, musique |
| `clean` | sobre, lisible partout | YouTube long format |
| `minimal` | petites capitales espacées | luxe, corporate |

## Démarrage rapide

```bash
# ASS + SRT synchronisé
python3 scripts/generate.py --transcript interview.json --style ali \
  --canvas auto --out subs.ass --srt subs.srt --events-json events.json

# Incrustation + aperçu PNG
python3 scripts/generate.py --media clip.mp4 --style hormozi \
  --burn clip-captions.mp4 --preview apercu.png --preview-time 2.5

# Mots-clés surlignés + emojis produits par emoji-keyword-mapper
python3 scripts/generate.py --transcript t.json --style karaoke-pop \
  --keywords keywords.json --emoji-map emoji-map.json --burn out.mp4
```

## Fonctionnement des animations

- **pop** : `\fscx/\fscy` 78 → 114 → 100 sur 200 ms, plus `\fad` court.
- **karaoké** : balises `\kf` par mot (remplissage progressif) + couleur sur mot-clé.
- **slide** : `\move` vertical court.
- **auto-fit** : la police est réduite par palier (jusqu'à ×0,5) et le texte est
  replié sur 2 lignes maximum pour rester dans 90 % de la largeur.
- **emoji** : suffixe collé au mot (`RÉTENTION📉`) avec un espace avant la balise
  suivante.

## Options

- `--canvas auto|1080x1920|1920x1080|1080x1080`
- `--font "Montserrat ExtraBold"` (une alerte indique si la police est absente)
- `--font-size`, `--max-words`, `--position bottom|center|top`
- `--primary`, `--highlight`, `--outline-color`, `--border-style 1|3`
- `--uppercase` / `--no-uppercase`
- `--list-styles`

## Sorties

- `.ass` : fichier de sous-titres animés (ouvrable dans VLC, Resolve, Premiere via plug-in).
- `.srt` : version texte synchronisée.
- `events.json` : événements prêts pour After Effects (`after-effects-scripting`) et Resolve.
- MP4 avec sous-titres incrustés (`--burn`), PNG d'aperçu (`--preview`).

## Limites et conseils

- L'incrustation nécessite **libass** (`ffmpeg -filters | grep ass`). Sans libass, le ASS
  reste utilisable dans le NLE ; le script en informe.
- Les **emojis** exigent une police emoji installée (Noto Color Emoji, Apple Color Emoji).
  Sur un serveur minimal, les emojis peuvent apparaître en carrés : c'est un problème de
  police, pas de fichier ASS.
- Les polices du style (Montserrat…) ne sont pas embarquées : installer la famille ou
  passer `--font "DejaVu Sans"`.
- Un rendu à 720p utilise un canvas 720x1280 et une police mise à l'échelle automatiquement.

## Suite logique

`emoji-keyword-mapper` pour les mots-clés/emojis, `sound-effect-cue-automator` pour
synchroniser un « pop » sur chaque apparition.
