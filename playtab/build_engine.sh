#!/bin/bash
set -e
source ~/ps2-web-recomp/tools/emsdk/emsdk_env.sh >/dev/null 2>&1
export EM_CACHE=/home/kbmeh/xbox-web/tesm/emcache EM_LIBEXEC=/home/kbmeh/xbox-web/tesm/emlib EMSDK_BIN=/home/kbmeh/xbox-web/tesm/emlib ROOT=/home/kbmeh/xbox-web/tesm/openmw-web
export PATH=/home/kbmeh/xbox-web/tesm/emlib:$PATH
cd /home/kbmeh/xbox-web/tesm/openmw-web
echo "== configure $(date)"; bash configure-openmw.sh
echo "== ninja $(date)"; ninja -j12 -C build-wasm64 components openmw-lib
echo "== link $(date)"; bash wasm-build/link-openmw.sh
echo "== done $(date)"
