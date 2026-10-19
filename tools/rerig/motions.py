"""Retarget source motions onto a rerigged mod's skeleton as its own `motions.glb` (standard §6 `motions`).

python3 tools/rerig/motions.py COSTUME.glb SRC.glb OUT.glb HST_NAME=SRC_ANIM[+LOOP_ANIM][@FRAMES] …

Per joint the source's world rotation change from its bind pose is applied to the mod joint's world rest rotation
(both rigs share the bind pose: rerig.py places the mod's joints at the source's own), then turned back into a local
rotation under the mod's parent joint. Joints with no source (Spine2, the finger segments, the racket) keep their rest
local. The root (`Bip01`) follows the source pelvis's offset from its bind spot, scaled by the hips' height ratio; the
source's own locators (`ROOTNODE`, `pc_locator`) are left out, since the game moves the player itself. `@FRAMES` is the
donor clip's length at 60 Hz: the source plays at its own speed (60 Hz), the loop repeating to fill it; a longer
intro plays whole, past the donor's end (HST draws it on its own clock: mods.rs `own_motions`).
A trailing `!` (`re_gu=ga_pc00_bi_r00!@40`) pins the root's horizontal position at rest: golf celebrations that walk
off the spot stay where the player stands (only the height follows the pelvis).
A source clip's face (`weights` channels on its morph meshes) goes along, frame for frame with the body, on a
mesh-less `face` node whose `extras.targetNames` are the source's target names (the costume keeps them: rerig.py), so
HST plays the clip's own face instead of the donor's.
"""
import sys
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import node_mat, norm, quat_mat, mat_quat, read  # noqa: E402

FPS = 60.0
SKIP = {"ROOTNODE", "pc_locator"}


def parents(g):
    return {c: i for i, n in enumerate(g["nodes"]) for c in n.get("children", [])}


def sampler(g, b, anim):
    """node index -> {path: (times, values)} of one animation."""
    out = {}
    for c in anim["channels"]:
        s = anim["samplers"][c["sampler"]]
        t = read(g, b, s["input"]).ravel()
        v = read(g, b, s["output"]).reshape(len(t), -1)
        out.setdefault(c["target"]["node"], {})[c["target"]["path"]] = (t, v)
    return out


def at(tv, t):
    times, vals = tv
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    i = np.searchsorted(times, t) - 1
    u = (t - times[i]) / (times[i + 1] - times[i])
    a, b = vals[i], vals[i + 1]
    if len(a) == 4 and np.dot(a, b) < 0:
        b = -b
    v = a * (1 - u) + b * u
    return v / np.linalg.norm(v) if len(a) == 4 else v


def source_worlds(g, b, anim, t):
    """Node index -> world matrix (glTF world) of the source at time t, its locators held at rest."""
    ch = sampler(g, b, anim) if anim else {}
    par = parents(g)
    W = {}

    def world(i):
        if i not in W:
            n = dict(g["nodes"][i])
            if i in ch and norm(n.get("name", "")) not in SKIP:
                for path, tv in ch[i].items():
                    n[path] = list(at(tv, t))
            W[i] = (world(par[i]) if i in par else np.eye(4)) @ node_mat(n)
        return W[i]

    for i in range(len(g["nodes"])):
        world(i)
    return W


def unit(m):
    return m / np.linalg.norm(m, axis=0)


def length(g, b, anim):
    return max(float(read(g, b, s["input"]).max()) for s in anim["samplers"])


# body capsules (joint chain, radius m; "^" is the head's top) and points along the racket (Racket-joint +Y, butt to
# tip 0.944 m: standard §1) for `racket_inside`
BODY = [(("Bip01Pelvis", "Bip01Spine", "Bip01Spine1", "Bip01Spine2", "Bip01Neck"), 0.13),
        (("Bip01LThigh", "Bip01RThigh"), 0.12),
        (("Bip01LThigh", "Bip01LCalf"), 0.08), (("Bip01RThigh", "Bip01RCalf"), 0.08)]
HEAD = (("Bip01Head", "^"), 0.17)  # with the hair: one point in it is enough (a racket across the head crosses it fast)
RACKET = np.linspace(0.12, 0.92, 17)
HIDE_FRAMES = 0.12  # share of a clip's frames with the racket through the body that hides it for the whole clip


def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-9), 0.0, 1.0)
    return np.linalg.norm(p - (a + t * ab))


