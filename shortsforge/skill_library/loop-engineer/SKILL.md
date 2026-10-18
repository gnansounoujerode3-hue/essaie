---
id: loop-engineer
name: Ingénieur de Boucle
description: Concevoir une fin qui se reconnecte au début pour maximiser le temps de visionnage et la rétention.
version: 1.0.0
tags: [boucle, rétention, rewatch, structure]
when_to_use: Dès que le corps du Short est monté. La boucle est le levier le plus sous-estimé du format.
inputs:
  - Plan de coupe
  - Script
outputs:
  - Dispositif de bouclage (visuel + sonore + textuel)
  - Séquence de fin/CTA réécrite
  - Plan de coupe du plan d'ouverture réinjecté
checklist:
  - La dernière frame et la première frame se ressemblent
  - Le plan 1 est réinjecté à la fin (ou un plan jumeau)
  - Le CTA est intégré à la boucle, pas collé après
  - Pas de fondu au noir final
  - Test de lecture en boucle : 3 cycles sans décrochage
---

# Ingénieur de Boucle

## Pourquoi la boucle change tout

Une vidéo de 22 s vue 3 fois = 66 s de « temps de visionnage » pour
l'algorithme. C'est le même signal qu'une vidéo de 66 s — mais avec le
taux de complétion d'un format court. La boucle est donc un levier
**gratuit** : aucun coût de production, aucun coût de durée.

## Les 4 types de raccord

| Type | Principe | Difficulté |
| --- | --- | --- |
| **Visuel** | Le dernier plan ressemble au premier (même sujet, même cadrage, même couleur) | Facile |
| **Sonore** | Le dernier son s'enchaîne sur le premier (le kick du début revient) | Facile |
| **Textuel** | La dernière phrase se prolonge logiquement dans la première | Moyenne |
| **Narratif** | La vidéo est un cercle : on revient au point de départ | Difficile (mais puissant) |

**Objectif** : combiner au moins **visuel + sonore**. Le raccord sonore
(coûter 0) suffit à supprimer la sensation de « fin ».

## Méthode : le « plan jumeau »

1. Choisir le plan d'ouverture (hook).
2. Dupliquer ce plan **à la fin** (0,8 à 1,2 s), avec le **même mouvement de
   caméra au même point du zoom** → le raccord est invisible.
3. Le CTA est incrusté **sur** ce plan jumeau (pas après).
4. La musique boucle naturellement (le beat est écrit pour boucler).

```
[HOOK plan A] → [corps] → [CTA + plan A répété] ⟲
```

## Écriture du CTA circulaire

L'erreur classique : « Abonne-toi ! » puis fin. Le spectateur sent la fin.

À la place, on écrit un **CTA qui ouvre** :

| CTA linéaire (faible) | CTA circulaire (fort) |
| --- | --- |
| « Abonne-toi pour plus d'astuces » | « Le 2ᵉ conseil est encore pire. Stay. » |
| « Like si tu as compris » | « D'abord le 1 : ne coupe pas. Le 2 arrive. » |
| « Commente ta ville » | « Dis-moi lequel tu appliques. Le 2ᵉ change tout. » |

La dernière phrase **promet la suite** tout en **refermant** sur le début.

## Suppression de la « fin »

- **Pas de fondu au noir** : le noir signale la fin.
- **Pas de plan de sortie** (« merci pour avoir regardé »).
- **Flash de 2 frames** sur le dernier mot → coupe sèche.
- **La musique ne s'arrête pas** : elle boucle au tempo (le même kick qui
  ouvre le Short le referme).

## Test de boucle (obligatoire)

1. Lire la vidéo **3 fois de suite** en boucle automatique.
2. À la 2ᵉ et 3ᵉ visionnage, le spectateur doit **croire qu'il voit un
   nouveau début** (pas « ah, encore »).
3. Vérifier que le **son** ne « tombe » : pas de silence à la jonction.
4. Chronométrer : si l'utilisateur s'arrête à la 2ᵉ boucle, la fin n'est pas
   assez reliée au début.

## Variante : la boucle à 2 modules

Pour les Shorts de 30-45 s :

```
Module 1 (0-15 s) : le problème
Module 2 (15-30 s) : la solution
Fin (30-32 s) : re-plan du Module 1 avec le CTA
```

Le spectateur voit le début de la solution passer au début du problème : la
compréhension se fait en boucle et la rétention double.

## Livrable

```yaml
loop:
  enabled: true
  strategy: twin-shot        # twin-shot | visual | audio-only
  twin_shot: h1              # id du plan dupliqué en fin
  twin_duration: 1.1
  audio_loop: true           # la musique boucle au tempo
  final_flash: true
cta:
  text: "LE 2ᵉ CONSEIL EST ENCORE PIRE"
  subtext: "Reste, tu vas l'adorer"
  at: 26.4
  duration: 3.2
  style: loop
```
