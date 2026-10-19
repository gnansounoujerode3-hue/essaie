# Pipelines VESK

Six recettes complètes, testées avec les scripts du dépôt. Remplacer les noms de
fichiers, garder l'ordre des étapes.

> Tous les scripts sont appelés par leur chemin. Si les skills sont installés dans
> `~/.claude/skills`, remplacer `skills/` par `~/.claude/skills/<nom>/`.

---

## A. Short viral depuis un long format

```bash
# 1) Transcription + analyse
python3 skills/speech-to-text-whisper/scripts/transcribe.py podcast.mp4 --language fr
python3 skills/video-transcript-analyser/scripts/analyze.py \
  --transcript podcast.transcript.json --media podcast.mp4 --md derush.md

# 2) Extraire 6 clips avec sous-titres Hormozi
python3 skills/highlight-detector-ai/scripts/detect.py \
  --transcript podcast.transcript.json --media podcast.mp4 \
  --clips 6 --min 18 --max 45 --render-dir clips/ --captions hormozi

# 3) Recadrer un clip horizontal en 9:16 (si la source est 16:9)
python3 skills/auto-framing-916/scripts/reframe.py \
  --media clips/clip-01.mp4 --out clips/clip-01-916.mp4

# 4) Sound design + pression sonore
python3 skills/sound-effect-cue-automator/scripts/build_catalog.py --generate --out sfx
python3 skills/sound-effect-cue-automator/scripts/plan_cues.py \
  --transcript podcast.transcript.json --media clips/clip-01-916.mp4 \
  --caption-events clips/clip-01-captioned.ass --scenes scenes.json \
  --sfx-dir sfx --wav sfx.wav --mix clips/clip-01-final.mp4
```

**À vérifier** : le hook tient dans les 1,5 premières secondes ; le clip ne commence
pas sur « euh » ; la musique n'écrase pas la voix.

---

## B. Podcast propre et rythmé

```bash
# 1) Voix : denoise + loudness -16 LUFS
python3 skills/audio-cleaning-enhancer/scripts/clean.py \
  --input episode.mp4 --out episode-voix.wav --preset podcast --md audio.md

# 2) Couper les blancs (garde 80 ms de respiration)
python3 skills/silence-removal-automation/scripts/cut_silences.py \
  --media episode.mp4 --mode remove --margin 0.08 \
  --transcript episode.transcript.json --srt episode-cut.srt \
  --render episode-cut.mp4 --md cut.md

# 3) Musique calée sur les coupes
python3 skills/music-beat-sync/scripts/beat_sync.py \
  --media episode-cut.mp4 --json beats.json --cuts-json cuts.json

# 4) Export social + archive
python3 skills/ffmpeg-power-tools/scripts/ffmpeg_tool.py compress \
  episode-cut.mp4 -o episode-social.mp4 --target-size 80
```