def racket_inside(world, named):
    """Whether a point along the racket is inside the head (with its hair), or three (~15 cm) inside the body, this
    frame (a held racket goes through them in moves made without one: claps, hugs, hands on hips or hair)."""
    r = named.get("Racket")
    if r is None or "Bip01Head" not in named:
        return False
    head = world(named["Bip01Head"])
    top = head[:3, 3] + 0.2 * np.array([0.0, 1.0, 0.0])  # ponytail: straight up, not along the head's own axis
    at = lambda n: top if n == "^" else world(named[n])[:3, 3]
    pts = [(world(r) @ np.array([0.0, y, 0.0, 1.0]))[:3] for y in RACKET]
    inside = lambda caps: sum(any(seg_dist(p, c[i], c[i + 1]) < rad for c, rad in caps for i in range(len(c) - 1)) for p in pts)
    body = [([at(n) for n in chain if n in named], rad) for chain, rad in BODY]
    return inside(body) >= 3 or inside([([at(n) for n in HEAD[0]], HEAD[1])]) >= 1


def make(costume, src, out, clips):
    """clips: [(hst_name, [source anims: intro, then an optional loop], frames or None[, pin])]; pin keeps the root's
    horizontal position at rest."""
    cg, cb = glb.read(costume)
    sg, sb = glb.read(src)
    anims = {a["name"]: a for a in sg["animations"]}
    sidx = {norm(n.get("name", "")): i for i, n in enumerate(sg["nodes"])}
    cpar = parents(cg)
    joints = cg["skins"][0]["joints"]
    joints_set = set(joints)
    cnames = {i: norm(cg["nodes"][i].get("name", "")) for i in range(len(cg["nodes"]))}
    # the costume's rest worlds (glTF world)
    W0, _ = __import__("rerig").worlds(cg)
    S0 = source_worlds(sg, sb, None, 0.0)
    root = next(j for j in joints if cnames[j] == "Bip01")
    hip = sidx["Bip01Pelvis"]
    scale = W0[root][1, 3] / S0[hip][1, 3]

    o = glb.Builder()
    # the costume's node tree, no meshes or skins (channels bind by joint name)
    for n in cg["nodes"]:
        o.node(**{k: n[k] for k in ("name", "children", "translation", "rotation", "scale", "matrix") if k in n})
    o.g["scenes"] = [dict(cg["scenes"][cg.get("scene", 0)])]
    # the source's face targets by name, over every morph mesh node (weights channels key them per node)
    fnodes = [i for i, nd in enumerate(sg["nodes"]) if "mesh" in nd and sg["meshes"][nd["mesh"]].get("extras", {}).get("targetNames")]
    fnames = list(dict.fromkeys(t for i in fnodes for t in sg["meshes"][sg["nodes"][i]["mesh"]]["extras"]["targetNames"]))
    face_node = None

    for name, seq, frames, *rest in clips:
        pin = bool(rest and rest[0])
        lens = [length(sg, sb, anims[s]) for s in seq]
        # at least the donor's frames, and the whole intro at its own speed (never squeezed: M1q, golf reactions ran
        # up to 3x fast squeezed into HST's shorter clips)
        n = max(frames, int(round(lens[0] * FPS))) if frames else int(round(sum(lens) * FPS))
        # frame f of the HST clip -> (source anim, time): the intro, then the loop over and over
        plan = []
        for f in range(n + 1):
            t = f / FPS
            if t <= lens[0] or len(seq) == 1:
                plan.append((seq[0], min(t, lens[0])))
            else:
                plan.append((seq[1], (t - lens[0]) % lens[1]))
        rot = {j: [] for j in joints}
        mirrored = set()
        pos = []
        chans = {a: sampler(sg, sb, anims[a]) for a in seq}
        faced = any("weights" in chans[a].get(i, {}) for a in seq for i in fnodes)
        face = []
        named = {cnames[j]: j for j in joints}
        through = 0
        for a, t in plan:
            if faced:
                w = dict.fromkeys(fnames, 0.0)
                for i in fnodes:
                    tv = chans[a].get(i, {}).get("weights")
                    if tv:
                        names = sg["meshes"][sg["nodes"][i]["mesh"]]["extras"]["targetNames"]
                        v = [np.interp(t, tv[0], tv[1][:, k]) for k in range(len(names))]
                        w.update((n, max(w[n], x)) for n, x in zip(names, v))
                face.append([w[n] for n in fnames])
            S = source_worlds(sg, sb, anims[a], t)
            Wa = {}

            def wa(j):
                if j in Wa:
                    return Wa[j]
                p = cpar.get(j)
                pw = wa(p) if p is not None and p in joints_set else W0[p] if p is not None else np.eye(4)
                s = sidx.get(cnames[j])
                if s is not None:
                    d = unit(S[s][:3, :3]) @ unit(S0[s][:3, :3]).T  # rotation only (Open Tee's root scales by 0.01)
                    m = np.eye(4)
                    m[:3, :3] = d @ W0[j][:3, :3]
                    m[:3, 3] = (pw @ node_mat(cg["nodes"][j]))[:3, 3]
                else:
                    m = pw @ node_mat(cg["nodes"][j])
                if j == root:
                    m[:3, 3] = W0[j][:3, 3] + scale * (S[hip][:3, 3] - S0[hip][:3, 3])
                Wa[j] = m
                return m

            for j in joints:
                p = cpar.get(j)
                pw = wa(p) if p in joints_set else W0[p] if p is not None else np.eye(4)
                L = np.linalg.inv(pw) @ wa(j)
                R = unit(L[:3, :3])
                if np.linalg.det(R) < 0:  # a mirrored helper (OT1's negative-scale nubs/dummies): left at rest
                    mirrored.add(j)
                    R = np.eye(3)
                rot[j].append(mat_quat(R))
                if j == root:
                    t = L[:3, 3].copy()
                    if pin:  # game space: y is height, x/z the floor
                        r0 = node_mat(cg["nodes"][j])[:3, 3]
                        t[0], t[2] = r0[0], r0[2]
                    pos.append(t)
            through += racket_inside(wa, named)
        times = np.arange(n + 1, dtype=np.float32) / FPS
        ti = o.accessor(times, glb.FLOAT, "SCALAR", minmax=True)
        ch, sm = [], []
        for j in joints:
            if (sidx.get(cnames[j]) is None or j in mirrored) and j != root:
                continue
            q = np.array(rot[j], np.float32)
            for k in range(1, len(q)):  # keep the quaternions on one hemisphere
                if np.dot(q[k], q[k - 1]) < 0:
                    q[k] = -q[k]
            sm.append({"input": ti, "output": o.accessor(q, glb.FLOAT, "VEC4"), "interpolation": "LINEAR"})
            ch.append({"sampler": len(sm) - 1, "target": {"node": j, "path": "rotation"}})
        sm.append({"input": ti, "output": o.accessor(np.array(pos, np.float32), glb.FLOAT, "VEC3"), "interpolation": "LINEAR"})
        ch.append({"sampler": len(sm) - 1, "target": {"node": root, "path": "translation"}})
        if faced:
            if face_node is None:
                face_node = o.node(name="face", extras={"targetNames": fnames})
            sm.append({"input": ti, "output": o.accessor(np.array(face, np.float32).ravel(), glb.FLOAT, "SCALAR"), "interpolation": "LINEAR"})
            ch.append({"sampler": len(sm) - 1, "target": {"node": face_node, "path": "weights"}})
        anim = {"name": name, "channels": ch, "samplers": sm}
        if through > HIDE_FRAMES * len(plan):  # §6 Racket: the game hides it while this clip plays
            anim["extras"] = {"racket": False}
        o.add("animations", anim)
    o.write(out)


