"""Hot Shots Golf Fore! (PS2, SCUS-97401) character data for HST mods (notes/fore.md "Mod data").
Everything is read at run time from extracted/fore and out/ (never committed).

stats(), MAP, style(pc), heights(), voices(pc), reactions(pc) as package.py / gag_stats.py / sizing.py expect.
`python3 tools/rerig/fore_data.py` prints the whole cast.
"""
import glob
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYSTEM = "extracted/fore/ZZBIN/SYSTEM.BIN"
BASE = 0x22CC80      # SYSTEM.BIN load address (its own jal targets land on its function starts; the pointer list checks it)
NAMES = 0xFDE40      # 24 × 0x40 character records: body type, unlock, name[16] @2, 3-letter voice code @0x12
PTRS = 0x136430      # 24 pointers to those records (GAME.BIN's player struct keeps one)
STATS = 0x136490     # 24 × 0x20 stat records: 5 floats, then signed bytes (club / ball tables use the same 5 floats)
SLUG = ["phoebe", "mike", "emma", "sam", "misaki", "brad", "chaos", "regis", "maya", "falcon", "renee", "z", "mel",
        "allan", "tiffany", "kamala", "toni", "tbone", "lin", "louise", "zeus", "hubert", "ratchet", "jak"]


def _p(*a):
    return os.path.join(ROOT, *a)


def _sys():
    b = open(_p(SYSTEM), "rb").read()
    for i in range(24):
        assert struct.unpack_from("<I", b, PTRS + 4 * i)[0] == BASE + NAMES + 0x40 * i, "not SCUS-97401's SYSTEM.BIN"
    return b


def roster():
    """{pc: (name, voice code, body type)} from SYSTEM.BIN's character records."""
    b = _sys()
    out = {}
    for i in range(24):
        r = b[NAMES + 0x40 * i:NAMES + 0x40 * (i + 1)]
        out[i] = (r[2:18].split(b"\0")[0].decode(), r[0x12:0x15].decode().lower(), r[0])
    return out


def raw():
    """{pc: (5 floats, 12 signed bytes)} as stored."""
    b = _sys()
    return {i: (struct.unpack_from("<5f", b, STATS + 0x20 * i), struct.unpack_from("<12b", b, STATS + 0x20 * i + 20))
            for i in range(24)}


def stats():
    """{pc: {stat: str}}. Floats 0-3 of the stat record, by position (1.0 = average):
    Power  = float 0, the shot-power multiplier (code: driver power = it + club + ball; Z/Jak 1.17 top, Emma/Regis 0.98).
    Control = 2 - float 1, INVERTED: float 1 is lower-is-better (every club/ball that raises it gives power or
             spin, every one that lowers it costs impact or float 4: a penalty, i.e. dispersion).
    Impact = float 2, impact-zone size (beginners Emma/Regis 1.25, experts Z/Jak 0.75; capped in code; every
             upgraded club costs 0.07-0.15 of it, as forgiveness traded for performance).
    Spin   = float 3 (spin clubs/balls raise it).
    Float 4 (0.6-1.2, 1.0 for most) and the bytes (three -1/0/+1 flags, one 8-15 value) are not identified."""
    return {pc: {"Power": f"{f[0]:.2f}", "Control": f"{2 - f[1]:.2f}", "Impact": f"{f[2]:.2f}", "Spin": f"{f[3]:.2f}",
                 "Float4": f"{f[4]:.2f}"} for pc, (f, _) in raw().items()}


_POW = "Power (Fore's shot-power multiplier, SYSTEM.BIN stat float 0): longer hitter, harder strokes"
_IMP = "Impact (Fore's impact-zone size, stat float 2; beginners biggest): a forgiving sweet spot, as HST's timing windows"
MAP = {c: (["Power"], _POW) for c in ("Serv POW", "Strk POW", "LOW POW", "Voley POW", "V LOW POW", "Lob POW")}
MAP.update({c: (["Control"], "Control (2 − stat float 1, which is lower-is-better dispersion): straighter strokes")
            for c in ("Strk CON", "Voley CON", "Serv CON")})
