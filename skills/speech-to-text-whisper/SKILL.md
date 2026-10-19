---
name: speech-to-text-whisper
description: Transcription audio/vidéo ultra-précise avec timestamps (mots et segments) via faster-whisper, Whisper local, OpenAI ou Groq. Utiliser ce skill pour « transcrire une vidéo », « générer des sous-titres », « obtenir un SRT » ou « horodater la parole ».
license: MIT
metadata:
  version: 1.0.0
  category: analyse
  requires: ffmpeg
---

# Transcription (Whisper)

Le point d'entrée audio de tout le pack. Sort un JSON horodaté **mot par mot**,
plus SRT/VTT/TXT/Markdown lisibles.

## Quand l'utiliser

- Transcrire un rush, un podcast ou une réunion en JSON horodaté mot par mot.
- Produire un SRT/VTT lisible pour YouTube ou un NLE.
- Alimenter les skills d'analyse, de sous-titres et de B-rolls (format pivot commun).
- Choisir entre moteur local (gratuit, privé) et API (rapide, sans installation).

## Moteurs disponibles

| Provider | Type | Installation | Remarques |
|----------|------|--------------|-----------|
| `faster-whisper` | local | `pip install faster-whisper` | **recommandé** : rapide, CPU OK, hors-ligne après téléchargement |
| `whisper` | local | `pip install openai-whisper` | référence OpenAI, plus lent |
| `openai` | API | `export OPENAI_API_KEY=…` | `whisper-1`, limite ~25 Mo par requête |
| `groq` | API | `export GROQ_API_KEY=…` | `whisper-large-v3`, très rapide |
| `auto` | — | — | choisit le premier disponible |

```bash
python3 scripts/transcribe.py --doctor        # diagnostic
python3 scripts/transcribe.py --list-providers
```

## Démarrage rapide

```bash
# Local, français, tous les formats
python3 scripts/transcribe.py interview.mp4 --language fr \
  --formats json,srt,vtt,md

# Dossier entier, préfixe de sortie commun
python3 scripts/transcribe.py rushes/ --out-prefix sorties/ep01 --provider groq

# Rapide sans timings de mots
python3 scripts/transcribe.py clip.mp4 --no-word-timestamps --formats srt
```

## Options

- `--model tiny|base|small|medium|large-v3` (défaut `small` ; `large-v3` pour la précision maximale).
- `--language fr|en|auto` : forcer la langue améliore la ponctuation et les accents.
- `--no-vad` : désactive la détection de voix (utile si les coupures mangent des mots).
- `--srt-max-chars 42` : longueur des lignes SRT.
- `--formats json,srt,vtt,txt,md`.

## Sorties

```
interview.transcript.json   # format pivot : segments + words
interview.srt               # sous-titres standard
interview.vtt               # web
interview.txt               # [mm:ss] texte
interview.transcript.md     # tableau lisible
```

Exemple de segment :

```json
{"start": 12.4, "end": 15.1,
 "text": "Regarde ce chiffre",
 "words": [{"word": "Regarde", "start": 12.4, "end": 12.75}, …]}
```

## Limites et bonnes pratiques

- Les modèles sont téléchargés au premier usage (plusieurs centaines de Mo).
- Pour les vidéos de plus de 25 Mo via API : découper en amont
  (`ffmpeg-power-tools cut`) ou privilégier un moteur local.
- Un enregistrement très bruité doit d'abord passer par `audio-cleaning-enhancer`.
- Les langues mélangées (franglais) sont mieux gérées avec `large-v3`.

## Suite logique

`video-transcript-analyser`, puis `animated-captions-generator` et `highlight-detector-ai`.
