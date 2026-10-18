---
id: perf-analyst
name: Analyste de Performance
description: Lire les métriques d'un Short publié, diagnostiquer la rétention et prescrire les corrections.
version: 1.0.0
tags: [analytics, métriques, diagnostic, growth]
when_to_use: 24 h après publication, puis à chaque itération.
inputs:
  - Métriques de la plateforme (hook rate, complétion, watch time, partages)
  - Spec du Short publié
outputs:
  - Diagnostic (le maillon faible)
  - 3 corrections priorisées
  - Version 2 du plan de coupe
checklist:
  - Une seule hypothèse par itération
  - Correction appliquée dans les 24 h
  - Comparaison des métriques avant/après sur la même cohorte
  - Archive des learnings dans docs/LEARNINGS.md
---

# Analyste de Performance

## Lecture du parcours en 4 temps

```
IMPRESSION  →  HOOK RATE  →  WATCH TIME  →  COMPLETION  →  ACTION
 (portée)      (0-3 s)       (temps moyen)   (fin)          (like/partage/abonné)
```

On diagnostique **le premier maillon qui casse**, jamais le dernier.

| Maillon faible | Diagnostic | Correction | Skill |
| --- | --- | --- | --- |
| Impressions | Aucun distribution | Hashtags, heure, format, compte | — |
| Hook rate | Accroche faible | Changer le hook (3 variantes) | `hook-architect` |
| Watch time (0-5 s) | Rupture de rythme | Plans < 3 s, coupe sur le beat | `rhythm-director` |
| Watch time ( milieu) | Corps creux | Reformuler en « 3 erreurs » | `script-compiler` |
| Complétion | Fin molle | Boucle + CTA circulaire | `loop-engineer` |
| Partages | Pas de valeur partageable | Chiffre / liste à copier | `script-compiler` |
| Abonnés | Promesse absente | CTA + preuve | `cta-converter` |

## Lecture fine de la courbe de rétention

```
100% ┤█
     │█            ← chute brutale : hook faible ou visuel illisible
 70% ┤██
     │████         ← décroissance normale (20-30 % de perte sur 22 s)
 40% ┤██████
     │████████     ← plateau bas : contenu sans intérêt
     └────────────
      0s    5s   10s  15s  20s
```

| Forme | Diagnostic |
| --- | --- |
| Chute à 0-1 s | Le hook n'accroche pas (ou le premier plan est vide/noir) |
| Chute à 3-4 s | La promesse n'est pas tenue : le corps ne suit pas |
| Plateau haut | Bon contenu : à répliquer sur d'autres sujets |
| Chute à la fin | Fin molle : boucle et CTA à refaire |
| Creux au milieu | Plan trop long ou texte illisible à cet instant |

## Grille d'itération

```
Itération 1 : hook A → 5,2 % de hook rate, complétion 41 %
Diagnostic  : hook faible ET complétion faible
Itération 2 : hook B (question binaire) + plans raccourcis à 2,2 s
               → hook rate 8,1 %, complétion 58 %
Conclusion  : le hook était le maillon 1, le rythme le maillon 2
```

## Règles d'analyse

1. **Comparer sur la même cohorte** (même plage horaire, même audience,
   même durée de publication). Comparer 22 h à 2 h est un piège.
2. **Le hook rate dépend du média organique** : un Short publié sur une
   audience froide sera toujours moins bon qu'unShort repartagé.
3. **Ne pas confondre portée et performance** : une vidéo qui performe mal
   mais se fait partager par 3 comptes vaut mieux qu'une vidéo à 6 % de
   hook rate.
4. **Un test = une variable.** Sinon on multiplic les corrélations
   fortuites.
5. **Documenter** : chaque itération laisse une trace écrite
   (`docs/LEARNINGS.md`), c'est ce qui compound.

## Sortie attendue

```yaml
diagnosis:
  published_at: "2026-10-14T18:30:00Z"
  metrics: {hook_rate: 0.052, completion: 0.41, watch_time: 9.8, shares: 0.004}
  broken_link: hook
  confidence: high
  fixes:
    - {priority: 1, change: "hook → question binaire", skill: hook-architect}
    - {priority: 2, change: "plans 3 s → 2,2 s", skill: rhythm-director}
    - {priority: 3, change: "CTA circulaire", skill: loop-engineer}
  next_test: hook_binaire_v2
```
