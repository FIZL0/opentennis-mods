"""Sizing a source game's characters to HST's cast (standard §2 "Size").

Height: HST's own metres per centimetre, by sex — the median over HST's standard-body characters (TParam モデル
標準: model types 0, 4, 5) of Bip01 rest height / TParam 身長 — times each source character's height in cm from its
game's data (or the model's own Bip01 height where the data has none), then one factor for the whole game, calibrated
on Gloria, who is on HST's disc too: the factor that gives the game's Gloria HST's Gloria's Bip01 height. Open Tee
has no Gloria but is Open Tee 2's first ten at the same sizes, so it takes their sizes; Fore! shares no one with HST
or the other games (its Brad is not Get a Grip's) and keeps its own model scale (factor 1: the same engine and units
as HST's MDLs). One factor per game keeps the source's relative heights; per-sex metres-per-cm keeps HST's women/men
proportions.
Out of Bounds measures that height head to foot instead (top of the mesh, with HST's metres per cm of top height and
Gloria's top for the factor; each character's Bip01 then follows from its own proportions and head factor): its
cartoon bodies (Suzuki, Fernando, Felipe, Bloom, Maruyama, Nick) have short legs under big heads, so a Bip01 sized
from the cm stood them a head taller than the stock roster (user 2026-10-24). Its Suzuki is HST's Suzuki too, so he
takes HST's Suzuki's top height, as Gloria sets the factor.
Head: chibi games (Get a Grip, Open Tee 2) shrink each character's head about the neck by its own factor: the game's
head share of the way from 1 to the factor that would bring that character's head ratio (neck joint to the top of the
head mesh, over Bip01 height; the smallest over its costumes, so a hat doesn't count) to the median of HST's standard
bodies; never grown. The share is the one that makes the game's Gloria as tall head to foot as HST's Gloria, else
HEAD_SHARE.
"""
import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import G, binds, norm, read, worlds  # noqa: E402

STANDARD_BODY = (0, 4, 5)  # TParam モデルタイプ of 標準 bodies (1 JJ chibi, 2 power, 3 reach, 6 Suzuki)
# each head factor goes this far from 1 toward the full match of HST's median head ratio: the full match looked a
# little small-headed on Get a Grip's bodies (user, 2026-10-08), so half of it
HEAD_SHARE = 0.5
# each game's Gloria (pc number), the one character on HST's disc too: her Bip01 sets the game's factor (user 2026-10-12)
GLORIA = {"getagrip": 13, "oob": 16, "opentee2": 20}
# games whose whole cast shares one skeleton: everyone takes Gloria's head factor, since the per-character one
# measures hair too (Taiga's spiky hair got him 0.50 against Brad's 0.62, the smallest head on screen; user 2026-10-12)
ONE_HEAD = {"getagrip"}
# games sized head to foot (top of the mesh) rather than by Bip01 (opentennis B663)
TOP_SIZED = {"oob"}
# characters on HST's disc too, besides Gloria, who take their HST twin's top height outright: {game: {pc: HST name}}
TWINS = {"oob": {13: "Suzuki"}}


def head_ratio(path):
    """(top of the head mesh - Bip01Neck height) / Bip01 height of a game-space model (HST export or rerig output)."""
    g, b = glb.read(path)
    W, parent = worlds(g)
    B, _ = binds(g, b)
    nodes = g["nodes"]

    def in_head(i):
        while True:
            if norm(nodes[i].get("name", "")) == "Bip01Head":
                return True
            if i not in parent:
                return False
            i = parent[i]

    top = -np.inf
    for i, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        for p in g["meshes"][n["mesh"]]["primitives"]:
            pos = read(g, b, p["attributes"]["POSITION"])
            if "skin" in n:  # skinned positions are game space
                hj = np.array([in_head(j) for j in g["skins"][n["skin"]]["joints"]])
                w = (read(g, b, p["attributes"]["WEIGHTS_0"]) * hj[read(g, b, p["attributes"]["JOINTS_0"]).astype(np.int64)]).sum(1)
                v = pos[w > 0.5]
            elif in_head(i):
                v = (G @ W[i] @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]
            else:
                continue
            if len(v):
                top = max(top, float(-v[:, 1].min()))
    return (top + B["Bip01Neck"][1, 3]) / -B["Bip01"][1, 3]


def heights(path):
    """(Bip01, Bip01Neck, top of all meshes) rest heights in m of a game-space model (HST export or rerig output)."""
    g, b = glb.read(path)
    W, _ = worlds(g)
    B, _ = binds(g, b)
    top = -np.inf
    for i, n in enumerate(g["nodes"]):
        if "mesh" not in n:
            continue
        for p in g["meshes"][n["mesh"]]["primitives"]:
            pos = read(g, b, p["attributes"]["POSITION"])
            v = pos if "skin" in n else (G @ W[i] @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]
            top = max(top, float(-v[:, 1].min()))
    neck = B.get("Bip01Neck", B["Bip01Head"])  # Fore's Ratchet has no neck
    return -B["Bip01"][1, 3], -neck[1, 3], top


