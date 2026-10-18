# Méthode ShortsForge — du scroll au rewatch

Cette méthode transforme une intention marketing en une vidéo courte, regardable sans son, rythmée et exploitable en test. Elle est codifiée par les skills du dossier `skills/` et vérifiée par `sf qa`.

## 1. Choisir un seul résultat

Avant d'écrire, répondre en une phrase :

- **Pour qui ?** Une audience, pas « tout le monde ».
- **Quel problème / désir ?** Un point concret et reconnaissable.
- **Quelle transformation ?** Ce que le spectateur saura, évitera ou fera après la vidéo.
- **Quelle action finale ?** Une seule : s'abonner, commenter, cliquer, enregistrer, acheter.

Un Short n'est pas un mini-webinaire. Une idée, une promesse, une action.

## 2. Écrire le hook (0–3 s)

Le hook fait arrêter le pouce, pas réciter la marque. Il doit rester compréhensible même si le son est coupé et le contexte inconnu.

### Formules à tester

- **Erreur/coût :** « Cette erreur fait fuir tes clients. »
- **Résultat concret :** « Trois coupes pour doubler le rythme. »
- **Curiosité ouverte :** « Le détail que personne ne sous-titre. »
- **Contraste :** « Tu postes plus. Tu vends moins. »
- **Démonstration :** montrer le résultat avant l'explication.
- **Question ciblée :** « Tes vidéos perdent tout le monde après trois secondes ? »

### Règles de montage du hook

1. Commencer par le mot utile, le geste ou le résultat ; supprimer « Salut, je m'appelle… ».
2. Une seule proposition, idéalement 3–8 mots à l'écran.
3. Hook visuel et verbal synchronisés avant 0,3 s ; pas d'intro/logo animé.
4. Installer une promesse ou une boucle ouverte, puis la payer dans la vidéo.
5. Préparer 3–5 hooks réellement différents pour le test A/B.

La note automatique (`score_hook`) aide à trier ; elle ne sait pas si la promesse est vraie ni si elle résonne avec l'audience. Relecture humaine obligatoire.

## 3. Construire le corps (3–50 s)

### Script oral

- Viser 15–45 s au total (souvent 20–35 s pour une idée simple).
- Une idée utile par phrase ; phrases courtes, langue parlée, verbes actifs.
- Avancer : **promesse → preuve/exemple → explication → payoff**.
- Remplacer les affirmations vagues par un chiffre, une action, un avant/après ou un cas concret.
- Écrire pour être dit à voix haute. Lire une fois au chronomètre, puis couper 10–20 %.
- Ne pas créer de fausse statistique ; toute preuve chiffrée doit être vérifiable.

### Rythme visuel

- Couper ou transformer le cadre toutes les **1,5–3 s** : jump cut, angle, plan de détail, insert, capture, graphique ou geste.
- Un plan long n'est justifié que s'il montre une action qui évolue.
- Ajouter un mouvement lent (Ken Burns, pan, léger handheld) pour éviter l'image figée ; éviter les zooms agressifs permanents.
- Insérer du B-roll précisément sur le nom de l'objet ou de l'action ; ne pas couvrir le visage/élément qui porte l'information.
- Utiliser transitions flash/whip/glitch/dip avec parcimonie, uniquement si elles accentuent une coupe.
- Chaque changement doit soutenir le message ; pas de surcharge gratuite.

## 4. Concevoir l'image pour le mobile

- Master : **1080 × 1920, 9:16, 30 fps**.
- Visage/objet principal dans la zone centrale ; prévoir les recadrages des plateformes.
- Titres, captions, stickers importants à l'intérieur de la safe zone : éviter la bande haute, les contrôles en bas et la colonne d'icônes à droite.
- Contraste élevé, 1–2 familles typographiques, mots courts.
- Un accent de couleur pour le mot à retenir ; fond semi-opaque si la source est chargée.
- Limiter stickers, flèches et popups à ceux qui montrent une relation ou une action.
- Le hook et le CTA ne doivent pas masquer le sujet ni les sous-titres.

La zone de sécurité ShortsForge est un point de départ configurable dans `safe_zone`, pas un gabarit officiel unique : vérifiez sur chaque plateforme et sur un téléphone réel.

## 5. Sous-titrer pour le visionnage muet

