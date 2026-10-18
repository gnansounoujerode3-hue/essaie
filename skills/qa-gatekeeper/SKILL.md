---
id: qa-gatekeeper
name: Gardien de Qualité
description: Contrôler la conformité d'un Short avant publication (format, rythme, zone de sécurité, audio, score).
version: 1.0.0
tags: [qualité, contrôle, publication, conformité]
when_to_use: Systématiquement avant chaque publication, et après chaque modification du rendu.
inputs:
  - ShortSpec
  - Fichier rendu (optionnel mais recommandé)
outputs:
  - Score /100 et grade (S à E)
  - Liste des non-conformités bloquantes
  - Corrections priorisées
checklist:
  - Score ≥ 80 (S ou A) avant publication
  - Aucun contrôle en échec
  - Zone de sécurité respectée
  - Couverture de sous-titres ≥ 85 %
  - Loudness ≈ -14 LUFS
---

# Gardien de Qualité

## Grille de contrôle automatique

| # | Contrôle | Pondération | Seuil |
| --- | --- | --- | --- |
| 1 | Format 9:16 (1080x1920) | 8 | obligatoire |
| 2 | Durée 15-45 s | 10 | ≥ 15 s |
| 3 | Hook ≤ 3 s, ≤ 9 mots, noté ≥ 70/100 | 15 | obligatoire |
| 4 | Rythme : moyenne de plan 1,3-3,2 s, aucun > 3 s | 14 | ≥ 1,3 s |
| 5 | Sous-titres : couverture ≥ 85 %, taille ≥ 60 px | 16 | obligatoire |
| 6 | Zone de sécurité (haut/bas/droite) | 8 | obligatoire |
| 7 | CTA dans les 3 dernières secondes | 10 | obligatoire |
| 8 | Boucle activée | 6 | recommandé |
| 9 | Bande-son : voix + musique + SFX | 9 | voix obligatoire |
| 10 | Loudness ≈ -14 LUFS, true peak ≤ -1,5 dBFS | 8 | ± 2,5 LU |

**Échec bloquant** (on ne publie pas) : 1, 3, 5, 6, 7, 10.
**Avertissement** : on peut publier, mais on note le correctif.

## Grille de notation

| Score | Grade | Décision |
| --- | --- | --- |
| 90-100 | S | Publier + décliner en variantes |
| 80-89 | A | Publier |
| 70-79 | B | Publier si le test est important, corriger ensuite |
| 55-69 | C | Corriger avant publication |
| 40-54 | D | Refaire le montage |
| < 40 | E | Refaire depuis le script |

## Procédure

```bash
sf qa examples/mon_short.yaml            # score + rapport
sf qa examples/mon_short.yaml --render   # rend puis contrôle
```

Le rapport liste pour chaque contrôle : le statut, la note, le détail mesuré
et l'action corrective. Le code de sortie est ≠ 0 s'il y a un échec
bloquant → utilisable en intégration continue.

## Contrôles manuels (non automatisables)

1. **Lecture complète sans son** : le sens passe-t-il uniquement avec les
   sous-titres ?
2. **Lecture avec son mais image floue** : le son porte-t-il le message ?
3. **Test mobile** : la voix reste-t-elle claire en haut-parleur ?
4. **Test « scroll »** : le hook arrête-t-il le pouce en 1 seconde ?
5. **Test boucle** : 3 visionnages sans décrochage.
6. **Test « ami »** : une personne hors du projet comprend-elle de quoi ça
   parle en 5 secondes ?

## Journal de non-conformités

Toute non-conformité est notée dans `docs/LEARNINGS.md` avec la cause racine.
Les récurrents deviennent des règles du skill concerné (c'est ainsi que la
bibliothèque s'améliore à chaque production).
