#!/usr/bin/env bash
# VESK — vérifie l'installation et exécute une mini-pipeline de bout en bout.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0; FAIL=0
ok()   { printf "  \033[0;32m✓\033[0m %s\n" "$*"; PASS=$((PASS+1)); }
bad()  { printf "  \033[0;31m✗\033[0m %s\n" "$*"; FAIL=$((FAIL+1)); }
head_() { printf "\n\033[0;36m%s\033[0m\n" "$*"; }

PY="${PYTHON:-python3}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

head_ "Environnement"
"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)' \
  && ok "Python $( $PY -c 'import platform;print(platform.python_version())' )" \
  || bad "Python 3.9+ requis"
FFMPEG_BIN_RESOLVED="$("$PY" -c "
import sys; sys.path.insert(0, '$ROOT/shared')
try:
    from vesk.ffmpeg import ffmpeg_bin
    print(ffmpeg_bin())
except Exception as exc:
    print('')
")"
if [[ -n "$FFMPEG_BIN_RESOLVED" ]]; then ok "FFmpeg : $FFMPEG_BIN_RESOLVED"; else bad "FFmpeg introuvable"; fi
HAS_LIBASS=0
if [[ -n "$FFMPEG_BIN_RESOLVED" ]] && "$FFMPEG_BIN_RESOLVED" -hide_banner -filters 2>/dev/null | grep -qE '^\s*[TSC.]{3}\s+ass\s'; then
  ok "libass disponible (incrustation ASS)"; HAS_LIBASS=1
else
  bad "libass absent : les incrustations ASS échoueront (le reste fonctionne)"
fi

