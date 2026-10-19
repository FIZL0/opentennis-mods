"""More takes for a golf mod's voice programs, picked by what the character's unused English lines say.

fill(game, pc, prog, why) -> (prog, why): after a data module's own picks (fore_data / oob_data / opentee_data
`voices`), each program gets more of the character's own lines up to MAX (HST's key count for the shouts 0-5; for
the reactions 7-10 more than HST draws today, so a player that cycles through every take has them). A line is taken
only when its whole transcript is one of a program's phrases (RULES) and it is short enough; lines that name golf
(GOLF), address someone ("you"), name a person (a capitalised word mid-line) or ask a question (bar 2/4, which are
the startled ones) are never taken.

The transcripts are faster-whisper's, cached by tools/voice_candidates.py in out/voice_candidates/.transcripts.json
(game data, git-ignored; run that tool first, with faster-whisper installed). Without the cache nothing is added.
Sources are voice_candidates.sources(): the English banks only (never the Japanese copies: other actors), less any
sample another character of the game also has (shared effects). OOB's yaji bank (ga_ya: taunts at the other player)
is left out.
"""
import hashlib
import json
import os
import re
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import voice_candidates as vc  # noqa: E402

CACHE = os.path.join(ROOT, "out/voice_candidates/.transcripts.json")
# takes per program: HST's keys for 0-5 (standard §5), 7-10 up to 8
MAX = {0: 3, 1: 5, 2: 3, 3: 3, 4: 2, 5: 1, 7: 8, 8: 8, 9: 8, 10: 8}
N = {"fore": 24, "oob": 17, "opentee2": 21}

# whole-line phrases per program (lower case, punctuation stripped, a phrase may repeat: "go go"), and the longest
# take in seconds. 0/3 are wordless effort grunts, 1 the shot shouts, 2 a slip, 4 a startled whiff, 5 a pained cry.
EFFORT = r"(hah?|hup|hy?ah?|hi?ya+h?|ho+h?|hoo+|ya+h?|tah|toh|heh|hn+|nn+h?|hng|hm+ph|ei|eya|ora|sei|yo+sh)"
RULES = {
    0: (rf"{EFFORT}( {EFFORT})*", 0.7),
    3: (rf"{EFFORT}( {EFFORT})*", 0.7),
    1: (r"(go|go go|go on|fly|fly fly|take that|there|yes|yeah|yah|nice|that's it|all ?right|get in|let's go|here goes|"
        r"perfect|got it|i got it|yep|okay go|right there|good)", 1.0),
    2: (r"(oops|whoops|whoopsie|oopsie|uh[- ]?oh|oh no|no+|darn|dang|shoot|oh dear|yikes|whoa|oh shoot|oh man|ack|eek)", 1.1),
    4: (r"(huh|what|eh|hm+|wha|what the|ehh+|really|whoa|wait|hey)", 1.0),
    5: (r"(ouch|ow+|oww+|ugh|argh+|oof|gah|ouf|agh|ah ouch|ow ow)", 0.9),
    7: (r"(yes+|yeah+|yay|all ?right|i did it|did it|nice|great|perfect|got it|i got it|woo+(hoo+)?|yahoo|awesome|"
        r"excellent|it's in|fantastic|amazing|wonderful|lucky|hooray|ha ha|haha|hahaha|beautiful|easy|bingo|"
        r"that's it|that's the way|way to go|there we go|there you go|yes yes|oh yeah|all right|alright|good|very good|"
        r"how's that|how about that|yes i did it|i'm the best|victory|bravo|super|brilliant|piece of cake|oh yes|"
        r"nailed it|bullseye|right on|sweet|cool|whoo+|yippee|woohoo|yeehaw|yes good|good one|i'm good|"
        r"(yes|yeah|alright|all right|great|nice|perfect|awesome)( (yes|yeah|alright|all right|great|nice|perfect|"
        r"awesome|i did it|it's in|that's it|good))+)", 2.5),
    8: (r"(no+|oh no+|no no+|aw+|aww+ man|oh man|shoot|aw shoot|darn|dang|darn it|dang it|rats|nuts|geez|jeez|"
        r"what a shame|what a pity|oh well|too bad|bad luck|unlucky|so close|almost|not again|why|but why|oh why|"
        r"terrible|awful|that was awful|i messed up|i blew it|that's bad|how could i|i can't believe it|"
        r"damn|ugh|argh|blast|drat|next time|maybe next time|oh dear|not good|no good|that's no good|"
        r"what a pity|pity|shame|i lost|darn it all|no way|oh no no|no no no|"
        r"(oh|aw|ah|no|ugh)( (no+|shoot|darn|man|why|well|dear|terrible|awful|not again|rats|nuts))+)", 2.5),
}
RULES[9] = (RULES[7][0], 3.5)
RULES[10] = (RULES[8][0], 3.5)
GOLF = re.compile(r"\b(hole|holes|putt|putts|putting|birdie|eagle|albatross|par|bogey|green|greens|bunker|fairway|club|"
                  r"clubs|caddie|caddy|cuddy|tee|rough|bounds|cup|pin|flag|wind|course|golf|golfer|iron|wood|driver|"
                  r"fore|four|chip|hole in one|ob|water|sand|lie|score|card|round|stroke|strokes)\b")


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z' ]", " ", t.lower().replace("-", " "))).strip()


