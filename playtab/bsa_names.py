#!/usr/bin/env python3
# bsa_names.py <xbox Morrowind.bsa> <Morrowind.esm> <out names.txt> [more files or folders to scan for names...]
# The Xbox Morrowind.bsa keeps only the TES3 name hashes (no name table). Recover the names by
# hashing candidate paths: every path-like string in the ESM, then every texture / animation
# name found inside the NIFs already named, repeated until nothing new matches.
import re, struct, sys

BS = '\\'


def tes3_hash(name):
    s = name.lower().replace('/', BS).encode('latin1')
    l = len(s) >> 1
    lo = off = 0
    for i in range(l):
        lo ^= (s[i] << (off & 0x1F)) & 0xFFFFFFFF
        off += 8
    hi = off = 0
    for i in range(l, len(s)):
        t = (s[i] << (off & 0x1F)) & 0xFFFFFFFF
        hi ^= t
        n = t & 0x1F
        if n:
            hi = ((hi << (32 - n)) | (hi >> n)) & 0xFFFFFFFF
        off += 8
    return lo, hi


def load_bsa(path):
    d = open(path, 'rb').read()
    ver, ho, n = struct.unpack_from('<III', d, 0)
    recs = [struct.unpack_from('<II', d, 12 + 8 * i) for i in range(n)]
    hashes = [struct.unpack_from('<II', d, 12 + ho + 8 * i) for i in range(n)]
    base = 12 + ho + 8 * n
    return d, recs, hashes, base


PATH_RE = re.compile(rb"[A-Za-z0-9_\\/ .'\-]{1,120}\.(?:nif|dds|tga|bmp|kf)", re.I)
WORD_RE = re.compile(rb"[A-Za-z][A-Za-z0-9_]{2,60}")
PREFIXES = ('meshes' + BS, 'textures' + BS, 'icons' + BS, 'bookart' + BS, 'splash' + BS, '')


def candidates(s):
    s = s.strip().replace('/', BS).lower().lstrip(BS)
    out = {s}
    if '.' not in s:
        return out
    stem, ext = s.rsplit('.', 1)
    forms = [s]
    if ext in ('tga', 'bmp', 'dds'):
        forms += [stem + '.dds', stem + '.tga', stem + '.bmp']
    for p in PREFIXES:
        for t in forms:
            out.add(p + t)
    if ext == 'nif':  # x-prefixed animation companions
        b = s.rsplit(BS, 1)
        d = (b[0] + BS) if len(b) > 1 else ''
        n = b[-1]
        for v in ('x' + n, 'x' + n[:-4] + '.kf'):
            out.add('meshes' + BS + d + v)
            out.add(d + v)
    return out


def main():
    d, recs, hashes, base = load_bsa(sys.argv[1])
    want = {h: i for i, h in enumerate(hashes)}
    names = {}
    tried = set()
    import os
    srcs = [sys.argv[2]] + sys.argv[4:]
    todo = set()
    for src in srcs:
        files = [src] if os.path.isfile(src) else [os.path.join(r, f) for r, _, fs in os.walk(src) for f in fs]
        for fn in files:
            try:
                todo |= set(m.decode('latin1') for m in PATH_RE.findall(open(fn, 'rb').read()))
            except OSError:
                pass
    # Engine code also builds names from a bare word ("menu_newgame" -> textures\menu_newgame.dds):
    # try every word of the sources with the usual folders and extensions.
    words = set()
    for src in srcs[1:]:
        files = [src] if os.path.isfile(src) else [os.path.join(r, f) for r, _, fs in os.walk(src) for f in fs]
        for fn in files:
            try:
                words |= set(m.decode('latin1') for m in WORD_RE.findall(open(fn, 'rb').read()))
            except OSError:
                pass
    for w in words:
        for p, e in (('textures' + BS, '.dds'), ('icons' + BS, '.dds'), ('meshes' + BS, '.nif'), ('', '.dds')):
            todo.add(p + w + e)
    rnd = 0
    variants_done = False
    while todo:
        rnd += 1
        new = set()
        for s in todo:
            for c in candidates(s):
                if c in tried:
                    continue
                tried.add(c)
                i = want.get(tes3_hash(c))
                if i is not None and i not in names:
                    names[i] = c
                    if c.endswith('.nif') or c.endswith('.kf'):
                        size, off = recs[i]
                        for m in PATH_RE.findall(d[base + off: base + off + size]):
                            new.add(m.decode('latin1'))
        print(f'round {rnd}: {len(names)} of {len(hashes)} named', file=sys.stderr)
        if not new and not variants_done:
            # Numbered siblings of every name found (tx_sun_05 -> tx_sun_00..99, water00..31, ...).
            variants_done = True
            for c in list(names.values()):
                for m in re.finditer(r'\d+', c):
                    w = len(m.group())
                    for k in range(10 ** min(w, 2) if w <= 2 else 100):
                        new.add(c[:m.start()] + str(k).zfill(w) + c[m.end():])
        todo = new
    with open(sys.argv[3], 'w', encoding='latin1') as f:
        for i in range(len(hashes)):
            f.write(f'{i}\t{hashes[i][0]:08x}{hashes[i][1]:08x}\t{recs[i][0]}\t{names.get(i, "")}\n')
    kinds = {}
    for i in range(len(hashes)):
        if i not in names:
            k = d[base + recs[i][1]: base + recs[i][1] + 4]
            kinds[k] = kinds.get(k, 0) + 1
    print('unnamed by kind:', kinds, file=sys.stderr)


if __name__ == '__main__':
    main()
