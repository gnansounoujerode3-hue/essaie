---
id: brand-voice
name: Voix de Marque
description: Adapter le ton, le vocabulaire et l'identité visuelle d'un Short à une marque précise.
version: 1.0.0
tags: [marque, ton, identité, cohérence]
when_to_use: Avant le script (cadre) et à chaque déclinaison (couleur, format, durée).
inputs:
  - Charte de marque (ton, couleurs, polices, vocabulaire)
  - Audience cible
  - Objectif commercial
outputs:
  - Fiche de marque opérationnelle (tokens)
  - Règles de ton appliquées au script
  - CharteShortSpec (couleurs/polices prêtes à l'emploi)
checklist:
  - 2 couleurs max pour le texte à l'écran (primaire + accent)
  - 1 police d'affichage + 1 police de sous-titre
  - Vocabulaire de la marque respecté (pas de jargon hors charte)
  - Aucun élément graphique concurrent du logo
  - Variantes de marque (couleur) prêtes pour A/B
---

# Voix de Marque

## Fiche de marque opérationnelle (tokens)

```yaml
brand:
  name: "Nom de la marque"
  primary: "#FF2E63"     # couleur de surbrillance (mot actif, chiffre)
  accent:  "#25F4EE"     # couleur secondaire (badge, contour)
  ink:     "#FFFFFF"     # texte principal
  paper:   "#0B0B0F"     # fond / contour de texte
  font_title:   "anton"      # titres accrocheurs (impact, condensé)
  font_caption: "inter-800"  # sous-titres (neutrales, très lisibles)
  font_sticker: "inter-900"  # autocollants
```

**Règle de contraste** : `ink` sur `paper` doit dépasser 4,5:1 (lisibilité
WCAG AA). Le `primary` est réservé à **un seul élément par frame** (le mot
actif, le chiffre clé) : utilisé partout, il ne met plus rien en valeur.

## Registres et ton

| Registre | Vocabulary | Pour qui | Exemple de hook |
| --- | --- | --- | --- |
| **Expert** | Données, termes métier, précision | Pros, B2B | « 62 % de tes leads meurent avant le RDV » |
| **Pédagogue** | Étapes, images simples, action | Débutants, grand public | « 3 gestes, et ta vidéo passe à 10 k » |
| **Provocant** | Chiffre, contradiction, opinion | Audience engaged | « Ton montage est trop propre. » |
| **Humour** | Autodérision, mème, situation | Audience jeune | « J'ai montage 47 Reels. Aucun n'a marché. » |

Le registre doit être **unique** sur tout le Short : le mélange « expert
sérieux + mème + humour » détruit la confiance.

## Cohérence visuelle

- **Un seul style d'image** : photos réelles *ou* illustrations *ou* captures,
  pas un mélange. Les exceptions sont des B-rolls clairement « d'illustration ».
- **Une seule famille de typo** : 2 polices maximum.
- **Logo** : petit, en haut, jamais au centre ; et seulement si la marque est
  déjà connue (sinon, on détourne l'attention).
- **Couleurs** : le fond ne doit jamais être la couleur de la marque en
  aplat plein (ça écrase le texte).

## Adaptations par plateforme

| Plateforme | Durée cible | Zone basse | Sous-titres | Son |
| --- | --- | --- | --- | --- |
| TikTok | 21-34 s | 320 px | Mot par mot | Voix + musique |
| Reels | 15-30 s | 300 px | Mot par mot | Voix + musique |
| Shorts | 30-58 s | 250 px | Phrase | Voix + musique |
| LinkedIn | 45-90 s | 260 px | Phrase | Voix prioritaire |

## Déclinaisons de marque prêtes à rendre

```yaml
variants:
  - {id: "brand_a", brand: {primary: "#FF2E63", accent: "#25F4EE"}}   # marque
  - {id: "brand_b", brand: {primary: "#7C5CFF", accent: "#FFD400"}}   # variante couleur
  - {id: "brand_c", brand: {primary: "#00E5A0", accent: "#FF2E63"}}   # variante contraste
```

Tester la **couleur** est souvent plus rentable que tester un nouveau hook :
le changement de couleur accent ne modifie ni le message ni le rythme, donc
l'analyse reste lisible (test à une variable).

## Checklist de conformité

1. Le script ne contient que le vocabulaire de la marque (pas de concurrent
   nommé).
2. Le hook et le CTA utilisent le même registre.
3. La couleur `primary` n'apparaît que sur 1 élément à la fois.
4. Les sous-titres utilisent `font_caption` (jamais `font_title`).
5. Le logo n'est visible que s'il est nécessaire.
