"""Get a Grip's character.csv stats -> HST TParam.csv overrides (standard §6 `params.override`).

Each mapped TParam column takes its value by rank: a Get a Grip character's position among Get a Grip's 15 on the
source stat (ties share their average rank) picks the cell at the same position in HST's 14 rows of that column,
sorted. So the cast keeps Get a Grip's relative strengths but only ever gets values HST's own cast has (integer
columns stay integers, `a/b/c` cells are whole HST cells). Columns with no Get a Grip source stay the donor row's.
"""
import csv
import itertools
import io
import os

# TParam column -> (Get a Grip source stats, averaged; why). The table in notes/getagrip.md mirrors this.
MAP = {
    "Serv POW": (["FlatservePower", "SpinservePower", "SliceservePower"], "serve power (mean of the three serves)"),
    "Strk POW": (["Power"], "overall (stroke) power"),
    "LOW POW": (["Power"], "low-ball stroke power (HST keeps it = Strk POW)"),
    "Voley POW": (["VolleyPower"], "volley power"),
    "V LOW POW": (["VolleyPower"], "low volley power (HST keeps it ≈ Voley POW)"),
    "Lob POW": (["LobPower"], "lob power"),
    "Lob POW2": (["LobPower"], "lob power (second lob)"),
    "Top SPIN": (["TopSpin"], "topspin"),
    "Slice SPIN": (["Spin"], "overall spin (Get a Grip's own slice spin is the same for everyone)"),
    "Drop SPIN": (["Spin"], "overall spin (Get a Grip's own drop spin is the same for everyone)"),
    "Strk CON": (["Technique"], "overall technique = stroke aim range"),
    "Voley CON": (["VolleyTechnique"], "volley technique"),
    "Serv CON": (["FlatserveTechnique", "SpinserveTechnique", "SliceserveTechnique"], "serve technique (mean)"),
    "ショット ウサギIMP GI/NI/BI": (["Impact"], "Impact = timing window (Usa/Kame = early/late, as HST's ウサギ/カメ)"),
    "ショット カメIMP GI/NI/BI": (["Impact"], "Impact = timing window, late side"),
    "SPE": (["Speed"], "run speed"),
    "STA": (["Stamina"], "stamina"),
    "Agili": (["Acceleration"], "acceleration"),
    "リーチ(cm)": (["Leach"], "reach"),
    "飛びつき（遠）開始": (["Leach"], "dive start (HST: 2 × reach)"),
    "飛びつき限界": (["Leach"], "dive limit (HST: 4 × reach)"),
}
# Playstyle 1/2/3 -> TParam タイプ. Read off the stats: 3 has the best volley technique and forward speed (net),
# 2 the worst volleys and backward speed with rising/air/lob specialists (baseline), 1 sits between (all-round).
STYLE = {"1": "オール", "2": "ベース", "3": "ネット"}


def squash(s):
    return " ".join(s.split())


def tparam(path):
    """HST's TParam.csv (cp932): headers (line breaks as spaces) and the 14 character rows."""
    rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("cp932"))))
    return [squash(h) for h in rows[0]], [r for r in rows[1:] if r and r[0].isdigit()]


def key(cell):
    return tuple(float(x) for x in cell.split("/"))


def ranks(values):
    """Average 0-based rank of each value (ties share it)."""
    order = sorted(values)
    return [(order.index(v) + len(order) - 1 - order[::-1].index(v)) / 2 for v in values]


def hst_xb(root):
    """HST's unpacked disc: build.sh's out/files/hst (from the HST disc in iso/), else the remaster's fixtures/xb
    (context/xb before it moved there)."""
    for p in [os.path.join(root, "out/files/hst"), os.path.join(root, "../opentennis/fixtures/xb")]:
        if os.path.isdir(p):
            return p
    return os.path.join(root, "../opentennis/context/xb")


def find_tparam(root):
    for p in [os.environ.get("HST_TPARAM", ""),
              os.path.join(hst_xb(root), "PCDATA/PCDATA.XB/data/taguchi/Data/TParam.csv")]:
        if p and os.path.isfile(p):
            return p
    return None


