---
id: script-compiler
name: Compilateur de Script
description: Transformer une idée brute en script minuté de 15 à 45 secondes, taillé pour la voix et le montage.
version: 1.0.0
tags: [script, voix-off, structure, copywriting]
when_to_use: Après le hook, avant le montage. Un script minuté évite 80 % des trous au montage.
inputs:
  - Hook retenu
  - 1 à 3 messages clés
  - Durée cible
outputs:
  - Script complet avec timecodes
  - Phrases calibrées pour la voix (10-14 mots max)
  - Légendes de sous-titres synchronisées
checklist:
  - Une idée par phrase, 10 à 14 mots
  - Total 90 à 160 mots selon la durée
  - Voix = 150 mots/minute (x1.05 si voix rapide)
  - Chaque phrase = une coupe possible
  - CTA présent dans les 3 dernières secondes
---

# Compilateur de Script

## Structure canonique

```
0-3 s     HOOK        (une phrase, 6-9 mots)
3-30 s    CORPS       (3 à 7 « modules » de 1 idée)
30-38 s   PREUVE      (résultat, chiffre, démonstration)
38-45 s   CTA+BOUCLE  (action + raccord vers le début)
```

Le format **court** (15-30 s) est prioritaire : l'algorithme favorise les
vidéos regardées jusqu'au bout, et une vidéo de 22 s regardée 3 fois bat une
vidéo de 50 s regardée 1,2 fois.

## Le module de corps (7-9 s)

Chaque module suit la trame **Théorie → Chiffre → Action** :

1. **Annonce** (1 phrase) : « Troisième erreur : le son. »
2. **Explication** (1 phrase) : « 70 % regardent sans le son. »
3. **Action** (1 phrase) : « Écris tes sous-titres en gros. »

On ne développe jamais deux idées dans le même module. Si le spectateur doit
réfléchir, c'est qu'il y a deux idées : on coupe.

## Rythme de la voix

- **Débit cible** : 150 mots/minute (2,5 mots/seconde) en voix posée.
  Accélération acceptable : ×1,05 à ×1,10, jamais au-delà (intelligibilité).
- **Phrase** : 10 à 14 mots. Plus de 18 mots = respiration forcée, donc
  « blanc » au montage.
- **Nombre de mots total** : `durée × 2,5` (22 s ≈ 55 mots ; 38 s ≈ 95 mots).
- **Ponctuation = respiration** : une virgule = 0,2 s de pause, un point = 0,5 s.
  Ces pauses sont des leviers de montage (on coupe dessus).

## Règles de rédaction

- **Verbes à l'action** : « ouvre », « copie », « coupe », « teste ».
- **Pas de jargon non expliqué** : si un mot n'est pas compris par 80 % de
  l'audience, il est coupé.
- **Une métaphore par script maximum** (l'imagerie prend de la place à l'écran).
- **Les nombres écrits en chiffres** se lisent plus vite et clignotent mieux.
- **Ne jamais Promettre ce qu'on ne montre pas** : le hook promet, le corps
  remplit la promesse (sinon : rebounde + commentaires négatifs).

## Structure du livrable

```yaml
script:
  duration: 28.0
  lines:
    - { t: 0.0,  d: 2.6,  text: "Tes Reels flop ? C'est ce détail." }        # hook
    - { t: 2.6,  d: 4.2,  text: "Zéro son, et 70 % des gens ne comprennent rien." }
    - { t: 6.8,  d: 4.0,  text: "Écris tes sous-titres en gros, mot par mot." }
    - { t: 10.8, d: 4.4,  text: "Deuxième erreur : tu laisses ton logo au centre." }
    - { t: 15.2, d: 4.0,  text: "Première erreur : tu commences par te présenter." }
    - { t: 19.2, d: 4.2,  text: "Fais le test. Trois jours, et tu me dis." }
    - { t: 23.4, d: 4.6,  text: "Abonne-toi, je donne une astuce par jour." }  # CTA + boucle
```

## Autocontrôle (à faire systématiquement)

1. **Test de la phrase à voix haute** : dite en 12 s maximum, elle passe.
2. **Test des 5 premières secondes** : l'accroche écrite, lue à voix haute,
   donne-t-elle envie de continuer ? Si la réponse est « non » ou « çadepends »,
   on change.
3. **Test sans son** : le script seul (sous-titres) doit rester compréhensible.
4. **Test de la boucle** : la dernière phrase peut-elle précéder la première
   sans casser le sens ? (« Trois erreurs. La première : » → « Souvent. La
   première : »)

## Erreurs fréquentes

| Erreur | Correctif |
| --- | --- |
| Intro de 3 s avant le hook | Hook dès la frame 1 |
| 3 idées dans un plan | 1 idée = 1 plan = 1 phrase |
| Phrases de 25 mots | Couper en 2 phrases |
| « Like et abonne-toi si ça te plaît » | 1 seule action demandée |
| Boucler sans raison (même plan) | Rendre la fin visuellement reliée au début |
| Écrire pour être lu (ton écrit) | Écrire pour être dit (ton parlé) |
