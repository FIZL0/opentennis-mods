"""Clap takes put the racket away (opentennis B586), in place.

python3 tools/rerig/claps.py MOD_DIR…     (golf mods already packaged; bumps mod.json `version` if any changed)

A take whose source clip is one of its game's claps (by the source's own clip name, CLAP) is marked
`extras: {"racket": false}` in motions.glb (standard §6 Racket): clapping hands would otherwise go through the racket,
and the geometric check in motions.py misses some. No clap sound: the source games' clap SEs are the gallery's
applause, not the player's (user 2026-10-20); a `voice/11_0.wav` an earlier version shipped is removed.

package.py runs it on every golf mod it packages. By hand for mods already packaged: bump happens here, upload after.
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rerig import glb  # noqa: E402

# the source games' clap clips: the putt-gallery reactions `ku<pc>_cl` (Out of Bounds, Open Tee 2), the result
# screen's `rslt_clap_pc<pc>` (Out of Bounds), Fore!'s `clap_<pc>`
CLAP = re.compile(r"ku\d+_cl|rslt_clap_pc\d+|clap_\d+")
OFF = {"racket": False}


def sources(why):
    """The source clips a `motions_why` line names: 'reason; a then b, root held …' -> [a, b]."""
    return why.split("; ", 1)[-1].split(",")[0].split(" then ")


def apply(mod, manifest):
    """Mark `mod`'s clap takes racket-off (manifest updated, not written). -> whether anything changed."""
    claps = {k for k, why in manifest.get("motions_why", {}).items() if any(CLAP.fullmatch(s) for s in sources(why))}
    changed = False
    path = os.path.join(mod, "motions.glb")
    if os.path.exists(path):
        g, b = glb.read(path)
        for a in g.get("animations", []):
            if (a.get("name") in claps or a.get("extras", {}).get("clap")) and a.get("extras", {}).get("racket") is not False:
                a["extras"] = {**{k: v for k, v in a.get("extras", {}).items() if k != "clap"}, **OFF}
                changed = True
        if changed:
            js = json.dumps(g, separators=(",", ":")).encode()
            js += b" " * (-len(js) % 4)
            b = bytes(b) + b"\0" * (-len(b) % 4)
            out = bytearray(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(b)))
            out += struct.pack("<I", len(js)) + b"JSON" + js
            out += struct.pack("<I", len(b)) + b"BIN\0" + b
            open(path + ".tmp", "wb").write(out)
            os.replace(path + ".tmp", path)  # a new file: a hard link package.py made stays as it was
    wav = os.path.join(mod, "voice/11_0.wav")
    if os.path.exists(wav):
        os.remove(wav)
        changed = True
    for k in ("voice_counts", "voice_why"):
        if manifest.get(k, {}).pop("11", None) is not None:
            changed = True
    return changed


def main(dirs):
    from edge_clamp import bump
    for d in dirs:
        mf = os.path.join(d, "mod.json")
        if not os.path.exists(mf):
            continue
        m = json.load(open(mf))
        if apply(d, m):
            m["version"] = bump(m.get("version"))
            json.dump(m, open(mf, "w"), indent=1, ensure_ascii=False)
            print(m.get("id", d), "version", m["version"])


if __name__ == "__main__":
    main(sys.argv[1:])