def main():
    costume, src, out, *specs = sys.argv[1:]
    clips = []
    for s in specs:
        name, rest = s.split("=")
        rest, _, fr = rest.partition("@")
        pin = rest.endswith("!")
        clips.append((name, rest.rstrip("!").split("+"), int(fr) if fr else None, pin))
    make(costume, src, out, clips)


if __name__ == "__main__":
    main()


def ani_frames(path):
    """Length in 60 Hz frames of an HST `.ANI2` (last key tick / ticks per frame), as `hst_sim::pose::Clip`."""
    import struct
    d = open(path, "rb").read()
    al = lambda x: (x + 15) & ~15  # noqa: E731
    tpf, count = struct.unpack_from("<ii", d, 0)
    p, end, todo = 16, 0, [count]
    while todo:
        if not todo[-1]:
            todo.pop()
            continue
        todo[-1] -= 1
        p = al(p + 16 + struct.unpack_from("<i", d, p)[0])
        for _ in range(2):
            n = struct.unpack_from("<i", d, p)[0]
            p = al(p + 4)
            ticks = struct.unpack_from(f"<{n}i", d, p)
            p = al(p + 4 * n) + 16 * n
            end = max([end, *ticks])
        todo.append(struct.unpack_from("<i", d, p)[0])
        p = al(p + 4)
    return round(end / tpf)
