"""Further takes of a golf mod's reactions (standard §6 `motions`: `re_gu.1`, `re_gu.2`, …; opentennis M130/M131).

A reaction has one clip of the character's own (the data module's `reactions`); the game draws its takes in turn, one
each time the reaction starts. `takes(game, pc)` picks them from the mod's extracted clips when it is packaged and
keeps the result in out/rerig/takes.json (built from the user's disc, never committed).

    python3 tools/rerig/takes.py   # re-pick every mod, prints what was left out and why

Per game, each reaction has a list of candidate clips by name (RULES: the emotes, hole results and results-screen
poses whose name says the mood: guts/glad/wave/clap for the won point and game, angry/sulk/stomp/bogey/loss for
the lost); the reaction's own clip (the data module's `reactions`) is left out. A candidate is kept if
 - it starts facing the way the character's clips mostly do (pelvis yaw within 45 degrees of the median start of
   all its candidates: some characters stand a little turned in every pose) and ends within 60 (spins that end
   with the back to the camera are left out), and
 - its face channels agree with the mood when it has a face to speak of (Out of Bounds, some Fore!): smile/laugh
   at least as strong as anger/sorrow/vexing/sad for a won reaction, weaker for a lost one.
Fore!'s `up_NN` (the character rises out of the frame) and Open Tee 2's `ku_sh` (hands to the head, read as dismay
there) aren't candidates. Nor is a held pose (no joint turns STILL degrees) or a clip that carries the body out of the
shot (the pelvis rises or sinks more than LEAVES pelvis heights: starts or ends off-screen, flies up, drops through).
"""
import glob
import json
import os
import re
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
import motions  # noqa: E402
import oob_data  # noqa: E402
import fore_data  # noqa: E402
import opentee_data  # noqa: E402

RULES = {
    "oob": {"re_gu": ["ku{n}_gl", "ku{n}_ha", "ku{n}_cl", "ku{n}_sh"], "re_di": ["ku{n}_an", "ku{n}_su"],
            "re_gu_set": ["ga_pc{n}_bi_r01", "ga_pc{n}_ea_r00", "ga_pc{n}_pa_r00", "rslt_win_pc{n}", "rslt_vict_pc{n}",
                          "rslt_get_pc{n}"],
            "re_di_set": ["rslt_loss_pc{n}", "rslt_loss_pc{n}_2"]},
    "fore": {"re_gu": ["re_pc{n}_tp", "re_pc{n}_lp"], "re_di": ["re_pc{n}_ga", "re_pc{n}_os", "re_pc{n}_bw"],
             "re_gu_set": ["ga_pc{n}_bi_r00", "ga_pc{n}_bi_r01", "ga_pc{n}_ea_r00", "ga_pc{n}_pa_r00", "clap_{n}"],
             "re_di_set": ["ga_pc{n}_bo_r00"]},
    "opentee2": {"re_gu": ["ku{n}_ha", "ku{n}_cl"], "re_di": ["ku{n}_an", "re_pc{n}_da", "re_pc{n}_os"],
                 "re_gu_set": ["ga_pc{n}_bi_r00", "ga_pc{n}_bi_r01", "ga_pc{n}_ea_r00", "ga_pc{n}_pa_r00"],
                 "re_di_set": ["ga_pc{n}_bo_r00"]},
}
STILL = 30  # degrees: a clip whose joints all turn less than this is a held pose, not an emote
LEAVES = 1.0  # pelvis heights: further than the floor (a sit or slump stays under it) is leaving the shot, up or down
HAPPY = ("smile", "laugh", "joy")
SAD = ("anger", "sorrow", "vexing", "muka", "sad", "bu", "scowl", "cry")
GLBS = {"oob": "out/anims/oob/pc??_*.glb", "fore": "out/anims/fore/pc??_*_c00-03.glb",
        "opentee2": "out/anims/opentee2/pc??_*.glb"}


