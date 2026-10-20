---
name: marketing-video-pipeline
description: Pipeline tout-en-un « rush brut en entrée, UNE vidéo marketing finie en sortie » — vertical 9:16, silences et reprises supprimés, cadrage sur le visage, sous-titres gros (mot actif en jaune), zooms de rythme, voix égalisée à -14 LUFS, MP4 H.264+AAC prêt à publier en une seule commande. Utiliser ce skill pour « monter une vidéo », « faire une vidéo TikTok/Reels/Shorts », « montage automatique » ou « transformer un rush en vidéo prête à publier ».
license: MIT
metadata:
  version: 1.0.0
  category: montage
  requires: ffmpeg, faster-whisper et opencv (optionnels)
---

# Montage vidéo marketing tout automatique

Un rush brut entre, **un seul** `.mp4` marketing en sort : vertical, rythmé,
sous-tité, son normalisé. Une commande, six étapes internes, quatre niveaux
de repli si quelque chose coince — aucune connaissance en montage requise.

## Quand l'utiliser

- L'utilisateur envoie un rush et veut « sa vidéo » prête pour TikTok, Reels ou Shorts.
- Dérushage + montage + sous-titres + cadrage doivent tenir dans **une seule** passe.
- Pas de NLE sous la main : tout se passe en local avec FFmpeg + Python.

Pour choisir les meilleurs moments, placer un B-roll ou créer un habillage
étape par étape, préférer les skills spécialisés (« Suite logique » en bas).

## Ce que la chaîne fait toute seule

| Étape | Action |
|-------|--------|
| 1/6 Normalisation | 30 i/s constantes, ≤ 2560 px, couleurs HDR d'iPhone → SDR, rotation téléphone corrigée, AAC |
| 2/6 Audio | voix extraite en WAV 16 kHz pour l'analyse |
| 3/6 Transcription | faster-whisper mot à mot ; faux sous-titres éliminés ; les phrases répétées sont remplacées par la **dernière prise** |
| 4/6 Plan de coupe | passages parlés gardés, pauses > 0,45 s coupées, coupes calées pile sur des images |
| 5/6 Cadrage + rendu | 9:16 par défaut, suivi de visage (sinon image entière sur fond flou), zoom 110 % une coupe sur deux, sous-titres avec mot actif en jaune, hook/CTA si demandés, son débruité et normalisé à **-14 LUFS**, ducking de la musique, H.264 CRF 18 + AAC 192 kb/s |
| 6/6 Contrôles | piste vidéo/audio, durée cohérente, taille ≥ 200 Ko ; sinon repli automatique `full` → `safe` → `plain` → `basic` |

## Prérequis

```bash
python3 --version                          # 3.9+ conseillé (3.8+ accepté)
ffmpeg -version | head -n 1                # sinon : apt/brew/winget install ffmpeg
python3 -m pip install --quiet faster-whisper opencv-python-headless
```

- **Obligatoire** : Python + FFmpeg (sans admin : `pip install imageio-ffmpeg`,
  le script le détecte tout seul).
- **Fortement conseillé** : `faster-whisper` (sous-titres + coupes intelligentes)
  et `opencv-python-headless` (cadrage visage) — sans eux, le montage continue
  en mode dégradé (coupes par détection de silence, cadrage centré).
- **Polices** : `fc-list | head -n 3` doit répondre ; sinon
  `apt-get install -y fontconfig fonts-dejavu-core`.
- Internet à la première exécution (modèle Whisper « small » ≈ 0,5 Go).

## Démarrage rapide

```bash
# 1. Le rush, en chemin absolu
INPUT="/chemin/absolu/rush.mp4"; ls -lh "$INPUT"

# 2. Montage en avant-plan (vidéo courte)
python3 scripts/montage_marketing.py "$INPUT" --out-dir ./output

# 2'. Ou en arrière-plan, puis répéter la surveillance jusqu'au résultat
nohup python3 scripts/montage_marketing.py "$INPUT" --out-dir ./output > run.log 2>&1 &
for i in $(seq 1 20); do sleep 15; grep -q -E "^FINAL_VIDEO=|^MONTAGE_ECHEC" run.log && break; done
tail -n 8 run.log
```

Deux seules lignes comptent dans le log :

- `FINAL_VIDEO=/chemin/fichier.mp4` → **succès** : livrer ce fichier.
- `MONTAGE_ECHEC: raison` → échec : Dépannage, puis Plan C.

Durée normale : 1 à 3× la durée du rush (bien plus au premier lancement, à
cause du téléchargement du modèle). Ne **jamais** relancer un montage en cours ;
pour débloquer un processus figé : `pkill -f montage_marketing.py`.

## Options

Aucune option par défaut : n'en ajouter que si l'utilisateur le demande.

