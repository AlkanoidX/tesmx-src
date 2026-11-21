#!/usr/bin/env python3
# esm_refs.py <Morrowind.esm> <names.txt> <files.txt>
# Lists the asset paths the ESM names (models, icons, sounds, voices) and checks that each one is
# found in the renamed BSA (names.txt from bsa_names.py) or as a loose file on the disc
# (files.txt from xiso.py list). Prints the counts per kind and the paths not found.
import re, struct, sys

BS = '\\'


def records(d):
    p = 0
    while p < len(d):
        tag = d[p:p + 4]
        size = struct.unpack_from('<I', d, p + 4)[0]
        body = d[p + 16:p + 16 + size]
        yield tag, body
        p += 16 + size


def subs(body):
    q = 0
    while q + 8 <= len(body):
        t = body[q:q + 4]
        n = struct.unpack_from('<I', body, q + 4)[0]
        yield t, body[q + 8:q + 8 + n]
        q += 8 + n


def z(b):
    return b.split(b'\0', 1)[0].decode('latin1').replace('/', BS).lower()


def main():
    d = open(sys.argv[1], 'rb').read()
    bsa = set()
    for line in open(sys.argv[2], encoding='latin1'):
        f = line.rstrip('\n').split('\t')
        if len(f) > 3 and f[3]:
            bsa.add(f[3])
    loose = set()
    for line in open(sys.argv[3], encoding='latin1'):
        p = line.strip().split(None, 1)
        if len(p) == 2:
            loose.add(p[1].replace('/', BS).lower())
    refs = {}  # kind -> set
    for tag, body in records(d):
        for t, v in subs(body):
            if tag == b'INFO' and t == b'SNAM':
                refs.setdefault('voice', set()).add(z(v))
            elif t == b'MODL':
                refs.setdefault('mesh', set()).add('meshes' + BS + z(v))
            elif t in (b'ITEX', b'TNAM') and tag not in (b'SCPT',):
                s = z(v)
                if s.endswith(('.tga', '.dds', '.bmp')):
                    refs.setdefault('icon/tex', set()).add(s)
            elif tag == b'SOUN' and t == b'FNAM':
                refs.setdefault('sound', set()).add(z(v))
    base_names = {}
    for p in loose:
        base_names.setdefault(p.rsplit(BS, 1)[-1], []).append(p)
    for kind, s in sorted(refs.items()):
        miss = []
        for r in sorted(s):
            if kind == 'mesh':
                ok = r in bsa
            elif kind == 'icon/tex':
                stem = r.rsplit('.', 1)[0]
                ok = any((p + stem + '.dds') in bsa for p in ('icons' + BS, 'textures' + BS, ''))
            else:  # sounds and voices are loose files, under other folders on the Xbox disc
                tail = r.split(BS, 1)[-1]
                ok = tail in loose or r.rsplit(BS, 1)[-1] in base_names
            if not ok:
                miss.append(r)
        print(f'{kind}: {len(s)} referenced, {len(miss)} not found')
        for m in miss[:15]:
            print('   ', m)


main()
