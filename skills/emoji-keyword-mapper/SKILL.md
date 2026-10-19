---
name: emoji-keyword-mapper
description: Analyse le texte des sous-titres pour détecter les mots-clés et associer automatiquement des emojis pertinents (dictionnaire FR/EN de plus de 200 entrées), avec timings pour l'incrustation. Utiliser ce skill pour « ajouter des emojis aux sous-titres », « mots-clés à surligner » ou « habillage emoji ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg
---

# Mots-clés & emojis

Détecte les mots qui méritent un emoji ou un surlignage, et fournit les trois
formats consommés par les autres skills.

## Quand l'utiliser

- Ajouter des emojis aux sous-titres animés, sans les placer à la main.
- Extraire les mots-clés d'une transcription pour les surligner ou les taguer.
- Fournir les fichiers `emoji-map.json` / `keywords.json` consommés par les autres skills.
- Vérifier la répétition d'un mot dans un discours (avant de couper).

## Démarrage rapide

```bash
python3 scripts/map_emojis.py --transcript interview.json \
  --out emoji-map.json --keywords-out keywords.json --timeline emoji-events.json \
  --md transcription-annotee.md
```

Puis :

```bash
python3 ../animated-captions-generator/scripts/generate.py --transcript interview.json \
  --style hormozi --emoji-map emoji-map.json --keywords keywords.json --burn out.mp4
```

## Ce qui est détecté

1. **Mots illustrables** : présence dans le dictionnaire `emojis.json`
   (argent, IA, temps, émotions, santé, réseau social…), insensible aux accents
   et à la casse.
2. **Mots forts** : `secret`, `erreur`, `argent`, `preuve`, `méthode`… même sans emoji.
3. **Mots répétés** : au moins 2 occurrences.
4. Score = fréquence × longueur × bonus mot fort, puis tri.

Les formes contractées (`c'est`, `aujourd'hui`) sont normalisées et les mots vides
(`salut`, `aujourd'hui`, `vais`…) sont écartés.

## Sorties

- `emoji-map.json` : `{"map": {"retention": "📉", …}}` → consommé par les captions.
- `keywords.json` : liste scorée avec occurrences et timecodes → surlignage.
- `emoji-events.json` : `{"events": [{"time", "end", "word", "emoji", "position"}]}`
  → incrustation indépendante (Resolve/AE/FFmpeg `drawtext`).
- `transcription-annotee.md` : transcription avec emojis en contexte.

## Options

- `--config emojis.json` : dictionnaire personnalisé (même structure).
- `--max-keywords 20`, `--min-count 1`.
- `--dry-run` : affiche les mots-clés sans écrire de fichier.

## Personnaliser le dictionnaire

```json
{
  "version": 1,
  "fallback": "✨",
  "emojis": {"mon-mot": "🚀", "autre-mot": "🔥"},
  "categories": {"ma-thematique": ["mon-mot", "autre-mot"]}
}
```

Les clés doivent être en minuscules sans accents (le script normalise).

## Limites

- Détection lexicale : pas de désambiguïsation sémantique (« avocat » métier vs fruit).
- Un emoji par mot, pas de séquences animées.
- Les emojis ne s'affichent que si une police emoji est disponible sur la machine
  qui rend la vidéo.

## Suite logique

`animated-captions-generator` (surlignage + emojis), `motion-design-templates` (callouts).
