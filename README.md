# ShortsForge

**Le studio open-source pour concevoir, monter et contrôler des Shorts marketing verticaux.** ShortsForge transforme une idée et un `ShortSpec` YAML/JSON en MP4 H.264/AAC — avec coupes, mouvements de caméra, textes animés, B-roll, sous-titres mot par mot, voix, musique duckée, SFX et contrôle qualité.

> La méthode est codifiée dans 13 skills Markdown autonomes et composables. Le rendu est un vrai moteur Python/FFmpeg : ce dépôt n'est pas seulement une collection de conseils.

## La méthode en 15 secondes

- **0–3 s :** hook immédiatement compréhensible, promesse ou curiosité.
- **3–50 s :** une idée à la fois, coupes visuelles environ toutes les **1,5 à 3 s**.
- **Tout au long :** mouvement discret (Ken Burns/pan), B-roll, texte graphique, sous-titres lisibles même sans son.
- **Fin :** un CTA clair ou un raccord visuel/sonore qui relance le hook.
- **Format :** 9:16, **1080 × 1920**, 30 fps, zone de sécurité centrée, durée conseillée 15–45 s.

Le détail de la méthode est dans [METHOD.md](METHOD.md), et les commandes fréquentes dans [CHEATSHEET.md](CHEATSHEET.md).

## Démarrage rapide

Prérequis : Python 3.10 ou plus récent. Le paquet `imageio-ffmpeg` apporte un FFmpeg statique ; aucune installation système de FFmpeg n'est nécessaire.

```bash
# Depuis la racine du dépôt
./setup.sh
./sf doctor
./sf skills list
./sf qa examples/demo_3_erreurs.yaml
./sf render examples/demo_3_erreurs.yaml --qa
```

`setup.sh` crée `.venv`, installe le moteur et ses dépendances, puis génère les banques locales de musique et de bruitages. `.venv/` est volontairement ignoré par Git ; relancez le script sur chaque nouvelle machine.

Installation manuelle équivalente :

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
./sf doctor
```

## Produire un premier Short

### 1. Composer un brief avec les skills

```bash
./sf brief \
  --skills hook-architect script-compiler rhythm-director broll-curator caption-artist audio-mixmaster loop-engineer cta-converter qa-gatekeeper \
  --context "Marque de cosmétiques naturels; audience 20–35 ans; objectif: obtenir des abonnements." \
  --out output/brief.md
```

Afficher un skill autonome :

```bash
./sf skills show hook-architect
./sf skills prompt --skills hook-architect script-compiler caption-artist
./sf skills index  # régénère skills/manifest.json
```

### 2. Générer un plan depuis un script

```bash
./sf plan \
  --title "Trois erreurs qui tuent tes vues" \
  --slug trois-erreurs \
  --duration 28 \
  --script "3 erreurs qui tuent tes vues. Un : commence par te présenter. Deux : laisse des plans morts. Trois : oublie les sous-titres. Abonne-toi pour la suite." \
  --source assets/media/creator_studio.jpg assets/media/editing_timeline.jpg assets/media/phone_closeup.jpg \
  --out examples/trois-erreurs.yaml