def overrides(stats, path, mapping=None, styles=None):
    """{pc: (override dict, why dict)} for a game's characters `stats` ({pc: {stat: value}}; Get a Grip: its
    character.csv rows). `mapping`: a game's own MAP (default Get a Grip's); `styles`: {pc: (タイプ, why)} (default
    Get a Grip's Playstyle column). Other games' modules (fore_data.py, oob_data.py, opentee_data.py) supply both."""
    head, rows = tparam(path)
    pcs = sorted(stats)
    out = {n: ({}, {}) for n in pcs}
    for col, (src, why) in (mapping or MAP).items():
        c = head.index(squash(col))
        hst = sorted((r[c] for r in rows), key=key)
        if any(s not in stats[n] or stats[n][s] in ("", None) for n in pcs for s in src):
            continue
        vals = [sum(float(stats[n][s]) for s in src) / len(src) for n in pcs]
        for n, v, r in zip(pcs, vals, ranks(vals)):
            cell = hst[round(r / (len(pcs) - 1) * (len(hst) - 1))]
            o, w = out[n]
            o[col] = int(cell) if cell.isdigit() else cell
            w[col] = f"{why}: {'+'.join(src)} {v:g}, rank {r + 1:g} of {len(pcs)} -> {cell}"
    if styles is not None:
        for n in pcs:
            t, why = styles.get(n, (None, None))
            if t:
                out[n][0]["タイプ"] = t
                out[n][1]["タイプ"] = why
        return out
    for n in pcs:
        o, w = out[n]
        p = stats[n].get("Playstyle")
        if p in STYLE:
            o["タイプ"] = STYLE[p]
            w["タイプ"] = f"Playstyle {p} -> {STYLE[p]}"
    return out


def ai_row(style, sex, height, chars):
    """The HST character whose AI row plays `style`: same type, same sex if one has it, nearest Bip01 height."""
    pool = [c for c in chars if c["type"] == style]
    pool = [c for c in pool if c["sex"] == sex] or pool
    return min(pool, key=lambda c: abs(c["bip01_height"] - height)) if pool else None


def hst_types(path):
    head, rows = tparam(path)
    return {int(r[0]): r[head.index("タイプ")] for r in rows}


# opentennis B182: every mod plays at the level of HST's expert row (the select grid's bottom row)
EXPERTS = (8, 9, 10, 11)  # Miranda, Kent, Lola, Will
# the band: power, spin, control (aim + timing windows), speed, stamina, reach; the dives follow reach (2× / 4×)
BAND = ["Serv POW", "Strk POW", "LOW POW", "Voley POW", "V LOW POW", "Lob POW", "Lob POW2", "Top SPIN", "Slice SPIN",
        "Drop SPIN", "Strk CON", "Voley CON", "Serv CON", "ショット ウサギIMP GI/NI/BI", "ショット カメIMP GI/NI/BI",
        "SPE", "Agili", "STA", "リーチ(cm)"]
KEEP = {"oob_pc12_anya", "getagrip_pc03_wendy"}  # already where the user wants them


def place(v, cells):
    """`v`'s average 0-based rank among `cells` (ties share it), as a fraction of the way from first to last."""
    lo = sum(key(c) < key(v) for c in cells)
    hi = sum(key(c) <= key(v) for c in cells) - 1
    return min(max((lo + hi) / 2, 0), len(cells) - 1) / (len(cells) - 1)


