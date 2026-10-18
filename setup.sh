#!/usr/bin/env bash
# Installation de ShortsForge : environnement virtuel isolé + dépendances.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PY="${PYTHON:-python3}"

if ! "$PY" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "✖ ShortsForge nécessite Python 3.10 ou plus récent." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "→ création de l'environnement virtuel .venv"
  if ! "$PY" -m venv .venv; then
    rm -rf .venv
    echo "✖ Impossible de créer .venv. Sous Debian/Ubuntu, installez le paquet python3-venv puis relancez." >&2
    exit 1
  fi
fi

echo "→ installation des dépendances Python"
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt
./.venv/bin/python -m pip install --quiet -e .

echo "→ vérification des nappes musicales et des bruitages locaux"
if [ ! -f assets/sfx/whoosh.mp3 ]; then
  ./.venv/bin/python -m shortsforge.cli sfx all
fi
for style in upbeat_minor bright_pop corporate_hop dark_trap; do
  if [ ! -f "assets/music/beat_${style}.mp3" ]; then
    ./.venv/bin/python -m shortsforge.cli music --style "$style" --duration 45
  fi
done

./sf skills index

echo
echo "✓ Installation terminée."
echo "  ./sf doctor        # état de l'environnement"
echo "  ./sf skills list   # bibliothèque de skills"
echo "  ./sf studio        # studio web (aperçu live)"
