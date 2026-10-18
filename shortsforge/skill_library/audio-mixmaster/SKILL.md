---
id: audio-mixmaster
name: Mixeur Audio
description: "Monter la bande-son d'un Short : voix isolée, musique tendance duckée, bruitages au rythme des coupes."
version: 1.0.0
tags: [audio, voix, musique, sfx, mixage]
when_to_use: "Dès que le plan de coupe est figé. L'audio porte 50 % de la perception de qualité."
inputs:
  - Voice-over
  - Nappe musicale (ou générée)
  - Liste des plans (pour caler les bruitages)
outputs:
  - Mixage final normalisé (-14 LUFS)
  - Liste des bruitages avec timecodes
  - Check-list de propreté sonore
checklist:
  - Voix au centre, sans bruit de fond, compressée
  - Musique 12 à 20 dB sous la voix
  - Ducking automatique de la musique sous la parole
  - 4 à 8 bruitages, jamais plus de 2 par plan
  - Loudness intégré ≈ -14 LUFS, true peak ≤ -1,5 dBFS
  - 0,2 s de silence avant le hook (le vide attire l'oreille)
---

# Mixeur Audio

## Hiérarchie de mixage

```
Voix        ████████████████████████████   -6 à -3 dBFS (crest moyen)
Musique     ███████████                    -18 à -24 dB (duckée sous la voix)
Bruitages   ███████                        -10 à -16 dB (ponctuels)
```

**Règle** : la musique est un *lit*, pas une chanson. Si on fredonne la
musique en regardant la vidéo, elle est trop forte. Si on ne l'entend plus
pendant la voix, on peut la monter de 3 dB.

## Traitement de la voix

1. **High-pass 80 Hz** — supprime le rumble et le bruit de ventilation.
2. **Low-pass 13 kHz** — adoucit les sibilantes, allège le fichier.
3. **Compression** (ratio 3:1, seuil -18 dB) — stabilise le niveau.
4. **Normalisation de la loudness** (EBU R128, -14 LUFS, true peak -1,5 dBFS).
5. **Ducking** : la musique baisse de 6 à 10 dB dès que la voix parle
   (sidechain, attaque 8 ms, relâche 320 ms).

## La voix

- **Une seule prise**, pas de coupe dans le flux de la voix.
- **Débit** : 2,5 mots/s ; accélération ×1,05 à ×1,10 max.
- **Distance micro** : 15-20 cm, légèrement décentré pour éviter les plosives.
- **Silence de tête** : 0,2-0,5 s avant la première syllabe (le spectateur
  entend le vide et se prépare).
- Si la voix est trop dense, on **retire des mots** (jamais on n'accélère au-delà
  de ×1,1).

## Nappe musicale

Le ShortForge génère 4 ambiances prêtes à l'emploi (`assets/music/`) :

| Style | Usage |
| --- | --- |
| `upbeat_minor` | Tutoriels, conseils, business |
| `bright_pop` | Produit, lifestyle, mood positif |
| `corporate_hop` | B2B, preuve, communiqué |
| `dark_trap` |storytime, tension, révélation |

Règles : **128 BPM**, 4 temps, la coupe suit la percussion. Si la musique
pulse tous les temps, on coupe sur les temps (tous les 0,47 s ou tous les
1,875 s), sinon on coupe sur les 2 temps.

## Bruitages (SFX) : le vocabulaire du montage

| Son | Moment | Gain |
| --- | --- | --- |
| `impact` | Première frame du hook | -8 dB |
| `whoosh` | Changement de sujet / plan majeur | -14 dB |
| `pop` | Apparition d'un mot ou d'un chiffre | -12 dB |
| `click` | Micro-ponctuation, liste à puces | -18 dB |
| `ding` | Révélation, preuve, avant/après | -12 dB |
| `riser` | Montée vers le CTA | -14 dB |
| `swoosh` | B-roll qui entre | -16 dB |
| `zoom` | Zoom de caméra / chiffre choc | -14 dB |

**Maximum 2 bruitages par plan** et 4 à 8 au total. Le bruitage se pose
**sur la coupe** (0-1 frame avant), jamais au milieu d'une phrase.

## Chaîne de mixage ShortsForge

```
voix   → highpass → lowpass → dynaudnorm → split ─┬→ mixage final
musique → trim → fade → volume(-20dB) → sidechaincompress(voix) ─┘
SFX    → adelay(t) → volume → mixage final
mixage → apad → trim → loudnorm(-14 LUFS) → limiter → AAC 160k
```

## Contrôle final (à l'oreille et sur la crête maximale)

1. ** Écoute casque** : la voix reste-t-elle nette sur la musique ?
2. **Mesure** : `ffmpeg -i short.mp4 -af ebur128` → intégré ≈ -14 LUFS,
   true peak ≤ -1,5 dBFS.
3. **Test « bruit de chambre »** : couper la vidéo, ne garder que le son.
   Le rythme est-il compréhensible ? (sinon : ajouter des SFX aux coupes).
4. **Test sur téléphone** en haut-parleur : la voix est-elle encore intelligible ?
