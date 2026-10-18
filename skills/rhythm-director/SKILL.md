---
id: rhythm-director
name: Directeur de Rythme
description: Découper le script en plans de 1,5 à 3 secondes et construire le flux visuel (jump cuts, mouvements, transitions).
version: 1.0.0
tags: [montage, rythme, plans, transitions]
when_to_use: Dès que le script est validé, avant de chercher les images.
inputs:
  - Script minuté
  - Sources disponibles (photos, vidéos, illustrations)
outputs:
  - Plan de coupe (shot list) avec durées, mouvements, transitions
  - Liste des B-rolls à produire
  - Timing des transitions et des bruitages
checklist:
  - Aucun plan > 3 s (sauf preuve visuelle forte)
  - Changement visuel toutes les 1,5 à 3 s
  - 0 blanc, 0 hésitation, 0 respiration audible
  - Le hook a son propre plan (0-3 s)
  - Transitions cohérentes (1 style, pas 4)
---

# Directeur de Rythme

## La règle des 1,5-3 s

Le cerveau décroche quand l'image ne change pas. Rythme cible :

| Type de plan | Durée | Usage |
| --- | --- | --- |
| Hook | 2,0 - 3,0 s | Une image, un mot choc |
| Démonstration | 1,5 - 2,5 s | Action à l'écran |
| Preuve | 2,5 - 3,5 s | Avant/après, chiffre, capture |
| B-roll d'illustration | 1,2 - 2,0 s | Métaphore, mème, visuel d'appoint |
| CTA | 2,0 - 3,0 s | Finition + boucle |

Au-delà de **3 s** sans changement visuel, la rétention chute. En dessous de
**1,2 s**, l'image devient illisible (le spectateur n'a pas le temps de lire
le texte incrusté).

## Jump cuts : la coupe par défaut

- **Cut sec** = 90 % des coupes. Aucune transition ne mange de temps.
- **Flash blanc (2-3 frames)** = ponctuation forte (chiffre choc, révélation).
- **Whip pan** = changement de sujet, energie.
- **Dip to black** = changement de chapitre (1 sur 10 maximum).

**Interdit** : les transitions longues (fade 0,5 s, dissolve), les zooms
ralentis, les fonds blancs qui « respirent ». Tout ce qui retarde le début de
la nouvelle image.

## Mouvements de caméra (Ken Burns)

| Mouvement | Expression | Effet |
| --- | --- | --- |
| `kenburns-in` | zoom 1,00 → 1,14 | Montée d'attention |
| `kenburns-out` | zoom 1,14 → 1,00 | Révéler un élément |
| `pan-left` / `pan-right` | zoom 1,12 + déplacement | Traverser, dynamiser |
| `shake` | zoom + micro-déplacement sinusoïdal | Urgence, « choc » |
| `static` | rien | Uniquement sur une capture d'écran ou un plan texte |

**Un seul mouvement par plan.** Ne jamais cumuler zoom + panoramique + shake.

## Le plan de coupe (format de travail)

```yaml
shots:
  - id: h1
    duration: 2.6
    source: assets/media/hook.jpg
    motion: {kind: kenburns-in, start_scale: 1.0, end_scale: 1.14}
    transition: cut
    texts:
      - {text: "TES REELS FLOP ?", position: upper, size: 112, effect: pop, duration: 2.6}
  - id: s2
    duration: 2.2
    source: assets/media/sans_son.jpg
    motion: {kind: kenburns-out, start_scale: 1.12, end_scale: 1.0}
    transition: flash
    broll:
      - {source: assets/media/sticker_70.png, position: top-right, width: 380, at: 0.2, duration: 1.8}
```

## Rythme sonore couplé au rythme visuel

Le **son est le métronome** du montage :

- Un **bruitage « whoosh »** à chaque coupe majeure (pas à chaque plan).
- Un **« pop »** sur l'apparition du mot clé ou du chiffre.
- Un **« ding »** sur la révélation (avant/après).
- Un **« impact »** sur la première frame du hook.
- **Silence** (ou drop musical) 0,2 s avant le hook : le vide attire l'oreille.

## Règle de cohérence

Un Short = **un style visuel**. Si on utilise des transitions flash, on les
utilise toutes de la même manière (même durée, même intensite). Le mélange
« un plan fancy, trois plans bruts » est le signal n°1 de montage amateur.

## Contrôle final du plan de coupe

1. **Test thumb** : fait défiler les miniatures en 1 s. Si deux plans se
   ressemblent, on en coupe un.
2. **Test sans le son** : la vidéo reste compréhensible et rythmée.
3. **Test avec le son** : le rythme de la musique et celui des coupes ne se
   battent pas (si la musique est percussive, on coupe sur les temps).
4. **Test des 3 dernières secondes** : la fin doit ressembler au début
   (voir le skill `loop-engineer`).
