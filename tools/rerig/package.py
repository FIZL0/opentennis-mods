"""Package every rerigged character as a mod folder (standard/HST-CHARACTER-STANDARD.md §1, §6).

python3 tools/rerig/package.py [game…]     (after batch.py; default every game)  ->  out/mods/<game>_<slug>/

Files are hard links into out/ (game data: never commit). Every game gets: costumes; a same-sex donor with the
nearest Bip01 height; the face (morph, or face.json for the PSP texture swaps); voices sorted into HST programs; the
source stats ranked onto TParam as params.override (gag_stats.overrides; needs HST's TParam.csv: HST_TPARAM or
../opentennis/fixtures/xb) with ai_row by play style where the game has one; the game's own point/set reactions
as motions.glb (motions.py; needs ../opentennis/fixtures/xb/PCANI for the donor clip lengths; golf roots held,
PIN); and a racket in its outfit's colours (pick_racket). Get a Grip's data is
in gag_stats.py, the golf games' in fore_data.py / oob_data.py / opentee_data.py. Handedness: a golf mod whose
costumes wear a glove on the left hand is left-handed (glove hand = racket hand, standard §6 `hand`) and ships its
costumes pre-mirrored (mirror.py) instead of linked; the rest stay right-handed, left for a human to confirm.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools/psp2gltf"))
sys.path.insert(0, HERE)
import glb  # noqa: E402
from rerig import binds  # noqa: E402
import racket  # noqa: E402
import colour  # noqa: E402
import edge_clamp  # noqa: E402
import claps  # noqa: E402
import face_alias  # noqa: E402
import sizing  # noqa: E402
import gag_stats as gagmap  # noqa: E402
import motions  # noqa: E402
import mirror  # noqa: E402
import takes  # noqa: E402
import more_voices  # noqa: E402

GAME_NAME = {"fore": "Hot Shots Golf Fore! (PS2)", "oob": "Hot Shots Golf: Out of Bounds (PS3)",
             "getagrip": "Hot Shots Tennis: Get a Grip (PSP)",
             "opentee2": "Hot Shots Golf: Open Tee 2 (PSP)"}
# HST reaction motion <- Get a Grip's own reaction (intro, then its loop), per character (motions.py)
PIN = {"fore": True, "oob": True, "opentee2": True}  # golf celebrations walk off their spot (notes/fore.md, oob.md): hold the root
# Hz a game plays its exported clips at (60 if not listed): Open Tee 2's face TATs run twice as long as its body clips
# in every emote, win and hole result (win00 90 frames vs 3.0 s), so it plays them at 30 Hz (opentennis B613).
# The others' face tracks end with their body clips (Get a Grip's TATs, Fore!'s MOR: ratio 1, never 2): 60 Hz as exported.
HZ = {"opentee2": 30}
GAG_REACT = {"re_gu": "gu01", "re_di": "di01", "re_gu_set": "gu_set01", "re_di_set": "di_set01"}
HST_ANI = gagmap.hst_xb(ROOT) + "/PCANI"
# Get a Grip cue -> HST voice program (programs 7-10 follow reaction motions 0x2c-0x2f: re_gu, re_di, re_gu_set,
# re_di_set). approx: 1 and 2 (st_ji/st_nb meaning unknown). body = hit by the ball ('Ow!', 'Ouch!', "Nah, I'm hit!").
GAG_VOICE = {0: ["smash"], 1: ["st_ji"], 2: ["st_nb"], 3: ["receive"], 4: ["swing"], 5: ["body"],
             6: ["start", "call", "go", "chance"],
             7: ["point_get", "rep_get", "hnr:good"], 8: ["point_lost", "rep_lost", "hnr:bad"],
             9: ["set_get", "hnr:winA", "hnr:winB"], 10: ["set_lost", "hnr:loseA"]}
# 7-10 take the second take set's cues too (sgv_PCNNb: the same cues, other recordings), after the first set's, and the
# honours bank's (hnr_PCNN: good/bad and the trophy win/lose lines); a recording two cues share is used once
GAG_BANKS = {7: "ab", 8: "ab", 9: "ab", 10: "ab"}


def link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def gag_voices(n, dst):
    d = os.path.join(ROOT, f"out/voices/getagrip/pc{n:02d}")
    out = {}
    for prog, cues in GAG_VOICE.items():
        files, seen = [], set()
        for bank in GAG_BANKS.get(prog, "a"):
            for cue in cues:
                if cue.startswith("hnr:"):
                    if bank != "a":
                        continue
                    pat = f"hnr_pc{n:02d}_pc_voice_{cue[4:]}*.wav"
                else:
                    pat = f"sgv_pc{n:02d}{bank}_pc_voice_{cue}*.wav"
                for f in sorted(glob.glob(os.path.join(d, pat))):
                    h = hashlib.md5(open(f, "rb").read()).hexdigest()
                    if h not in seen:
                        seen.add(h)
                        files.append(f)
        files = files[:KEYS.get(prog, 5)]
        for k, f in enumerate(files):
            link(f, os.path.join(dst, f"voice/{prog}_{k}.wav"))
        out[prog] = len(files)
    return out


# HST voice program -> keys it plays (standard §5); reactions 7-10 take any number (HST's own draw reaches keys 0-2,
# 0-4, 0-1, 0-1; a mod's further takes are there for a player that cycles through all of them), capped at 16
KEYS = {0: 3, 1: 5, 2: 3, 3: 3, 4: 2, 5: 1, 6: 5, 7: 16, 8: 16, 9: 16, 10: 16}
REACTION_PROGRAM = {"re_gu": 7, "re_di": 8, "re_gu_set": 9, "re_di_set": 10}
# Rackets (M1r). No source game has a per-character racket (Get a Grip's Racket_param has no character column,
# notes/getagrip.md; the golf games have none), so each mod gets the one of the 24 there are whose frame is nearest
# its outfit's colours (colour.py): Get a Grip's 10 models (parts/racket: racket000-008 = items Racket_0N0-0N2, which
# share a model each, and racket050 = Racket_500) as racket.glb, or one of HST's 14 disc rackets (PC/PCnnC00.XB
# racket_nn, read from the user's disc: mod.json `disc_racket`). When none comes near, a Get a Grip racket with its
# paint turned to the outfit's main colour. A golf mod holds a Get a Grip racket with Emi's grip, moved hand to hand.
GAG_RACKETS = ["00", "01", "02", "03", "04", "05", "06", "07", "08", "50"]
GAG_PAINTED = ["01", "02", "03", "05", "06", "07"]  # one-colour frames, for the tint
GAG_RACKET = os.path.join(ROOT, "out/models/getagrip/parts/racket/racket{}.glb")
GAG_GRIP = os.path.join(ROOT, "out/rerig/getagrip/pc00_emi/pc00_emi_set3.glb")
HST_RACKET = os.path.join(ROOT, "out/models/hst/pc{:02d}_c00.glb")  # hst-gltf hst ../opentennis/fixtures/xb out/models/hst
HST_NAMES = ["Ashley", "Cody", "Jun", "Kaito", "Momoko", "JJ", "Carol", "Big Chief", "Miranda", "Kent", "Lola", "Will",
             "Gloria", "Suzuki"]
HST_SAME = {"gloria": 12, "suzuki": 13}  # the same character in HST: her/his own racket there
NEAR = 0.05  # colour.match below this for every racket: tint one instead
TIE = 0.02  # within this of the best: as good, take one no other mod of the game holds
_used = {}
_hists = {}


def racket_hist(r):
    if r not in _hists:
        if r[0] == "gag":
            _hists[r] = colour.hist(*colour.samples(GAG_RACKET.format(r[1]), head=True))
        else:
            p = HST_RACKET.format(r[1])
            if not os.path.exists(p):
                sys.exit(f"{p} missing: build HST's models from your disc (hst-gltf hst ../opentennis/fixtures/xb out/models/hst)")
            _hists[r] = colour.hist(*colour.samples(p, {"racket"}, head=True))
    return _hists[r]


def pick_racket(game, n, name, donor, mod, manifest, costumes, cast):
    """Racket for mod `n` of `game` (`cast`: every pc number -> name of the game, for the reserved HST picks).

    The same character's HST racket if there is one; else the racket whose frame colours best match costume 0's
    outfit, preferring among near-equal ones one no other mod of the game holds; else (no match reaches NEAR) a
    Get a Grip one-colour frame tinted to the outfit's main colour."""
    used = _used.setdefault(game, set())
    reserved = {("disc", HST_SAME[c]) for c in cast.values() if c in HST_SAME}
    gag = [("gag", r) for r in GAG_RACKETS if os.path.exists(GAG_RACKET.format(r)) and (game == "getagrip" or os.path.exists(GAG_GRIP))]
    tint = None
    if name in HST_SAME:
        pick = ("disc", HST_SAME[name])
    else:
        outfit = colour.hist(*colour.samples(costumes[0], body=True))
        score = {r: colour.match(outfit, racket_hist(r)) for r in gag + [("disc", k) for k in range(14)] if r not in reserved}
        best = max(score.values())
        tint = colour.paint(outfit) if best < NEAR else None
        if tint is not None and gag:
            pick = next((r for r in gag if r[1] in GAG_PAINTED and r not in used), ("gag", GAG_PAINTED[0]))
        else:
            tint = None
            pick = max((r for r in score if score[r] >= best - TIE), key=lambda r: (r not in used, score[r]))
    used.add(pick)
    out = os.path.join(mod, "racket.glb")
    manifest.pop("disc_racket", None)
    if pick[0] == "disc":
        if os.path.exists(out):
            os.remove(out)
        manifest["disc_racket"] = pick[1]
        why = (f"the same character's racket in HST ({HST_NAMES[pick[1]]})" if name in HST_SAME else
               f"HST {HST_NAMES[pick[1]]}'s racket, the nearest frame colour to the outfit")
        manifest["racket_why"] = f"{why}: PC/PC{pick[1]:02d}C00.XB racket_{pick[1]:02d}, read from your disc"
    else:
        part = GAG_RACKET.format(pick[1])
        item = "Racket_500" if pick[1] == "50" else f"Racket_0{int(pick[1])}0"
        if game == "getagrip":
            racket.make(part, costumes[0], out, tint=tint)
            grip = "its source grip on the hand"
        else:
            racket.make(part, GAG_GRIP, out, target=costumes[0], tint=tint)
            grip = "Get a Grip Emi's grip carried rigidly from her right hand to this one's (rerigged hands share HST's bone axes)"
        why = (f"Get a Grip's racket{pick[1]}.xb (item {item}) painted {colour.hexs(tint)}, the outfit's main colour, "
               "as no racket's frame comes near it" if tint is not None else
               f"Get a Grip's racket{pick[1]}.xb (item {item}{', its other colours share the model' if pick[1] != '50' else ''}), "
               "the nearest frame colour to the outfit")
        manifest["racket_why"] = f"{why} (Get a Grip has no per-character racket); {grip}, resized to HST's 0.944 m"