def hst(key="bip01_height"):
    """HST's metres per cm by sex ('f'/'m') and target head ratio, from standard/hst_skeleton.json; `key` "top_height"
    gives metres of head-to-foot height per cm instead of Bip01."""
    cs = [c for c in json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"] if c["model_type"] in STANDARD_BODY]
    k = {s: float(np.median([c[key] / c["height_cm"] for c in cs if c["sex"] == s])) for s in "fm"}
    return k, float(np.median([c["head_ratio"] for c in cs]))


def getagrip():
    """slug -> (sex, height cm, source) for Get a Grip: height class from chrsel_param_chara.csv (the number after the
    name, = character.csv Height / 1.15), sex from Parts_Body.txt PC_SEX of the character's own Body_3NN (0 f, 1 m)."""
    base = os.path.join(ROOT, "out/files/getagrip/PSP_GAME/USRDIR/xbdata")
    sel = glob.glob(base + "/menu/**/chrsel_param_chara.csv", recursive=True)[0]
    rows = [r for r in csv.reader(open(sel, encoding="cp932")) if r and r[0][-3:].isdigit()]
    body = list(csv.reader(open(glob.glob(base + "/common/**/Parts_Body.txt", recursive=True)[0], encoding="utf-8-sig"), delimiter="\t"))
    h = body[0]
    sex = {int(r[h.index("PC_ONLY_1")]): "fm"[int(r[h.index("PC_SEX")])] for r in body[1:] if r[0].startswith("Body_3")}
    out = {}
    for n, r in enumerate(rows):
        out[n] = (sex[n], int(r[0][-3:]), f"chrsel_param_chara.csv height class {r[0][-3:]}, Parts_Body Body_3{n:02d} PC_SEX")
    return out


def source(game):
    """slug -> (sex, height cm or None, source) from the game's own data (its data module), or None."""
    if game == "getagrip":
        return getagrip()
    try:
        if game == "fore":
            import fore_data
            return fore_data.heights()
        if game == "oob":
            import oob_data
            return oob_data.heights()
        if game in ("opentee", "opentee2"):
            import opentee_data
            return opentee_data.heights(game)
    except (ImportError, OSError, IndexError) as e:
        print(game, "no height data:", e)
    return None


def model_height(path):
    g, b = glb.read(path)
    return -binds(g, b)[0]["Bip01"][1, 3]


def plan(game, models):
    """game, {pc number: [plain-rerigged model paths]} -> ({pc: (height m, why)}, {pc: (head factor, why)}, info)
    or None. A character whose game gives no height in cm keeps its own (plain rerig) Bip01 height (× the game's
    body scale where it has one); one game factor puts the tallest at TOP (only ever shrinking when heights are cm)."""
    src = source(game)
    if not src:
        return None
    top = game in TOP_SIZED
    key, what = ("top_height", "top") if top else ("bip01_height", "Bip01")
    k, want = hst(key)
    cast = json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"]
    raw, how = {}, {}
    for n in models:
        sex, cm, why, *sc = src.get(n, (None, None, "not in the game's tables"))
        if cm and sex in k:
            raw[n] = k[sex] * cm
            how[n] = f"{why}: {cm:g} cm {'woman' if sex == 'f' else 'man'} × HST {k[sex]:.6f} m/cm of {what} height"
        else:
            raw[n] = min(heights(p)[2] if top else model_height(p) for p in models[n])
            how[n] = f"{why}; no height in cm in the data: the model's own {what} height {raw[n]:.4f} m"
            if sc:  # the game's own body scale of a shared skeleton (Open Tee face.csv `scale`)
                raw[n] *= sc[0]
                how[n] += f" × the game's scale {sc[0]:g}"
    # one factor per game, calibrated on a character HST's disc also has (Gloria)
    share, why_c = HEAD_SHARE, "no character shared with HST's disc: the game's own model scale"
    c = 1.0
    if game in GLORIA:
        n = GLORIA[game]
        disc = next(x for x in cast if x["name"] == "Gloria")
        c = disc[key] / raw[n]
        why_c = f"pc{n:02d} Gloria's {what} to HST's Gloria {disc[key]:g} m"
        # chibi heads: the share that also brings her head-to-foot to HST's Gloria's
        B, N, T = min((heights(p) for p in models[n]), key=lambda h: h[2] / h[0])
        f = (disc["top_height"] * B / disc["bip01_height"] - N) / (T - N)
        r = min(head_ratio(p) for p in models[n])
        if not top and f < 1 and r > want:
            share = (1 - f) / (1 - want / r)
            why_c += f", head share {share:.3f} so her top is HST's Gloria's {disc['top_height']:g} m"
    sizes = {n: (raw[n] * c, f"{how[n]} × game factor {c:.4f} ({why_c})") for n in models}
    heads = {}
    for n in models:
        r = min(head_ratio(p) for p in models[n])
        f = min(1.0, 1 - share * (1 - want / r))
        why = f"head ratio {r:.3f}, {share:.3f} of the way to HST's {want:.3f}"
        heads[n] = (f, why)
    if game in ONE_HEAD:
        n = GLORIA[game]
        heads = {m: (heads[n][0], f"one skeleton for the cast: pc{n:02d} Gloria's factor ({heads[n][1]})") for m in models}
    for n, name in TWINS.get(game, {}).items():
        if n in models:
            t = next(x for x in cast if x["name"] == name)[key]
            sizes[n] = (t, f"HST's {name} too: HST's {name}'s {what} height {t:g} m")
    if top:  # head to foot -> Bip01: the costume without a hat (smallest top / Bip01), its head shrunk about the neck
        for n in models:
            B, N, T = min((heights(p) for p in models[n]), key=lambda h: h[2] / h[0])
            h = sizes[n][0] * B / (N + heads[n][0] * (T - N))
            sizes[n] = (h, f"{sizes[n][1]}; top {sizes[n][0]:.4f} m -> Bip01 {h:.4f} m by its own proportions and head factor")
    return sizes, heads, {"hst_m_per_cm": k, "game_factor": c, "game_factor_why": why_c, "head_ratio_hst": want, "head_share": share}