def expert(manifest, path, hst):
    """Moves a mod's BAND columns into HST's expert rows: a value's place among HST's 14 rows of the column -> the same
    place between the experts' lowest and highest (numbers interpolated and rounded, `a/b/c` cells whole expert cells),
    so each mod keeps its strengths. ai_row: the expert of its play style (else any expert), the donor's sex, nearest
    height. `hst`: standard/hst_skeleton.json's characters. Returns {column: (old, new)}; done once per manifest."""
    if manifest["id"] in KEEP or manifest.get("params_band") == "expert":
        return {}
    head, rows = tparam(path)
    by = {int(r[0]): r for r in rows}
    o = manifest["params"].setdefault("override", {})
    base = by[manifest["params"]["base"]]
    ch = {}
    for col in BAND:
        c = head.index(squash(col))
        old = str(o.get(col, base[c]))
        ex = sorted((by[e][c] for e in EXPERTS), key=key)
        x = place(old, [r[c] for r in rows]) * (len(ex) - 1)
        if "/" in old:
            new = ex[int(x + 0.5)]
        else:
            i = min(int(x), len(ex) - 2)
            new = int(float(ex[i]) + (x - i) * (float(ex[i + 1]) - float(ex[i])) + 0.5)
        o[col] = new
        ch[col] = (old, str(new))
    for col, k in (("飛びつき（遠）開始", 2), ("飛びつき限界", 4)):
        old = str(o.get(col, base[head.index(squash(col))]))
        o[col] = k * o["リーチ(cm)"]
        ch[col] = (old, str(o[col]))
    style = o.get("タイプ") or by[manifest["ai_row"]][head.index("タイプ")]
    d = hst[manifest["donor"]]
    pool = [dict(c, type=by[c["index"]][head.index("タイプ")]) for c in hst if c["index"] in EXPERTS]
    pool = [c for c in pool if c["type"] == style] or pool
    pool = [c for c in pool if c["sex"] == d["sex"]] or pool
    a = min(pool, key=lambda c: abs(c["bip01_height"] - d["bip01_height"]))
    ch["ai_row"] = (str(manifest["ai_row"]), str(a["index"]))
    manifest["ai_row"] = a["index"]
    manifest["ai_row_why"] = (f"expert band (opentennis B182): HST's expert of play style {style} if one has it, else any, "
                              f"{'same sex, ' if a['sex'] == d['sex'] else ''}nearest the donor's height ({a['name']})")
    manifest["params_band"] = "expert"
    manifest["params_band_why"] = {k: f"{v[0]} -> {v[1]}" for k, v in ch.items()} | {
        "_rule": "a value's place among HST's 14 TParam rows of the column -> the same place between the expert rows' "
                 "(8-11) lowest and highest (tools/rerig/gag_stats.py expert); dives = 2×/4× reach; params_why is "
                 "the value before this"}
    return ch


# opentennis: each mod's own grades (§6 `stats`) and whose serve/strokes/volleys it hits (§6 `shots`), shaped like
# HST's expert row: a strong suit or two, a weak one, a low Impact; a few stronger outliers.
CATEGORIES = [[12, 22, 54], [13, 15, 16, 17, 18, 19, 20, 26, 34, 35, 46, 50, 53], [14, 21, 37, 38, 48, 51],
              [28, 29, 30, 31, 32, 33], [40, 41, 42, 43]]  # TParam columns of Serve, Stroke, Volley, Impact, Footwork
GRADED_KEEP = KEEP | {"oob_pc02_sophie"}
# 2026-10-27 (user): these three now declare `stats` too (their own grades, cells nudged to those grades' means). Their
# manifests from before are in kept_before_stats.json: to revert one, write its entry back over out/mods/<id>/mod.json
# and bump `version` past the current one.
# by the mod's overall standing (its mean category score, TIERS): templates, one picked by id: the letters its
# Serve/Stroke/Volley/Footwork take (0 F … 5 A), best suit first, and its Impact; the sum (A = 5) in the comment.
TEMPLATES = [[((5, 3, 2, 2), 1), ((4, 3, 3, 2), 1)],  # Kent-like, 13: one big suit or none
             [((5, 4, 3, 3), 1), ((4, 4, 4, 4), 1), ((5, 4, 4, 2), 1)],  # Lola-like 16, Miranda-like 17, lopsided 16
             [((5, 5, 4, 3), 0)],  # Will-like, 17
             [((5, 5, 4, 3), 2)]]  # outlier, 19
TIERS = (0.48, 0.597, 0.605)  # set on the 2026-10-27 roster: about its bottom fifth, middle, top 7 %, top 5 %


def load_grades(root):
    """The disc's select-screen grades by character ([Serve, Stroke, Volley, Impact, Footwork], 0 F … 5 A): the file
    HST_GRADES names, else the remaster's `grades` tool on its disc image."""
    import subprocess
    if os.environ.get("HST_GRADES"):
        text = open(os.environ["HST_GRADES"]).read()
    else:
        hst = os.path.join(root, "../opentennis")
        iso = os.path.join(hst, "Hot Shots Tennis (USA).iso")
        text = subprocess.run(["cargo", "run", "-q", "-p", "hst-data", "--bin", "grades", "--", iso], cwd=hst,
                              capture_output=True, text=True, check=True).stdout
    return [[int(v) for v in line.split()] for line in text.splitlines() if line.strip()]


