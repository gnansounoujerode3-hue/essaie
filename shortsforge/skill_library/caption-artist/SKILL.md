---
id: caption-artist
name: Artiste des Sous-Titres
description: Concevoir les sous-titres dynamiques (mot par mot), lisibles, en zone de sécurité, synchronisés à la voix.
version: 1.0.0
tags: [sous-titres, typographie, accessibilité, lisibilité]
when_to_use: "Dès que la voix est enregistrée. Les sous-titres ne sont pas une option : 70 % des shorts sont vus sans son."
inputs:
  - Voice-over (ou script minuté)
  - Charte graphique (couleurs, polices)
outputs:
  - Fichier de sous-titres synchronisé (ASS, mot par mot)
  - Position et taille validées dans la zone de sécurité
  - Variante « phrase » pour les plans denses
checklist:
  - Couverture de 100 % de la voix
  - 2 lignes maximum, 4 à 7 mots par ligne
  - Taille 60-90 px sur 1080 de large
  - Mot actif surligné (couleur accent) à 105 % de l'échelle
  - Bloc centré horizontalement, entre 40 % et 78 % de la hauteur
  - Jamais dans les 320 px du bas ni les 210 px de droite
---

# Artiste des Sous-Titres

## Pourquoi

- **70 %** des vues de Shorts se font sans le son.
- Un sous-titre dynamique (mot actif surligné) retient l'œil et **compense la
  vitesse de lecture** : le cerveau « accroche » le mot qui change.
- Le sous-titre est aussi un **moteur de recherche** : Instagram et TikTok
  indexent le texte à l'écran.

## Mode « karaoke » (par défaut)

Une seule ligne de sous-titres à l'écran. À chaque mot, **le mot actif change
de couleur** (accent de la marque) et passe à 105 %. Les autres restent
blancs. L'illusion : le texte se « tape » sous les yeux.

Implémentation ShortsForge : `CaptionLine(highlight="word")`. Le layout est
calculé au pixel (métriques de police), chaque mot est positionné en absolu
dans le fichier ASS → **aucun reflow** de la ligne, le mot surligné ne
déplace jamais les autres.

## Mode « phrase »

Pour les plans denses (chiffres longs, définitions), on garde la phrase
entière en blanc et on met en valeur le **mot clé** avec un fond ou une
couleur accent. Plus lisible, moins dynamique.

## Paramètres de rendu

| Paramètre | Valeur | Pourquoi |
| --- | --- | --- |
| Taille | 68-84 px | 60 px minimum sur 1080 de large |
| Police | ExtraBold / Black | Le gras porte la lisibilité en mouvement |
| Contour | 6-9 px noir | Lisible sur fond blanc comme sur fond clair |
| Ombre | 3-5 px | Détache sans halo |
| Interligne | 1,18 | Lignes aérées |
| Mots par ligne | 4 à 7 | Au-delà, la lecture ralentit |
| Majuscules | Oui (mots courts) / non (phrases longues) | Majuscules = plus d'impact, moins de lisibilité sur les phrases |

## Zone de sécurité (mesures réelles, format 1080x1920)

```
┌────────────────────────────┐  0 px
│  220 px   zone haute (UI)  │  logo, compteurs, boutons du haut
├────────────────────────────┤
│                            │
│      220 - 1600 px         │  zone utile
│   (sous-titres ici)        │
│                            │
├────────────────────────────┤  1600 px
│  320 px  zone basse (UI)   │  description, CTA, boutons
└────────────────────────────┘  1920 px
```

Côté **droit** : 210 px réservés (likes, commentaires, partage). Ne jamais
terminer une ligne de sous-titre à moins de 210 px du bord droit.

Verticalement, le bloc de sous-titres est centré sur **68 %** de la hauteur
(≈ 1300 px) : ni trop haut (conflit avec le hook), ni trop bas (caché par
l'UI).

## Synchronisation

1. **Enregistrer la voix en une seule prise** (pas de montage dans la voix).
2. **Détecter les silences** (`sf align`) pour placer les début de phrase.
3. **Distribuer les mots** à l'intérieur de la phrase selon la longueur
   réelle des mots (+ 0,2 s de pause sur les virgules, + 0,5 s sur les points).
4. **Vérifier** : la surbrillance doit suivre la voix mot pour mot.

Si la voix est trop rapide (plus de 14 mots par phrase), on ralentit la voix
(×1,05) plutôt que de couper la phrase.

## Accessibilité et outreach

- **Contraste** : blanc sur fond sombre, ou noir sur fond clair. Jamais
  blanc sur blanc.
- **Ne pas coller deux couches de texte** : si un titre est à l'écran, le
  sous-titre se décale ou disparaît.
- **Taille minimale** : 60 px. En dessous, la moitié de l'audience décroche.
- Les sous-titres constituent aussi le **texte alternatif** de la plateforme :
  ils doivent porter le sens, pas la ponctuation.

## Erreurs fréquentes

| Erreur | Impact | Correctif |
| --- | --- | --- |
| Texte au bas de l'écran | Masqué par l'UI | Centrer à 68 % |
| 3 lignes de 9 mots | Illisible | 2 lignes max, 4-7 mots |
| Phrase = phrase de la voix | Rythme mou | Phrase ≠ ligne de sous-titre |
| Pas de surbrillance | Moins de rétention | Mot actif en couleur accent |
| Sous-titre à 40 px | Invisible en mouvement | 68-84 px |
