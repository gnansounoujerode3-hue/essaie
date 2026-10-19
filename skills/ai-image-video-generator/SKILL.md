---
name: ai-image-video-generator
description: Construit des prompts de réalisation et des payloads API pour Midjourney, Runway, Luma, Sora, Kling, Pika et FLUX, génère un plan de shots IA depuis une transcription et peut lancer les générations (Runway/Luma) avec téléchargement. Utiliser ce skill quand les banques d'images ne suffisent pas : « générer un B-roll IA », « prompt Midjourney », « Runway/Luma », « visuel sur mesure ».
license: MIT
metadata:
  version: 1.0.0
  category: habillage
  requires: ffmpeg (optionnel), clé API du provider pour l'exécution
---

# Génération d'images & vidéos IA

Le skill ne remplace pas les modèles : il produit des **prompts de réalisateur**,
des **payloads prêts à envoyer** et sait **exécuter** les providers qui exposent une
API officielle.

## Quand l'utiliser

- Écrire des prompts de réalisation cohérents (lumière, focale, mouvement, durée) pour un shot précis.
- Construire un plan de shots IA à partir d'une transcription, avec continuité visuelle.
- Lancer et récupérer une génération Runway ou Luma via API, sans quitter le terminal.
- Préparer un brief pour Midjourney, Sora, Kling ou Pika, qui n'exposent pas d'API publique.

## Providers

| Provider | Type | API | Variable |
|----------|------|-----|----------|
| Midjourney | image | non (Discord/web) | — |
| Runway Gen-4 | vidéo | oui | `RUNWAY_API_KEY` |
| Luma Dream Machine | vidéo | oui | `LUMAAI_API_KEY` |
| Sora | vidéo | non | — |
| Kling | vidéo | oui | selon le compte |
| Pika | vidéo | non | — |
| FLUX / SDXL | image | oui (auto-hébergé) | selon l'instance |

```bash
python3 scripts/generate.py guide
```

## Construire un prompt

```bash
python3 scripts/generate.py prompt \
  --subject "bureau de nuit, monteur devant sa timeline" \
  --action "il coupe une séquence" --setting "pièce sombre, néons" \
  --shot-type hook --provider runway --out prompt.json
```

Le prompt assemble : sujet, action, décor, caméra, lumière, style, palette, mood,
et ajoute les contraintes verticales (9:16, aucun texte à l'écran, durée).

## Plan de shots depuis une transcription

```bash
python3 scripts/generate.py plan --media podcast.mp4 --provider luma \
  --every 8 --max-shots 15 --md shots.md --out shots.json
```

Une proposition toutes les N secondes, avec le texte source, la requête courte et
le prompt complet.

## Exécuter réellement

```bash
export RUNWAY_API_KEY=…     # ne jamais coller la clé dans le chat
python3 scripts/generate.py request --provider runway --prompt "…" \
  --execute --download --output-dir ai-assets
```

Le script envoie la tâche, suit son état (`GET /tasks/{id}` ou `/generations/{id}`),
puis télécharge le rendu terminé. Erreurs HTTP détaillées et timeout configurable
(`--timeout 600`).

## Bonnes pratiques

- Générer en **9:16 natif** plutôt que recadrer.
- 5 à 8 s par plan : le montage coupera dedans.
- Garder la même palette que l'habillage (voir `motion-design-templates`).
- Les plans IA illustrent, ils ne **prouvent** rien : ne pas les utiliser pour simuler
  un résultat client.
- Vérifier les conditions d'utilisation de chaque provider (droits commerciaux, watermark).

## Limites

- Midjourney, Sora et Pika n'ont pas d'API publique : le skill fournit le prompt,
  pas l'automatisation.
- Le coût est à la charge du compte provider (crédits).
- Aucune génération hors ligne.

## Suite logique

`broll-finder-indexer` (placer les plans), `animated-captions-generator`, `ffmpeg-power-tools`.
