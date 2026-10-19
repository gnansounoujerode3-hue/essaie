# Exigences & dépendances

## Socle (obligatoire)

| Composant | Version | Pourquoi |
|-----------|---------|----------|
| Python | ≥ 3.9 | type hints `X | Y`, `dict[str, Any]` |
| FFmpeg | ≥ 5.0 idéalement | encodage, filtres, `silencedetect`, `loudnorm` |
| ffprobe | optionnel | métadonnées détaillées ; repli sinon |

Aucun paquet Python n'est requis pour les skills de montage, sous-titres, B-rolls
lexicaux, SFX, BPM, motion design, NLE et hooks.

## Extensions optionnelles

| Besoin | Installation | Skills concernés |
|--------|--------------|------------------|
| Transcription locale | `pip install faster-whisper` | speech-to-text-whisper |
| Transcription locale (alt.) | `pip install openai-whisper` | speech-to-text-whisper |
| Suivi de visage, scènes | `pip install opencv-python-headless` | auto-framing-916, sound-effect-cue-automator |
| Recherche CLIP | `pip install torch transformers pillow` | broll-finder-indexer |

## Filtres FFmpeg utilisés

| Filtre | Usage | Repli |
|--------|-------|-------|
| `ass`, `subtitles` | incrustation des sous-titres | fichier .ass utilisable dans un NLE |
| `silencedetect` | détection des blancs | — |
| `loudnorm` | normalisation EBU R128 | — |
| `afftdn` | réduction de bruit | `anlmdn` (plus doux) |
| `deesser` | dé-esseur | ignoré si absent |
| `alimiter` | limiteur final | — |
| `atempo` | accélération des silences | chaînage automatique > ×2 |
| `apad`, `amerge` | mixage SFX | — |

Vérifier : `ffmpeg -hide_banner -filters | grep -E "ass|loudnorm|afftdn"`.

## Clés API (toutes optionnelles)

| Variable | Service | Sans la clé |
|----------|---------|-------------|
| `OPENAI_API_KEY` | Whisper API | transcription locale |
| `GROQ_API_KEY` | Whisper large-v3 API | transcription locale |
| `ELEVENLABS_API_KEY` | isolation de voix | `afftdn` local |
| `RUNWAY_API_KEY` | génération vidéo | prompts seulement |
| `LUMAAI_API_KEY` | génération vidéo | prompts seulement |
| `PEXELS_API_KEY` | B-rolls | index local |
| `PIXABAY_API_KEY` | B-rolls | index local |

## Logiciels NLE

| Logiciel | Version | Ce que VESK produit |
|----------|---------|---------------------|
| Premiere Pro | 2020+ | FCPXML, XMEML, EDL, JSX |
| After Effects | CC 2019+ | JSX (comp, captions, expressions) |
| DaVinci Resolve | 18+ (Studio pour l'API complète) | FCPXML + script Python |

Aucun logiciel NLE n'est requis pour produire des vidéos finales : FFmpeg suffit.

## Performances indicatives

| Tâche | 10 min de rush | Notes |
|-------|----------------|-------|
| Transcription `small` (CPU 8 cœurs) | 3–6 min | `large-v3` : ×3 |
| Auto-cut + rendu 1080p | 2–4 min | surtout l'encodage |
| Sous-titres ASS | < 1 s | rendu 1080p : temps réel ×1–2 |
| Analyse BPM | 3–8 s | 22 kHz mono |
| Index 500 rushes (lexical) | 10–30 s | CLIP : plusieurs minutes |

## Espace disque

- Modèles Whisper : 75 Mo (`base`) à 3 Go (`large-v3`).
- CLIP : ~600 Mo (poids du modèle).
- Sorties intermédiaires : prévoir 2 à 3 × la taille des rushes.
