# VESK — Video Editing Skills Kit

[![CI](https://github.com/gnansounoujerode3-hue/essaie/actions/workflows/ci.yml/badge.svg)](https://github.com/gnansounoujerode3-hue/essaie/actions/workflows/ci.yml)

**19 skills de montage vidéo automatisé + 1 skill méta (`find-skills`)** pour agents IA
(Claude Code, Cursor, Codex…), en français, sans dépendance obligatoire hors **FFmpeg**
et **Python 3.9+**.

Chaque skill est un dossier `skills/<nom>/` avec :
- un `SKILL.md` au format Agent Skills (frontmatter `name` + `description`),
- des scripts CLI exécutables immédiatement,
- ses données de référence (styles, templates, dictionnaires, catalogue).

```
Dérushage → sous-titres animés → B-rolls/recadrage → sound design
→ NLE (Premiere / After Effects / Resolve) → analyse de rétention → hooks
```

---

## 1. Installation rapide

```bash
git clone <ce-repo> vesk && cd vesk

# macOS / Linux — copie vers ~/.claude/skills
./scripts/install.sh

# Liens symboliques (les mises à jour du dépôt sont immédiates)
./scripts/install.sh --mode link

# Dossier personnalisé / installation partielle
./scripts/install.sh --target ~/.config/agents/skills \
  --only animated-captions-generator,silence-removal-automation

# Vérifier que tout fonctionne (39 contrôles + mini-pipeline)
./scripts/selftest.sh

# Voir le pack à l'œuvre sur un rush généré automatiquement
./scripts/demo.sh demo

# Retirer l'installation
./scripts/install.sh --uninstall
```

Raccourcis équivalents : `make install`, `make link`, `make test`, `make selftest`,
`make demo`, `make uninstall` (voir `Makefile`).

Windows (PowerShell) :

```powershell
.\scripts\install.ps1
.\scripts\install.ps1 -Mode link -Target C:\skills -Force
.\scripts\install.ps1 -Only animated-captions-generator,viral-hooks-library
.\scripts\install.ps1 -Uninstall
```

### Prérequis

| Élément | Obligatoire | Notes |
|---------|-------------|-------|
| Python **3.9+** | oui | stdlib uniquement pour le socle |
| **FFmpeg** (avec libass) | oui pour la vidéo | `brew install ffmpeg-full` · `sudo apt install ffmpeg` · `winget install Gyan.FFmpeg` |
| ffprobe | non | repli automatique sur `ffmpeg -i` |
| faster-whisper | non | transcription locale — `pip install faster-whisper` |
| pywhispercpp + modèle ggml | non | transcription locale sans téléchargement de modèle par le code — `pip install pywhispercpp` |
| opencv-python-headless | non | suivi de visage / détection de plans |
| torch + transformers + pillow | non | recherche sémantique CLIP |
| clés API | non | OpenAI / Groq / ElevenLabs / Runway / Luma / Pexels / Pixabay |

Sans admin : `pip install imageio-ffmpeg` fournit un binaire FFmpeg que le socle détecte
automatiquement (variable `FFMPEG_BIN` pour forcer un chemin).

---

## 2. Les 20 skills

### 1 · Dérushage, analyse & tri intelligents

| Skill | Rôle |
|-------|------|
| [`video-transcript-analyser`](skills/video-transcript-analyser/SKILL.md) | silences, tics de langage, débit, mots-clés, répétitions → rapport de dérushage |
| [`speech-to-text-whisper`](skills/speech-to-text-whisper/SKILL.md) | transcription horodatée **mot par mot** (faster-whisper, Whisper, OpenAI, Groq) |
| [`silence-removal-automation`](skills/silence-removal-automation/SKILL.md) | auto-cut des blancs (suppression ou accélération) + sous-titres remappés |
| [`highlight-detector-ai`](skills/highlight-detector-ai/SKILL.md) | hooks et moments forts scorés, clips 18–45 s prêts à publier |

### 2 · Génération de sous-titres dynamiques

| Skill | Rôle |
|-------|------|
| [`animated-captions-generator`](skills/animated-captions-generator/SKILL.md) | styles Hormozi / Ali Abdaal / karaoké / néon, pop par mot, auto-fit anti-débordement |
| [`emoji-keyword-mapper`](skills/emoji-keyword-mapper/SKILL.md) | mots-clés + emojis (200+ entrées FR/EN) avec timings |

### 3 · Habillage visuel, B-rolls & transitions

| Skill | Rôle |
|-------|------|
| [`broll-finder-indexer`](skills/broll-finder-indexer/SKILL.md) | index de rushes, recherche lexicale **ou CLIP**, téléchargement Pexels/Pixabay |
| [`auto-framing-916`](skills/auto-framing-916/SKILL.md) | 16:9 → 9:16 avec suivi de visage, centré ou fond flou |
| [`motion-design-templates`](skills/motion-design-templates/SKILL.md) | titres, lower thirds, chapitres, citations, compteurs, CTA en ASS |
| [`ai-image-video-generator`](skills/ai-image-video-generator/SKILL.md) | prompts + payloads Midjourney/Runway/Luma/Sora/FLUX, exécution Runway & Luma |

### 4 · Sound design & mixage audio

| Skill | Rôle |
|-------|------|
| [`sound-effect-cue-automator`](skills/sound-effect-cue-automator/SKILL.md) | whoosh/pop/braam placés sur transitions, mots-clés et sous-titres, mixés |
| [`audio-cleaning-enhancer`](skills/audio-cleaning-enhancer/SKILL.md) | denoise, EQ, compression, loudness EBU R128 2 passes, isolation ElevenLabs |
| [`music-beat-sync`](skills/music-beat-sync/SKILL.md) | BPM + grille de beats, coupes recalées, accents visuels sur les temps |

### 5 · Automatisation & scripts pour logiciels (NLE)

| Skill | Rôle |
|-------|------|
| [`premiere-pro-extendscript-generator`](skills/premiere-pro-extendscript-generator/SKILL.md) | FCPXML / XMEML / EDL / marqueurs + JSX d'import, markers, export |
| [`after-effects-scripting`](skills/after-effects-scripting/SKILL.md) | comp, placement, captions keyframées, pulse BPM, sauvegarde `.aep` |
| [`davinci-resolve-python-api`](skills/davinci-resolve-python-api/SKILL.md) | timeline FCPXML, marqueurs, LUT, CDL, rendu automatique |
| [`ffmpeg-power-tools`](skills/ffmpeg-power-tools/SKILL.md) | compresser, convertir, découper, GIF, vignettes, hardsub, batch |

### 6 · Analyse des tendances & optimisation

| Skill | Rôle |
|-------|------|
| [`retention-chart-analyzer`](skills/retention-chart-analyzer/SKILL.md) | courbes YouTube, décrochages/pics, croisement avec la transcription |
| [`viral-hooks-library`](skills/viral-hooks-library/SKILL.md) | 24 hooks, storyboard 3 s, sons/visuels, variantes A/B |

### 7 · Écosystème & découverte

| Skill | Rôle |
|-------|------|
| [`find-skills`](skills/find-skills/SKILL.md) | trouver le bon skill : recherche locale (déjà installé ?) puis skills.sh via `npx skills`, contrôle qualité (installations, source, étoiles) et installation. Adapté du skill amont `find-skills` de [vercel-labs/skills](https://skills.sh/vercel-labs/skills/find-skills) (MIT) |

---

## 3. Démarrage en 5 commandes

```bash
# 1. Transcrire (ou fournir un SRT existant)
python3 skills/speech-to-text-whisper/scripts/transcribe.py interview.mp4 --language fr

# 2. Analyser et couper les silences
python3 skills/silence-removal-automation/scripts/cut_silences.py \
  --media interview.mp4 --render interview-cut.mp4 \
  --transcript interview.transcript.json --srt interview-cut.srt

# 3. Sous-titres animés + emojis
python3 skills/emoji-keyword-mapper/scripts/map_emojis.py \
  --transcript interview-cut.transcript.json --out emoji-map.json --keywords-out keywords.json
python3 skills/animated-captions-generator/scripts/generate.py \
  --transcript interview-cut.transcript.json --style hormozi \
  --emoji-map emoji-map.json --keywords keywords.json --burn interview-final.mp4

# 4. Sound design automatique
python3 skills/sound-effect-cue-automator/scripts/build_catalog.py --generate --out sfx
python3 skills/sound-effect-cue-automator/scripts/plan_cues.py \
  --transcript interview-cut.transcript.json --media interview-final.mp4 \
  --keywords keywords.json --wav sfx.wav --mix interview-sfx.mp4

# 5. Clips courts à partir des meilleurs moments
python3 skills/highlight-detector-ai/scripts/detect.py \
  --transcript interview.transcript.json --media interview.mp4 \
  --render-dir clips/ --captions hormozi
```

Toutes les commandes acceptent `--help` et `--dry-run` quand une action est destructive.

---

## 4. Pipelines prêtes à l'emploi

| Objectif | Enchaînement |
|----------|--------------|
| **Short depuis un long format** | `highlight-detector-ai` → `auto-framing-916` → `animated-captions-generator` → `sound-effect-cue-automator` |
| **Podcast propre et rythmé** | `audio-cleaning-enhancer` → `silence-removal-automation` → `music-beat-sync` → `ffmpeg-power-tools` |
| **Montage délégué à un monteur** | `highlight-detector-ai` → `broll-finder-indexer` → `premiere-pro-extendscript-generator` (FCPXML + JSX) |
| **Rendu DaVinci étalonné** | `davinci-resolve-python-api` (timeline + LUT + CDL + render) |
| **Refonte d'une vidéo qui décroche** | `retention-chart-analyzer` → `viral-hooks-library` → réécriture du hook → re-montage |
| **Habillage IA** | `ai-image-video-generator` (plan) → `broll-finder-indexer` (placement) → `motion-design-templates` |
| **Capacité manquante** | `find-skills` (local d'abord, puis skills.sh) → `npx skills add <propriétaire>/<dépôt>@<skill> -g -y` |
| **Rush brut → vidéo finale** | chaîne combinée VESK + video-use + HyperFrames/Remotion : [`docs/MONTAGE-COMBINE.md`](docs/MONTAGE-COMBINE.md) |

Détails et commandes exactes : [`docs/PIPELINES.md`](docs/PIPELINES.md).

---

## 5. Architecture

```
vesk/
├── skills/                     # 20 skills autonomes (SKILL.md + scripts/ + données)
│   └── <skill>/
│       ├── SKILL.md            # frontmatter name/description + mode d'emploi
│       ├── scripts/*.py        # CLI
│       └── *.json              # styles, templates, dictionnaires, catalogues
├── shared/vesk/                # bibliothèque commune (stdlib + FFmpeg)
│   ├── ffmpeg.py               # découverte FFmpeg, probe, silencedetect, burn
│   ├── transcript.py           # modèle de transcription, SRT/VTT, timings de mots
│   ├── speech.py               # faster-whisper / whisper / OpenAI / Groq / ElevenLabs
│   ├── captions.py             # moteur ASS animé (pop, karaoké, auto-fit)
│   ├── media.py                # TimeMap, rendu multi-coupes, recadrage, vitesses
│   ├── analyze.py              # scoring hooks / moments forts
│   ├── assets.py               # index B-roll, recherche lexicale + CLIP
│   ├── music.py                # BPM, beats, énergie, accents
│   ├── clean.py                # chaîne audio + loudness 2 passes
│   ├── sfx.py                  # cues, synthèse SFX, mix
│   ├── motion.py               # 8 templates de motion design
│   ├── retention.py            # parsing et analyse des courbes
│   ├── hooks.py                # bibliothèque de hooks + plan 3 s
│   ├── nle_premiere.py         # FCPXML / XMEML / EDL / JSX Premiere
│   ├── nle_aftereffects.py     # JSX After Effects
│   ├── davinci.py              # scripts Resolve
│   ├── imagegen.py             # prompts et exécution IA
│   └── skillfinder.py          # découverte de skills (local + skills.sh)
├── scripts/install.sh|ps1      # installation
├── scripts/selftest.sh         # diagnostic + pipeline de bout en bout
├── tests/                      # 42 tests unitaires (sans FFmpeg)
├── examples/                   # plan de montage, rétention CSV, transcriptions
└── docs/                       # pipelines, dépannage, exigences
```

### Principe de résolution de la bibliothèque partagée

Chaque script cherche `vesk/` dans les parents (`shared/` en dépôt, `_shared/` après
installation) : le même fichier fonctionne cloné ou copié.

### Format pivot

Toute la chaîne parle le même JSON :

```json
{
  "language": "fr",
  "duration": 61.2,
  "segments": [
    {"id": 1, "start": 0.5, "end": 2.8, "text": "…",
     "words": [{"word": "Regarde", "start": 0.5, "end": 0.9}]}
  ]
}
```

Accepté en entrée : JSON, SRT, VTT, TXT (réparti automatiquement).

---

## 6. Clés API (facultatives)

| Service | Variable | Usage |
|---------|----------|-------|
| OpenAI Whisper | `OPENAI_API_KEY` | transcription API |
| Groq | `GROQ_API_KEY` | transcription très rapide |
| ElevenLabs | `ELEVENLABS_API_KEY` | isolation de la voix |
| Runway | `RUNWAY_API_KEY` | génération vidéo + téléchargement |
| Luma | `LUMAAI_API_KEY` | génération vidéo |
| Pexels | `PEXELS_API_KEY` | B-rolls gratuits |
| Pixabay | `PIXABAY_API_KEY` | B-rolls gratuits |

Sans clé, tout le reste fonctionne : transcription locale, sous-titres, montage,
sound design, NLE. **Ne jamais coller une clé dans une conversation** : exporter la
variable d'environnement.

---

## 7. Limites connues (assumées)

- **Pas de rendu tiers payant** : Midjourney, Sora et Pika n'ont pas d'API publique ;
  le skill fournit des prompts de qualité, pas l'automatisation.
- **Pas de vrai 3D** : le motion design est vectoriel 2D en ASS. Pour de la 3D,
  passer par le JSX After Effects.
- **Scoring de hooks lexical** : il repère les structures qui retiennent, il ne comprend
  pas le sens profond. Toujours relire.
- **Emojis et polices** : dépendent des polices installées sur la machine qui rend.
  Le script prévient quand une police manque et réduit la taille pour éviter tout débordement.
- **API Resolve** : l'étalonnage CDL est global ; le scripting est plus complet en
  version Studio.
- **FFmpeg sans libass** : les fichiers ASS restent produits et utilisables dans un NLE,
  seule l'incrustation directe échoue (message explicite).

---

## 8. Tests et qualité

```bash
python3 -m unittest discover -s tests -v    # 42 tests, sans FFmpeg
bash scripts/selftest.sh                    # 39 contrôles + pipeline réelle
```

Le selftest génère ses propres médias de test (lavfi), vérifie les 20 skills, les CLI,
la compilation, puis exécute transcription → cut → captions → burn → highlights →
B-rolls → SFX → BPM → rétention → hooks → compression.

---

## 9. Dépannage

Voir [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) : FFmpeg/libass absent,
polices manquantes, emojis en carrés, Whisper lent, FCPXML non relié, permissions
macOS, console Windows en cp1252, etc.

## 10. Licence

MIT. Les SFX générés sont libres de droits (synthèse FFmpeg). Les B-rolls téléchargés
conservent leur licence d'origine (`licenses.json`). Les polices (Montserrat, Inter)
ne sont pas incluses : installer la famille depuis Google Fonts, ou utiliser une
police système.
