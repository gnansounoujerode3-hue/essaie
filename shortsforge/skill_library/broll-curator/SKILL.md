---
id: broll-curator
name: Curator de B-Roll
description: Sélectionner, produire et incruster les plans d'illustration qui rendent une vidéo vivante sans surcharger.
version: 1.0.0
tags: [b-roll, visuels, overlays, direction artistique]
when_to_use: Après le plan de coupe, en parallèle de la recherche de sources.
inputs:
  - Plan de coupe
  - Thème et univers visuel de la marque
outputs:
  - Liste des B-rolls (image ou clip) avec position et durée
  - Autocollants et éléments graphiques
  - Plan d'illustration de ce qui manque
checklist:
  - 1 B-roll maximum par plan
  - B-roll toujours en périphérie (haut/bas), jamais au centre du texte
  - Coins arrondis + liseré blanc (sensation de « carte »)
  - Opacité 0,9-1,0 ; ne jamais cacher le visage ou le texte
  - 0 emoji si le ton de marque est sérieux
---

# Curator de B-Roll

## Définition opérationnelle

Un B-roll est un **plan d'illustration** posé au-dessus (overlay) ou en
remplacement du plan principal. Il ne porte pas l'information : il la rend
mémorable. Règle : **1 idée = 1 plan principal + 0 ou 1 B-roll**.

## Où le placer

```
┌──────────────────────┐
│  zone titre           │  ← 0-15 % : hook, compteurs
│                      │
│  ┌────────┐          │
│  │ B-roll │  (haut)  │  ← 15-40 % : illustration
│  └────────┘          │
│                      │
│   ZONE TEXTE         │  ← 45-75 % : sous-titres, titre courant
│                      │
│  ┌────────┐          │
│  │ B-roll │  (bas)   │  ← 75-92 % : illustration secondaire
│  └────────┘          │
│  zone CTA/UI         │  ← 92-100 % : boutons, CTA
└──────────────────────┘
```

**Le centre (45-75 %) est réservé au texte.** Un B-roll au centre tue la
lisibilité des sous-titres : c'est la première cause de « je ne comprends pas
la vidéo ».

## Sources de B-roll, par ordre de préférence

1. **Écrans de l'application/produit** — le B-roll le plus crédible.
2. **Photo réelle en situation** — un visage, la main, l'écran.
3. **Illustration plate (flat design)** — cohérente, facile à produire.
4. **Mème / sticker** — humoristique, attention immédiate (usage unique).
5. **Capture d'écran annotée** — preuve, chiffres, « avant/après ».
6. **Emoji / symbole** — uniquement pour un ton léger, et jamais plus d'un
   par plan.

## Fabrication rapide (sans stock)

- **Captures** : `assets/media/*.png` détourées en coins arrondis (rayon 28 px)
  avec liseré blanc 6 px → effet « carte ».
- **Chiffres** : un mot-clé en très grand + une flèche + la source.
- **Avant/après** : coupe image en deux, liseré blanc, effet « pop » à l'entrée.
- **Illustration IA** : prompt = sujet + style + cadrage vertical, ex.
  « plan large, lumière naturelle, ambiance startup, format 9:16 ».

## Autocollants

| Type | Usage | Règle |
| --- | --- | --- |
| Badge texte (« NOUVEAU », « ASTUCE ») | Ancrage d'attention | 1 par plan max, coin haut-droit |
| Emoji | Émotion,Thom | 1, jamais 3 |
| Flèche / pointer | Montrer un détail | Doit viser un élément réel du plan |
| Progress / compteur | Créer's l'urgence | « 3/3 » sur les listes |

Les autocollants se posent avec une **animation d'entrée** (pop 0,2 s) et
disparaissent avec la coupe, jamais par fondu mou.

## Règles de non-surencharge

- Max **2 couches** simultanées au-dessus du plan principal (B-roll + sticker).
- Le B-roll ne doit **jamais** couvrir du texte.
- Un B-roll par plan, une durée de 1,2 à 2,0 s.
- Si le plan principal est déjà riche (capture d'écran détaillée), **pas** de
  B-roll : on surcharge pour rien.

## Livrable

```yaml
broll:
  - {source: assets/media/phone_70pct.png, position: top-right, width: 400,
     at: 0.2, duration: 1.8, radius: 28, border: true}
stickers:
  - {text: "70 %", position: top-left, at: 0.4, duration: 1.6, scale: 1.0}
```