- Les captions suivent la voix ; viser une couverture quasi complète.
- Afficher un mot à la fois ou un petit groupe synchronisé ; mettre le mot-clé en couleur, sans faire rebondir toute la ligne.
- Une ou deux lignes courtes, typiquement 60–90 px sur une composition 1080 × 1920.
- Contraste/stroke suffisant sur les plans clairs et sombres.
- Centrer horizontalement dans la zone utile ; laisser la bouche et le produit visibles.
- Vérifier accents, nombres, ponctuation et mots découpés. Le fichier ASS doit rester lisible sur petit écran.

Le renderer calcule le placement au pixel avec les métriques réelles des polices puis produit des événements ASS karaoké. `sf align` améliore les timecodes en repérant les silences du voice-over ; écouter et corriger les cas ambigus.

## 6. Mixer le son

Ordre de priorité : **voix > effet utile > musique**.

- Enregistrer près du micro, dans une pièce calme ; filtrer le grave parasite et égaliser sans rendre la voix artificielle.
- Isoler et nettoyer la voix ; le moteur la normalise et la passe à 1,06× par défaut. Ajuster entre 1,05× et 1,10× seulement si la diction reste naturelle.
- Garder la musique nettement sous la voix, duckée automatiquement pendant la parole.
- Caler un whoosh, pop, impact ou ding sur une coupe ou une révélation ; petits niveaux, pas un SFX à chaque syllabe.
- Le mix vise environ **−14 LUFS intégrés** avec limiteur ; écouter aussi sur haut-parleur de téléphone et casque.
- Commencer sans longue intro sonore ; un court silence peut être volontaire, mais ne pas laisser de trou involontaire.

Les musiques/SFX livrés sont générés par synthèse locale, pas issus des tendances actuelles. Avant publication, remplacer la nappe si nécessaire par un son autorisé et disponible dans l'application cible.

## 7. Finir par une action ou une boucle

### CTA de conversion

Un CTA, un verbe, un bénéfice : « Abonne-toi pour la suite », « Enregistre ce plan », « Écris “GUIDE” en commentaire ». Le relier à la promesse de la vidéo. Le placer dans les dernières secondes sans faire disparaître la valeur utile.

### Boucle

- Reprendre l'image, le mouvement, un mot ou le son du premier plan.
- Faire que la dernière phrase mène naturellement au hook ; pas de « fin » ni de fondu au noir qui annonce le replay.
- Synchroniser taille, cadrage, couleur et mouvement des images de début/fin.
- Tester le raccord en boucle réelle : regarder au moins deux répétitions sans toucher l'écran.

Une boucle n'est pas un substitut au payoff : la promesse doit être tenue avant de relancer le début.

## 8. Préparer la publication et mesurer

1. Exporter le master 9:16, regarder en entier sur téléphone, son activé puis coupé.
2. Vérifier le titre, la couverture, les sous-titres automatiques de la plateforme et la zone des boutons.
3. Publier avec un seul CTA et un texte d'accompagnement adapté à la plateforme.
4. Consigner la rétention à 1–3 s, la durée moyenne, le taux de complétion, les replays, sauvegardes, partages et conversions.
5. Diagnostiquer la première chute, pas seulement les vues totales : hook, clarté, densité, payoff, CTA.
6. Tester une seule variable par variante (hook **ou** rythme **ou** CTA). Garder le reste identique ; ne pas annoncer de gagnant sur un seul petit échantillon.

ShortsForge donne un score de conformité et signale les écarts. Il ne prédit pas l'algorithme, ne mesure pas la vérité d'une promesse et n'automatise ni la publication ni la collecte d'analytics.

## 9. Contrôle avant export

- [ ] 9:16, 1080 × 1920, 30 fps ; durée 15–45 s.
- [ ] Hook visible et compréhensible avant 3 s.
- [ ] Corps centré sur une seule idée ; payoff concret.
- [ ] Aucun plan mort ; changement visuel moyen toutes les 1,5–3 s.
- [ ] B-roll et graphismes utiles, pas décoratifs.
- [ ] Captions mot à mot lisibles, exactes et en zone sûre.
- [ ] Voix nette, musique duckée, SFX discrets ; mix vérifié sur téléphone.
- [ ] CTA unique dans la fin ou raccord de boucle testé.
- [ ] Droits des médias et de la musique vérifiés pour la plateforme.
- [ ] `sf qa <spec.yaml>` exécuté ; tout avertissement examiné.
