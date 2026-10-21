"""I3M motion -> glTF animation (resampled, LINEAR)."""
import numpy as np

import glb
import i3m

FPS = 60.0
CONJUGATE = False  # file quaternion is the node's local rotation (column-vector sense); see notes


def spin_keys(tr):
    """A track whose every key turns about the model's Y only (the sky's cloud rings): its keys' angles unwrapped
    along the quaternion's double cover, so a 180-degree step keeps the way its sign says (c20's 0, 180, 360);
    None for any other track."""
    if len(tr.times) < 2 or np.abs(tr.rot[:, [0, 2]]).max() > 1e-4:
        return None
    half = np.unwrap(np.arctan2(tr.rot[:, 1], tr.rot[:, 3]))
    return 2 * half


def sample_track(tr, duration, fps=FPS, spin=False):
    """`spin`: a Y-only turn goes at a constant rate from key to key, through the loop's wrap too (every cloud
    ring's keys are evenly spread in angle and time; the squad evaluation eased each segment, and at the clamped
    ends the whole loop)."""
    n = max(int(round(duration * fps)), 0) + 1
    ts = np.minimum(np.arange(n) / fps, duration) if n > 1 else np.zeros(1)
    if len(tr.times) == 1:
        ts = ts[:1]
    P, R, S = [], [], []
    prev = None
    angles = spin_keys(tr) if spin else None
    for t in ts:
        p, q, s = i3m.evaluate(tr, t)
        if angles is not None:
            a = np.interp(t, tr.times, angles)
            q = np.array([0.0, np.sin(a / 2), 0.0, np.cos(a / 2)])
        if CONJUGATE:
            q = q * np.array([-1, -1, -1, 1])
        if prev is not None and np.dot(prev, q) < 0:
            q = -q
        prev = q
        P.append(p)
        R.append(q)
        S.append(s)
    return ts, np.array(P), np.array(R), np.array(S)


def add_animation(b, name, motion, by_name, skeleton=None, spin=False):
    chans, samps = [], []
    time_acc = {}
    for tr in motion.tracks:
        node = by_name.get(tr.name)
        if node is None:
            continue
        ts, P, R, S = sample_track(tr, motion.duration, spin=spin)
        key = len(ts)
        if key not in time_acc:
            time_acc[key] = b.accessor(ts, glb.FLOAT, "SCALAR", minmax=True)
        tin = time_acc[key]
        for path, vals, typ in (("translation", P, "VEC3"), ("rotation", R, "VEC4"), ("scale", S, "VEC3")):
            if path == "scale" and np.allclose(vals, 1, atol=1e-4):
                continue
            out = b.accessor(vals, glb.FLOAT, typ)
            samps.append({"input": tin, "output": out, "interpolation": "LINEAR"})
            chans.append({"sampler": len(samps) - 1, "target": {"node": node, "path": path}})
    if chans:
        b.add("animations", {"name": name, "channels": chans, "samplers": samps})
