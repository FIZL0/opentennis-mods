"""Clap clips and their sound (opentennis B586), in place.

python3 tools/rerig/claps.py MOD_DIR…     (golf mods already packaged; bumps mod.json `version` if any changed)

A take whose source clip is one of its game's claps (by the source's own clip name, CLAP) is marked
`extras: {"racket": false, "clap": true}` in motions.glb (standard §6 Claps): HST stows the racket while it plays and
plays the mod's clap sound, `voice/11_0.wav` (standard §5, program 11), as it starts. The sound is the source game's
own clap SE (SOUND, its extracted bank under out/audio). A mod with no clap clip gets no program 11.

package.py runs it on every golf mod it packages (after the voices, which clear voice/). By hand for mods already
packaged: bump happens here, upload after.
"""
import json
import os
import re
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rerig import glb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
PROGRAM = 11
# the source games' clap clips: the putt-gallery reactions `ku<pc>_cl` (Out of Bounds, Open Tee 2), the result
# screen's `rslt_clap_pc<pc>` (Out of Bounds), Fore!'s `clap_<pc>`
CLAP = re.compile(r"ku\d+_cl|rslt_clap_pc\d+|clap_\d+")
# each game's clap SE in its extracted sound banks (notes/audio.md Claps)
SOUND = {
    "oob": "out/audio/oob/PS3_GAME/USRDIR/xbdata/nakazawa/lobby01_sound.xb/data/sound/se/abata.sgd/004.wav",
    "opentee2": "out/audio/opentee2/PSP_GAME/USRDIR/xbdata/cmn/cmn1.xb1/data/sound/plse.sgd/042.wav",
    "fore": "out/audio/fore/GE/GE.XB/data/sound/se/plse.hd/024.wav",
}


def sources(why):
    """The source clips a `motions_why` line names: 'reason; a then b, root held …' -> [a, b]."""
    return why.split("; ", 1)[-1].split(",")[0].split(" then ")


def apply(mod, game, manifest):
    """Mark `mod`'s clap takes and give it the clap sound (manifest updated, not written). -> whether anything changed."""
    claps = {k for k, why in manifest.get("motions_why", {}).items() if any(CLAP.fullmatch(s) for s in sources(why))}
    changed = False
    path = os.path.join(mod, "motions.glb")
    if claps and os.path.exists(path):
        g, b = glb.read(path)
        for a in g.get("animations", []):
            if a.get("name") in claps and a.get("extras") != {"racket": False, "clap": True}:
                a["extras"] = {"racket": False, "clap": True}
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
    wav = os.path.join(mod, f"voice/{PROGRAM}_0.wav")
    src = os.path.join(ROOT, SOUND.get(game, "-"))
    counts, whys = manifest.setdefault("voice_counts", {}), manifest.setdefault("voice_why", {})
    if claps and os.path.exists(src):
        if not os.path.exists(wav) or open(wav, "rb").read() != open(src, "rb").read():
            os.makedirs(os.path.dirname(wav), exist_ok=True)
            shutil.copy2(src, wav)
            changed = True
        why = f"clap sound for {', '.join(sorted(claps))}: {SOUND[game].split('/', 2)[2]}"
        if counts.get(str(PROGRAM)) != 1 or whys.get(str(PROGRAM)) != why:
            counts[str(PROGRAM)], whys[str(PROGRAM)] = 1, why
            changed = True
    elif os.path.exists(wav) or str(PROGRAM) in counts:
        if os.path.exists(wav):
            os.remove(wav)
        counts.pop(str(PROGRAM), None)
        whys.pop(str(PROGRAM), None)
        changed = True
    return changed


def main(dirs):
    from edge_clamp import bump
    for d in dirs:
        mf = os.path.join(d, "mod.json")
        if not os.path.exists(mf):
            continue
        m = json.load(open(mf))
        game = os.path.basename(os.path.normpath(d)).split("_")[0]
        if apply(d, game, m):
            m["version"] = bump(m.get("version"))
            json.dump(m, open(mf, "w"), indent=1, ensure_ascii=False)
            print(m.get("id", d), "claps, version", m["version"])


if __name__ == "__main__":
    main(sys.argv[1:])
