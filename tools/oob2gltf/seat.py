"""An Out of Bounds lobby seat as a mod's `seat.glb` (standard §6 `motions`, `extras.seat`): the piano bench the
lobby avatars sit on, or Kratos's throne from his lobby set, in the character's root space (metres, Y down, floor at
y = 0, facing +Z), scaled so its sitting surface meets the sitting character and placed under them.

    python3 tools/oob2gltf/seat.py OUT.glb bench|throne HIPS X Z   # the sitting hips: height, and where they are (metres)

Only the drawn mesh is exported: the models also carry their collision shells (materials whose own texture is a ground
attribute, metal/rock/fairway) as plain meshes over and around the drawn one.
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

# kind: (archive, model, height of its sitting surface (None: its top), depth of the spot the hips go (source units),
# the surface's height as a share of the hips' height). The throne's seat is 0.518 high, 0.9 deep (front edge at
# z = 0.2, backrest at -0.53 to -0.6 going up); Kratos's seated takes have the bottom of his buttocks at two thirds of
# his hip height and recline about 35 degrees, so the hips go near the front edge and his upper back meets the backrest.
SEATS = {"bench": ("nakazawa/lobby03.xb", "L03Pchair.rem", None, 0.0, 0.8),
         "throne": ("nakazawa/lobby0303.xb", "L99kratoschair.rem", 0.518, 0.04, 0.67)}


def colour_map(r, mi, files, attrs):
    """Material `mi`'s colour map (the first slot that isn't a specular, normal or ground-attribute map), as a loose
    .dds."""
    for s in r.materials[mi]["slots"]:
        if 0 <= s < len(r.texobjs):
            stem = os.path.splitext(r.textures[r.texobjs[s][1]])[0].lower()
            # named .bmp/.psd in the model, shipped as .dds
            if not stem.endswith(("_s", "_sp", "_n", "-nomal", "-normal", "_normal")) and stem not in attrs and stem + ".dds" in files:
                return files[stem + ".dds"]
    return None


def shell(r, mi, attrs):
    """Material `mi` belongs to a collision shell: its own (first) texture is a ground attribute."""
    t = r.materials[mi]["slots"][0]
    return 0 <= t < len(r.texobjs) and os.path.splitext(r.textures[r.texobjs[t][1]])[0].lower() in attrs


def export(out, kind, hips, x, z):
    lobby, model, hi, back, share = SEATS[kind]
    top = share * hips
    files = {p.name.lower(): p for p in sorted(Path(paths.XB, lobby).rglob("*")) if p.is_file()}
    # the collision attributes (rock, fairway, metal: what the ball does on it) also sit in the texture slots
    attrs = {p.stem.lower() for p in Path(paths.XB, lobby).rglob("attribute/*")}
    r = rem.Rem(files[model.lower()].read_bytes())
    ms = [m for m in static.meshes(r) if not shell(r, m["material"], attrs)]
    s = top / (hi or max(float(m["pos"][:, 1].max()) for m in ms))
    o = glb.Builder()
    mats, prims = {}, []
    for m in ms:
        mi = m["material"]
        if mi not in mats:
            mat = {"name": r.materials[mi]["name"], "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0},
                   "doubleSided": True}
            tex = colour_map(r, mi, files, attrs)
            if tex is not None:
                f = io.BytesIO()
                dds.load(tex.read_bytes()).convert("RGB").save(f, "PNG")
                mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": o.image(f.getvalue(), tex.stem)}
            mats[mi] = o.add("materials", mat)
        # source: Y up → root space: Y down, the sitting surface at -top, the hips' spot at (x, z)
        pos = (m["pos"] - [0.0, 0.0, back]) * np.array([s, -s, s], np.float32) + np.array([x, 0.0, z], np.float32)
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
    export(sys.argv[1], sys.argv[2], *map(float, sys.argv[3:6]))
