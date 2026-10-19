---
name: viral-hooks-library
description: Bibliothèque de 24 structures d'accroches TikTok/Reels/Shorts (curiosité, contrarian, résultat, histoire, problème, liste, preuve, urgence, défi, comparaison) avec storyboard des 3 premières secondes, sons, visuels et variantes A/B. Utiliser ce skill pour « trouver un hook », « accroche virale », « première seconde » ou « améliorer une intro ».
license: MIT
metadata:
  version: 1.0.0
  category: optimisation
  requires: rien
---

# Bibliothèque de hooks viraux

## Quand l'utiliser

- Écrire un hook pour un Short/Reel/TikTok sans repartir d'une page blanche.
- Tester plusieurs angles (curiosité, contrarian, preuve) sur le même sujet.
- Construire le storyboard des 3 premières secondes (visuel, texte, son).
- Diagnostiquer un hook faible repéré par `retention-chart-analyzer`.

## Explorer

```bash
python3 scripts/generate_hooks.py --list
python3 scripts/generate_hooks.py --list-category contrarian
```

## Générer un plan de hook

```bash
python3 scripts/generate_hooks.py --topic "les sous-titres animés" \
  --platform tiktok --count 5 --md hook.md --json hook.json \
  --set "public=créateurs" --set "chiffre=87 %"
```

Astuce : inclure l'article dans le sujet (« **les** sous-titres animés », « **le** montage »
plutôt que le mot seul) pour une phrase correcte.

## Ce que contient le plan

- **Hook principal** avec angle, mécanique, score viral estimé et justification.
- **Storyboard 0 → 3 s** : plan, intention, mouvement de caméra, son.
- **Structure 0 → 20 s** : pattern interrupt, promesse, contexte, première valeur, boucle/CTA.
- **4 variantes** issues d'autres catégories.
- **3 A/B tests** (question, preuve, contrarian).
- **Réglages de montage** : format, style de captions, requêtes B-roll, pacing,
  première frame.

## Les 10 mécaniques

| Mécanique | Principe |
|-----------|----------|
| boucle ouverte | promettre puis repousser la révélation |
| contraste | casser une croyance |
| preuve sociale | chiffre, résultat, témoin |
| enjeu | ce que le spectateur perd |
| identification | viser explicitement un public |
| pattern interrupt | rupture visuelle/sonore à 0,5 s |

## Options

- `--category` (10 catégories), `--platform tiktok|reels|shorts|youtube|linkedin`
- `--set clé=valeur` pour remplir `{sujet}`, `{public}`, `{chiffre}`, `{delai}`…
- `--seed 7` pour varier la sélection de templates.
- `--library hooks.json` pour une bibliothèque personnalisée.

## Limites

- Les templates sont des **structures**, pas des phrases prêtes à publier : adapter au
  ton de la chaîne.
- Le « score viral » est heuristique (chiffre, question, contraste, longueur, adresse
  directe) — ce n'est pas une prédiction.
- Les tendances évoluent : mettre à jour `hooks.json` régulièrement.

## Suite logique

`highlight-detector-ai` (extrait existant), `animated-captions-generator` (hook lisible),
`music-beat-sync` (impact sur le premier mot), `retention-chart-analyzer` (mesurer).
