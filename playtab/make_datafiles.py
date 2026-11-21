#!/usr/bin/env python3
# make_datafiles.py <tesm.iso> <names.txt> <out Data Files dir>
# Turns the Xbox Morrowind GOTY disc into the PC "Data Files" layout that OpenMW reads:
#   Morrowind.esm                 from the disc (Tribunal and Bloodmoon are merged into it), with the
#                                 subrecords the Xbox packs differently rewritten by esm_xbox2pc.py
#   Morrowind.bsa                 rewritten in the PC TES3 layout with the names bsa_names.py found
#                                 (files whose name was not found are left out: nothing names them)
#   Sound/<path from the ESM>     the disc keeps sounds and voices at its root without the
#                                 Fx/Cr/Vo level, and voices as Xbox ADPCM .wav where the ESM says .mp3
#   Music/, Video/, Splash/       copied from the disc's Data Files (music WMA files named .mp3)
# Writes <out>/../datafiles-report.txt with what could not be placed.
import os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BS = '\\'


class Iso:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.f.seek(0x10000)
        assert self.f.read(20) == b'MICROSOFT*XBOX*MEDIA'
        root_sec, root_size = struct.unpack('<II', self.f.read(8))
        self.files = {}  # lower path -> (real path, sector, size)
        self._walk(root_sec, root_size, '')

    def _walk(self, sec, size, prefix):
        self.f.seek(sec * 2048)
        d = self.f.read(size)

        def node(off):
            if off * 4 >= len(d):
                return
            l, r, s, sz, attr, n = struct.unpack_from('<HHIIBB', d, off * 4)
            if l == 0xFFFF:
                return
            name = d[off * 4 + 14: off * 4 + 14 + n].decode('latin1')
            if l:
                node(l)
            if attr & 0x10:
                if sz:
                    self._walk(s, sz, prefix + name + '/')
            else:
                self.files[(prefix + name).lower()] = (prefix + name, s, sz)
            if r:
                node(r)
        node(0)

    def read(self, lower):
        _, s, sz = self.files[lower]
        self.f.seek(s * 2048)
        return self.f.read(sz)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


def write_bsa(out, entries):
    """entries: list of (name lower with backslashes, bytes). PC TES3 BSA, sorted by hash."""
    from bsa_names import tes3_hash
    entries = sorted(entries, key=lambda e: (tes3_hash(e[0])[0], tes3_hash(e[0])[1]))
    n = len(entries)
    names = b''
    name_offs = []
    for name, _ in entries:
        name_offs.append(len(names))
        names += name.encode('latin1') + b'\0'
    hash_off = 12 * n + len(names)
    recs = b''
    off = 0
    for _, data in entries:
        recs += struct.pack('<II', len(data), off)
        off += len(data)
    with open(out, 'wb') as f:
        f.write(struct.pack('<III', 0x100, hash_off, n))
        f.write(recs)
        f.write(b''.join(struct.pack('<I', o) for o in name_offs))
        f.write(names)
        for name, _ in entries:
            lo, hi = tes3_hash(name)
            f.write(struct.pack('<II', lo, hi))
        for _, data in entries:
            f.write(data)


def main():
    iso = Iso(sys.argv[1])
    out = sys.argv[3]
    report = []

    # 1. ESM and loose Data Files folders.
    for low, (real, _, _) in iso.files.items():
        if low.startswith('data files/') and not low.endswith(('.bsa', '.esm.map')):
            if low.startswith('data files/fonts/'):
                continue  # Xbox font format; OpenMW uses its own fonts
            rel = real[len('Data Files/'):]
            if low.startswith('data files/music/') and low.endswith('.wma'):
                # The engine asks for music/special/morrowind title.mp3 and the PC names; FFmpeg
                # finds the WMA by its content, so only the name changes.
                rel = rel[:-4] + '.mp3'
            write(os.path.join(out, rel), iso.read(low))
    # The ESM packs some subrecords differently from the PC layout: rewrite them.
    import subprocess
    esm = os.path.join(out, 'Morrowind.esm')
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'esm_xbox2pc.py'),
                    esm, esm], check=True)

    # 2. BSA with names.
    d = iso.read('data files/morrowind.bsa')
    ver, ho, n = struct.unpack_from('<III', d, 0)
    base = 12 + ho + 8 * n
    entries = []
    dropped = 0
    for line in open(sys.argv[2], encoding='latin1'):
        f = line.rstrip('\n').split('\t')
        i = int(f[0])
        size, off = struct.unpack_from('<II', d, 12 + 8 * i)
        if len(f) > 3 and f[3]:
            entries.append((f[3], d[base + off: base + off + size]))
        else:
            dropped += 1
    write_bsa(os.path.join(out, 'Morrowind.bsa'), entries)
    report.append(f'bsa: {len(entries)} files written, {dropped} without a name left out')

    # 3. Sounds: every sound path the ESM names (records and script text).
    esm = iso.read('data files/morrowind.esm')
    refs = set(m.decode('latin1').replace('/', BS).lower().strip()
               for m in re.findall(rb'[A-Za-z0-9_\\/ .\'\-]{1,120}\.(?:wav|mp3)', esm, re.I))
    by_tail = {}
    by_base = {}
    for low in iso.files:
        if low.endswith(('.wav', '.mp3')) and not low.startswith('data files/'):
            by_tail[low.replace('/', BS)] = low
            by_base.setdefault(low.rsplit('/', 1)[-1], []).append(low)
    placed = {}
    for r in sorted(refs):
        r = r.lstrip(BS)
        if r.startswith('sound' + BS):
            r = r[6:]
        tail = r.split(BS, 1)[1] if BS in r else r
        hit = None
        for t in (tail, tail[:-4] + '.wav', tail[:-4] + '.mp3'):
            if t in by_tail:
                hit = by_tail[t]
                break
        if hit is None:
            b = r.rsplit(BS, 1)[-1]
            for t in (b, b[:-4] + '.wav', b[:-4] + '.mp3'):
                if len(by_base.get(t, [])) == 1:
                    hit = by_base[t][0]
                    break
        if hit is None:
            report.append('sound not on disc: ' + r)
            continue
        # Keep the disc's extension (the engine is patched to try .wav for a missing .mp3).
        dest = r[:-4] + hit[-4:]
        placed[hit] = dest
    unused = [low for low in by_tail.values() if low not in placed]
    # Files no record names are kept too (cheap, and scripts may build names the scan cannot see):
    # race/sex voice folders and the Misc/Dagoth voice folders go under Vo, the rest under Fx.
    for low in unused:
        top = low.split('/', 1)[0]
        kind = 'vo' if ('/' in low and (len(top) == 1 or top in ('misc', 'dagoth'))) else 'fx'
        placed[low] = kind + BS + low.replace('/', BS)
    for hit, dest in placed.items():
        write(os.path.join(out, 'Sound', *dest.split(BS)), iso.read(hit))
    report.append(f'sounds: {len(placed) - len(unused)} placed from records, '
                  f'{len(unused)} no record names (kept under vo/ or fx/)')
    report += ['  unplaced: ' + u for u in sorted(unused)]
    with open(os.path.join(out, '..', 'datafiles-report.txt'), 'w', encoding='latin1') as f:
        f.write('\n'.join(report) + '\n')
    print('\n'.join(report[:12]))


main()
