# ShortsForge — aide-mémoire

## Formule d'un Short performant

```text
0.0–3.0 s     HOOK : promesse / résultat / erreur, immédiatement
3.0–(fin-3)   CORPS : une idée, preuve, exemple, payoff
3 dernières s CTA unique OU raccord de boucle sur le premier plan

9:16 • 1080×1920 • 30 fps • 15–45 s
Coupes visuelles : 1,5–3 s • captions au centre • safe zone haut/bas/droite
Voix en avant (1,05–1,10×) • musique duckée • SFX discrets
```

## Démarrer

```bash
./setup.sh
./sf doctor
./sf skills list
```

## Composer un brief

```bash
./sf brief \
  --skills hook-architect script-compiler rhythm-director broll-curator caption-artist audio-mixmaster loop-engineer cta-converter qa-gatekeeper \
  --context "Audience, offre, objectif, ton de marque" \
  --out output/brief.md
```

Voir une skill complète :

```bash
./sf skills show hook-architect
./sf skills prompt --skills hook-architect script-compiler caption-artist
./sf skills index
```

## Planifier

```bash
./sf plan \
  --title "Titre du Short" \
  --slug titre-du-short \
  --duration 28 \
  --script "Le hook. Première idée. Deuxième idée. Le payoff. Abonne-toi pour la suite." \
  --source assets/media/creator_studio.jpg assets/media/editing_timeline.jpg \
  --out examples/titre-du-short.yaml
```

Le script doit contenir au moins un hook et une phrase de corps. Ajuster le spec généré : sources par plan, motion, textes, stickers, B-roll, music, voiceover, SFX et CTA.

## Voix → sous-titres → rendu

```bash
./sf align examples/titre-du-short.yaml --voice assets/audio/vo_demo.mp3
./sf render examples/titre-du-short.yaml --qa
./sf qa examples/titre-du-short.yaml --json
```

Réglages dans le YAML :

```yaml
voiceover:
  path: assets/audio/vo_demo.mp3
  speed: 1.06       # recommandé 1.05–1.10, rester naturel
  gain_db: 0

music:
  path: assets/music/beat_upbeat_minor.mp3
  gain_db: -19
  duck: true

cta:
  text: "ABONNE-TOI"
  subtext: "1 astuce par jour"
  at: 24.5
  duration: 2.5
```

## Générer une musique/SFX

```bash
./sf music --style upbeat_minor --duration 30 --bpm 128
./sf music --style bright_pop --duration 30 --bpm 124
./sf music --style corporate_hop --duration 30 --bpm 116
./sf music --style dark_trap --duration 30 --bpm 140
./sf sfx all
```

Les banques fournies sont procédurales. Pour le rendu publié, n'utiliser qu'une musique dont l'usage est autorisé ; un son tendance doit être ajouté/remplacé dans la plateforme si sa licence l'exige.

## Batch et Studio

```bash
./sf batch examples/
./sf studio --host 0.0.0.0 --port 8080
```

Le Studio liste les MP4 d'`output/`, lit les vidéos, montre le score QA après un rendu et permet de lancer un spec depuis le navigateur.

## Vérification rapide

```bash
python -m unittest discover -s tests -v
python -m compileall -q shortsforge
./sf qa examples/demo_3_erreurs.yaml
```

## Échelle QA

- **S (90–100)** : prêt après relecture humaine et vérification des droits.
- **A (80–89)** : bon ; traiter les alertes visibles.
- **B/C (55–79)** : corriger les points faibles avant publication.
- **D/E (<55)** : reprendre le hook, le montage ou la conformité.

Un score élevé n'est pas une garantie de performance commerciale.