def _ok(text):
    """a line any program may take: English words only, no golf, nobody addressed or named"""
    if not text or GOLF.search(_norm(text)) or re.search(r"\byou(r|'re)?\b", _norm(text)):
        return False
    toks = re.findall(r"[A-Za-z']+|[.!?]", text)
    first = {0} | {i + 1 for i, w in enumerate(toks) if w in ".!?"}
    names = [w for i, w in enumerate(toks) if w[:1].isupper() and w not in ("I", "I'm", "I'll", "I've", "OK", "Okay")
             and i not in first]
    return any(w not in ".!?" for w in toks) and not names


def _md5(f):
    return hashlib.md5(open(f, "rb").read()).hexdigest()


def _dur(f):
    with wave.open(f) as w:
        return w.getnframes() / w.getframerate()


_shared = {}


def _english(game, pc):
    """{md5: wav} of the character's English lines no other character of the game has"""
    if game not in _shared:
        owners = {}
        for p in range(N[game]):
            for f in vc.sources(game, p)[0]:
                owners.setdefault(_md5(f), set()).add(p)
        _shared[game] = owners
    out = {}
    for f in sorted(vc.sources(game, pc)[0]):
        if game == "oob" and re.search(r"/ga_ya_pc\d\d\.sgd/", f):
            continue
        h = _md5(f)
        if _shared[game].get(h) == {pc}:
            out.setdefault(h, f)
    return out


def candidates(game, pc, cache=None):
    """{program: [(wav, transcript)]} of the character's lines each program's rule takes, shortest first for the shouts
    (0-5) and the reaction lines in source order"""
    if cache is None:
        cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    out = {p: [] for p in RULES}
    for h, f in _english(game, pc).items():
        if h not in cache:
            continue
        text, lang, prob = cache[h]
        if lang != "en" and prob > 0.6:
            continue
        n = _norm(text)
        d = _dur(f)
        for p, (rule, longest) in RULES.items():
            if d > longest or not re.fullmatch(rule, n):
                continue
            if p not in (2, 4) and "?" in text:
                continue
            if p in (0, 3, 5) and not n:
                continue
            if p not in (0, 3) and not _ok(text):
                continue
            if p in (9, 10) and d < 0.6:  # the game- and set-ending lines: a phrase, not a yelp
                continue
            out[p].append((f, text, d))
    for p in out:
        out[p].sort(key=lambda x: (x[2] if p in (0, 1, 2, 3, 4, 5) else 0, x[0]))
    return {p: [(f, t) for f, t, _ in v] for p, v in out.items() if v}


def fill(game, pc, prog, why):
    """prog/why with each program topped up to MAX from candidates() (a line already in the mod is never added twice)"""
    if game not in N or not os.path.exists(CACHE):
        return prog, why
    used = {_md5(f) for fs in prog.values() for f in fs}
    prog = {p: list(fs) for p, fs in prog.items()}
    why = dict(why)
    for p, cands in sorted(candidates(game, pc).items()):
        have = prog.setdefault(p, [])
        added = 0
        # 3 (the dive) may share 0's grunts, as the data modules' own picks do
        taken = used - {_md5(f) for f in prog.get(0, [])} if p == 3 else used
        for f, _ in cands:
            if len(have) >= MAX[p]:
                break
            h = _md5(f)
            if h in taken or f in have:
                continue
            have.append(f)
            used.add(h)
            added += 1
        if added:
            why[p] = (why.get(p, "") + "; " if why.get(p) else "") + \
                f"+{added} more of the character's own lines by what they say (more_voices.py RULES {p})"
        if not have:
            del prog[p]
    return prog, why


if __name__ == "__main__":  # summary: lines added per mod and program
    games = sys.argv[1:] or list(N)
    cache = json.load(open(CACHE))
    for g in games:
        for pc in range(N[g]):
            c = candidates(g, pc, cache)
            print(g, pc, {p: len(v) for p, v in sorted(c.items())})
