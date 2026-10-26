"""Hot Shots Golf: Out of Bounds (PS3, pc00-16; pc17-19 in the PSN edition) character data for HST mods (notes/oob.md "Mod data").
Everything is read at run time from out/ (never committed).

stats(), MAP, style(pc), heights(), voices(pc), reactions(pc) as package.py / gag_stats.py / sizing.py expect.
`python3 tools/rerig/oob_data.py` prints them all.
"""
import glob
import json
import os
import re
import struct
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USR = "out/files/oob/PS3_GAME/USRDIR/xbdata"
AUD = "out/audio/oob/PS3_GAME/USRDIR/xbdata"


def _p(*a):
    return os.path.join(ROOT, *a)


# ---- stats ----------------------------------------------------------------------------------------------------

# ueno/ability/player.dat ("ABI_PLAY", big-endian): 17 records (20 in the PSN edition) of 5 f32 + 7 i32. The floats are the character-select
# bars in order (charaselect chrsel_prmset: bar_power, bar_control, bar_impact, bar_spin, bar_side); the ints were
# read off the help texts (draw/fade, rough, bunker, rain, approach weaknesses), the last is the profile's sex.
FLOATS = ("power", "control_spread", "impact", "spin", "side")
INTS = ("curve", "rough", "bunker", "rain", "approach", "_const", "sex")
# menu_help.to strings 500-516 describe the 17 in character-select order, not pc order (the PSN edition's
# Kratos, Toro, Sackboy follow in pc order: "Expert Big Hitter: great draw shots", "Novice Spin Cat", "Novice Big
# Hitter. Great fade shot", as their curve flags). Matched by the flags
# (e.g. "poor in rough" = rough -1, "hits draw" = curve +1) and the tiers (the 5 lowest powers are Novice, ...).
HELP_PC = [0, 1, 2, 3, 13, 4, 7, 6, 8, 5, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19]
TYPES = ("All-rounder", "Big Hitter", "Control Player", "Spin Player", "Special")


def _player():
    d = open(_p(USR, "ueno/common/main.xb0/data/ueno/ability/player.dat"), "rb").read()
    assert d[:8] == b"ABI_PLAY"
    n = struct.unpack_from(">I", d, 0x14)[0]
    out = []
    for k in range(n):
        o = struct.unpack_from(">I", d, 0x30 + 4 * k)[0]
        f = struct.unpack_from(">5f", d, o)
        i = struct.unpack_from(">7i", d, o + 20)
        out.append(dict(zip(FLOATS, (round(x, 4) for x in f)), **dict(zip(INTS, i))))
    return out


def _help():
    s = open(_p(USR, "ookubo/menu/menu_common.xb0/data/text/menu_help.to"), "rb").read().split(b"\0")
    i = next(k for k, x in enumerate(s) if x.startswith(b"Novice All-rounder"))
    return {pc: s[i + k].decode().strip() for k, pc in enumerate(HELP_PC)}


def _profile(pc):
    f = _p(USR, f"kikkawa/menu/profile_txt.xb0/data/kikkawa/menu/profile/profile2/pc{pc:02d}.dat")
    return open(f, encoding="utf-8-sig").read().splitlines()


def stats():
    """{pc: {stat: str}}. control = 2 - control_spread: the game's control value is a spread multiplier (lower is
    better: club.dat/ball.dat trade +power for +control, and the help calls Sonia 1.2 / L.J. 1.3 'poor/terrible
    control'), so it is inverted to make higher = better like every other column. power/impact/spin/side: higher
    = more (longer drives, bigger impact window, more backspin, more curve)."""
    hl = _help()
    out = {}
    for pc, r in enumerate(_player()):
        if pc not in hl:  # the table's rows past the cast (no help text): no character to package
            continue
        h = hl[pc]
        out[pc] = {"name": _profile(pc)[0], **{k: str(v) for k, v in r.items() if k != "_const"},
                   "control": str(round(2 - r["control_spread"], 4)), "help": h,
                   "tier": h.split()[0], "type": next(t for t in TYPES if t.split()[0] in h)}  # Toro: "Spin Cat"
    return out