def scores(cells, rows, grades):
    """How good `cells` (a TParam row) is in each category, 0 … 1: per column its place among the stock rows,
    flipped where the stock grades fall as the column rises, averaged."""
    out = []
    for k, cols in enumerate(CATEGORIES):
        g = [grades[int(r[0])][k] for r in rows]
        mg = sum(g) / len(g)
        vals = []
        for c in cols:
            stock = [r[c] for r in rows]
            if len({key(v) for v in stock}) < 2:
                continue
            ps = [place(v, stock) for v in stock]
            mp = sum(ps) / len(ps)
            corr = sum((a - mp) * (b - mg) for a, b in zip(ps, g))
            if corr:
                x = place(cells[c], stock)
                vals.append(x if corr > 0 else 1 - x)
        out.append(sum(vals) / len(vals) if vals else 0.5)
    return out


def stable(s):
    import hashlib
    return int(hashlib.sha1(s.encode()).hexdigest(), 16)


def card_scores(cells, power):
    """The remaster's select-card score per category (hst-base grades.rs `scores`): `cells` the mod's row, `power`
    the rows whose serve, strokes and volleys it hits."""
    v = lambda r, c: float(str(r[c]).split("/")[0])
    serve, stroke, volley = v(power[0], 12), v(power[1], 13), v(power[2], 14)
    return [serve + 0.1 * v(cells, 22), stroke + 0.1 * v(cells, 17), volley - 0.25 * stroke + 0.1 * v(cells, 21),
            v(cells, 28) - 0.1 * serve, v(cells, 40) - 0.01 * v(cells, 57)]


def card_grades(cells, power, rows, grades):
    """The select card's letters (grades.rs `grades_of`, 6 = S): cuts halfway between the stock grades."""
    stock = [card_scores(r, [r, r, r]) for r in rows]
    own = card_scores(cells, power)
    out = []
    for k in range(5):
        at = [(sc[k], grades[int(r[0])][k]) for sc, r in zip(stock, rows)]
        def cut(g):
            lo = [x for x, h in at if h < g]
            hi = [x for x, h in at if h >= g]
            return (max(lo) + min(hi)) / 2 if lo and hi else float("inf")
        g = sum(own[k] > cut(g) for g in range(1, 6))
        out.append(6 if g == 5 and own[k] > 2 * max(x for x, _ in at) - cut(5) else g)
    return out


def graded_cells(manifest, head, rows, grades):
    """The mod's row as the game builds it for the card's columns: base, `scale`, `stats` (each category's cells the
    mean of its grade's stock rows, grades.rs `graded_row`), overrides."""
    by = {int(r[0]): r for r in rows}
    cells = list(by[manifest["params"]["base"]])
    cells[57] = str(int(float(cells[57]) * manifest.get("scale", 1.0) + 0.5))
    stats = manifest["stats"]
    stats = stats * 5 if len(stats) == 1 else stats
    for k, cols in enumerate(CATEGORIES):
        want = min("FEDCBAS".index(stats[k]), 5)  # ponytail: S taken as A here; the card scores S rows anyway
        near = min({g[k] for g in grades}, key=lambda g: abs(g - want))
        group = [r for r in rows if grades[int(r[0])][k] == near]
        for c in (22, 17, 21, 28, 40):
            if c in cols:
                parts = [r[c].split("/") for r in group]
                cells[c] = "/".join(str(int(sum(float(p[i]) for p in parts) / len(parts) + 0.5)) for i in range(len(parts[0])))
    for col, val in manifest["params"].get("override", {}).items():
        cells[head.index(squash(col))] = str(val)
    return cells


