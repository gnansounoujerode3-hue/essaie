#!/usr/bin/env bash
# VESK — démo complète sans rush : fabrique un clip de test, puis enchaîne les skills.
#
#   ./scripts/demo.sh [dossier_sortie]
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-demo}"
PY="${PYTHON:-python3}"
export VESK_QUIET=1   # démo lisible : masque les lignes de commande FFmpeg
mkdir -p "$OUT"

ffmpeg_bin="$("$PY" -c "
import sys
sys.path.insert(0, '$ROOT/shared')
from vesk.ffmpeg import ffmpeg_bin
print(ffmpeg_bin())
")"
echo "▸ FFmpeg : $ffmpeg_bin"

echo "▸ Génération du rush de démonstration (26 s, 720x1280)…"
"$ffmpeg_bin" -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=size=720x1280:rate=30:duration=26" \
  -f lavfi -i "aevalsrc=0.22*sin(2*PI*210*t)*if(between(t\,5\,6.2)+between(t\,12\,13)\,0\,1):s=48000:d=26" \
  -c:v libx264 -preset ultrafast -crf 26 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest \
  "$OUT/rush.mp4"

echo "▸ Analyse de la transcription d'exemple…"
"$PY" "$ROOT/skills/video-transcript-analyser/scripts/analyze.py" \
  --transcript "$ROOT/examples/transcript-example.srt" --media "$OUT/rush.mp4" \
  --json "$OUT/analyse.json" --md "$OUT/analyse.md" >/dev/null

echo "▸ Auto-cut des silences…"
"$PY" "$ROOT/skills/silence-removal-automation/scripts/cut_silences.py" \
  --media "$OUT/rush.mp4" --render "$OUT/rush-cut.mp4" \
  --transcript "$ROOT/examples/transcript-example.srt" --srt "$OUT/cut.srt" \
  --json "$OUT/cut.json" >/dev/null

echo "▸ Mots-clés et emojis…"
"$PY" "$ROOT/skills/emoji-keyword-mapper/scripts/map_emojis.py" \
  --transcript "$ROOT/examples/transcript-example.srt" \
  --out "$OUT/emoji-map.json" --keywords-out "$OUT/keywords.json" >/dev/null

echo "▸ Sous-titres animés incrustés…"
"$PY" "$ROOT/skills/animated-captions-generator/scripts/generate.py" \
  --transcript "$ROOT/examples/transcript-example.srt" --style hormozi \
  --emoji-map "$OUT/emoji-map.json" --keywords "$OUT/keywords.json" \
  --media "$OUT/rush-cut.mp4" --out "$OUT/captions.ass" --srt "$OUT/captions.srt" \
  --burn "$OUT/rush-captioned.mp4" --preview "$OUT/apercu.png" --preview-time 2.5 >/dev/null

echo "▸ Moments forts et hooks…"
"$PY" "$ROOT/skills/highlight-detector-ai/scripts/detect.py" \
  --transcript "$ROOT/examples/transcript-example.srt" --media "$OUT/rush.mp4" \
  --clips 3 --min 6 --max 12 --json "$OUT/highlights.json" --md "$OUT/highlights.md" >/dev/null
"$PY" "$ROOT/skills/viral-hooks-library/scripts/generate_hooks.py" \
  --topic "le montage vidéo" --count 4 --md "$OUT/hooks.md" >/dev/null

echo "▸ BPM et sound design…"
"$PY" "$ROOT/skills/music-beat-sync/scripts/beat_sync.py" \
  --media "$OUT/rush-cut.mp4" --json "$OUT/beats.json" --md "$OUT/beats.md" >/dev/null
"$PY" "$ROOT/skills/sound-effect-cue-automator/scripts/build_catalog.py" \
  --generate --out "$OUT/sfx" >/dev/null
"$PY" "$ROOT/skills/sound-effect-cue-automator/scripts/plan_cues.py" \
  --transcript "$ROOT/examples/transcript-example.srt" --media "$OUT/rush-cut.mp4" \
  --keywords "$OUT/keywords.json" --sfx-dir "$OUT/sfx" \
  --wav "$OUT/sfx.wav" --mix "$OUT/rush-sfx.mp4" --md "$OUT/cues.md" >/dev/null

echo "▸ Plan NLE (Premiere / After Effects / Resolve)…"
"$PY" "$ROOT/skills/premiere-pro-extendscript-generator/scripts/build_premiere.py" \
  --media "$OUT/rush-cut.mp4" --duration 10 --out-prefix "$OUT/premiere/edit" \
  --jsx "$OUT/premiere/import.jsx" >/dev/null
"$PY" "$ROOT/skills/davinci-resolve-python-api/scripts/build_resolve.py" \
  --media "$OUT/rush-cut.mp4" --duration 10 --out-prefix "$OUT/resolve/job" >/dev/null

echo "▸ Rétention et habillage…"
"$PY" "$ROOT/skills/retention-chart-analyzer/scripts/analyze_retention.py" \
  --csv "$ROOT/examples/retention.csv" --md "$OUT/retention.md" >/dev/null
"$PY" "$ROOT/skills/motion-design-templates/scripts/motion.py" \
  --template title --text "Démo VESK" --subtitle "19 skills, zéro plug-in" \
  --out "$OUT/titre.ass" >/dev/null

echo
echo "✅ Démo prête dans $OUT/"
echo "   rush-sfx.mp4 · apercu.png · analyse.md · highlights.md · hooks.md"
echo "   premiere/edit.fcpxml · resolve/job-resolve.py · retention.md"
