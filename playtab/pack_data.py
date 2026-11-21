#!/usr/bin/env python3
# pack_data.py <Data Files dir> <out disc dir> [MiB]
# Lays every file of the converted Data Files end to end in one stream, cut into chunks
# cNNNN.bin (chunk k = bytes k * chunk of the stream), and writes disc.json:
#   {"chunk": bytes, "size": stream bytes, "files": [{"p": path, "o": offset, "s": size}, ...]}
# The page's service worker answers OpenMW's Range reads of mwdata/<path> from those chunks.
# Order = the order the game needs them: the ESM (read whole at start), the title music and the
# splash screens, the BSA, then sounds, music and films.
import json, os, sys

src, out = sys.argv[1], sys.argv[2]
chunk = int(sys.argv[3] if len(sys.argv) > 3 else 8) << 20


def rank(p):
    lo = p.lower()
    for i, pre in enumerate(('morrowind.esm', 'music/special/', 'splash/', 'morrowind.bsa',
                             'sound/fx/', 'music/explore/', 'sound/', 'music/', 'video/')):
        if lo.startswith(pre):
            return (i, lo)
    return (9, lo)


paths = []
for r, _, fs in os.walk(src):
    for f in fs:
        paths.append(os.path.relpath(os.path.join(r, f), src).replace(os.sep, '/'))
paths.sort(key=rank)
os.makedirs(out, exist_ok=True)
files, off, k, buf = [], 0, 0, bytearray()


def flush(final=False):
    global k, buf
    while len(buf) >= chunk or (final and buf):
        with open(os.path.join(out, 'c%04d.bin' % k), 'wb') as o:
            o.write(buf[:chunk])
        del buf[:chunk]
        k += 1


for p in paths:
    with open(os.path.join(src, p), 'rb') as f:
        d = f.read()
    files.append({'p': p, 'o': off, 's': len(d)})
    off += len(d)
    buf += d
    flush()
flush(True)
with open(os.path.join(out, 'disc.json'), 'w') as o:
    json.dump({'chunk': chunk, 'size': off, 'files': files}, o, separators=(',', ':'))
print(len(files), 'files', off, 'bytes', k, 'chunks')
