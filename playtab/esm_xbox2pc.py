#!/usr/bin/env python3
# esm_xbox2pc.py <xbox Morrowind.esm> <out Morrowind.esm>
# Rewrites the subrecords whose layout the Xbox ESM packs differently from the PC one, so the
# PC readers (OpenMW) take it. Record sizes in the record headers are fixed up.
# Known differences (found by OpenMW's "record size mismatch" errors):
#   INFO DATA  Xbox 8 bytes:  u8 type, u8 pad, i16 disposition, i8 rank, i8 gender, i8 pcrank, u8 pad
#              PC  12 bytes:  u8 type, 3 pad,  i32 disposition, i8 rank, i8 gender, i8 pcrank, u8 pad
#              (the low byte matches the parent DIAL's type; disposition is the journal index for
#              journal entries: 10, 20, 100 ...)
import struct, sys
from collections import Counter


def info_data(v):
    if len(v) != 8:
        return v
    t, disp = v[0], struct.unpack_from('<h', v, 2)[0]
    return struct.pack('<B3xi', t, disp) + v[4:8]


FIX = {(b'INFO', b'DATA'): info_data}


def main():
    d = open(sys.argv[1], 'rb').read()
    out = bytearray()
    changed = Counter()
    p = 0
    while p < len(d):
        tag = d[p:p + 4]
        size = struct.unpack_from('<I', d, p + 4)[0]
        head = d[p + 8:p + 16]
        body = d[p + 16:p + 16 + size]
        nb = bytearray()
        q = 0
        while q + 8 <= len(body):
            t = body[q:q + 4]
            n = struct.unpack_from('<I', body, q + 4)[0]
            v = body[q + 8:q + 8 + n]
            f = FIX.get((tag, t))
            if f:
                w = f(v)
                if w != v:
                    changed[(tag + b' ' + t).decode()] += 1
                v = w
            nb += t + struct.pack('<I', len(v)) + v
            q += 8 + n
        nb += body[q:]
        out += tag + struct.pack('<I', len(nb)) + head + nb
        p += 16 + size
    open(sys.argv[2], 'wb').write(out)
    print(dict(changed), len(d), '->', len(out))


if __name__ == '__main__':
    main()
