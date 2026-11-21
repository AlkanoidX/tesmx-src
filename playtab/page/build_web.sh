#!/bin/bash
# build_web.sh: fills ~/xbox-web/tesm/web (the test site, served by ../serve.py) from the engine build and these
# scripts: openmw.wasm / openmw.data (the page downloads them, engineFile), e/<stamp>/openmw.js (engine.html loads it),
# engine.html (make_engine.py), streamfs.js, data-sw.js, disc -> the chunks, index.html (make_page.py).
set -e
T=~/xbox-web/tesm; W=$T/web; P=$T/openmw-web; HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p $W
cp -f $P/build-wasm64/openmw.wasm $P/build-wasm64/openmw.data $W/
STAMP=$(sha1sum $W/openmw.wasm | cut -c1-12)
rm -rf $W/e; mkdir -p $W/e/$STAMP
cp -f $P/build-wasm64/openmw.js $W/e/$STAMP/
cp -f $P/play/streamfs.js $W/
cp -f "$HERE/../site/data-sw.js" $W/
python3 "$HERE/make_engine.py" $P/play/index.html $W/engine.html $STAMP
ln -sfn "/mnt/e/XBOX PLAYTAB/Morrowind-Xbox/2-DISQUE-BIN-GITHUB/disc" $W/disc
python3 "$HERE/make_page.py"
