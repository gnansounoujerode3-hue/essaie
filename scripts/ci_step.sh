#!/usr/bin/env bash
# Exécute une commande de CI, rejoue sa sortie et publie la fin du journal en
# annotations GitHub Actions (::error::) quand elle échoue.
#
#   bash scripts/ci_step.sh "Validation" python tests/validate_skills.py --help-check
#
# Pourquoi : les journaux bruts des runners ne sont pas toujours accessibles
# (stockage externe filtré) ; les annotations, elles, restent lisibles via l'API.
set -uo pipefail

LABEL="${1:?libellé manquant}"
shift

LOG="$(mktemp)"
cleanup() { rm -f "$LOG"; }
trap cleanup EXIT

set +e
"$@" >"$LOG" 2>&1
status=$?
set -e

cat "$LOG"

if [[ $status -ne 0 ]]; then
  echo "::group::Dernières lignes ($LABEL, code $status)"
  # 20 dernières lignes, échappées pour le protocole d'annotation
  tail -n 20 "$LOG" | while IFS= read -r line; do
    line="${line//'%'/'%25'}"
    line="${line//$'\r'/}"
    printf '::error::%s\n' "$line"
  done
  echo "::endgroup::"
fi

exit "$status"