head_ "Skills (19)"
count=0
for dir in "$ROOT"/skills/*/; do
  [ -f "$dir/SKILL.md" ] || continue
  count=$((count+1))
  if "$PY" -c "import pathlib,sys; t=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'); sys.exit(0 if t.startswith('---') and 'name:' in t and 'description:' in t else 1)" "$dir/SKILL.md"; then
    ok "$(basename "$dir")"
  else
    bad "$(basename "$dir") — frontmatter invalide"
  fi
done
[[ $count -eq 19 ]] && ok "19 skills présents" || bad "$count skills trouvés (19 attendus)"

head_ "CLI"
for script in "$ROOT"/skills/*/scripts/*.py; do
  if "$PY" "$script" --help >/dev/null 2>&1; then :; else bad "$(basename "$script") --help"; fi
done
ok "toutes les CLI répondent à --help"

head_ "Compilation"
if "$PY" -m py_compile $(find "$ROOT/shared" "$ROOT/skills" -name '*.py') 2>"$TMP/compile.err"; then
  ok "modules Python compilés"
else
  bad "erreur de compilation"; tail -5 "$TMP/compile.err"
fi

head_ "Tests unitaires"
if [[ -f "$ROOT/tests/test_vesk.py" ]]; then
  if "$PY" -m unittest discover -s "$ROOT/tests" -q >"$TMP/tests.log" 2>&1; then
    ok "$(grep -oE 'Ran [0-9]+ tests' "$TMP/tests.log" | head -1)"
  else
    bad "tests unitaires en échec"; tail -20 "$TMP/tests.log"
  fi
fi

if [[ -n "$FFMPEG_BIN_RESOLVED" ]]; then
  head_ "Pipeline de bout en bout"
  export FFMPEG_BIN="$FFMPEG_BIN_RESOLVED"
  "$FFMPEG_BIN" -hide_banner -loglevel error -y \
    -f lavfi -i "testsrc2=size=360x640:rate=30:duration=6" \
    -f lavfi -i "aevalsrc=0.2*sin(2*PI*220*t)*if(between(t\,2\,3)\,0\,1):s=48000:d=6" \
    -c:v libx264 -preset ultrafast -crf 30 -pix_fmt yuv420p -c:a aac -shortest "$TMP/clip.mp4" \
    && ok "clip de test généré" || bad "génération du clip de test"

  cat > "$TMP/t.srt" <<'SRT'
1
00:00:00,200 --> 00:00:02,000
Aujourd'hui je vais te montrer trois astuces de montage.

2
00:00:03,100 --> 00:00:05,800
Regarde ce chiffre : 87 % de rétention en 30 jours.
SRT

  if "$PY" "$ROOT/skills/video-transcript-analyser/scripts/analyze.py" \
      --transcript "$TMP/t.srt" --media "$TMP/clip.mp4" --json "$TMP/a.json" >/dev/null 2>&1; then
    ok "analyse de transcription"
  else bad "analyse de transcription"; fi

  if "$PY" "$ROOT/skills/silence-removal-automation/scripts/cut_silences.py" \
      --media "$TMP/clip.mp4" --render "$TMP/cut.mp4" --transcript "$TMP/t.srt" \
      --srt "$TMP/cut.srt" >/dev/null 2>&1; then
    ok "auto-cut des silences"
  else bad "auto-cut des silences"; fi

  if "$PY" "$ROOT/skills/animated-captions-generator/scripts/generate.py" \
      --transcript "$TMP/t.srt" --style hormozi --out "$TMP/c.ass" >/dev/null 2>&1; then
    ok "sous-titres animés (ASS)"
  else bad "sous-titres animés"; fi
  if [[ $HAS_LIBASS -eq 1 ]]; then
    if "$PY" "$ROOT/skills/animated-captions-generator/scripts/generate.py" \
        --transcript "$TMP/t.srt" --style hormozi --media "$TMP/clip.mp4" \
        --out "$TMP/c2.ass" --burn "$TMP/burn.mp4" --preset ultrafast --crf 30 >/dev/null 2>&1; then
      ok "incrustation libass"
    else bad "incrustation libass"; fi
  fi

  if "$PY" "$ROOT/skills/highlight-detector-ai/scripts/detect.py" \
      --transcript "$TMP/t.srt" --media "$TMP/clip.mp4" --clips 2 --min 3 --max 6 \
      --json "$TMP/h.json" >/dev/null 2>&1; then
    ok "détection de moments forts"
  else bad "détection de moments forts"; fi

  if "$PY" "$ROOT/skills/broll-finder-indexer/scripts/index_library.py" \
      --library "$TMP" --out "$TMP/lib.json" >/dev/null 2>&1; then
    ok "index B-roll"
  else bad "index B-roll"; fi

  if "$PY" "$ROOT/skills/sound-effect-cue-automator/scripts/build_catalog.py" \
      --generate --out "$TMP/sfx" >/dev/null 2>&1; then
    ok "pack SFX généré"
  else bad "pack SFX"; fi

  if "$PY" "$ROOT/skills/music-beat-sync/scripts/beat_sync.py" \
      --media "$TMP/clip.mp4" --json "$TMP/beats.json" >/dev/null 2>&1; then
    ok "analyse BPM"
  else bad "analyse BPM"; fi

  if "$PY" "$ROOT/skills/retention-chart-analyzer/scripts/analyze_retention.py" \
      --csv "$ROOT/examples/retention.csv" --md "$TMP/r.md" >/dev/null 2>&1; then
    ok "analyse de rétention"
  else bad "analyse de rétention"; fi

  if "$PY" "$ROOT/skills/viral-hooks-library/scripts/generate_hooks.py" \
      --topic "le montage vidéo" --count 3 --md "$TMP/hooks.md" >/dev/null 2>&1; then
    ok "hooks viraux"
  else bad "hooks viraux"; fi

  if "$PY" "$ROOT/skills/ffmpeg-power-tools/scripts/ffmpeg_tool.py" \
      compress "$TMP/clip.mp4" -o "$TMP/small.mp4" --crf 32 --preset ultrafast >/dev/null 2>&1; then
    ok "compression FFmpeg"
  else bad "compression FFmpeg"; fi
fi

head_ "Résultat"
printf "  %d réussite(s), %d échec(s)\n\n" "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]] && { printf "\033[0;32mInstallation prête.\033[0m\n"; exit 0; }
printf "\033[0;33mCertains contrôles ont échoué : voir docs/TROUBLESHOOTING.md\033[0m\n"; exit 1
