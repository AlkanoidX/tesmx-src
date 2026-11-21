#!/bin/bash
# deliver.sh <delivery folder> <ftp folder name> <github owner/repo>: fills the delivery's FTP folder from
# ~/xbox-web/tesm/web (run build_web.sh first). Layout (user's rule): <delivery>/<X_INITIALS>/ = the files for the FTP,
# <delivery>/2-DISQUE-BIN-GITHUB/ = the git repo of the game data pushed to GitHub (disc/ chunks + disc.json).
set -e
OUT="$1/$2"; REPO="$3"; WEB=~/xbox-web/tesm/web
rm -rf "$OUT"; mkdir -p "$OUT/disc"
cp -L "$WEB/index.html" "$WEB/engine.html" "$WEB/streamfs.js" "$WEB/data-sw.js" "$OUT/"
cp -rL "$WEB/e" "$OUT/"
gzip -9 -c "$WEB/openmw.wasm" > "$OUT/openmw.wasm.gz"
gzip -9 -c "$WEB/openmw.data" > "$OUT/openmw.data.gz"
cp ~/xbox-web/tesm/openmw-web/LICENSE "$OUT/licenses.txt"
python3 - "$1/2-DISQUE-BIN-GITHUB/disc/disc.json" "$OUT/disc/disc.json" "$REPO" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
d["base"] = "https://raw.githubusercontent.com/%s/main/disc/" % sys.argv[3]
json.dump(d, open(sys.argv[2], "w"), separators=(",", ":"))
EOF
cat > "$OUT/LISEZMOI.txt" <<'EOF'
The Elder Scrolls III: Morrowind - Game of the Year Edition (Xbox) pour le navigateur.
Envoyer ce dossier tel quel sur le FTP, avec son nom (X_TESM) : ce nom est la cle des sauvegardes, ne jamais le renommer.
- index.html, engine.html, streamfs.js, data-sw.js, openmw.wasm.gz, openmw.data.gz, e/, licenses.txt, disc/disc.json : dans le dossier du jeu.
- data-sw.js (service worker) doit etre servi a cote de index.html (https).
- Sauvegarde cloud : la page charge /pt-cloud-xbox/cloud-xbox.js, commun a tous les jeux Xbox (deja a la racine du site, absent de ce dossier).
Les donnees du jeu (850 Mo, donnees du disque Xbox converties au format PC) ne sont pas ici : la page les lit sur GitHub
(adresse dans disc/disc.json) et les garde sur l'appareil.
Le site doit envoyer les en-tetes COOP/COEP (comme les pages PS2). Navigateurs : Chrome, Edge, Brave (bureau) ; pas Firefox ni Safari.

Moteur : OpenMW, version navigateur openmw-web (github.com/Virtastic/openmw-web), licence GPL-3.0 (licenses.txt),
avec les changements de ce portage (decodeurs ADPCM Xbox et WMA, voix .wav a la place des .mp3).
Icones des boutons tactiles : game-icons.net (Lorc, Delapouite), licence CC BY 3.0 ; ce credit doit rester visible quelque part sur le site.
EOF
ls -la "$OUT" "$OUT/disc"
du -sh "$OUT"