_cast = {}


def data(game):
    """The game's data module (fore_data / oob_data / opentee_data) as uniform callables, or None."""
    try:
        if game == "fore":
            import fore_data as d
        elif game == "oob":
            import oob_data as d
        else:
            import opentee_data as d
    except ImportError:
        return None
    if game in ("opentee", "opentee2"):
        mp = d.MAP[game] if isinstance(d.MAP, dict) and game in d.MAP else d.MAP
        return dict(stats=lambda: d.stats(game), map=mp, style=lambda n: d.style(game, n),
                    voices=lambda n: d.voices(game, n), reactions=lambda n: d.reactions(game, n),
                    faces=lambda n: d.faces(game, n), results=lambda n: {}, name=GAME_NAME[game].split(" (")[0])
    return dict(stats=d.stats, map=d.MAP, style=d.style, voices=d.voices, reactions=d.reactions,
                faces=getattr(d, "faces", lambda n: None), results=getattr(d, "results", lambda n: {}),
                name=GAME_NAME[game].split(" (")[0])


def cast(game, D, tp):
    """The game's whole cast: (raw stats, {pc: (override, why)}), once per game (ranks need everyone)."""
    if game not in _cast:
        st = D["stats"]() or {}
        styles = {n: D["style"](n) for n in st}
        _cast[game] = (st, gagmap.overrides(st, tp, D["map"], styles) if tp and st else {})
    return _cast[game]


