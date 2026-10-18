---
id: variant-lab
name: Laboratoire de Variantes
description: Produire des variantes A/B systématiques (hook, CTA, durée, couleur) pour trouver ce qui performe.
version: 1.0.0
tags: [test, a/b, optimisation, données]
when_to_use: Après avoir un Short qui fonctionne. On ne scale pas un Short qui n'a pas été testé.
inputs:
  - Un Short validé (spec + rendu)
  - Hypothèse de performance à tester
outputs:
  - 3 à 5 variantes comparables (une seule variable changée)
  - Grille de lecture des métriques
  - Plan de publication
checklist:
  - Une seule variable modifiée par variante
  - Hook, CTA, durée, couleur, couverture de sous-titres = axes validés
  - Même heure de publication
  - Durée de test ≥ 24 h avant de conclure
  - Critère de décision écrit avant le test
---

# Laboratoire de Variantes

## Principe

On ne teste jamais « tout en même temps ». Chaque variante modifie **une seule
variable** pour que la conclusion soit causale. Les axes qui reviennent le
plus souvent :

| Axe | Valeurs testées | Impact typique |
| --- | --- | --- |
| Hook | 3-5 formulations | +30 à +80 % de hook rate |
| Durée | 15 s / 22 s / 35 s | ±25 % de complétion |
| CTA | action / curiosité / question | ±40 % de taux de clic |
| Couleur d'accent | 2-3 variantes | +10 à +20 % de watch time |
| Musique | 2 ambiances | ±15 % de rétention |
| Présence de voix | avec / sans | ±50 % (décisif) |

## Méthode

1. **Écrire l'hypothèse** avant de publier :
   « Si je remplace le hook par une question binaire, le hook rate doit passer
   de 6 % à 9 %, sans perte de complétion. »
2. **Fixer la variable** : tout le reste est identique (même audio, même
   visuel, même heure, même description).
3. **Publier en séquence** (24-48 h d'écart) ou simultanément sur des
   comptes différents.
4. **Attendre 24 h** minimum (le signal se stabilise après 6 h mais le
   bruit est encore fort).
5. **Décider** : on garde la variante gagnante, on archive les autres.

## Grille de lecture

| Métrique | Ce qu'elle dit | Seuil |
| --- | --- | --- |
| **Hook rate** (vues ÷ impressions) | L'accroche fonctionne | > 8 % (excellent > 12 %) |
| **Taux de complétion** | Le contenu tient | > 60 % sur 22 s |
| **Watch time moyen** | La durée moyenne regardée | > 80 % de la durée |
| **Rejouements** | La boucle fonctionne | > 1,5× |
| **Taux de partage** | La valeur perçue | > 1 % |
| **Taux d'enregistrement** | L'intention | > 2 % |
| **Clics lien bio** | La conversion | > 0,8 % |

## Diagnostic : le symptôme → la cause

| Symptôme | Cause probable | Skill à appliquer |
| --- | --- | --- |
| Hook rate bas | Accroche faible / trop tardif | `hook-architect` |
| Complétion faible après 3 s | Corps trop lent, plans trop longs | `rhythm-director` |
| Watch time plat, complétion bonne | Boucle absente | `loop-engineer` |
| Partages faibles | Pas de « valeur à transmettre » | `script-compiler` |
| Commentaires multiples | CTA ambigu | `cta-converter` |
| Rétention haute mais peu de vues | Pas de distribution (publication/hashtags) | hors périmètre |

## Grille de production

```yaml
experiment:
  name: hook_binaire_v2
  hypothesis: "Une question binaire fera passer le hook rate de 6 % à 9 %."
  variable: hook
  control: "hook_a"
  variants:
    - {id: "hook_b", hook_text: "Tu veux 1 000 ou 100 000 vues ?"}
    - {id: "hook_c", hook_text: "3 erreurs. La 3ᵉ est invisible."}
  metric: hook_rate
  threshold: 0.09
  duration_h: 48
```

## Règle d'hygiène

- **Ne pas changer de format** (vertical → carré) pendant un test.
- **Ne pas publier deux variantes du même Short** sur le même compte en même
  temps : l'algorithme et l'audience se confondent.
- **Documenter** chaque test (hypothèse, variable, résultat) : c'est le
  capital réel d'une chaîne de Shorts, pas les vidéos elles-mêmes.