def clips(f, wanted):
    """{clip: (start yaw, end yaw, happy, sad, moves, leaves)} of the clips named in `wanted`: pelvis yaw from the bind
    pose in degrees, mean face-channel weights by mood, the most any joint turns from its first-frame rotation in
    degrees, and the most the pelvis rises or sinks from its first-frame height, in pelvis heights."""
    g, b = glb.read(f)
    targets = {m["name"]: (m.get("extras") or {}).get("targetNames") or [] for m in g.get("meshes", [])}
    mesh_of = {i: g["meshes"][n["mesh"]]["name"] for i, n in enumerate(g["nodes"]) if "mesh" in n}
    hip = {motions.norm(n.get("name", "")): i for i, n in enumerate(g["nodes"])}["Bip01Pelvis"]
    unit = lambda m: m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0)  # noqa: E731
    w0 = motions.source_worlds(g, b, None, 0.0)
    bind, tall = unit(w0[hip]), abs(w0[hip][1, 3]) or 1.0

    def yaw(a, t):
        d = unit(motions.source_worlds(g, b, a, t)[hip]) @ bind.T
        return float(np.degrees(np.arctan2(d[0, 2], d[2, 2])))
    out = {}
    for a in g["animations"]:
        if a["name"] not in wanted:
            continue
        h = s = 0.0
        for c in a["channels"]:
            tn = targets.get(mesh_of.get(c["target"]["node"]), []) if c["target"]["path"] == "weights" else []
            if tn:
                v = glb.get_accessor(g, b, a["samplers"][c["sampler"]]["output"]).reshape(-1)
                v = v[: len(v) // len(tn) * len(tn)].reshape(-1, len(tn)).mean(0)
                h += float(sum(x for t, x in zip(tn, v) if t.lower().startswith(HAPPY)))
                s += float(sum(x for t, x in zip(tn, v) if t.lower().startswith(SAD)))
        n = motions.length(g, b, a)
        ws = [motions.source_worlds(g, b, a, t) for t in np.linspace(0.0, n, 24)]
        js = [j for j in ws[0] if j in ws[-1]]
        turn = max(np.degrees(np.arccos(np.clip((np.trace(unit(w[j]) @ unit(ws[0][j]).T) - 1) / 2, -1, 1)))
                   for w in ws for j in js)
        rise = max(abs(w[hip][1, 3] - ws[0][hip][1, 3]) for w in ws) / tall
        out[a["name"]] = (yaw(a, 0.0), yaw(a, n), h, s, float(turn), float(rise))
    return out


def pick(game, pc, f):
    """({hst reaction: [take, …]}, [why a candidate was left out])."""
    n = f"{pc:02d}"
    own = {"oob": lambda: oob_data.reactions(pc), "fore": lambda: fore_data.reactions(pc),
           "opentee2": lambda: opentee_data.reactions(game, pc)}[game]()[1]
    cand = {slot: [t.format(n=n) for t in tpl] for slot, tpl in RULES[game].items()}
    st = clips(f, {c for cs in cand.values() for c in cs})
    if not st:
        return {}, []
    ref = statistics.median(v[0] for v in st.values())
    off = lambda y: abs((y - ref + 180) % 360 - 180)  # noqa: E731
    takes, left = {}, []
    for slot, cs in cand.items():
        won = slot in ("re_gu", "re_gu_set")
        for c in cs:
            if c not in st or c in own.get(slot, []):
                continue
            y0, y1, h, s, turn, rise = st[c]
            why = (f"starts turned {off(y0):.0f}" if off(y0) > 45 else f"ends turned {off(y1):.0f}" if off(y1) > 60
                   else f"barely moves ({turn:.0f})" if turn < STILL
                   else f"leaves the shot ({rise:.1f} pelvis heights)" if rise > LEAVES
                   else f"face {h:.2f} happy / {s:.2f} sad" if h + s >= 0.3 and (h >= s) != won else None)
            if why:
                left.append(f"{game} pc{n} {slot} {c}: {why}")
            else:
                takes.setdefault(slot, []).append(c)
    return takes, left


CACHE = os.path.join(ROOT, "out/rerig/takes.json")


def takes(game, pc, fresh=False):
    """{hst reaction: [source clip, …]} of mod (game, pc), else {}; picked once, then read from CACHE."""
    c = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    k = f"{game}/{pc:02d}"
    if fresh or k not in c:
        f = sorted(glob.glob(os.path.join(ROOT, GLBS[game].replace("pc??", f"pc{pc:02d}")))) if game in GLBS else []
        t, left = pick(game, pc, f[0]) if f else ({}, [])
        c[k] = t
        print("\n".join("takes: left out " + x for x in left), file=sys.stderr)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(c, open(CACHE, "w"), indent=1, sort_keys=True)
    return c[k]


if __name__ == "__main__":
    for game, pat in GLBS.items():
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            takes(game, int(os.path.basename(f)[2:4]), fresh=True)
