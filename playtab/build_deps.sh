#!/bin/bash
set -e
source ~/ps2-web-recomp/tools/emsdk/emsdk_env.sh >/dev/null 2>&1
export EM_CACHE=/home/kbmeh/xbox-web/tesm/emcache EM_LIBEXEC=/home/kbmeh/xbox-web/tesm/emlib EMSDK_BIN=/home/kbmeh/xbox-web/tesm/emlib ROOT=/home/kbmeh/xbox-web/tesm/openmw-web JOBS=12
export PATH=/home/kbmeh/xbox-web/tesm/emlib:$PATH
cd /home/kbmeh/xbox-web/tesm/openmw-web
[ -n "${DEPS:-}" ] || { echo == fetch; bash wasm-build/fetch-deps.sh; }
echo "== build $(date)"; bash wasm-build/build-deps.sh ${DEPS:-}
echo "== done $(date)"
[ -n "${THEN_ENGINE:-}" ] && bash /home/kbmeh/xbox-web/tesm/build_engine.sh