_POW = "power (golf drive power multiplier, 0.945-1.21): a longer hitter hits harder"
_CON = "control = 2 - control_spread (the game's shot-spread multiplier, inverted): straighter, more accurate"
_IMP = "impact (impact-zone size multiplier; the novices have the biggest): a forgiving sweet spot, as HST's timing windows"
MAP = {
    "Serv POW": (["power"], _POW),
    "Strk POW": (["power"], _POW),
    "Voley POW": (["power"], _POW),
    "Strk CON": (["control"], _CON),
    "Voley CON": (["control"], _CON),
    "Serv CON": (["control"], _CON),
    "ショット ウサギIMP GI/NI/BI": (["impact"], _IMP + " (early side)"),
    "ショット カメIMP GI/NI/BI": (["impact"], _IMP + " (late side)"),
    "Top SPIN": (["spin"], "spin (backspin multiplier): more spin on the ball"),
    "Drop SPIN": (["spin"], "spin (backspin multiplier): more bite on drop shots"),
    "Slice SPIN": (["spin", "side"], "spin + side (side = how far the character curves the ball): sidespin"),
}


def style(pc):
    """(タイプ or None, why) from the help text's class. Control/Spin/Special describe shot quality, not court
    position, so they get none."""
    s = stats()[pc]
    t = {"All-rounder": "オール", "Big Hitter": "ビッグ"}.get(s["type"])
    return t, f"menu help: \"{s['help']}\"" + ("" if t else " (no tennis style follows from it)")


def heights():
    """{pc: (sex, cm, why)}: profile2 height (feet'inches"), sex from player.dat (0 = female, as the bios' pronouns)."""
    out = {}
    for pc, r in enumerate(_player()):
        h = _profile(pc)[4]
        m = re.match(r"(\d+)'(\d+)", h)
        cm = round((int(m[1]) * 12 + int(m[2])) * 2.54) if m else None
        out[pc] = ("fm"[r["sex"]], cm, f"profile2 pc{pc:02d}.dat height {h}; player.dat sex {r['sex']}")
    return out


# ---- voices ---------------------------------------------------------------------------------------------------

def sgxd(path):
    """{(group, index): (cue name, [(wave, semitones, ms, stop ms or None)])}, plus each wave's sample count. A SEQD
    note is `d0, n, n BCD digits` = program*128 + key (`d2` the same stops it); the RGND region with that key gives
    the wave and its root note (shift = key - root + fine/128 semitones; tools/audio.py writes the shifted rate into
    the exported wav). `f1, n, n BCD digits` waits that many ms (the cue header's tick rate is 1000)."""
    d = open(path, "rb").read()
    u = lambda o: struct.unpack_from("<I", d, o)[0]
    ch, o = {}, 0x10
    while o + 8 < len(d) and d[o:o + 4].isalpha():
        ch[d[o:o + 4].decode()] = o
        o += 8 + u(o + 4)
    r = ch["RGND"]
    progs = [[struct.unpack_from("<14I", d, u(r + 0x14 + 8 * p) + 0x38 * k) for k in range(u(r + 0x10 + 8 * p))]
             for p in range(u(r + 0xc))]
    w = ch["WAVE"]
    samples = [u(w + 0x30 + 0x38 * k) for k in range(u(w + 0xc))]
    s, cues = ch["SEQD"], {}
    for g in range(u(s + 0xc)):
        t = u(s + 0x10 + 4 * g)
        if not t:
            continue
        for i in range(u(t + 4)):
            o = u(t + 8 + 4 * i) & 0x7fffffff
            if not o:
                continue
            h = struct.unpack_from("<5I", d, o)
            body = d[o + 20:o + 20 + h[4]]
            name = d[h[1]:d.find(b"\0", h[1])].decode() if 0 < h[1] < len(d) else "?"
            notes, k, ms, on = [], 0, 0, {}
            while k < len(body):
                n = body[k + 1] if k + 1 < len(body) else 0
                bcd = body[k + 2:k + 2 + n].hex() if 1 <= n <= 2 else ""
                if body[k] == 0xf1 and bcd.isdigit():
                    ms += int(bcd)
                    k += 2 + n
                elif body[k] == 0xd2 and bcd.isdigit():
                    if int(bcd) in on:
                        i_ = on.pop(int(bcd))
                        notes[i_] = notes[i_][:3] + (ms,)
                    k += 2 + n
                elif body[k] == 0xd0 and bcd.isdigit():
                    p, key = divmod(int(bcd), 128)
                    rg = next((x for x in (progs[p] if p < len(progs) else [])
                               if (x[6] & 0xff) <= key <= (x[6] >> 8 & 0xff)), None)
                    if rg:
                        on[int(bcd)] = len(notes)
                        notes.append((rg[13], key - (rg[7] & 0xff) + (rg[7] >> 8 & 0xff) / 128, ms, None))
                    k += 2 + n
                else:
                    k += 1
            cues[(g, i)] = (name, notes)
    return cues, samples


