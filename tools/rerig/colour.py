"""A model's main colour, for matching a mod's racket to its outfit (package.py pick_racket).

python3 tools/rerig/colour.py RACKET.glb...   prints each racket's main frame colour

A model's surface is sampled: every triangle's texture colour at its UV centre (times the material's base colour and
any vertex colour), weighted by its area. A racket's colours are its frame's, an outfit's its clothes' (no hair, face
or skin), and a racket fits an outfit by the colour the two share.
"""
import io
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "../psp2gltf"))
import glb  # noqa: E402
from rerig import read, worlds  # noqa: E402


def samples(path, mesh_names=None, head=False, body=False):
    """(rgb N×3 in 0..1, weight N, centre N×3) over the model's triangles (only meshes named in `mesh_names`, when
    given; `head`: a racket's frame only, the rim of the wide half along its long axis: no handle, grip tape, strings; `body`: an outfit's
    clothes only: no rigid mesh on its head bone, no skinned triangle on its head, neck, forearms or hands, and
    no skin tone (bare arms and legs))."""
    g, b = glb.read(path)
    imgs = {}

    def image(ti):
        si = g["textures"][ti]["source"]
        if si not in imgs:
            v = g["bufferViews"][g["images"][si]["bufferView"]]
            o = v.get("byteOffset", 0)
            imgs[si] = np.asarray(Image.open(io.BytesIO(bytes(b[o:o + v["byteLength"]]))).convert("RGBA"), np.float32) / 255
        return imgs[si]

    W, _ = worlds(g)
    # a rigid mesh (no skin: a head on its bone) is in its node's space; a skinned one is already in place
    place = {n["mesh"]: W[i] for i, n in enumerate(g["nodes"]) if "mesh" in n and "skin" not in n}
    names = [n.get("name", "") for n in g["nodes"]]
    up = {c: i for i, n in enumerate(g["nodes"]) for c in n.get("children", [])}
    under_head = lambda i: i in up and ("Head" in names[up[i]] or under_head(up[i]))
    on_head = {n["mesh"] for i, n in enumerate(g["nodes"]) if "mesh" in n and "skin" not in n and under_head(i)}
    # per skinned mesh, which of its skin's joints carry no clothes
    bare = {n["mesh"]: np.array([any(k in names[x] for k in ("Head", "Neck", "Forearm", "Hand", "Finger")) for x in g["skins"][n["skin"]]["joints"]])
            for n in g["nodes"] if "mesh" in n and "skin" in n}
    rgb, w, at = [], [], []
    for mi, m in enumerate(g["meshes"]):
        if mesh_names is not None and m.get("name") not in mesh_names:
            continue
        for p in m["primitives"]:
            a = p["attributes"]
            v = read(g, b, a["POSITION"])[:, :3]
            if mi in place:
                v = v @ place[mi][:3, :3].T + place[mi][:3, 3]
            ix = read(g, b, p["indices"]).astype(int).reshape(-1, 3) if "indices" in p else np.arange(len(v)).reshape(-1, 3)
            area = np.linalg.norm(np.cross(v[ix[:, 1]] - v[ix[:, 0]], v[ix[:, 2]] - v[ix[:, 0]]), axis=1) / 2
            mat = g["materials"][p["material"]] if "material" in p else {}
            pbr = mat.get("pbrMetallicRoughness", {})
            c = np.tile(np.array(pbr.get("baseColorFactor", [1, 1, 1, 1]), np.float32), (len(ix), 1))
            if "baseColorTexture" in pbr and "TEXCOORD_0" in a:
                im = image(pbr["baseColorTexture"]["index"])
                uv = read(g, b, a["TEXCOORD_0"])[ix].mean(1) % 1.0
                h, wd = im.shape[:2]
                c = c * im[(uv[:, 1] * h).astype(int).clip(0, h - 1), (uv[:, 0] * wd).astype(int).clip(0, wd - 1)]
            if "COLOR_0" in a:
                vc = read(g, b, a["COLOR_0"])[ix].mean(1)
                c[:, :vc.shape[1]] *= vc
            # see-through (strings, cut-outs) is not the colour; texture alpha is coverage only on MASK / BLEND (§2)
            keep = c[:, 3] > mat.get("alphaCutoff", 0.5) if mat.get("alphaMode", "OPAQUE") != "OPAQUE" else np.ones(len(ix), bool)
            if body and "JOINTS_0" in a and mi in bare:
                # triangles mostly on the head, neck, forearms or hands: face, hair, bare skin
                j = read(g, b, a["JOINTS_0"]).astype(int)[np.arange(len(v)), read(g, b, a["WEIGHTS_0"]).argmax(1)]
                keep &= ~(bare[mi][j][ix].sum(1) >= 2)
            if body and mi in on_head:
                continue
            rgb.append(c[keep, :3])
            w.append(area[keep])
            at.append(v[ix].mean(1)[keep])
    rgb, w, at = np.vstack(rgb), np.concatenate(w), np.vstack(at)
    if head:
        c = at - at.mean(0)
        ax = np.linalg.svd(c, full_matrices=False)[2][0]
        t = c @ ax
        wide = lambda m: np.linalg.norm(c[m] - np.outer(t[m], ax), axis=1).mean()
        mid = (t.min() + t.max()) / 2
        m = t > mid if wide(t > mid) > wide(t <= mid) else t <= mid
        # the frame: the head's rim, not the strings and their emblem inside it
        h = at[m] - at[m].mean(0)
        uv = h @ np.linalg.svd(h, full_matrices=False)[2][:2].T
        r = np.linalg.norm(uv / np.abs(uv).max(0), axis=1)
        m[m] = r > 0.8
        rgb, w = rgb[m], w[m]
    if body:
        # bare arms and legs: skin tones (Lab lightness 35-90, a warm red-yellow of low to middling chroma)
        L = lab(rgb)
        m = ~((L[:, 0] > 35) & (L[:, 0] < 90) & (L[:, 1] > 4) & (L[:, 1] < 30) & (L[:, 2] > 8) & (L[:, 2] < 38) & (L[:, 2] > 0.7 * L[:, 1]))
        rgb, w = rgb[m], w[m]
    return rgb, w


