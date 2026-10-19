# Exemples

| Fichier | Usage |
|---------|-------|
| `transcript-example.srt` | transcription d'exemple pour tester tous les skills sans Whisper |
| `edit-example.json` | plan de montage au format pivot (Premiere / AE / Resolve) |
| `retention.csv` | export de rétention YouTube factice pour `retention-chart-analyzer` |

```bash
# Tester la chaîne de sous-titres sans transcrire
python3 skills/animated-captions-generator/scripts/generate.py \
  --transcript examples/transcript-example.srt --style hormozi --out /tmp/demo.ass

# Générer un plan Premiere/AE/Resolve
python3 skills/premiere-pro-extendscript-generator/scripts/build_premiere.py \
  --plan examples/edit-example.json --out-prefix /tmp/edit

# Analyser une courbe de rétention
python3 skills/retention-chart-analyzer/scripts/analyze_retention.py \
  --csv examples/retention.csv --md /tmp/retention.md
```