def _bank(pc, kind):
    # .xb0 = the English takes (all 17 pcs); the .xb copy (pc00-14) is the Japanese cast (checked by speech recognition)
    f = glob.glob(_p(USR, f"sound/pc/ga_pc_{pc:02d}.xb0/data/sound/voice/game/pc/ga_{kind}_pc{pc:02d}.sgd"))[0]
    return f, _p(AUD, os.path.relpath(f, _p(USR)))


# The in-game bank ga_sg_pcNN has the same 58 SEQD slots (group 0: 42, group 1: 16 second takes) for everyone;
# the cue *names* are each actor's script lines (pc01: 04A-38E, Felipe: 20A-61) and pc00's are partly out of
# order, so the slot is the event. The profile screen's voice bank (me_pro_pcNN) names its groups in one numbering
# for all 17 and its "Play Animation" page (profile_chip04) lists Victory Pose, Reaction, Taunt 1, Taunt 2:
#   Victory Pose = 49A 49B 50A 51A = sg slots (0,29) (0,30) (0,31) (0,33)
#   Reaction     = 30 48 60A 39    = sg slots (0,10) (0,28) (0,40) (0,19)
#   Taunts       = 140-150         = ga_ya (yaji: heckling the other player's shot)
# (0,29)-(0,34) and their second takes (1,9)-(1,14) are one family (pc01 calls them all line 16A-16L; two are
# named Rare_Gattsu = rare guts pose): 6 hole-result reactions, multi-part cues timed to the ga_* clips.
# No table ties any other slot to a golf event (the program, HSG5PS3.self, is encrypted), so the events below were
# read off the lines themselves: every sg cue of all 17 transcribed with faster-whisper (opentennis B209); the
# same slot says the same thing in each actor's words. The family is NOT all celebrations: (0,29)/(1,9) is the
# disaster ("No! That was awful!", "Oh no! It's not there!"), (0,30)/(1,10) par (some sound let down), (0,31)/(1,11)
# and (0,33)/(1,13) the big wins, (0,32)/(1,12) a win that ends in a stumble ("Yeah! Ugh! Oops!"), (0,34)/(1,14)
# the caddie ("Don't touch me!"). Short lines: (0,6)/(1,3) effort grunts; (0,7)/(0,8) shot shouts ("Haya!",
# "Go!"); (0,9)/(0,10) "Fly!", "That's it!"; (0,12)/(0,14)/(1,15) "Oops!", "Whoops!", "No!"; (0,13)/(0,38) "Huh?",
# "What?"; (0,27)/(0,28)/(0,37)/(1,8) "It's in!", "Yes!", "I did it!"; (0,16)/(0,18)/(0,22)/(0,23)/(0,40)
# "Oh no!", "Aw man!", "What a shame!"; (0,24)/(0,25) "Oh, what a pity", "Next time!".
SHOUT = [(0, 6), (1, 3)]
STROKE = [(0, 8), (0, 7), (0, 9), (0, 10)]
MISHIT = [(0, 12), (0, 14), (1, 15)]
WHIFF = [(0, 38), (0, 13)]
WON = [(0, 28), (0, 37), (1, 8), (0, 27)]
LOST = [(0, 29), (0, 40), (0, 22), (0, 18), (0, 23), (0, 16)]
SET_LOST = [(0, 25), (0, 24)]  # the hole results come first, as the cues of their clips (RESULTS)
# takes that say something else in that actor's script (transcripts in notes/oob.md "Voice lines")
SKIP = {0: {(0, 7), (0, 37), (0, 40)}, 1: {(0, 40)}, 2: {(0, 29)}, 5: {(0, 33)}, 8: {(0, 12)}, 10: {(0, 30), (1, 10)},
        11: {(0, 12), (0, 30)}, 12: {(0, 16), (0, 37)}, 14: {(0, 23), (0, 27), (1, 10)}, 15: {(0, 40)}, 16: {(0, 7)},
        17: {(0, 12), (0, 37)}}