def voices(prog, dst):
    """{program: [wav]} -> voice/<program>_<key>.wav (old sorted and unsorted voices removed first)."""
    for f in glob.glob(os.path.join(dst, "voice/*.wav")):
        os.remove(f)
    shutil.rmtree(os.path.join(dst, "voice/unsorted"), ignore_errors=True)
    out = {}
    for p, files in sorted(prog.items()):
        files = files[:KEYS.get(p, 5)]
        for k, f in enumerate(files):
            link(os.path.realpath(f), os.path.join(dst, f"voice/{p}_{k}.wav"))
        if files:
            out[p] = len(files)
    return out


# Source clips that sit on furniture the reaction doesn't have, and what goes under their takes (standard §6
# `extras.seat`, tools/oob2gltf/seat.py): Anya's eagle sits on air (the lobby's piano bench), Kratos's result screens
# on his throne. No other character's clip sits (2026-10-26: the low ones crouch, kneel or squat over their feet).
SEATED = {"ga_pc12_ea_r00": "bench", **{f"rslt_{k}_pc17": "throne" for k in ("wait", "win", "vict", "get", "loss")}}


def seat(seq):
    return {"seat": "seat.glb"} if seq and seq[0] in SEATED else {}


def golf(game, n, mod, manifest, costumes, donor, h, hst, tp, hst_type):
    """Fore, Out of Bounds, Open Tee 2 to the Get a Grip standard, from the game's data module."""
    D = data(game)
    if D is None:
        manifest["todo"].append("no data module for this game (tools/rerig/<game>_data.py)")
        return
    f = D["faces"](n)
    if f:
        def local(p):
            link(os.path.join(ROOT, p), os.path.join(mod, "face", os.path.basename(p)))
            return "face/" + os.path.basename(p)
        f = dict(f, materials=f.get("materials") or [f["face_material"]], neutral=local(f["neutral"]),
                 channels={k: v and local(v) for k, v in f["channels"].items()})
        json.dump(f, open(os.path.join(mod, "face.json"), "w"), indent=1, ensure_ascii=False)
        manifest["face"] = "texture"
    elif game.startswith("opentee"):
        manifest["face"] = "none"
    prog, vwhy = more_voices.fill(game, n, *D["voices"](n))
    prog = {p: fs[:KEYS.get(p, 5)] for p, fs in prog.items()}
    res = D["results"](n)  # {source clip: [the lines the game plays with it]}
    r = D["reactions"](n)
    if r and r[0] and r[1]:
        src, clips, whys = r
        plan = []
        for hst_name, seq in clips.items():
            pin = seq[-1] == "!" if seq and isinstance(seq[-1], str) else False
            seq = [x for x in seq if x != "!"]
            ani = os.path.join(HST_ANI, f"PC{donor['index']:02d}ANI.XB/data/taguchi/MtPc{donor['index']:02d}/{hst_name.replace('re_', f're_pc{donor['index']:02d}_')}.ANI2")
            frames, pin = motions.ani_frames(ani) if os.path.exists(ani) else None, PIN.get(game, False) or pin
            # the reaction's further takes (takes.py; the game draws one in turn as it starts), timed as the reaction;
            # a clip the source game plays with lines of its own says them (§6 `extras.voice`), one take per line:
            # its first in its place, the others as more takes after
            have = prog.get(REACTION_PROGRAM[hst_name], [])
            first, again = [], []
            for s in [seq] + [[x] for x in takes.takes(game, n).get(hst_name, [])]:
                ws = [w for w in res.get(s[0], []) if w in have]
                first.append((s, ws[0] if ws else None))
                again += [(s, w) for w in ws[1:]]
            for k, (s, w) in enumerate(first + again):
                name = f"{hst_name}.{k}" if k else hst_name
                if k:
                    whys[name] = f"take {k + 1} of {hst_name} (takes.py{', again for its other line' if k >= len(first) else ''})"
                if w:
                    whys[name] = f"{whys.get(name, '')} saying its own line, voice key {have.index(w)}".lstrip()
                plan.append((name, s, frames, pin, ({"voice": have.index(w)} if w else {}) | seat(s)))
        hz = HZ.get(game, 60)
        held = motions.make(costumes[0], src, os.path.join(mod, "motions.glb"), plan, rate=hz / 60)
        seat_glb = os.path.join(mod, "seat.glb")
        if held:  # ponytail: one seat per mod, under the first seated take (the takes reuse one sitting clip)
            name, (x, y, z) = next(iter(held.items()))
            kind = SEATED[next(s[0] for n, s, *_ in plan if n == name)]
            # under the sitting hips (seat.py sizes it from their height); root space is the world turned half way
            # round the forward axis (`game_space`): x and y flip
            subprocess.run([sys.executable, os.path.join(ROOT, "tools/oob2gltf/seat.py"), seat_glb, kind, str(y), str(-x), str(z)], check=True)
        elif os.path.exists(seat_glb):
            os.remove(seat_glb)
        manifest["motions"] = "motions.glb"
        manifest["motions_why"] = {k: f"{whys.get(k, '')}; {' then '.join(seq)}{', root held on its spot' if pin else ''}, played at {hz} Hz, its own length and at least the donor's clip ({fr} frames)"
                                   for k, seq, fr, pin, *_ in plan}
    sz = os.path.join(ROOT, f"out/rerig/{game}/sizing.json")
    if os.path.exists(sz):
        ch = json.load(open(sz))["characters"].get(f"pc{n:02d}")
        if ch:
            manifest["size_why"] = f"{ch['why']}; head × {ch['head_factor']:.4f} about the neck ({ch['head_why']})"
    manifest["voice"] = "voice/"
    manifest["voice_counts"] = {str(k): v for k, v in voices(prog, mod).items()}
    manifest["voice_why"] = {str(k): v for k, v in vwhy.items()}
    claps.apply(mod, manifest)  # clap takes put the racket away (claps.py)
    st, params = cast(game, D, tp)
    manifest["source_stats"] = st.get(n, {})
    if n in params and params[n][0]:
        o, w = params[n]
        manifest["params"]["override"] = o
        manifest["params_why"] = dict(w, _rule=f"rank among {D['name']}'s {len(st)} -> same rank in HST's 14 rows of that column "
                                                f"(tools/rerig/gag_stats.py with tools/rerig/{game.rstrip('2')}_data.py MAP); other columns: the donor's row")
        if "タイプ" in o:
            chars = [dict(c, type=hst_type[c["index"]]) for c in hst]
            sex = (sizing.source(game) or {}).get(n, (donor["sex"],))[0] or donor["sex"]
            a = gagmap.ai_row(o["タイプ"], sex, h, chars)
            if a:
                manifest["ai_row"] = a["index"]
                manifest["ai_row_why"] = f"play style {o['タイプ']}: {'same sex, ' if a['sex'] == sex else ''}nearest Bip01 height among HST's {o['タイプ']} players ({a['name']} {a['bip01_height']} m)"
    else:
        manifest["todo"].append("no stats in the source data: params stay the donor's")


