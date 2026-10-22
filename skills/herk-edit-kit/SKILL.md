---
name: herk-edit-kit
description: Système de style et de rythme pour éditer talking-head/shorts en local (node) — bibliothèque de styles nommés (vox-explainer, kallaway), templates de motion (popout, graph paper), philosophie de montage, validation de beat-sync et préflight des médias avant rendu.
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  source: https://github.com/nateherkai/herk-edit-kit
---

# Herk Edit Kit (import MIT)

Kit de direction artistique : des **styles réutilisables** (pas des presets jetables)
appliqués à chaque vidéo, pilotés par transcript et calés sur la musique.

## Quand l'utiliser

- « aligner le montage sur la musique » (beat-sync), « appliquer un style de marque »,
  « templates de titres/popout », « préflight avant rendu ».
- P1/rythme des refs : styles + beat-sync pour tenir le tempo 1 coupe / 2-4 s.

## Démarrage rapide

```bash
node scripts/preflight.mjs            # vérifie médias, polices, entrées
node scripts/validate-beat-sync.mjs   # calage rythmique des coupes
python3 scripts/check_style.py        # intégrité de style-library/registry.json
```

## Ce que le kit apporte (liste manquante comblée)

| Manque | Élément du kit |
|--------|----------------|
| P2 rythme/calage | `scripts/validate-beat-sync.mjs`, `scripts/preflight.mjs` |
| P1 layouts/titres | `style-templates/` (left-glass-popout, dark-graph-paper…) |
| P2 systeme de marque | `style-library/` (01-vox-explainer, 02-kallaway, `GUIDE.md`) |
| P2 direction artistique | `MOTION_PHILOSOPHY.md`, `docs/` |
| P2 workflow | `WORKSPACE.md` (guide d'origine CLAUDE.md), `scripts/new-video.mjs` |

## Commandes des scripts

- `node scripts/build-edl-review.mjs` — revue d'EDL
- `node scripts/check-kit.mjs` — intégrité du kit
- `node scripts/new-video.mjs` — scaffold projet vidéo
- `node scripts/preflight.mjs` — préflight médias
- `node scripts/preflight-all.mjs` — préflight en lot
- `node scripts/setup.mjs` — installation npm
- `node scripts/smoke-media.mjs` — tests médias
- `node scripts/sync-codex-skills.mjs` — sync skills
- `node scripts/transcribe-elevenlabs.mjs` — transcription (clé API)
- `node scripts/validate-beat-sync.mjs` — contrôle beat-sync
- `node scripts/video-use-to-hyperframes-transcript.mjs` — transcript HyperFrames
- `python3 scripts/check_style.py` — vérifie style-library/

## Structure

```
herk-edit-kit/
├── SKILL.md               # ce fichier
├── WORKSPACE.md           # guide d'origine (runtime, workflow)
├── MOTION_PHILOSOPHY.md   # principes de motion
├── style-templates/       # templates de titres motion
├── style-library/         # styles complets + registry.json
├── docs/                  # procédures détaillées
└── scripts/               # preflight, beat-sync, scaffolding
```

Licence : MIT (voir `LICENSE.upstream`) — source : nateherkai/herk-edit-kit.
