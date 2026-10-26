"""Unpack a retail PS3 .pkg (the PSN edition of Out of Bounds, NPUA80765) into OUTDIR: what a disc's PS3_GAME holds.

    python3 tools/unpkg.py GAME.pkg extracted/oob/PS3_GAME [--list]

A retail package is AES-128-CTR under the PS3's public package key, counter = the header's IV + block number. The
game's own files come out as plain files (the .edat in CLAPHANZ-* are only DLC licences); the program stays encrypted.
"""
import os, struct, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = bytes.fromhex('2E7B71D7C9C9A14EA3221F188828B8F8')
pkg, out = sys.argv[1], sys.argv[2]
f = open(pkg, 'rb')
h = f.read(0x80)
assert h[:4] == b'\x7fPKG'
items, = struct.unpack('>I', h[0x14:0x18])
doff, dsize = struct.unpack('>QQ', h[0x20:0x30])
riv = int.from_bytes(h[0x70:0x80], 'big')

def dec(off, n):
    """n bytes of the data area at off (a multiple of 16)."""
    f.seek(doff + off)
    iv = ((riv + off // 16) % (1 << 128)).to_bytes(16, 'big')
    return Cipher(algorithms.AES(KEY), modes.CTR(iv)).decryptor().update(f.read(n))

table = dec(0, items * 32)
for i in range(items):
    noff, nsz, off, sz, flags, _ = struct.unpack('>IIQQII', table[i * 32:i * 32 + 32])
    name = dec(noff & ~15, nsz + 16)[noff & 15:][:nsz].decode()
    kind = flags & 0xff
    if '--list' in sys.argv:
        print(kind, sz, name)
        continue
    path = os.path.normpath(os.path.join(out, name))
    assert path.startswith(os.path.normpath(out) + os.sep), name
    if kind == 4:  # directory
        os.makedirs(path, exist_ok=True)
        continue
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as w:
        for p in range(0, sz, 1 << 24):
            w.write(dec(off + p, min(1 << 24, sz - p)))
