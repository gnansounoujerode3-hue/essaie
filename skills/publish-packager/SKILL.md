---
id: publish-packager
name: Packager de Publication
description: Préparer le Short pour la publication multi-plateformes (titre, description, hashtags, miniature, exports).
version: 1.0.0
tags: [publication, distribution, titres, hashtags, formats]
when_to_use: Le rendu est validé et le score QA est bon. Le packaging peut doubler la portée d'un même Short.
inputs:
  - Short rendu et validé
  - Objectif (portée, communauté, ventes)
outputs:
  - Titre + description + hashtags par plateforme
  - Miniature (cover frame)
  - Exports multiples (9:16, 1:1, 4:5) et dossier de publication
checklist:
  - Titre ≤ 70 caractères, il complète le hook (pas de doublon)
  - 3 à 5 hashtags ciblés (pas 30)
  - Miniprise lisible en vignette
  - Export 1080x1920 (H.264, AAC, faststart)
  - Fichier nommé `slug_YYYYMMDD.mp4`
---

# Packager de Publication

## Le titre ne répète pas le hook

Le titre est la **suite** du hook : il donne une raison d'aller voir la vidéo
ou de s'abonner. Il ne répète pas le texte à l'écran.

| ❌ Redondant | ✅ Complémentaire |
| --- | --- |
| « 3 erreurs qui tuent tes vues » (hook identique) | « La 3ᵉ erreur, c'est celle que personne ne corrige » |
| « Astuce montage » | « Ton montage est trop propre : c'est ça le problème » |
| « Tuto reels » | « 20 s pour transformer un Reel ordinaire » |

## Règles de titre

- **≤ 70 caractères** (au-delà, c'est tronqué dans le feed).
- **Une majuscule strategique** (pas de CAPITALISATION TOTALE).
- **Un emoji**, max, en tête ou en fin — jamais au milieu d'un mot.
- **Curiosité ou promesse chiffrée** : « J'ai testé 7 hooks. Le 3ᵉ a fait 9× la moyenne ».
- **Pas de point d'exclamation multiple**, pas de « 🔥🔥🔥 ».

## Description

3 lignes maximum, la première doit être utile (pas « Pense à aimer et à partager »). Le
commentaire épinglé fait le travail de CTA secondaire.

## Hashtags

- **3 à 5 hashtags**, dont 1 large (#shorts #marketing #business), 2-3
  mid (#montage #reels #conseils), 1 niche (#creationdecontenu).
- Jamais 30 hashtags : signal de spam, portée réduite.
- Les hashtags goes **dans les 3 premières lignes** de la description (ils
  sont indexés en début de caption).

## Miniature (cover)

Extraire une frame représentative :

```bash
ffmpeg -ss 1.2 -i short.mp4 -frames:v 1 -vf "scale=1080:1920" cover.jpg
```

Règles : le visage ou le mot clé est visible, pas de texte coupé, contraste
fort — la vignette s'affiche en 120x213 px dans le feed.

## Exports multi-formats

| Format | Ratio | Usage |
| --- | --- | --- |
| `9:16` | 1080x1920 | TikTok, Reels, Shorts (master) |
| `1:1` | 1080x1080 | Feed LinkedIn / Twitter (recadrage centré sur le texte) |
| `4:5` | 1080x1350 | Feed Instagram (recadrage vertical réduit) |
| `16:9` | 1920x1080 | Embed web (optionnel, rare) |

Le recadrage doit garder le **bloc de sous-titres** : couper le plan 9:16 en
1:1 sans repositionner casse la lisibilité.

## Dossier de publication

```
output/publication/
├── short_20261018.mp4          # master 9:16
├── short_20261018_1x1.mp4
├── short_20261018_4x5.mp4
├── cover.jpg
├── caption_tiktok.txt
├── caption_reels.txt
├── caption_shorts.txt
├── hashtags.txt
└── meta.json                  # spec + score QA + métriques
```

## Grille de contrôle avant publication

1. Le fichier s'ouvre sur mobile (H.264 + AAC, `+faststart`).
2. Le son est audible au haut-parleur du téléphone.
3. La miniature est lisible en petit.
4. Le titre ne duplique pas le hook.
5. Le CTA est dans les 3 dernières secondes de la vidéo **et** dans la
   description.
6. Le score QA ≥ 80 (voir skill `qa-gatekeeper`).