# The PSN edition's guests (pc17-19) keep the 58 slots, but Kratos's hole results are in a group 10 of their own
# (his (0,29)-(0,34) and (1,9)-(1,14) are empty): the big wins and the curse at the fates, by transcript. Toro's
# slots hold cat sounds already sorted by event; Sackboy is silent bar one birdie cue, as in LittleBigPlanet.
EXTRA = {}
# whiffs that grunt instead (user 2026-10-26: Alex's startled lines are her "Dear, dear, dear")
WHIFF_GRUNT = {15}
# The hole-result clips ga_pcNN_<suffix> and the cues the game plays with them: the slot (0,29)-(0,33) of the clip's
# result and its second take (1,9)-(1,13) (the DLC banks name the slots BOGY/PAR/BIRDIE/BIRDIE_R/EAGLE; each cue's
# notes are timed to its clip). Kratos's are in his group 10: the timed result cue (named Bogy, Par, Birdie, Birdie_R,
# Eagle_1) and his two lines of that result (49A-51A, 52A-54A, as the others' slots are named); Toro's in group 10 by
# name. The bogey goes with the lost game (program 10), the rest with the won (9). Every cue is used: a clip with two
# plays once per cue (package.py), each saying its own (standard §6 `extras.voice`).
RESULTS = {"bo_r00": [(0, 29), (1, 9)], "pa_r00": [(0, 30), (1, 10)], "bi_r00": [(0, 31), (1, 11)],
           "bi_r01": [(0, 32), (1, 12)], "ea_r00": [(0, 33), (1, 13)]}
OWN_RESULTS = {17: {"bo_r00": [(10, 5), (10, 0), (10, 10)], "pa_r00": [(10, 6), (10, 1), (10, 11)],
                    "bi_r00": [(10, 7), (10, 2), (10, 12)], "bi_r01": [(10, 8), (10, 13)],
                    "ea_r00": [(10, 9), (10, 4), (10, 14)]},
               18: {"bo_r00": [(10, 0)], "pa_r00": [(10, 1)], "bi_r00": [(10, 2)], "bi_r01": [(10, 3)], "ea_r00": [(10, 4)]},
               # Sackboy: only his birdie clip's cue; bi_r01's has no clip of his, so it played over the others
               19: {"bi_r00": RESULTS["bi_r00"]}}
CUES = "out/voices/oob_cues"


def _mix(notes, wd, dst):
    """A cue's notes, each from its ms (to its stop, if any), summed into one 44.1 kHz 16-bit wav (peak-limited)."""
    parts = []
    for w, _, ms, stop in notes:
        with wave.open(os.path.join(wd, f"{w + 1:03d}.wav")) as f:
            rate, x = f.getframerate(), np.frombuffer(f.readframes(f.getnframes()), "<i2").astype(np.float32)
            if f.getnchannels() > 1:
                x = x.reshape(-1, f.getnchannels()).mean(1)
        x = np.interp(np.arange(0, len(x) / rate, 1 / 44100) * rate, np.arange(len(x)), x)  # the wav's true rate
        a = round(ms * 44.1)
        parts.append((a, x[:round(stop * 44.1) - a] if stop is not None else x))
    out = np.zeros(max(a + len(x) for a, x in parts), np.float32)
    for a, x in parts:
        out[a:a + len(x)] += x
    out *= min(1.0, 32767 / max(1.0, float(np.abs(out).max())))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with wave.open(dst, "wb") as f:
        f.setnchannels(1), f.setsampwidth(2), f.setframerate(44100)
        f.writeframes(out.astype("<i2").tobytes())
    return dst


def results(pc):
    """{clip: [wav]}: each hole-result clip's cues (RESULTS), mixed whole (_mix) into out/voices/oob_cues/pcNN/;
    a cue with no note (Sackboy's bar the birdies) or one that repeats an earlier cue note for note is left out."""
    path, wd = _bank(pc, "sg")
    cues, _ = sgxd(path)
    out, seen = {}, set()
    for suffix, slots in OWN_RESULTS.get(pc, RESULTS).items():
        for sl in slots:
            notes = cues.get(sl, ("", []))[1]
            if not notes or tuple(notes) in seen:
                continue
            seen.add(tuple(notes))
            dst = _p(CUES, f"pc{pc:02d}/{sl[0]}_{sl[1]}.wav")
            out.setdefault(f"ga_pc{pc:02d}_{suffix}", []).append(dst if os.path.exists(dst) else _mix(notes, wd, dst))
    return out
