"""Picks the golf mods' reaction takes (takes.py TAKES; opentennis M131) and prints them as TAKES entries.

    python3 tools/rerig/takes_pick.py > /tmp/takes.txt   # then paste over takes.py's generated block

Per game, each reaction has a list of candidate clips by name (RULES: the emotes, hole results and results-screen
poses whose name says the mood: guts/glad/wave/clap for the won point and game, angry/sulk/stomp/bogey/loss for
the lost); the reaction's own clip (the data module's `reactions`) is left out. A candidate is kept if
 - it starts facing the way the character's clips mostly do (pelvis yaw within 45 degrees of the median start of
   all its candidates: some characters stand a little turned in every pose) and ends within 60 (spins that end
   with the back to the camera are left out), and
 - its face channels agree with the mood when it has a face to speak of (Out of Bounds, some Fore!): smile/laugh
   at least as strong as anger/sorrow/vexing/sad for a won reaction, weaker for a lost one.
Fore!'s `up_NN` (the character rises out of the frame) and Open Tee 2's `ku_sh` (hands to the head, read as dismay
there) aren't candidates. Out of Bounds Sophie (pc02) is takes.py's hand-picked entry; the rules give the same.
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
HAPPY = ("smile", "laugh", "joy")
SAD = ("anger", "sorrow", "vexing", "muka", "sad", "bu", "scowl", "cry")
GLBS = {"oob": "out/anims/oob/pc??_*.glb", "fore": "out/anims/fore/pc??_*_c00-03.glb",
        "opentee2": "out/anims/opentee2/pc??_*.glb"}


def clips(f, wanted):
    """{clip: (start yaw, end yaw, happy, sad)} of the clips named in `wanted`: pelvis yaw from the bind pose in
    degrees, mean face-channel weights by mood."""
    g, b = glb.read(f)
    targets = {m["name"]: (m.get("extras") or {}).get("targetNames") or [] for m in g.get("meshes", [])}
    mesh_of = {i: g["meshes"][n["mesh"]]["name"] for i, n in enumerate(g["nodes"]) if "mesh" in n}
    hip = {motions.norm(n.get("name", "")): i for i, n in enumerate(g["nodes"])}["Bip01Pelvis"]
    unit = lambda m: m[:3, :3] / np.linalg.norm(m[:3, :3], axis=0)  # noqa: E731
    bind = unit(motions.source_worlds(g, b, None, 0.0)[hip])

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
        out[a["name"]] = (yaw(a, 0.0), yaw(a, motions.length(g, b, a)), h, s)
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
            y0, y1, h, s = st[c]
            why = (f"starts turned {off(y0):.0f}" if off(y0) > 45 else f"ends turned {off(y1):.0f}" if off(y1) > 60
                   else f"face {h:.2f} happy / {s:.2f} sad" if h + s >= 0.3 and (h >= s) != won else None)
            if why:
                left.append(f"{game} pc{n} {slot} {c}: {why}")
            else:
                takes.setdefault(slot, []).append(c)
    return takes, left


if __name__ == "__main__":
    lines, left = [], []
    for game, pat in GLBS.items():
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            pc = int(os.path.basename(f)[2:4])
            if (game, pc) == ("oob", 2):
                continue
            t, lo = pick(game, pc, f)
            left += lo
            if t:
                lines.append(f"    ({game!r}, {pc}): {json.dumps(t)},  # {os.path.basename(f).split('.')[0]}")
    print("\n".join(lines))
    print("\n".join("# left out: " + x for x in left), file=sys.stderr)
