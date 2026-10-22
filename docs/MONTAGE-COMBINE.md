# Montage combiné — du rush brut à la vidéo finale

La chaîne de production qui combine les points forts de chaque famille de skills
installée, dans le bon ordre. Principe : **un seul moteur par tâche**, choisi pour ce
qu'il fait de mieux, et les **règles de production de video-use** partout où une
erreur silencieuse est possible.

## Qui fait quoi

| Famille | Point fort retenu | Utilisé pour |
|---|---|---|
| **VESK** (ce dépôt) | scripts locaux reproductibles, 100 % FFmpeg/Python, en français | le gros du travail : transcription, dérushage, coupes, captions animées, B-rolls, 9:16, audio, SFX, exports NLE |
| **video-use** (browser-use) | méthode éditoriale : *demander → confirmer → exécuter → vérifier* + « Hard Rules » | la stratégie de coupe validée **avant** de toucher au rush ; coupes aux frontières de mots, fondus audio 30 ms, sous-titres **en dernier**, vérification du rendu avant livraison |
| **HyperFrames** (HeyGen) | motion design en HTML/JS (GSAP, Three.js, Lottie) rendu en vidéo, ~450 blocs du registry | habillages sur mesure : intro, titres animés, overlays, cartes, callouts — générés comme segments séparés puis composités |
| **Remotion** (officiel) | vidéo React déterministe, templates et données | variantes en série (même template × N données), data-vidéo, rendus pixel-parfait répétables (vérifier sa licence selon la structure) |
| **find-skills** (ce dépôt) | ne pas réinventer | si une capacité manque en cours de route, on cherche d'abord en local |

Règle de choix pour la couche « motion » : **VESK ASS** par défaut (rapide, local) ;
**HyperFrames** si l'effet demandé dépasse l'ASS (3D, physique, web) ;
**Remotion** si la même vidéo doit être déclinée en série. Jamais les deux moteurs
génératifs sur le même projet.

## La chaîne en 8 phases

Le rush brut ne quitte jamais son dossier : tous les livrables vont dans
`<dossier>/edit/` (transcriptions cachées, jamais re-transcrites sans raison).

### 1. Stratégie (video-use) — avant toute coupe

Confirmer en langage clair : objectif, plateforme(s), format(s), durée cible,
langue, style de captions, musique/SFX, passages intouchables ou à supprimer.
Sans brief, défauts : **Short vertical 9:16 de 30–45 s + version native**,
captions `hormozi` françaises, hook dans les 1,5 premières secondes.

### 2. Transcription mot à mot (VESK)

```bash
python3 skills/speech-to-text-whisper/scripts/transcribe.py rush.mp4 --language fr
# environnement restreint (aucun téléchargement de modèle possible) :
python3 skills/speech-to-text-whisper/scripts/transcribe.py rush.mp4 \
  --language fr --provider whispercpp --model base
```

`whispercpp` lit un modèle ggml déjà présent (`~/models/ggml-*.bin`,
`WHISPERCPP_MODEL` ou chemin direct) : `small`/`base` recommandés en français,
`tiny` en dépannage. Un SRT fourni par l'utilisateur fait aussi l'affaire.

### 3. Dérushage (VESK)

```bash
python3 skills/video-transcript-analyser/scripts/analyze.py \
  --transcript rush.transcript.json --media rush.mp4 --md edit/derush.md
python3 skills/highlight-detector-ai/scripts/detect.py \
  --transcript rush.transcript.json --media rush.mp4 --json edit/highlights.json
```

### 4. Coupe (VESK + règles video-use)

```bash
python3 skills/silence-removal-automation/scripts/cut_silences.py \
  --media rush.mp4 --render edit/rush-cut.mp4 \
  --transcript rush.transcript.json --srt edit/cut.srt
```

Règles non négociables héritées de video-use : **jamais de coupe au milieu d'un
mot** (frontières de mots de la transcription), **30–200 ms de marge** selon le
rythme, et on ne coupe que le plan confirmé en phase 1.

### 5. Image : recadrage, B-rolls, overlays (VESK, HyperFrames/Remotion si besoin)

```bash
python3 skills/auto-framing-916/scripts/reframe.py \
  --media edit/rush-cut.mp4 --out edit/rush-916.mp4        # si vertical
python3 skills/broll-finder-indexer/scripts/index_library.py \
  --library ~/Footage --out edit/library.json
python3 skills/motion-design-templates/scripts/motion.py \
  --template title --text "…" --out edit/titre.ass
```

Effet au-delà de l'ASS → générer l'overlay avec HyperFrames (ou le segment templaté
avec Remotion), le rendre à part, puis le compositer avec FFmpeg
(`overlay` + `setpts=PTS-STARTPTS+T/TB` pour caler son frame 0 — sinon on voit le
milieu de l'animation).

### 6. Audio (VESK)

```bash
python3 skills/audio-cleaning-enhancer/scripts/clean.py \
  --input edit/rush-cut.mp4 --out edit/voix.wav --preset podcast
python3 skills/sound-effect-cue-automator/scripts/build_catalog.py --generate --out edit/sfx
python3 skills/music-beat-sync/scripts/beat_sync.py \
  --media edit/rush-cut.mp4 --json edit/beats.json --cuts-json edit/cuts.json
```

### 7. Sous-titres animés — **en dernier** (VESK, règle video-use n° 1)

Après **tous** les overlays, sinon ils masquent les captions :

```bash
python3 skills/emoji-keyword-mapper/scripts/map_emojis.py \
  --transcript rush.transcript.json --out edit/emoji-map.json --keywords-out edit/keywords.json
python3 skills/animated-captions-generator/scripts/generate.py \
  --transcript rush.transcript.json --style hormozi \
  --emoji-map edit/emoji-map.json --keywords edit/keywords.json \
  --media edit/rush-916.mp4 --out edit/captions.ass --srt edit/captions.srt \
  --burn edit/final.mp4
```

### 8. Vérification avant livraison (video-use n° 7 : « si tu ne le publierais pas, ne le montre pas »)

- [ ] Extraire 5–10 frames (`ffmpeg -ss … -frames:v 1`) et les **regarder** :
      captions lisibles, aucun débordement, overlays au bon timecode.
- [ ] Écouter les jonctions : aucun « pop » aux coupes, voix toujours devant la musique.
- [ ] Hook compréhensible dès 1,5 s, son coupé (lecture muette).
- [ ] SRT maître recalé sur la timeline **de sortie** (pas celle du rush).
- [ ] Durée, format et poids conformes à la plateforme visée.

## Livrables

`edit/final.mp4` (+ déclinaisons), `edit/captions.srt`, transcription JSON,
rapports de dérushage, et sur demande un projet NLE (Premiere/AE/Resolve via les
skills VESK dédiés) pour la finition manuelle.

## Limites connues de la chaîne

- `whispercpp` en modèle `tiny` : transcription FR approximative — préférer
  `base`/`small`, faster-whisper, ou un SRT fourni.
- HyperFrames/Remotion rendent dans des projets Node séparés : prévoir
  l'installation de leurs dépendances au premier usage, et la licence Remotion
  pour les structures de 3+ personnes.
- Le scoring des moments forts reste lexical : la sélection finale se relit.