| Demande utilisateur | Option à ajouter |
|---------------------|------------------|
| YouTube, horizontal, paysage, 16:9 | `--format horizontal` |
| carré, post Instagram carré | `--format square` |
| garde le format d'origine | `--format keep` |
| ne coupe pas les côtés (démo produit, capture d'écran) | `--fit` (image entière sur fond flou) |
| sans sous-titres / sans zoom | `--no-subs` / `--no-zoom` |
| garde toutes les prises, ne supprime pas les répétitions | `--no-retakes` |
| ne touche pas au son | `--no-denoise` |
| plus dynamique / plus naturel | `--gap 0.30` / `--gap 0.80` |
| en anglais, espagnol, portuguais… | `--lang en` (défaut : auto) |
| musique de fond (fichier audio fourni) | `--music "/chemin/zen.mp3"` (ducking auto sous la voix) |
| titre d'accroche 3 s / appel à l'action 3 s | `--hook "Texte"` / `--cta "Texte"` |
| Whisper inutilisable / mémoire faible | `--no-whisper` / `--model base` (ou `tiny`) |

```bash
# Exemple : « version YouTube, sans zoom »
python3 scripts/montage_marketing.py "$INPUT" --out-dir ./output --format horizontal --no-zoom

# Exemple : « avec ma musique et un titre d'accroche »
python3 scripts/montage_marketing.py "$INPUT" --out-dir ./output \
  --music "/data/zen.mp3" --hook "Offre spéciale" --cta "Abonne-toi"
```

## Vérifier et livrer

```bash
OUT="$(grep '^FINAL_VIDEO=' run.log | tail -n 1 | cut -d= -f2-)"
ls -lh "$OUT"
ffmpeg -hide_banner -i "$OUT" 2>&1 | grep -E "Duration|Stream"
# contrôle visuel (facultatif) : une image, jamais livrée
ffmpeg -y -hide_banner -loglevel error -ss 3 -i "$OUT" -frames:v 1 controle_1.jpg
```

OK si : fichier > 200 Ko, durée > 3 s, ligne `Video:` (1080x1920 par défaut),
ligne `Audio:` si l'original en avait une, visage entier et sous-titres lisibles
sur l'image de contrôle. Livrer **le seul** `.mp4` (pièce jointe ou lien) —
ni log, ni script, ni image de contrôle, ni dossier `output/` en entier.

## Dépannage

| Symptôme | Action |
|----------|--------|
| `ffmpeg: command not found` | installer FFmpeg (Prérequis) |
| pip « externally-managed-environment » | ajouter `--break-system-packages` |
| `python3: command not found` | essayer `python`, puis `py` |
| log `Whisper unavailable` | continue **sans** sous-titres : vérifier internet, réinstaller `faster-whisper`, relancer **une** fois, sinon livrer quand même |
| modèle trop lent / `Killed` / `MemoryError` | relancer avec `--model base` (ou `tiny`) |
| log `No font found` | `apt-get install -y fontconfig fonts-dejavu-core`, relancer |
| commande coupée par un délai | lancer en arrière-plan (Démarrage rapide) |
| log figé > 10 min | `ps aux | grep montage` : plus de processus → relancer une fois ; sinon attendre, et après 40 min `pkill -f montage_marketing.py` puis Plan C |
| `MONTAGE_ECHEC: could not read/convert the input video` | `ffmpeg -i "$INPUT"` : erreur → fichier corrompu (une phrase pour le redemander) ; sinon Plan C |
| `MONTAGE_ECHEC: all render levels failed` | Plan C |
| `Level 'full' failed...`, `No stable face`, `OpenCV missing`, `Suspicious cut`, `Music file not found`, `audio=False` | **normaux** : replis automatiques, continuer jusqu'à `FINAL_VIDEO=` |
| visage coupé sur l'image de contrôle | relancer **une** fois avec `--fit` |
| sous Windows | `python` au lieu de `python3`, lancer sans `nohup` ni `&` |

## Plan C (secours)

Après deux échecs du montage complet, ou dépannage infructueux : conversion
FFmpeg simple — 9:16, -14 LUFS, lisible partout, sans coupes ni sous-titres
(marche aussi si la vidéo n'a pas de son) :

```bash
mkdir -p output
ffmpeg -y -i "$INPUT" \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000" \
  -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k -movflags +faststart \
  output/video_simple.mp4
```

Si cette commande échoue aussi : une seule phrase — « Je n'ai pas réussi à
monter cette vidéo : » suivi de l'erreur, en 15 mots maximum.

## Limites

Le script ne fait **pas** : logo ou habillage de marque, intro/outro
personnalisées, images d'illustration, traduction, choix créatif d'une
accroche, retouche manuelle. Dans ces cas, livrer le montage standard.

## Suite logique

`highlight-detector-ai` pour choisir les meilleurs extraits,
`viral-hooks-library` pour réécrire l'accroche,
`animated-captions-generator` + `motion-design-templates` pour l'habillage,
`broll-finder-indexer` pour les plans d'illustration.