MAP.update({c: (["Impact"], _IMP) for c in ("ショット ウサギIMP GI/NI/BI", "ショット カメIMP GI/NI/BI")})
MAP.update({c: (["Spin"], "Spin (Fore's spin, stat float 3)") for c in ("Top SPIN", "Slice SPIN", "Drop SPIN")})


def style(pc):
    return None, ("no play style in the data: Fore's stat record has -1/0/+1 flags (likely shot curve/trajectory, "
                  "unconfirmed) that do not describe a tennis style")


# Body types 0 and 3 are shared templates (0: six women with skirt/hair bones; 3: Sam, Maya, Falcon, Allan, Toni,
# Zeus, Jak). The others are one-off bodies; sex for those is from the roster, not the data.
_SEX_ONE_OFF = {1: "m", 2: "f", 5: "m", 6: "m", 7: "m", 10: "f", 11: "m", 12: "f", 17: "m", 21: "m", 22: "m"}


def heights():
    """{pc: (sex, None, why)}: Fore has no heights in its data (the character record holds only body type, name, voice
    code and flags), so each keeps its own model height."""
    out = {}
    for pc, (name, _, body) in roster().items():
        if body in (0, 3):
            sx, how = ("f" if body == 0 else "m"), f"body template t{body:02d} (shared, {'women' if body == 0 else 'men'})"
        else:
            sx, how = _SEX_ONE_OFF[pc], f"one-off body t{body:02d}; sex from the roster, not the data"
        out[pc] = (sx, None, f"Fore's SYSTEM.BIN character record has no height or sex; {how}")
    return out


# ---- voices ---------------------------------------------------------------------------------------------------

