#!/usr/bin/env bash
# VESK — installe les 20 skills de montage vidéo.
#
#   ./scripts/install.sh                     # copie vers ~/.claude/skills
#   ./scripts/install.sh --mode link         # liens symboliques (mise à jour instantanée)
#   ./scripts/install.sh --target ./my-skills
#   ./scripts/install.sh --only animated-captions-generator,viral-hooks-library
#   ./scripts/install.sh --force             # écrase une installation existante
#   ./scripts/install.sh --uninstall         # retire les skills de la cible
#
set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { printf "${CYAN}▸${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}!${NC} %s\n" "$*"; }
fail()  { printf "${RED}✗${NC} %s\n" "$*" >&2; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${HOME}/.claude/skills"
MODE="copy"
FORCE=0
ONLY=""
UNINSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)
      grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//' | head -n 13
      exit 0 ;;
    *) fail "Option inconnue : $1" ;;
  esac
done

[[ "$MODE" == "copy" || "$MODE" == "link" ]] || fail "--mode doit valoir copy ou link."
[[ -d "$ROOT/skills" ]] || fail "Dossier skills/ introuvable (lance le script depuis le dépôt)."
[[ -d "$ROOT/shared/vesk" ]] || fail "Dossier shared/vesk introuvable."

if [[ $UNINSTALL -eq 1 ]]; then
  removed=0
  for skill in "$ROOT"/skills/*/; do
    [[ -f "$skill/SKILL.md" ]] || continue
    dest="$TARGET/$(basename "$skill")"
    if [[ -e "$dest" || -L "$dest" ]]; then
      rm -rf "$dest"
      ok "retiré : $(basename "$skill")"
      removed=$((removed + 1))
    fi
  done
  info "$removed skill(s) retiré(s) de $TARGET"
  exit 0
fi

PY="$(command -v python3 || command -v python || true)"
[[ -n "$PY" ]] || fail "Python 3.9+ est requis."
"$PY" - <<'EOF' || fail "Python 3.9+ est requis."
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
EOF

if command -v ffmpeg >/dev/null 2>&1; then
  ok "FFmpeg détecté : $(ffmpeg -version 2>/dev/null | head -n1 | cut -d' ' -f1-3)"
else
  warn "FFmpeg introuvable : les skills vidéo échoueront."
  warn "  macOS : brew install ffmpeg   ·   Ubuntu : sudo apt install ffmpeg"
  warn "  Sans admin : pip install imageio-ffmpeg"
fi
command -v ffprobe >/dev/null 2>&1 || warn "ffprobe absent : repli automatique sur 'ffmpeg -i'."
if command -v ffmpeg >/dev/null 2>&1; then
  if ffmpeg -hide_banner -h filter=subtitles 2>&1 | grep -qi "unknown filter"; then
    warn "Ce FFmpeg est un build sans libass : impossible d'incruster les sous-titres."
    warn "  macOS : brew install ffmpeg-full  (build complet, keg-only : ajouter son bin au PATH)"
    warn "  Sans libass, les fichiers .ass restent utilisables dans VLC/Premiere/Resolve."
  fi
fi


mkdir -p "$TARGET"

# bash 3.2 (macOS) : pas de mapfile
ALL=()
for candidate in "$ROOT"/skills/*/; do
  [[ -f "${candidate}SKILL.md" ]] && ALL+=("${candidate%/}")
done
[[ ${#ALL[@]} -gt 0 ]] || fail "Aucun skill trouvé dans $ROOT/skills."

SELECTED=()
if [[ -n "$ONLY" ]]; then
  IFS=',' read -ra WANTED <<< "$ONLY"
  for name in "${WANTED[@]}"; do
    name="$(echo "$name" | xargs)"
    found=0
    for skill in "${ALL[@]}"; do
      if [[ "$(basename "$skill")" == "$name" ]]; then SELECTED+=("$skill"); found=1; fi
    done
    [[ $found -eq 1 ]] || fail "Skill inconnu : $name"
  done
else
  SELECTED=("${ALL[@]}")
fi

info "Installation de ${#SELECTED[@]} skill(s) → $TARGET (mode: $MODE)"
installed=0
for skill in "${SELECTED[@]}"; do
  name="$(basename "$skill")"
  dest="$TARGET/$name"
  if [[ -e "$dest" || -L "$dest" ]]; then
    if [[ $FORCE -eq 1 ]]; then rm -rf "$dest"; else warn "déjà présent, ignoré : $name (--force pour écraser)"; continue; fi
  fi
  if [[ "$MODE" == "link" ]]; then
    ln -s "$skill" "$dest"
  else
    mkdir -p "$dest"
    (cd "$skill" && tar --exclude='__pycache__' --exclude='*.pyc' -cf - .) | (cd "$dest" && tar -xf -)
    rm -rf "$dest/_shared"
    mkdir -p "$dest/_shared"
    (cd "$ROOT/shared" && tar --exclude='__pycache__' --exclude='*.pyc' -cf - vesk) | (cd "$dest/_shared" && tar -xf -)
    # données de tous les skills (styles, templates, hooks…) pour les appels croisés
    for data_dir in "$ROOT"/skills/*/; do
      for data_file in "$data_dir"*.json; do
        [ -f "$data_file" ] || continue
        mkdir -p "$dest/_shared/data/$(basename "$data_dir")"
        cp "$data_file" "$dest/_shared/data/$(basename "$data_dir")/"
      done
    done
  fi
  installed=$((installed + 1))
  ok "$name"
done

echo
ok "$installed skill(s) installé(s) dans $TARGET"
cat <<EOF

Utilisation depuis un agent (Claude Code, Cursor, etc.) :
  « Utilise le skill animated-captions-generator sur clip.mp4 avec le style hormozi »

Test rapide :
  python3 "$TARGET/animated-captions-generator/scripts/generate.py" --list-styles
  bash "$ROOT/scripts/selftest.sh"

Dépendances optionnelles :
  pip install faster-whisper            # transcription locale
  pip install opencv-python-headless    # suivi de visage + détection de plans
  pip install torch transformers pillow # recherche sémantique CLIP
EOF