def pick_shots(manifest, path, grades):
    """§6 `shots`: whose serve, strokes and volleys a mod with `stats` hits so its select card reads its `stats`: its
    donor's where they do, else (by id) Lola's slice-special serve when it fits, or another that fits. Returns the
    card's letters (its stats unless no mix fits; then the nearest)."""
    head, rows = tparam(path)
    by = {int(r[0]): r for r in rows}
    cells = graded_cells(manifest, head, rows, grades)
    stats = manifest["stats"] * (5 if len(manifest["stats"]) == 1 else 1)
    want = ["FEDCBAS".index(c) for c in stats]
    donor, h = manifest["donor"], stable(manifest["id"])
    best = None
    for mix in itertools.product(range(14), repeat=3):
        got = card_grades(cells, [by[c] for c in mix], rows, grades)
        miss = sum(abs(a - b) for a, b in zip(got, want))
        cost = (miss, sum(c != donor for c in mix), -(mix[0] == 10 and h % 2), stable(f"{manifest['id']}{mix}"))
        if best is None or cost < best[0]:
            best = (cost, mix, got)
    _, mix, got = best
    shots = {k: c for k, c in zip(("serve", "stroke", "volley"), mix) if c != donor}
    if "smash" in manifest.get("shots", {}):
        shots["smash"] = manifest["shots"]["smash"]
    manifest.pop("shots", None)
    if shots:
        manifest["shots"] = shots
    return "".join("FEDCBAS"[g] for g in got)


def graded(manifest, path, grades):
    """Gives a mod (after `expert`) its `stats` from its row's standing (TEMPLATES, its own suits ranked as its row
    ranks them) and `shots` that make its select card read them (`pick_shots`). Drops the graded columns' overrides
    (the grades set them). Returns the why, or None (kept, or done)."""
    if manifest["id"] in GRADED_KEEP or "stats" in manifest or "params" not in manifest:
        return None
    head, rows = tparam(path)
    by = {int(r[0]): r for r in rows}
    o = manifest["params"].get("override", {})
    cells = list(by[manifest["params"]["base"]])
    for col, v in o.items():
        cells[head.index(squash(col))] = str(v)
    sc = scores(cells, rows, grades)
    mean = sum(sc) / 5
    h = stable(manifest["id"])
    tier = sum(mean >= t for t in TIERS)
    suits, impact = TEMPLATES[tier][h % len(TEMPLATES[tier])]
    g = [0] * 5
    for k, v in zip(sorted([0, 1, 2, 4], key=lambda k: -sc[k]), suits):
        g[k] = v
    g[3] = impact + (max(range(5), key=lambda k: sc[k]) == 3 and impact < 2)
    graded_cols = {c for cols in CATEGORIES for c in cols}
    for col in [col for col in o if head.index(squash(col)) in graded_cols]:
        del o[col]
    manifest["stats"] = "".join("FEDCBA"[v] for v in g)
    card = pick_shots(manifest, path, grades)
    if card != manifest["stats"]:  # a grade no mix reaches (Footwork is its own row's): take what it plays at
        manifest["stats"] = card
        card = pick_shots(manifest, path, grades)
    why = (f"its row's category scores {' '.join(f'{x:.2f}' for x in sc)} (mean {mean:.3f}) -> tier {tier} of "
           f"tools/rerig/gag_stats.py TEMPLATES, best suit first; shots {manifest.get('shots') or 'all its donor'}"
           f" (card {card})")
    manifest["stats_why"] = why
    return why


if __name__ == "__main__":
    # python3 tools/rerig/gag_stats.py [out/mods]: move the packed mods into the expert band in place (once each)
    import glob
    import json
    import sys
    root = os.path.join(os.path.dirname(__file__), "../..")
    tp = find_tparam(root)
    hst = json.load(open(os.path.join(root, "standard/hst_skeleton.json")))["characters"]
    for f in sorted(glob.glob(os.path.join(sys.argv[1] if sys.argv[1:] else os.path.join(root, "out/mods"), "*/mod.json"))):
        m = json.load(open(f))
        if m.get("costume_of") is not None:
            continue
        ch = expert(m, tp, hst)
        if ch:
            json.dump(m, open(f, "w"), indent=1, ensure_ascii=False)
            print(m["id"], " ".join(f"{k} {a}->{b}" for k, (a, b) in ch.items() if a != b))
        # every BAND value (and ai_row) of every rebalanced mod lies within the experts' own
        head, rows = tparam(tp)
        for col in BAND:
            c = head.index(squash(col))
            ex = sorted((r[c] for r in rows if int(r[0]) in EXPERTS), key=key)
            v = m["params"].get("override", {}).get(col)
            assert m["id"] in KEEP or (v is not None and key(ex[0]) <= key(str(v)) <= key(ex[-1])), (m["id"], col, v)
        assert m["id"] in KEEP or m["ai_row"] in EXPERTS, m["id"]