def main():
    hst = json.load(open(os.path.join(ROOT, "standard/hst_skeleton.json")))["characters"]
    fp = os.path.join(ROOT, "out/models/getagrip/faces.json")
    gag_faces = json.load(open(fp)) if os.path.exists(fp) else {}
    gag_stats = {}
    csvp = glob.glob(os.path.join(ROOT, "out/files/getagrip/**/parameter/character.csv"), recursive=True)
    if csvp:
        rows = [r.split(",") for r in open(csvp[0], encoding="utf-8", errors="replace").read().splitlines() if r]
        head = rows[0]
        for r in rows[1:]:
            m = re.match(r"Pc_(\d+)_00", r[0])
            if m:
                gag_stats[int(m.group(1))] = dict(zip(head[1:], r[1:]))
    gag_sex = {}
    for g in GAME_NAME:
        if os.path.isdir(os.path.join(ROOT, f"out/files/{g}")):
            src = sizing.source(g)
            if src:
                gag_sex[g] = src
    # Get a Grip's stats onto HST's TParam columns by rank (gag_stats.py; needs HST's TParam.csv)
    tp = gagmap.find_tparam(ROOT)
    gag_params = gagmap.overrides(gag_stats, tp) if tp and gag_stats else {}
    hst_type = gagmap.hst_types(tp) if tp else {}
    made = 0
    for game in [g for g in GAME_NAME if g in (sys.argv[1:] or GAME_NAME)]:
        cast_names = {int(m.group(1)): m.group(2) for d in glob.glob(os.path.join(ROOT, f"out/rerig/{game}/*/"))
                      if (m := re.match(r"pc(\d+)_?(.*)", os.path.basename(d.rstrip("/"))))}
        for cdir in sorted(glob.glob(os.path.join(ROOT, f"out/rerig/{game}/*/"))):
            costumes = sorted(glob.glob(cdir + "*.glb"))
            if not costumes:
                continue
            slug = os.path.basename(cdir.rstrip("/"))
            m = re.match(r"pc(\d+)_?(.*)", slug)
            n = int(m.group(1))
            name = m.group(2) or os.path.basename(costumes[0]).split("_")[1]
            mod = os.path.join(ROOT, f"out/mods/{game}_pc{n:02d}_{name}")
            lefty, hand_why = False, None
            if game in PIN:  # golf: the glove hand holds the racket
                lefty, hand_why, _ = mirror.gloved(f"{game}_pc{n:02d}_{name}", costumes)
            for c in costumes:
                if lefty:
                    mirror.mirror(c, os.path.join(mod, "model", os.path.basename(c)))
                else:
                    link(c, os.path.join(mod, "model", os.path.basename(c)))
                # the face stand-ins (FACE_PICKS & co.) a model lacks; out/rerig may predate them (opentennis M131)
                face_alias.add_aliases(os.path.join(mod, "model", os.path.basename(c)))
                # textures sampled right at their edge clamp there: no seam down a mirrored face (opentennis B584)
                edge_clamp.clamp(os.path.join(mod, "model", os.path.basename(c)))
            g, b = glb.read(costumes[0])
            h = -binds(g, b)[0]["Bip01"][1, 3]
            pool, why = hst, "nearest Bip01 height"
            if game in gag_sex and gag_sex[game].get(n, (None,))[0] in ("f", "m"):  # sex known: nearest of HST's same-sex standard bodies
                pool = [c for c in hst if c["sex"] == gag_sex[game][n][0] and c["model_type"] in sizing.STANDARD_BODY]
                why = f"nearest Bip01 height among HST's standard-body {'women' if gag_sex[game][n][0] == 'f' else 'men'}"
            donor = min(pool, key=lambda c: abs(c["bip01_height"] - h))
            if sizing.GLORIA.get(game) == n:  # the game's Gloria is HST's Gloria: her own body, whatever the sizing
                donor = next(c for c in hst if c["name"] == "Gloria")
                why = "HST's Gloria herself"
            manifest = {"standard": 1, "id": f"{game}_pc{n:02d}_{name}", "name": name.replace("_", " ").title(),
                        "source": f"{GAME_NAME[game]} pc{n:02d}",
                        "costumes": [f"model/{os.path.basename(c)}" for c in costumes],
                        "donor": donor["index"], "donor_why": f"{why} ({h:.3f} m vs {donor['name']} {donor['bip01_height']} m)",
                        "hand": "left" if lefty else "right", "params": {"base": donor["index"], "override": {}},
                        "ai_row": donor["index"], "face": "morph", "voice": None, "todo": []}
            if hand_why:
                manifest["hand_why"] = hand_why
            if game in ("fore", "oob"):
                # already high-res: opentennis's upscale_mods.py leaves it alone
                manifest["upscale"] = False
            if game in ("getagrip",):
                f = gag_faces.get(slug) or next((v for k, v in gag_faces.items() if k.startswith(f"pc{n:02d}")), None)
                if f:
                    # ship the face textures inside the mod, paths relative to it
                    def local(p):
                        link(os.path.join(ROOT, p), os.path.join(mod, "face", os.path.basename(p)))
                        return "face/" + os.path.basename(p)
                    f = dict(f, materials=[f["face_material"]], neutral=local(f["neutral"]), channels={k: v and local(v) for k, v in f["channels"].items()})
                    json.dump(f, open(os.path.join(mod, "face.json"), "w"), indent=1)
                    manifest["face"] = "texture"
                # its own point/set reactions, retargeted, timed to the donor's clips (visual only, standard §6 motions)
                react = os.path.join(ROOT, f"out/anims/getagrip/pc{n:02d}_{name}_react.glb")
                if os.path.exists(react):
                    clips = []
                    for hst_name, src in GAG_REACT.items():
                        ani = os.path.join(HST_ANI, f"PC{donor['index']:02d}ANI.XB/data/taguchi/MtPc{donor['index']:02d}/{hst_name.replace('re_', f're_pc{donor['index']:02d}_')}.ANI2")
                        clips.append((hst_name, [f"re_pc{n:02d}_{src}", f"re_pc{n:02d}_{src}_loop"], motions.ani_frames(ani) if os.path.exists(ani) else None))
                    motions.make(costumes[0], react, os.path.join(mod, "motions.glb"), clips)
                    manifest["motions"] = "motions.glb"
                    manifest["motions_why"] = {k: f"Get a Grip re_pc{n:02d}_{v} then its _loop, played at 60 Hz, its own length and at least the donor's clip ({f} frames)"
                                               for (k, v), (_, _, f) in zip(GAG_REACT.items(), clips)}
                sz = os.path.join(ROOT, "out/rerig/getagrip/sizing.json")
                if os.path.exists(sz):
                    sz = json.load(open(sz))
                    ch = sz["characters"][f"pc{n:02d}"]
                    manifest["size_why"] = f"{ch['why']}; head × {ch['head_factor']:.4f} about the neck ({ch['head_why']})"
                manifest["voice"] = "voice/"
                manifest["voice_counts"] = gag_voices(n, mod)
                manifest["source_stats"] = gag_stats.get(n, {})
                if n in gag_params:
                    o, w = gag_params[n]
                    manifest["params"]["override"] = o
                    manifest["params_why"] = dict(w, _rule="rank among Get a Grip's 15 -> same rank in HST's 14 rows of that column (tools/rerig/gag_stats.py); other columns: the donor's row")
                    # the computer plays it with an HST AI row of the same play style (body and motions stay the donor's)
                    if "タイプ" in o:
                        chars = [dict(c, type=hst_type[c["index"]]) for c in hst]
                        a = gagmap.ai_row(o["タイプ"], gag_sex[game][n][0], h, chars)
                        if a:
                            manifest["ai_row"] = a["index"]
                            manifest["ai_row_why"] = f"play style {o['タイプ']} (Playstyle {gag_stats[n]['Playstyle']}): {'same sex, ' if a['sex'] == gag_sex[game][n][0] else ''}nearest Bip01 height among HST's {o['タイプ']} players ({a['name']} {a['bip01_height']} m)"
                manifest["todo"] += ["check voice programs 1/2 by ear (st_ji/st_nb)"]
            else:
                golf(game, n, mod, manifest, costumes, donor, h, hst, tp, hst_type)
            pick_racket(game, n, name, donor, mod, manifest, costumes, cast_names)
            if not lefty:
                manifest["todo"].append("confirm handedness")
            if tp:
                gagmap.expert(manifest, tp, hst)
            old = os.path.join(mod, "mod.json")
            if os.path.exists(old) and "version" in (prev := json.load(open(old))):
                manifest["version"] = prev["version"]  # bumped by hand before an upload (opentennis AGENT.md)
            json.dump(manifest, open(old, "w"), indent=1, ensure_ascii=False)
            made += 1
    print(made, "mods in out/mods/")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fresh
    fresh.check()
    main()