# HST program 5, the cry of a player the ball hits (one key): golf has no such event, so per actor one short take of
# the English ga_ev/ga_sg/ga_vs banks (bank/wave) picked by transcript: a pain word first ('Ouch!', 'Ow'), else a
# pained yelp ('Ugh!', 'Gah!', 'Wah!', うっ), else a startled 'Ah!'/'Oh!'; a wave other actors share is never one
# (opentennis B560, transcripts in notes/oob.md "Voice lines")
HIT = {0: "ev/009", 1: "sg/052", 2: "ev/008", 3: "vs/015", 4: "sg/055", 5: "sg/015", 6: "ev/038", 7: "ev/010",
       8: "sg/059", 9: "ev/009", 10: "ev/008", 11: "ev/005", 12: "sg/053", 13: "ev/015", 14: "vs/015", 15: "sg/014",
       16: "vs/015", 17: "ev/004"}  # Oh! うっ あ! Wah! Ugh! Ouch! Ah! UGH! Ah! Oh! Ow GAH! あ! D'AH! Ow. あ! Ah! UGH!


def hit_cry(pc):
    """[wav] for program 5 (HIT), or []."""
    if pc not in HIT:
        return []
    kind, w = HIT[pc].split("/")
    f = os.path.join(_bank(pc, kind)[1], f"{w}.wav")
    return [f] if os.path.exists(f) else []


def voices(pc):
    """({program: [wav]}, {program: why}). Each cue gives one file: its longest note's wave (a celebration cue
    plays 2-17 fragments in sequence; the wav is the main one)."""
    path, wd = _bank(pc, "sg")
    cues, samples = sgxd(path)

    def files(slots):
        out = []
        for sl in slots:
            if sl in SKIP.get(pc, ()):
                continue
            name, notes = cues.get(sl, ("", []))
            if not notes or "dummy" in name:
                continue
            w = max(notes, key=lambda n: samples[n[0]])[0]
            f = os.path.join(wd, f"{w + 1:03d}.wav")
            if os.path.exists(f) and f not in out:  # some banks reuse one wave for two slots
                out.append(f)
        return out

    res = results(pc)
    prog = {0: files(SHOUT), 1: files(STROKE), 2: files(MISHIT), 3: files(SHOUT),
            4: files(SHOUT if pc in WHIFF_GRUNT else WHIFF),
            5: hit_cry(pc), 7: files(WON), 8: files(LOST),
            9: [w for c, ws in res.items() if not c.endswith("bo_r00") for w in ws],
            10: [w for c, ws in res.items() if c.endswith("bo_r00") for w in ws] + files(SET_LOST)}
    for p, slots in EXTRA.get(pc, {}).items():
        prog[p] += [f for f in files(slots) if f not in prog[p]]
    why = {0: "sg (0,6)/(1,3): the effort grunts ('Hah!', 'Hup!'; the shortest line in every bank)",
           1: "sg (0,8)/(0,7)/(0,9)/(0,10): the shot shouts ('Hya!', 'Go!', 'Fly!', 'That's it!')",
           2: "sg (0,12)/(0,14)/(1,15): 'Oops!', 'Whoops!', 'No!'",
           3: "the effort grunts of program 0 (no dive in golf)",
           4: "the effort grunts of program 0 (WHIFF_GRUNT)" if pc in WHIFF_GRUNT else "sg (0,38)/(0,13): 'Huh?', 'What?'",
           5: f"{HIT.get(pc)}: no hit-by-the-ball line in golf; the actor's most pained short take (HIT)",
           7: "sg (0,28)/(0,37)/(1,8)/(0,27): the holed-putt lines ('Yes!', 'It's in!', 'I did it!')",
           8: "sg (0,29) the disaster hole result (e.g. 'No! That was awful!') and (0,40)/(0,22)/(0,18)/(0,23)/(0,16) "
              "the missed-shot lines ('Aw, shoot!', 'Oh no!', 'What a shame!')",
           9: "the birdie, eagle and par results' whole cues as the game times them to their clips (RESULTS), "
              "each the line of its own take",
           10: "the bogey result's whole cues (RESULTS), each the line of its take, then the resigned (0,25)/(0,24) "
               "('Next time!', 'Oh, what a pity')",
           6: "no partner call in golf; the taunts (ga_ya, lines 140-150) heckle the opponent, not a partner"}
    why = {p: w + " (sorted by what the lines say: notes/oob.md 'Voice lines')" if p != 6 else w for p, w in why.items()}
    prog = {p: f for p, f in prog.items() if f}
    # pitch: tools/audio.py writes each wave's true rate (RGND key/root/fine) into the wav header
    return prog, why


# ---- reactions ------------------------------------------------------------------------------------------------

SLUGS = {int(os.path.basename(f)[2:4]): f for f in glob.glob(_p("out/anims/oob/pc*.glb"))}


