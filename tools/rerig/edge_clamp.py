"""Clamp the textures a model samples right at their edge, in place (opentennis B584).

python3 tools/rerig/edge_clamp.py MOD_DIR…     (each mod's costumes or umpire.glb; bumps mod.json `version` if any changed)

The source games' samplers repeat (Fore!'s wrap flags, psp2gltf's and oob2gltf's one sampler), and many models lay
a mirrored half (a face, a shirt) with its middle on the texture's edge: u = 0 down the centre of Emma's face. A
repeating linear sample there takes half its colour from the texture's other side, which HST draws as a dark or
see-through seam down the middle. Where every UV that samples a texture stays inside [0, 1] on an axis, clamping that
axis draws the same everywhere except at that edge, so this sets it to CLAMP_TO_EDGE (a new sampler for the texture,
the rest of it kept) when some vertex comes within EDGE texels of the edge (mip levels widen the band). Textures on
parts the donor's eye track scrolls (skinned to an eye joint, or a mod.json `eyes` material) keep repeating.

package.py runs it on every costume it packages. By hand for mods already packaged: bump happens here, upload after.
"""
import io
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rerig import glb, read  # noqa: E402

REPEAT, CLAMP = 10497, 33071
# texels from the edge where a clamped sample can differ from a repeated one: half a texel at full size, 2^k times
# that at mip level k; 4 covers the levels a character is drawn at
EDGE = 4.0
# the slack an exported UV may sit outside [0, 1] and still count as on the edge
SLACK = 1e-4


def eye_joint(name):
    """Whether a joint name is an eye node a donor's `.UVA` track could scroll (`eye`, `L_eye`, `ANR#eye01`, `me`)."""
    last = re.split(r"[|#:]", name)[-1].lower()
    return "eye" in last or last in ("me", "s_me")


def image_size(g, b, i):
    v = g["bufferViews"][g["images"][i]["bufferView"]]
    o = v.get("byteOffset", 0)
    return Image.open(io.BytesIO(b[o:o + v["byteLength"]])).size


def clamp(path, eyes=()):
    """-> [(material, axis)] whose texture now clamps (path rewritten only if any)."""
    g, b = glb.read(path)
    joints = {}  # skin index -> joint names
    for k, s in enumerate(g.get("skins", [])):
        joints[k] = [g["nodes"][j].get("name", "") for j in s["joints"]]
    parent = {c: k for k, n in enumerate(g.get("nodes", [])) for c in n.get("children", [])}

    def rides_eye(k):  # a mesh without a skin rides the nearest joint at or above its node
        while k is not None:
            if eye_joint(g["nodes"][k].get("name", "")):
                return True
            k = parent.get(k)
        return False

    uses = {}  # texture -> [(uv array, eye part)]
    for ni, node in enumerate(g.get("nodes", [])):
        if "mesh" not in node:
            continue
        names = joints.get(node.get("skin"), [])
        for pr in g["meshes"][node["mesh"]]["primitives"]:
            mat = g["materials"][pr["material"]] if "material" in pr else {}
            t = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture")
            if t is None:
                continue
            a = pr["attributes"]
            if t.get("texCoord", 0) != 0 or "TEXCOORD_0" not in a:
                uses.setdefault(t["index"], []).append((None, True))  # not ours to judge
                continue
            eye = mat.get("name") in eyes or ("skin" not in node and rides_eye(ni))
            if names and "JOINTS_0" in a and "WEIGHTS_0" in a:
                jn, wt = read(g, b, a["JOINTS_0"]), read(g, b, a["WEIGHTS_0"])
                moved = np.unique(jn[wt > 0]).astype(int)
                eye = eye or any(eye_joint(names[j]) for j in moved if j < len(names))
            uses.setdefault(t["index"], []).append((read(g, b, a["TEXCOORD_0"]).astype(np.float64), eye))
    changed = []
    samplers = g.setdefault("samplers", [])
    for ti, us in sorted(uses.items()):
        if any(uv is None or eye for uv, eye in us):
            continue
        tex = g["textures"][ti]
        if "source" not in tex:
            continue
        size = image_size(g, b, tex["source"])
        old = samplers[tex["sampler"]] if "sampler" in tex else {}
        new = dict(old)
        for ax, key in ((0, "wrapS"), (1, "wrapT")):
            if new.get(key, REPEAT) != REPEAT:
                continue
            uv = np.concatenate([u[:, ax] for u, _ in us])
            if uv.size == 0 or uv.min() < -SLACK or uv.max() > 1 + SLACK:
                continue
            band = EDGE / size[ax]
            if uv.min() < band or uv.max() > 1 - band:
                new[key] = CLAMP
                changed += [(m.get("name"), "uv"[ax]) for m in g["materials"]
                            if m.get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index") == ti]
        if new != old:
            new.setdefault("magFilter", old.get("magFilter", 9729))
            tex["sampler"] = next((k for k, s in enumerate(samplers) if s == new), None)
            if tex["sampler"] is None:
                samplers.append(new)
                tex["sampler"] = len(samplers) - 1
    if changed:
        js = json.dumps(g, separators=(",", ":")).encode()
        js += b" " * (-len(js) % 4)
        b = bytes(b) + b"\0" * (-len(b) % 4)
        out = bytearray(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(b)))
        out += struct.pack("<I", len(js)) + b"JSON" + js
        out += struct.pack("<I", len(b)) + b"BIN\0" + b
        open(path + ".tmp", "wb").write(out)
        os.replace(path + ".tmp", path)  # a new file: a hard link package.py made into out/rerig stays as it was
    return changed


def bump(v):
    """'2' -> '3', 4 -> 5, None -> '2' (the type kept)."""
    if isinstance(v, int):
        return v + 1
    parts = str(v or "1").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def main(dirs):
    for d in dirs:
        mf = os.path.join(d, "mod.json")
        if not os.path.exists(mf):
            continue
        m = json.load(open(mf))
        hit = {}
        models = m.get("costumes", []) + (["umpire.glb"] if os.path.exists(os.path.join(d, "umpire.glb")) else [])
        for c in models:
            ch = clamp(os.path.join(d, c), m.get("eyes", []))
            if ch:
                hit[c] = ch
        if hit:
            m["version"] = bump(m.get("version"))
            json.dump(m, open(mf, "w"), indent=1, ensure_ascii=False)
        print(m.get("id", d), f"{sum(map(len, hit.values()))} clamped in {len(hit)} costumes, version {m['version']}" if hit else "-")


if __name__ == "__main__":
    main(sys.argv[1:])
