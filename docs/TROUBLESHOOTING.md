# Dépannage

## FFmpeg

**« FFmpeg introuvable »**
Le socle cherche dans cet ordre : `$FFMPEG_BIN`, `PATH`, binaire `imageio-ffmpeg`,
`/opt/homebrew/bin`, `/usr/local/bin`, `/snap/bin`.

```bash
which ffmpeg                       # doit renvoyer un chemin
export FFMPEG_BIN=/chemin/ffmpeg   # force un binaire précis
pip install imageio-ffmpeg         # solution sans droits admin
```

**« Ce FFmpeg n'a pas le filtre 'ass' » / build sans libass**
Depuis Homebrew v8, la formule `ffmpeg` est un build **slim** : ni `libass`, ni
`subtitles`, ni `drawtext`. Le build complet est une formule séparée, **keg-only** :

```bash
brew install ffmpeg-full
export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"   # à mettre dans ~/.zshrc
```

Autre solution sans droits admin : `pip install imageio-ffmpeg`, dont le binaire
embarqué inclut libass (le socle le détecte automatiquement).
Le pack interroge `ffmpeg -h filter=…` (stable entre versions) et se rabat sur
`subtitles` quand `ass` manque ; sans aucun des deux, il produit le `.ass` et
poursuit (la démo saute l'incrustation et l'aperçu avec un avertissement).

**« Ce FFmpeg n'a pas le filtre 'ass' » (ancien message)**
Build sans libass (fréquent avec certaines roues statiques). Solutions :
`brew install ffmpeg-full`, `sudo apt install ffmpeg`, ou télécharger un build Gyan/BtbN.
En attendant, les fichiers `.ass` produits restent utilisables dans VLC, Resolve ou Premiere.

**ffprobe absent ou cassé**
Un binaire `ffprobe` qui pointe vers ffmpeg provoque `Unrecognized option 'print_format'`.
Le socle détecte l'échec et retombe sur l'analyse `ffmpeg -i` (durée, résolution, fps,
audio). Pour des métadonnées complètes : installer le paquet ffmpeg complet.

## Polices et emojis

**Les sous-titres utilisent une autre police**
Montserrat/Inter ne sont pas embarquées. Installer les familles, ou forcer :
`--font "DejaVu Sans"` (Linux), `--font "Arial"` (Windows/macOS).

**Les emojis apparaissent en carrés**
Aucune police emoji installée sur la machine de rendu
(`fonts-noto-color-emoji` sur Debian/Ubuntu). Vérifier avec
`fc-list | grep -i emoji`. Le fichier ASS reste correct ; seul le rendu local manque.

**Le texte déborde de l'écran**
Le moteur réduit automatiquement la police (jusqu'à ×0,5) et replie sur 2 lignes.
Si cela persiste : `--canvas 720x1280` pour tester, ou `--max-words 2`.

## Transcription

**« Aucun moteur de transcription disponible »**
`pip install faster-whisper` (local) ou exporter `OPENAI_API_KEY` / `GROQ_API_KEY`.
Diagnostic : `python3 skills/speech-to-text-whisper/scripts/transcribe.py --doctor`.

**Premier lancement très long**
Le modèle Whisper est téléchargé (75 Mo pour `small`, 1,5 Go pour `large-v3`).
Utiliser `--model base` pour un test rapide, puis `small`/`medium`.

**Erreur 413 / 25 Mo via API**
Découper l'audio : `ffmpeg_tool.py cut … --reencode`, ou utiliser un moteur local.

**Mots collés / ponctuation absente**
Forcer la langue (`--language fr`), utiliser `--model large-v3`, et nettoyer l'audio
en amont (`audio-cleaning-enhancer`) : le bruit dégrade fortement la ponctuation.

## Vidéo

**« Départ à X s (pré-roll coupé) »**
Message informatif : la première plage commence après 0 s.

**Le rendu des coupes est plus long que prévu**
`render_cut` réencode en H.264 (`crf 18`, `preset medium`). Utiliser `--preset ultrafast`
pour un brouillon, `--crf 23` pour alléger.

**Le recadrage 9:16 coupe la tête**
Passer `--mode blur` (fond flou) ou ajuster `--keyframes` à la main. Haar peut rater
les visages de profil : vérifier avec `--analyze faces.json`.

**OpenCV manquant**
`pip install opencv-python-headless`. Sans lui, le recadrage `face` bascule
automatiquement en `center` et la détection de scènes est ignorée.

## NLE

**FCPXML importé mais médias non reliés**
Les chemins du FCPXML sont absolus (`file://localhost/…`). Si les rushes ont bougé,
relier manuellement dans Premiere, ou régénérer le plan avec les bons chemins.

**ExtendScript ne trouve pas `app.project`**
Le script doit être lancé depuis Premiere : Fichier → Scripts → Exécuter un script.
Un `.jsx` exécuté dans un terminal ne fait rien.

**Resolve : `ImportError: DaVinciResolveScript`**
L'API n'est disponible qu'avec Resolve lancé, et complète en version Studio.
Le script généré tente plusieurs chemins de modules ; vérifier la console Resolve.

**Resolve : le rendu ne démarre pas**
Un preset/codec installé est nécessaire (`--preset fichier.xml`), et le dossier de
sortie doit exister : le script le crée, mais vérifier les droits.

## Audio

**Le rendu sonne métallique**
`afftdn` trop agressif : baisser `--denoise` (20–30). Le débruiteur spectral crée des
artefacts sur les voix très dégradées.

**Le niveau final n'est pas à −16 LUFS**
Vérifier que la mesure 2 passes n'a pas été désactivée (`--single-pass`). Le rapport
affiche LUFS avant/après : si l'entrée est très dynamique, `loudnorm` linéaire peut
dériver légèrement ; relancer une passe sur la sortie.

**Les SFX ne s'entendent pas**
Vérifier les gains du catalogue (`sfx-catalog.json`), relancer
`build_catalog.py --generate`, et contrôler le mix (`--sfx-gain 3`).

## Système

**Windows : `UnicodeEncodeError` dans la console**
Le socle intercepte et réécrit en ASCII ; pour un affichage complet :
`set PYTHONUTF8=1` (ou `chcp 65001`).

**macOS : « operation not permitted » sur un dossier**
Donner à Terminal l'accès au dossier (Réglages → Confidentialité → Fichiers et dossiers),
ou travailler dans `~/Movies`.

**JSON invalide en sortie (`NaN`)**
Corrigé par `sanitize_json` : les valeurs non finies deviennent `null`. Si un ancien
fichier contient `NaN`, le relire avec `json.loads(..., parse_constant=…)` ou régénérer.

## Diagnostic global

```bash
bash scripts/selftest.sh          # 38 contrôles + pipeline réelle
python3 -m unittest discover -s tests -v
```

Si un contrôle échoue, la sortie indique le composant exact et le fichier à consulter.
