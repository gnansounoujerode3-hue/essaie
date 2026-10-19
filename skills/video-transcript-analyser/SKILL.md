---
name: video-transcript-analyser
description: Dérushage intelligent d'une vidéo ou d'un podcast — transcription horodatée, détection des silences, des tics de langage, du débit, des questions et des mots-clés, avec recommandations de montage. Utiliser ce skill quand il faut « analyser une vidéo », « dérusher », « trouver les silences », « repérer les tics de langage » ou préparer un montage.
license: MIT
metadata:
  version: 1.0.0
  category: analyse
  requires: ffmpeg
---

# Dérushage & analyse de transcription

Transforme un rush en **rapport de dérushage exploitable** : où sont les silences,
ce qu'il faut couper, comment le locuteur parle, quels mots reviennent.

## Quand l'utiliser

- Avant tout montage : savoir ce qu'il y a dans 45 minutes de rush.
- Repérer les silences à supprimer et les hésitations à couper.
- Préparer un brief de montage (rythme, structure, répétitions).
- Générer les sous-titres de base (SRT/VTT) en même temps que l'analyse.

## Démarrage rapide

```bash
# Analyse complète à partir d'une transcription existante
python3 scripts/analyze.py --transcript interview.srt --media interview.mp4 \
  --json analyse.json --md analyse.md --srt sous-titres.srt

# Transcription incluse (Whisper local ou API, voir speech-to-text-whisper)
python3 scripts/analyze.py --media interview.mp4 --language fr \
  --json analyse.json --md analyse.md
```

## Ce que le rapport contient

| Section | Détail |
|---------|--------|
| Statistiques | durée, mots, mots/minute, ratio de silence, nombre de questions |
| Silences | liste horodatée + les 12 plus longs |
| Tics de langage | « euh », « du coup », « en fait »… avec timecodes |
| Répétitions | n-grammes répétés (2 à 4 mots), score de répétition |
| Mots-clés | mots porteurs les plus fréquents (hors mots vides) |
| Segments lents | passages sous le seuil de mots/minute |
| Recommandations | actions concrètes de montage |

## Options utiles

- `--noise-db -35` : seuil de détection des silences (baisser si ambiance bruyante).
- `--min-silence 0.35` : durée minimale d'un silence.
- `--slow-wpm 95` : seuil de détection des passages lents.
- `--top-words 25` : taille de la liste de mots-clés.
- `--dry-run` : n'exécute ni transcription ni FFmpeg.

## Entrées / sorties

- **Entrées** : transcription JSON/SRT/VTT/TXT **ou** média (vidéo/audio).
- **Sorties** : JSON complet, rapport Markdown, SRT/VTT, texte brut.

Le JSON est le format pivot du pack : `{"language", "duration", "segments":[{"start","end","text","words"}]}`.
Il est consommé tel quel par les sous-titres, le B-roll, les SFX, les highlights et les hooks.

## Limites

- La détection de silences utilise `silencedetect` de FFmpeg : ajuster `--noise-db`
  sur un extrait de 30 s avant de traiter une heure de rush.
- Sans transcription, seuls les silences sont mesurés (pas de tics ni de mots-clés).

## Suite logique

`silence-removal-automation` → `highlight-detector-ai` → `animated-captions-generator`.

## Fichiers

- `scripts/analyze.py` — CLI d'analyse.
- `shared/vesk/analyze.py` — scoring sémantique réutilisable (devient `_shared/vesk/`
  après installation).
- `shared/vesk/transcript.py` — parsing et modèle de transcription.