# Voice picks per character, sorted by what each take says (every cue transcribed with faster-whisper small, English;
# opentennis B562). Fore! has no effort shout and no event that matches a tennis program one to one, so each program
# gets the takes whose words fit it:
#   0/1/3 stroke shouts: short (about a second at most) power / "yes" exclamations only (jy0/jy1 mostly, a few one-word co/ya/sc
#         lines); never a sentence or a bad-shot line, they play on most strokes.
#   2 mis-hit, 4 whiff: short bad-shot / surprised lines (jy2 mostly, "Oops."-type co/ya lines).
#   7 point won, 9 set won: the par/birdie/eagle celebrations (g) that say something happy, co/sc boasts, and for 9
#         the versus-result lines (vs) that are a win.
#   8 point lost, 10 set lost: laments only (jy2/jy3/jy4 groans, co/sc "not my day" lines, the losing vs lines, the
#         bogey g bank when it is a lament: Fore!'s bogey is often a laugh, e.g. Hubert's, and then it is left out).
#   5 (hit by the ball), 6 (partner calls): none, see notes/fore.md.
# Tags: jyN / gN = bank jy_<code>N / g_<code>N (g: 1 bogey, 2 par, 3/4 birdie, 5/6 eagle, by the costume-0
# celebration archive PCNN00SS.XB each sits in, its ga_ motion naming the result; Z's 7-10 are extra takes);
# co.N / ya.N = take N of co_<code> / ya_<code>; vsNN / scNN = bank vs_<code>NN / sc_<code>NN (vsNN.K / scNN.K: take K,
# else the first). Transcripts stay out of git (game data); notes/fore.md "Voices" says how to rebuild them.
PICKS = {
    0: {0: "jy0 jy1", 1: "jy0 jy1 ya.3 co.10", 3: "jy1 jy0", 2: "co.7 jy2", 4: "co.13",
        7: "g2 g4 co.11 co.10", 8: "sc15 co.7 co.4 sc18", 9: "g5 g4 vs00 vs02", 10: "vs07 vs06 vs04 vs05"},
    1: {0: "co.11 jy1 co.8", 1: "co.8 co.4 vs00.3 co.11 jy1", 3: "co.1 co.11 co.8", 2: "jy3 co.7 sc16", 4: "co.7 jy0",
        7: "g2 g3 g4 sc14 co.5", 8: "g1 sc16 sc18 co.12 vs00.6", 9: "g5 g3 vs00.2 vs00.3 vs00.4",
        10: "vs00.8 vs00.7 vs00.6 g1 vs00.5"},
    2: {0: "jy1 jy0", 1: "jy1 jy0 ya.3 sc03", 3: "jy1 jy0 sc03", 2: "co.6 jy2", 4: "co.6 jy2",
        7: "g2 g3 co.2 co.1", 8: "g1 jy4 co.6 sc17", 9: "g4 g3 co.2 vs02", 10: "vs05 vs07 vs04 g1 jy4"},
    3: {0: "jy0 jy1 ya.1", 1: "jy0 jy1 ya.1 ya.3 ya.2", 3: "jy0 jy1 ya.1", 2: "jy3 jy2", 4: "jy3",
        7: "g2 g3 g4 co.1", 8: "g1 jy3 sc19 vs06", 9: "g5 g6 vs00 g2", 10: "vs06 vs07 g1 sc19"},
    4: {0: "jy0 ya.6", 1: "jy0 ya.6", 3: "jy0 ya.6", 2: "jy2 sc14", 4: "sc14 ya.2",
        7: "co.2 g2 g4 co.1", 8: "g1 sc14 co.10", 9: "vs02 g4 g3 vs00", 10: "vs05 vs06 g1"},
    5: {0: "jy3 jy0 ya.11", 1: "jy3 jy4 ya.3 jy0", 3: "jy3 jy0 ya.11", 2: "jy2", 4: "jy2",
        7: "g2 g3 g4 vs00", 8: "g1 jy2 sc21", 9: "g5 vs00 g3", 10: "vs06 sc21 g1 vs07"},
    6: {0: "jy0 jy1 ya.6", 1: "jy0 jy1 ya.6", 3: "ya.6 jy1 jy0", 2: "jy4 jy2", 4: "jy4 jy2",
        7: "co.1 g2 g3 g4", 8: "g1 jy4 co.3", 9: "g5 g2 co.11", 10: "co.3 g1 jy4"},
    7: {0: "ya.8 jy1 co.1", 1: "ya.8 jy1 co.1 jy0", 3: "ya.8 jy0 jy1", 2: "jy3 jy2", 4: "jy3",
        7: "g2 g4 co.4 co.11", 8: "g1 jy2 sc14", 9: "g5 g3 co.5 jy5", 10: "g1 sc14 vs04"},
    8: {0: "co.1", 1: "co.1 co.4 sc01", 3: "co.1", 2: "jy1 jy4 jy0", 4: "jy0",
        7: "g2 g3 g4 co.5", 8: "jy4 co.6 co.13 sc16", 9: "g5 g4 sc01 co.11", 10: "co.13 co.6 vs04 vs05 sc16"},
    9: {0: "jy0 jy1", 1: "jy0 jy1", 3: "jy1 jy0", 2: "jy2 co.3", 4: "ya.6 jy2",
        7: "g2 g4 co.4 co.5", 8: "co.7 jy2 co.6", 9: "co.1 g5 vs00 g4", 10: "vs07 vs06 vs04 co.7"},
    10: {0: "jy0 ya.11", 1: "jy0 ya.11 jy1", 3: "jy0 jy1 ya.11", 2: "jy2 co.8", 4: "jy2 co.8",
         7: "g2 g3 jy4 g4", 8: "g1 jy2 co.12", 9: "g5 g4 vs00 vs03", 10: "g1 vs05"},
    11: {0: "jy1 ya.9 co.4", 1: "jy1 ya.9 co.9 co.4", 3: "jy1 ya.9", 2: "jy2 co.6", 4: "jy2 co.8",
         7: "g3 g2 g8 co.11", 8: "g1 jy2 sc21 vs07", 9: "g5 g10 vs00 vs01", 10: "vs06 vs04 vs07 g1"},
    12: {0: "jy1 jy0", 1: "jy0 jy1 jy3 jy2", 3: "jy1 jy0 jy3", 2: "sc21 co.7", 4: "sc21",
         7: "co.1 co.8 g3 co.13", 8: "g1 co.3 vs07 sc23", 9: "co.2 g6 g4 vs00", 10: "vs07 vs04 g1 sc23"},
    13: {0: "jy1 jy0", 1: "jy0 jy1", 3: "jy1 jy0", 2: "jy2 co.6 ya.7", 4: "ya.7 jy2",
         7: "g2 g3 sc07 jy6", 8: "jy4 co.6 ya.7", 9: "g5 g4 vs07 g6 g1", 10: "vs05 vs04 jy4 co.6"},
    14: {0: "jy0 jy1 co.6", 1: "jy0 jy1 co.6 ya.3 ya.2", 3: "jy0 co.6 ya.2", 2: "jy2 ya.7 jy3", 4: "ya.7 jy2",
         7: "g2 g3 co.4 co.2", 8: "g1 jy4 jy3", 9: "g5 g6 sc05 vs02", 10: "vs05 vs07 g1 vs06"},
    15: {0: "jy1 jy0", 1: "jy1 jy0", 3: "jy1 jy0", 2: "jy3 jy4", 4: "jy3",
         7: "g3 g5 co.1 vs01", 8: "jy4 co.7 vs06", 9: "g6 vs07 vs01 g3 g5", 10: "vs06 co.7 jy4"},
    16: {0: "jy3 sc05", 1: "sc05 jy3 ya.2", 3: "sc05 jy3", 2: "co.7 jy2", 4: "co.7 jy2",
         7: "g3 g5 co.5 co.2", 8: "g1 jy4 co.7 co.3", 9: "g6 g4 vs02 vs01 g2", 10: "jy4 g1 co.3"},
    17: {0: "jy1 jy2", 1: "jy1 jy2 co.5", 3: "jy1 jy2", 2: "sc23", 4: "jy2",
         # 9: not g6, whose line opens on 1.2 s of wordless rising hiss (opentennis B592)
         7: "g2 g3 g4 sc14", 8: "sc23 vs06 co.10", 9: "g5 vs01 co.1 vs03", 10: "vs06 sc23 co.10"},
    18: {0: "sc08 ya.1", 1: "sc08 ya.1 jy3 ya.11", 3: "sc08 ya.1", 2: "jy0 co.6", 4: "jy0",
         7: "g3 co.2 sc07 sc01", 8: "co.6 sc17 co.10 g1", 9: "co.11 g3 jy5 g4", 10: "vs06 vs05 sc17 co.10"},
    19: {0: "jy4 jy0", 1: "jy4 jy0 jy2", 3: "jy4 jy0", 2: "co.7 ya.6", 4: "co.7",
         7: "g3 g2 co.2 sc08", 8: "g1 vs04 ya.6 sc21", 9: "g6 vs01 g3 sc08", 10: "vs04 vs07 vs05 sc21 g1"},
    20: {0: "jy1 sc08", 1: "jy1 sc08", 3: "jy1", 2: "jy2", 4: "jy0",
         7: "co.2 co.1 g5 g4", 8: "g1 co.6 co.7 co.3", 9: "vs00 vs02 g4 g5 vs03", 10: "vs04 co.3 g1 co.7"},
    21: {0: "jy1 jy0", 1: "jy1 jy0", 3: "jy1 jy0", 2: "jy2 jy3", 4: "jy2",
         7: "g3 g4 co.4 g2", 8: "jy3 jy2 co.12 vs07", 9: "g6 g5 vs00 vs01", 10: "vs07 vs06 co.12 jy3"},
    22: {0: "jy0 jy1", 1: "jy0 jy1 co.5", 3: "jy0 jy1", 2: "jy4 jy2", 4: "jy2",
         7: "g2 g4 g3 co.10", 8: "g1 jy4 jy3 vs04", 9: "g5 g6 jy5 vs01 vs00", 10: "vs04 vs06 vs07 g1 vs05"},
    23: {0: "jy0 jy4", 1: "jy0 jy4 ya.2 ya.7", 3: "jy0 jy4", 2: "jy2 co.10", 4: "jy2",
         7: "g6 co.5 g2 co.3", 8: "co.10 sc15.1 jy2 g1", 9: "g4 vs01 vs02 vs00 co.4", 10: "vs03 vs07 vs04 g1 co.10"},
}
WHY = {0: "short power / 'yes' exclamations only, picked by transcript (Fore! has no effort shout)",
       1: "short good-shot exclamations, picked by transcript (no sentences, no bad-shot lines)",
       2: "short bad-shot lines (jy groans, 'oops'-type comments), picked by transcript",
       3: "same kind as program 0: short exclamations (golf has no dive)",
       4: "short surprised / bad-shot lines or a groan, picked by transcript (golf has no whiff voice; no sentences)",
       6: "none: golf has no partner calls (sc/vs are per-opponent and versus-result lines)",
       7: "happy par/birdie celebrations (g) and boasts (co/sc), picked by transcript",
       8: "laments only: groans, 'not my day' comments, the bogey line when it is one (Fore!'s bogey is often a laugh)",
       9: "happy eagle/birdie celebrations and winning versus-result lines (vs), picked by transcript",
       10: "losing versus-result lines and laments, picked by transcript"}