def _glb(f):
    d = open(f, "rb").read()
    n = struct.unpack_from("<I", d, 12)[0]
    j = json.loads(d[20:20 + n])
    return j, d, 28 + n


def _acc(j, d, bo, i):
    a, comp = j["accessors"][i], {"SCALAR": 1, "VEC3": 3, "VEC4": 4}
    v = j["bufferViews"][a["bufferView"]]
    c = comp[a["type"]]
    return np.frombuffer(d, np.float32, a["count"] * c, bo + v.get("byteOffset", 0) + a.get("byteOffset", 0)).reshape(-1, c)


def _clips(f):
    """{name: (frames at 60 Hz, pelvis horizontal travel in model units)}."""
    j, d, bo = _glb(f)
    pelvis = next(i for i, nd in enumerate(j["nodes"]) if nd.get("name") == "Bip01Pelvis")
    out = {}
    for a in j["animations"]:
        t = max(j["accessors"][s["input"]]["max"][0] for s in a["samplers"])
        move = 0.0
        for c in a["channels"]:
            if c["target"].get("node") == pelvis and c["target"]["path"] == "translation":
                p = _acc(j, d, bo, a["samplers"][c["sampler"]]["output"])
                move = float(np.ptp(p[:, [0, 2]], axis=0).max())
        out[a["name"]] = (round(t * 60), move)
    return out


# Meanings from the names (ku = the shared emote set: ga guts pose, di disappointed; ga_* = hole-result clips:
# ea/bi/pa/bo = eagle/birdie/par/bogey) and checked against each clip's face-morph channel: ku_ga / ga_bi /
# rslt_win drive smile+laugh targets, ku_di anger, ga_bo / rslt_loss sorrow (or sad/scowl).
PICK = {"re_gu": (r"ku\d\d_ga$", "ku_ga, the guts-pose emote (smile/laugh face)"),
        "re_di": (r"ku\d\d_di$", "ku_di, the disappointed emote (anger/sad face)"),
        "re_gu_set": (r"ga_pc\d\d_bi_r00$", "ga_bi_r00, the birdie celebration (smile face; ~90 frames like "
                                             "re_gu_set; rslt_win is 120)"),
        "re_di_set": (r"ga_pc\d\d_bo_r00$", "ga_bo_r00, the bogey reaction (sorrow face; ~95 frames like "
                                             "re_di_set; rslt_loss is 90)")}


def reactions(pc):
    """(glb, {hst: [intro]}, {hst: why}). One clip each, no loop. Times are as exported (60 Hz); the pelvis
    carries root motion (travel given in the why): package.py holds the root (PIN)."""
    f = SLUGS[pc]
    cl = _clips(f)
    clips, why = {}, {}
    for hst, (rx, w) in PICK.items():
        c = next((n for n in cl if re.match(rx, n)), None)
        if c:
            clips[hst] = [c]
            why[hst] = f"{c} ({cl[c][0]} frames, pelvis travel {cl[c][1]:.2f}): {w}"
    return f, clips, why


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gag_stats
    st, hs = stats(), heights()
    tp = gag_stats.find_tparam(ROOT)
    if tp:
        head, _ = gag_stats.tparam(tp)
        assert all(gag_stats.squash(c) in head for c in MAP), [c for c in MAP if gag_stats.squash(c) not in head]
    # self-check of the help-text order: flags the text names must be the ones player.dat has
    for pc, s in st.items():
        for word, k, v in (("rough", "rough", "-1"), ("rain", "rain", "-1"), ("draw", "curve", "1"),
                           ("fade", "curve", "-1"), ("good in the bunkers", "bunker", "1"), ("approach", "approach", "-1")):
            assert word not in s["help"] or s[k] == v, (pc, word)
    for pc, s in st.items():
        v, vw = voices(pc)
        g, cl, _ = reactions(pc)
        print(f"pc{pc:02d} {s['name']:<14} {hs[pc][0]} {hs[pc][1]}cm pow {s['power']} con {s['control']} "
              f"imp {s['impact']} spin {s['spin']} side {s['side']} | {s['tier']} {s['type']} -> {style(pc)[0]}")
        print("      voices", {p: len(f) for p, f in sorted(v.items())}, vw.get("pitch", ""))
        print("      reactions", {k: c[0] for k, c in cl.items()})
    print("override check:", {c: o for c, o in list(gag_stats.overrides(st, tp, MAP, {p: style(p) for p in st})[9][0].items())} if tp else "no TParam")
