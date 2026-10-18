---
id: hook-architect
name: Architecte de Hook
description: Concevoir l'accroche des 3 premières secondes qui bloque le scroll et force la rétention.
version: 1.0.0
tags: [hook, rétention, script, copywriting]
when_to_use: "Avant toute écriture de script. C'est le skill le plus rentable : 80 % de la rétention se joue sur les 3 premières secondes."
inputs:
  - Sujet ou promesse du Short
  - Audience cible et niveau de douleur
  - Offre / produit (optionnel)
outputs:
  - 5 hooks candidats notés
  - 1 hook gagnant + 2 variantes de secours
  - Texte à l'écran et phrase voix-off alignés
checklist:
  - Hook ≤ 3 s et ≤ 9 mots
  - Texte à l'écran en capitales, lisible en 0,8 s
  - Promesse ou question immédiate (pas de « salut aujourd'hui »)
  - 2 variantes A/B prêtes à rendre
---

# Architecte de Hook

## Principe

Le spectateur décide en **0,8 à 1,5 seconde** s'il reste. Le hook n'est pas une
introduction : c'est une **rupture de promesse**. Il doit créer une question
dans la tête du spectateur (« pourquoi ? », « comment ? », « ça marche vraiment ? »)
avant que le pouce ne bouge.

**Règle d'or** : on ne dit jamais *ce que* l'on va faire, on dit *ce que le
spectateur va obtenir* — ou ce qu'il va perdre.

## Les 8 mécanismes de hook testés

| # | Mécanisme | Formulation | Pourquoi ça marche |
| --- | --- | --- | --- |
| 1 | **Interruption de pattern** | « Arrête de faire ça. » | Cassure l'habitude, crée un conflit. |
| 2 | **Chiffre choc** | « 3 erreurs qui coûtent 40 % de tes vues. » | Le chiffre crée un ancrage mental (on retient « 3 » plus vite qu'« erreurs »). |
| 3 | **Question binaire** | « Tu veux 10 000 vues ou 1 000 ? » | La question binaire force la réponse. |
| 4 | **Preuve avant promesse** | « Voici mon short à 2 M de vues. » | Autorité + preuve immédiate. |
| 5 | **Contre-intuitif** | « Ne poste pas de Reels. » | La contradiction force l'attention. |
| 6 | **Urgence / coût** | « 24 h, puis je le supprime. » | FOMO + urgence. |
| 7 | **Identification** | « Si tu vends en ligne, regarde. » | Le spectateur se reconnaît. |
| 8 | **Secret /(angle mort)** | « Le truc que les agences ne te disent pas. » | Curiosité + suspicion dploit. |

## Arbre de décision

1. **Le spectateur sait-il de quoi ça parle ?**
   - Non → mécanisme 4 (preuve) ou 1 (interruption).
   - Oui → mécanisme 2, 3, 5 ou 6.
2. **A-t-il un problème non résolu ?**
   - Oui → 2 (chiffre) ou 7 (identification).
   - Non → 3 (question binaire) ou 5 (contre-intuitif).
3. **Existe-t-il une urgence réelle ?**
   - Oui → 6. Non → ne jamais mentir sur l'urgence (crédibilité > tactique).

## Grille de notation (0-100)

| Critère | Points | Comment juger |
| --- | --- | --- |
| Curiosité | 0-30 | Le spectateur doit vouloir la suite. |
| Clarté | 0-25 | On sait de quoi il s'agit sans explication. |
| Chiffre / preuve | 0-20 | Un élément concret (nombre, avant/après). |
| Ciblage | 0-15 | Le spectateur se reconnaît. |
| Rythme | 0-10 | ≤ 9 mots, pas de subordinate. |

**Seuil de production : 70/100.** En dessous, on réécrit.

## Règles de fabrication

- **≤ 9 mots.** Un hook n'est pas une phrase, c'est un coup de poing.
- **Le texte à l'écran ≠ la voix-off.** L'écran porte les mots de choc
  (« 3 ERREURS »), la voix porte la phrase complète.
- **Chiffres > adjectifs.** « 3 étapes » bat « la méthode simple ».
- **Interdit en ouverture** : « Salut », « Bienvenue », « Aujourd'hui je vais »,
  « Dans cette vidéo », « Tu ne vas pas en revenir ».
- **Majuscules + contraste** : le hook à l'écran se lit en 0,8 s, donc
  8 à 14 caractères par ligne, 2 lignes maximum.
- **Le hook et le CTA ne doivent pas être la même phrase** : l'un ouvre,
  l'autre convertit.

## Exemples transformés

| Version faible | Version forte |
| --- | --- |
| « Aujourd'hui je vais vous montrer comment réussir vos Reels » | « Tes Reels flop ? C'est ce détail. » |
| « Il y a beaucoup de raisons d'échouer sur les réseaux » | « 3 erreurs. Voilà pourquoi tu flappes. » |
| « Abonne-toi pour plus de conseils » | « Garde cette vidéo, tu vas en avoir besoin. » |

## Variantes à produire systématiquement

Pour chaque Short, sortir **5 hooks** (un par mécanisme différent) puis en
conserver **3** pour un test A/B :

- Hook A : visuel + chiffre (le plus fort enodr��).
- Hook B : question binaire (meilleur en audience fidèle).
- Hook C : preuve/avant-après (meilleur en contenu expertise).

Le test se fait sur le **hook rate** (vues ÷ impressions), pas sur les likes.

## Livrable attendu

```yaml
hook:
  text: "3 ERREURS QUI TUENT TES VUES"     # texte à l'écran
  subtext: "La 3ᵉ est invisible"            # sous-titre du hook
  badge: "À VOIR"                            # autocollant optionnel
  duration: 2.6
  variants:
    - id: A
      text: "0,8 % de rétention ? Voici pourquoi."
    - id: B
      text: "Tu veux 1 000 ou 100 000 vues ?"
  score: 82
```