def _tag(pc, code, t):
    """One PICKS tag -> its wav (see PICKS)."""
    m = re.fullmatch(r"(jy|g|co|ya|vs|sc)(\d*)(?:\.(\d+))?", t)
    k, bank, take = m.groups()
    name = f"{k}_{code}{bank}_{int(take or 1):03d}" if k in ("vs", "sc") or bank else f"{k}_{code}_{int(take):03d}"
    f = _p(f"out/voices/fore/pc{pc:02d}/{name}.wav")
    assert os.path.exists(f), f
    return f


def voices(pc):
    """({program: [wav]}, {program: why}) from PICKS. jy5/6 (played after a timed wait: encouragement aimed at the
    other player) and mepc (menu banter) are not used."""
    code = roster()[pc][1]
    prog = {p: [_tag(pc, code, t) for t in tags.split()] for p, tags in PICKS[pc].items()}
    return prog, {k: w for k, w in WHY.items() if k in prog or k == 6}


# ---- reactions ------------------------------------------------------------------------------------------------

def _anim_names(f):
    b = open(f, "rb").read()
    n, = struct.unpack_from("<I", b, 12)
    return {a["name"] for a in json.loads(b[20:20 + n])["animations"]}


def reactions(pc):
    """(glb, {hst: [intro]}, {hst: why}). Fore clips run at 60 Hz as exported; package.py retimes to the donor's.
    No loops: Fore's clips end in a still pose. Root translation measured on Bip01 (start -> end, ground plane)."""
    n = f"{pc:02d}"
    f = _p(f"out/anims/fore/pc{n}_{SLUG[pc]}_c00-03.glb")
    if not os.path.exists(f):
        return f, {}, {}
    a = _anim_names(f)
    pick = lambda *c: next((x for x in c if x in a), None)
    choice = {"re_gu": (pick(f"re_pc{n}_tp", f"re_pc{n}_lp"), "the happy short shot reaction (tp, else lp; smile/joy face, "
                                                             "0.5-1.2 s, root moves ≤ 0.4 m)"),
              "re_di": (pick(f"re_pc{n}_ga", f"re_pc{n}_os"), "re_ga (がっかり, sorrow/anger face, 1.1-1.5 s, root ≤ 0.2 m)"),
              "re_gu_set": (pick(f"win_{n}", f"ga_pc{n}_ea_r00"), "win, the results screen's winner (4.0 s, no root motion)"),
              "re_di_set": (pick(f"lost_{n}", f"ga_pc{n}_bo_r00"), "lost, the results screen's loser (3.0 s, root drifts "
                                                                   "≤ 0.6 m: package.py pins it)")}
    return f, {k: [c] for k, (c, _) in choice.items() if c}, {k: w for k, (c, w) in choice.items() if c}


if __name__ == "__main__":
    st, hs, ro = stats(), heights(), roster()
    assert [ro[i][0] for i in (0, 11, 22, 23)] == ["Phoebe", "Z", "Ratchet", "Jak"]
    assert all(set(MAP[c][0]) <= set(st[0]) for c in MAP)
    print("pc name     sex  " + " ".join(f"{k:>7}" for k in st[0]) + "  voices{prog:n}  reactions")
    for pc in range(24):
        prog, _ = voices(pc)
        _, cl, _ = reactions(pc)
        print(f"{pc:02d} {ro[pc][0]:8} {hs[pc][0]}    " + " ".join(f"{v:>7}" for v in st[pc].values()),
              "{" + ", ".join(f"{k}:{len(v)}" for k, v in sorted(prog.items())) + "}",
              {k: v[0] for k, v in cl.items()})