```

Le plan découpe le script en segments visuels courts et réserve un plan CTA à la fin. Complétez ensuite les mouvements, textes, stickers, médias et timecodes dans le YAML. Le modèle complet est dans [`examples/demo_3_erreurs.yaml`](examples/demo_3_erreurs.yaml).

### 3. Aligner la voix, rendre et vérifier

```bash
./sf align examples/trois-erreurs.yaml --voice assets/audio/vo_demo.mp3
./sf render examples/trois-erreurs.yaml --qa
./sf qa examples/trois-erreurs.yaml --json
```

Vous pouvez remplacer la voix de démonstration par un fichier enregistré ou généré avec l'outil vocal de votre choix. `sf align` détecte les pauses avec FFmpeg puis recale les mots sur la voix. Le moteur accélère la voix à **1,06× par défaut** (réglable dans `voiceover.speed`).

### 4. Ouvrir le Studio

```bash
./sf studio --host 0.0.0.0 --port 8080
```

Le Studio affiche la bibliothèque de skills, les specs, les MP4 présents dans `output/`, leur prévisualisation avec lecture/saut, et lance un rendu en arrière-plan. Il est servi par le même processus Python ; aucune compilation Node n'est requise.

## Commandes `sf`

| Commande | Rôle |
| --- | --- |
| `sf doctor` | Vérifie Python, FFmpeg, dépendances, polices, musique, SFX et skills. |
| `sf skills list\|show\|prompt\|index` | Explore, compose ou indexe la bibliothèque de skills. |
| `sf brief --skills ...` | Assemble un brief à partir d'une sélection de skills. |
| `sf plan` | Convertit le script en plans, captions, hook et CTA. |
| `sf render spec.yaml --qa` | Rend le MP4 et affiche son score QA. |
| `sf batch examples/` | Rend tous les specs YAML/JSON d'un dossier et donne un récapitulatif. |
| `sf qa spec.yaml [--json]` | Calcule le score de méthode/conformité et mesure le loudness si le MP4 existe. |
| `sf align spec.yaml --voice voix.mp3` | Synchronise les sous-titres au voice-over. |
| `sf music --style upbeat_minor --duration 30` | Génère une nappe musicale procédurale. |
| `sf sfx all` | Génère la bibliothèque de bruitages procéduraux. |
| `sf studio --port 8080` | Lance l'interface web locale. |

Pour les options complètes : `./sf <commande> --help`.

## Ce que produit le moteur

- **Vidéo :** conteneur MP4, H.264/libx264, 1080 × 1920, 30 fps, profil High, faststart.
- **Montage :** plans image ou vidéo, jump cuts, mouvements Ken Burns/pan/shake, flash/whip/glitch/dip, dégradés de secours.
- **Graphisme :** hook et CTA, typographie, stickers, B-roll en incrustation, étalonnage léger configurable.
- **Sous-titres :** rendu ASS/libass, affichage mot à mot/karaoké sans recomposition, polices fournies, zone de sécurité.
- **Audio :** voix filtrée/normalisée, accélération réglable, ducking sidechain de la musique, SFX retardés, cible de mix autour de −14 LUFS, limiteur true-peak.
- **QA :** score /100 et grade S–E pour le format, la durée, le hook, le rythme, les captions, la zone utile, le CTA, la boucle et le loudness.

Le score est un **outil de diagnostic**, pas une garantie de vues : les performances dépendent aussi du sujet, du public, de la distribution et des tests créatifs.

## Bibliothèque de skills

Les 13 compétences indépendantes se trouvent dans `skills/<id>/SKILL.md` :

1. `hook-architect` — hook et variantes d'accroche
2. `script-compiler` — script oral de 15–45 s
3. `rhythm-director` — rythme, plans, mouvements et coupes
4. `broll-curator` — B-roll, overlays et éléments graphiques
5. `caption-artist` — sous-titres dynamiques, taille et placement
6. `audio-mixmaster` — voix, musique, ducking et SFX
7. `loop-engineer` — raccord de fin et rewatch
8. `cta-converter` — action unique et mesurable
9. `brand-voice` — ton et identité de marque
10. `variant-lab` — tests A/B contrôlés
11. `perf-analyst` — diagnostic des métriques après publication
12. `publish-packager` — titres, descriptions, formats et packaging
13. `qa-gatekeeper` — contrôle avant publication

`skills/manifest.json` est l'index machine ; `sf skills prompt --skills ...` ou `sf brief --skills ...` permet de composer des compétences dans un agent ou un workflow.

## Spécification YAML

`ShortSpec` rassemble la vérité de production : marque, safe zone, format, hook, plans, mouvements, textes, stickers, B-roll, captions, voice-over, musique, SFX, CTA, boucle et sortie. Les sources relatives sont résolues depuis la racine du dépôt. Voir le schéma dans [`shortsforge/spec.py`](shortsforge/spec.py) et l'exemple complet dans `examples/`.

## Audio et droits médias

Les nappes et SFX fournis sont **synthétisés localement** : ce ne sont pas des tendances récupérées en ligne. Pour publier, remplacez la nappe par un son tendance autorisé dans la bibliothèque de la plateforme ou par une musique dont vous détenez les droits. Les trois images verticales du clip de démonstration ont été générées pour le projet ; remplacez-les par vos rushes ou vos médias sous licence. Les détails sont dans [`assets/media/README.md`](assets/media/README.md).

Aucun service externe de stock, de TTS ou de publication n'est appelé par le moteur. L'upload vers TikTok, Reels ou Shorts reste une étape manuelle.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q shortsforge
./sf doctor
```

Le smoke test historique est disponible avec `python examples/test_basic.py` (il écrit un petit MP4 dans `output/`).

## Structure

```text
shortsforge/          moteur Python, CLI, serveur et Studio
skills/               playbooks Markdown + manifest.json
assets/fonts/          polices pour Pillow/libass
assets/music/          beds procéduraux
assets/sfx/            bruitages procéduraux
assets/media/          visuels de démonstration (remplaçables)
assets/audio/          voix off de démonstration
examples/              smoke test et ShortSpec YAML
output/                MP4, QA et fichiers temporaires (ignorés par Git)
```