Variante douce : `--mode speed --speed 6` (les blancs deviennent un time-lapse au lieu
d'être supprimés).

---

## C. Montage délégué à un monteur (Premiere)

```bash
# 1) Sélection des meilleurs moments
python3 skills/highlight-detector-ai/scripts/detect.py \
  --media interview.mp4 --clips 8 --min 15 --max 40 --json selects.json

# 2) B-rolls
python3 skills/broll-finder-indexer/scripts/index_library.py \
  --library ~/Footage --out library.json
python3 skills/broll-finder-indexer/scripts/find_broll.py \
  --manifest library.json --transcript interview.transcript.json \
  --out broll-plan.json --md broll-plan.md --csv broll.csv

# 3) Plan de montage JSON (assemblage manuel des deux sorties)
cat > edit.json <<'JSON'
{
  "name": "Interview — selects",
  "fps": 30, "width": 1920, "height": 1080,
  "clips": [
    {"source": "interview.mp4", "in": 42.0, "out": 58.0},
    {"source": "broll/cafe.mp4", "in": 0.0, "out": 3.0},
    {"source": "interview.mp4", "in": 74.0, "out": 96.0}
  ]
}
JSON

# 4) Échanges NLE
python3 skills/premiere-pro-extendscript-generator/scripts/build_premiere.py \
  --plan edit.json --out-prefix premiere/edit \
  --jsx premiere/import.jsx --jsx-markers premiere/markers.jsx
```

Le monteur importe `premiere/edit.fcpxml` dans Premiere, puis exécute `import.jsx`
(Fichier → Scripts). Les rushes doivent être aux mêmes chemins absolus.

---

## D. Rendu DaVinci Resolve étalonné

```bash
python3 skills/davinci-resolve-python-api/scripts/build_resolve.py \
  --plan edit.json --out-prefix resolve/job --timeline "Short 01" \
  --lut LUTs/look.cube --render-dir ~/Renders --format mp4 --codec H264 \
  --color --contrast 1.08 --saturation 1.05
```

1. Copier `resolve/job-resolve.py` dans le dossier Scripts de Resolve.
2. Ouvrir Resolve, charger un projet.
3. Workspace → Scripts → `job-resolve`.

Le script importe `job.fcpxml`, ajoute les marqueurs, applique la LUT puis lance le rendu.

---

## E. Refonte d'une vidéo qui décroche

```bash
# 1) Comprendre où l'audience part
python3 skills/retention-chart-analyzer/scripts/analyze_retention.py \
  --csv retention.csv --transcript ancienne-video.transcript.json --md retention.md

# 2) Trouver un nouveau hook
python3 skills/viral-hooks-library/scripts/generate_hooks.py \
  --topic "le sujet de la vidéo" --platform youtube \
  --set "public=créateurs" --md hooks.md

# 3) Re-monter : couper les passages identifiés + corriger l'intro
python3 skills/silence-removal-automation/scripts/cut_silences.py \
  --media ancienne-video.mp4 --render v2.mp4 --transcript ancienne-video.transcript.json
```

Le rapport croisé liste les timecodes de drop **et la phrase prononcée** à ce moment.

---

## F. Habillage IA (banque insuffisante)

```bash
# 1) Plan de shots + prompts
python3 skills/ai-image-video-generator/scripts/generate.py plan \
  --transcript interview.transcript.json --provider luma \
  --every 8 --max-shots 12 --md shots.md --out shots.json

# 2) Génération (clé API) et téléchargement
export LUMAAI_API_KEY=…            # ne pas coller la clé dans le chat
python3 skills/ai-image-video-generator/scripts/generate.py request \
  --provider luma --prompt "…" --execute --download --output-dir ai-assets

# 3) Placement + habillage
python3 skills/broll-finder-indexer/scripts/index_library.py \
  --library ai-assets --out ai-library.json
python3 skills/broll-finder-indexer/scripts/find_broll.py \
  --manifest ai-library.json --transcript interview.transcript.json --out ai-plan.json
python3 skills/motion-design-templates/scripts/motion.py \
  --template lower-third --text "Studio VESK" --subtitle "Épisode 12" \
  --burn interview.mp4 --video-out interview-branded.mp4
```

---

## G. Chaîne « tout automatique » (une commande par étape)

```bash
set -e
SRC="$1"
python3 skills/speech-to-text-whisper/scripts/transcribe.py "$SRC" --language fr
BASE="${SRC%.*}"
python3 skills/video-transcript-analyser/scripts/analyze.py \
  --transcript "$BASE.transcript.json" --media "$SRC" --md "$BASE-derush.md"
python3 skills/silence-removal-automation/scripts/cut_silences.py \
  --media "$SRC" --render "$BASE-cut.mp4" --transcript "$BASE.transcript.json"
python3 skills/emoji-keyword-mapper/scripts/map_emojis.py \
  --transcript "$BASE.transcript.json" --out emoji-map.json --keywords-out keywords.json
python3 skills/animated-captions-generator/scripts/generate.py \
  --transcript "$BASE.transcript.json" --style hormozi \
  --emoji-map emoji-map.json --keywords keywords.json \
  --media "$BASE-cut.mp4" --burn "$BASE-final.mp4"
python3 skills/sound-effect-cue-automator/scripts/build_catalog.py --generate --out sfx
python3 skills/sound-effect-cue-automator/scripts/plan_cues.py \
  --transcript "$BASE.transcript.json" --media "$BASE-final.mp4" \
  --keywords keywords.json --sfx-dir sfx --wav sfx.wav --mix "$BASE-sfx.mp4"
```

Durée typique pour 10 minutes de rush sur un laptop récent : 6 à 15 minutes
(transcription `small` comprise), sans compter les téléchargements de modèles.