def lab(rgb):
    """sRGB 0..1 -> CIE Lab (D65)."""
    c = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    f = lambda t: np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)
    x, y, z = (f(xyz / [0.9505, 1.0, 1.089]).T)
    return np.stack([116 * y - 16, 500 * (x - y), 200 * (y - z)], 1)


STEP = 18  # Lab histogram bin size (about a just-different colour step for clothes)


def hist(rgb, w):
    """Colour histogram {Lab bin: share}, weights summing to 1."""
    out = {}
    for k, x in zip(map(tuple, (lab(rgb) / STEP).round().astype(int)), w / w.sum()):
        out[k] = out.get(k, 0.0) + x
    return out


def match(outfit, racket):
    """How well a racket's frame (`hist`) goes with an outfit (`hist`): the colour they share (histogram
    intersection). White, grey and black count only for an outfit with no colour to speak of (under a tenth), and
    then only by how plain the frame is (squared): a black outfit takes a black racket over a black-and-yellow one."""
    if sum(x for k, x in outfit.items() if grey(k)) > 0.9:
        lit = lambda h: np.bincount([max(k[0], 0) for k in h], [x for x in h.values()], 8)  # lightness alone
        return float(np.minimum(lit(outfit), lit(racket)).sum()) * sum(x for k, x in racket.items() if grey(k)) ** 2
    return sum(min(x, racket[k]) for k, x in outfit.items() if k in racket and not grey(k))


def grey(k):
    return abs(k[1]) + abs(k[2]) <= 1


def srgb(L):
    """CIE Lab (D65) N×3 -> sRGB 0..1."""
    fy = (L[:, 0] + 16) / 116
    f = np.stack([fy + L[:, 1] / 500, fy, fy - L[:, 2] / 200], 1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * [0.9505, 1.0, 1.089]
    c = xyz @ np.linalg.inv(np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])).T
    return np.clip(np.where(c > 0.0031308, 1.055 * np.abs(c) ** (1 / 2.4) - 0.055, 12.92 * c), 0, 1)


def main(h):
    """A histogram's heaviest coloured bin as sRGB 0..1 (None if it has none)."""
    c = [(x, k) for k, x in h.items() if not grey(k)]
    return srgb(np.array([max(c)[1]], float) * STEP)[0] if c else None


def paint(h):
    """The colour to paint a racket for outfit histogram `h` (None if it has no clear one): the coloured bin with
    the most share × chroma, skipping browns and dull light tans (skin, hair and shoes read there; a brown racket looks wrong)
    and a colour under PAINT of the outfit."""
    c = [(x * np.hypot(k[1], k[2]), k) for k, x in h.items()
         if not grey(k) and not (0 < k[1] <= k[2] and np.hypot(k[1], k[2]) < 2.5 or 0 < k[1] < k[2] and k[0] * STEP < 55)]
    w, k = max(c, default=(0, None))
    return srgb(np.array([k], float) * STEP)[0] if w >= PAINT else None


PAINT = 0.08


def tint(png, rgb):
    """A racket texture (PNG bytes) with its coloured pixels (the frame's paint) turned to `rgb`: each takes the
    colour's hue and chroma, its lightness moved by as much as theirs is off the colour's, so the shading stays."""
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    a = np.asarray(im, np.float32) / 255
    L = lab(a[..., :3].reshape(-1, 3))
    c = np.hypot(L[:, 1], L[:, 2]) > 20
    t = lab(np.asarray([rgb], float))[0]
    if c.any():
        L[c, 0] += t[0] - L[c, 0].mean()
        L[c, 1:] = t[1:]
        a[..., :3] = srgb(L).reshape(a[..., :3].shape)
    out = io.BytesIO()
    Image.fromarray((a * 255).round().astype(np.uint8), "RGBA").save(out, "PNG")
    return out.getvalue()


def hexs(rgb):
    return "#%02x%02x%02x" % tuple((np.asarray(rgb) * 255).round().astype(int))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, hexs(main(hist(*samples(p, head=True)))))
