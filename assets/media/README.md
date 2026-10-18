# Médias de démonstration

Les fichiers `creator_studio.jpg`, `editing_timeline.jpg` et `phone_closeup.jpg` sont des visuels générés pour la démonstration ShortsForge. Ils ne représentent pas une personne réelle ni une marque réelle. Ces images sont incluses pour rendre le spec de démonstration exécutable ; remplacez-les par vos propres rushes ou des médias dont vous avez vérifié les droits avant toute publication.

Pour fournir vos propres sources, utilisez les champs `shots[].source` et `shots[].broll[].source` du `ShortSpec`. Les chemins relatifs sont résolus depuis la racine du dépôt. Le moteur accepte les images courantes (JPEG, PNG, WebP) et les vidéos que FFmpeg sait décoder.

Les autres médias du clip de démonstration sont dans `assets/audio/` (voix de démonstration) et `assets/music/`, `assets/sfx/` (audio synthétisé localement). Les musiques et SFX sont des placeholders procéduraux, pas des tendances sous licence ; choisissez un son autorisé pour la publication finale.
