#!/usr/bin/env python3
# make_engine.py <openmw-web play/index.html> <out engine.html> <engine stamp>
# The PlayTab page (index.html, make_page.py) runs OpenMW's own page in a same-origin frame: engine.html is
# openmw-web's play/index.html with two changes:
#  - its first script hands its window to the PlayTab page (parent.ptEngineHook) before anything else runs, so the
#    page puts in its gamepad, its sound chain, the engine files it already downloaded, the resolution, and stops
#    mouse capture (rule: no mouse capture);
#  - the engine files are looked for in e/<stamp>/ (openmw-web's own versioned path), so a browser never pairs this
#    page with an older engine.
import sys

src, out, stamp = sys.argv[1], sys.argv[2], sys.argv[3]
c = open(src, encoding='utf-8').read()
HOOK = ('<script>/* PlayTab: the page that holds this frame sets it up first (make_engine.py) */'
        'try{if(parent!==window&&parent.ptEngineHook)parent.ptEngineHook(window)}catch(e){console.warn("ptEngineHook",e)}</script>')
head = '<meta charset="utf-8">'
assert c.count(head) >= 1
c = c.replace(head, head + HOOK, 1)
ver = 'var __ENGINE_VER = "__ENGINE_VERSION__";'
assert c.count(ver) == 1
c = c.replace(ver, 'var __ENGINE_VER = "%s";' % stamp)
open(out, 'w', encoding='utf-8').write(c)
print('engine.html written,', stamp)
