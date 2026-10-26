"""An Out of Bounds lobby seat as a mod's `seat.glb` (standard §6 `motions`, `extras.seat`): the piano bench the
lobby avatars sit on, in the character's root space (metres, Y down, floor at y = 0, facing +Z), scaled so its top
meets the sitting character and centred under them.

    python3 tools/oob2gltf/seat.py OUT.glb TOP X Z   # TOP: seat height in metres; X, Z: where it goes
"""
import io
import os
import sys
from pathlib import Path

import numpy as np

import dds
import glb
import paths
import rem
import static

LOBBY = os.path.join(paths.XB, "nakazawa/lobby03.xb")
MODEL = "L03Pchair.rem"  # ponytail: one seat for every character; a per-character pick goes in a table here


def colour_map(r, mi, files):
    """Material `mi`'s colour map (the first slot that isn't a specular or normal map), as a loose .dds."""
    for s in r.materials[mi]["slots"]:
        if 0 <= s < len(r.texobjs):
            stem = os.path.splitext(r.textures[r.texobjs[s][1]])[0].lower()
            # named .bmp/.psd in the model, shipped as .dds
            if not stem.endswith(("_s", "_sp", "_n", "-nomal", "-normal", "_normal")) and stem + ".dds" in files:
                return files[stem + ".dds"]
    return None


def export(out, top, x, z):
    files = {p.name.lower(): p for p in sorted(Path(LOBBY).rglob("*")) if p.is_file()}
    r = rem.Rem(files[MODEL.lower()].read_bytes())
    ms = static.meshes(r)
    hi = max(float(m["pos"][:, 1].max()) for m in ms)
    s = top / hi
    o = glb.Builder()
    mats, prims = {}, []
    for m in ms:
        mi = m["material"]
        if mi not in mats:
            mat = {"name": r.materials[mi]["name"], "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0},
                   "doubleSided": True}
            tex = colour_map(r, mi, files)
            if tex is not None:
                f = io.BytesIO()
                dds.load(tex.read_bytes()).convert("RGB").save(f, "PNG")
                mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": o.image(f.getvalue(), tex.stem)}
            mats[mi] = o.add("materials", mat)
        # source: Y up, metres → root space: Y down, the bench's top at -top
        pos = m["pos"] * np.array([s, -s, s], np.float32) + np.array([x, 0.0, z], np.float32)
        nrm = m["normal"] * np.array([1.0, -1.0, 1.0], np.float32)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-8)
        uv = m["uvs"][0][:, :2] if m["uvs"] else np.zeros((len(pos), 2), np.float32)
        # the y flip turns the winding: swap two corners to keep the faces outward
        tris = m["tris"][:, [0, 2, 1]]
        prims.append({"attributes": {"POSITION": o.accessor(pos.astype(np.float32), 34962, minmax=True),
                                     "NORMAL": o.accessor(nrm.astype(np.float32), 34962),
                                     "TEXCOORD_0": o.accessor(uv.astype(np.float32), 34962)},
                      "indices": o.accessor(tris.ravel().astype(np.uint32), 34963), "material": mats[mi]})
    mesh = o.add("meshes", {"name": "seat", "primitives": prims})
    o.g["scenes"][0]["nodes"].append(o.add("nodes", {"name": "seat", "mesh": mesh}))
    o.write(out)


if __name__ == "__main__":
    export(sys.argv[1], *map(float, sys.argv[2:5]))
