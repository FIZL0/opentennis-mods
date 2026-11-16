#!/usr/bin/env python3
"""Symlink each playable character's voice WAVs: out/voices/<game>/pcNN/<bank>_<NNN>.wav (+ <bank>_<cue name>.wav where the bank has names) (relative links into out/audio).
usage: tools/voices.py   (run after tools/audio.py). Fore: the 3-letter code is mapped to NN via PC/PCNN/ dirs.
A disc's other-language copy of a voice archive (notes/audio.md "Language", LANG) goes under out/voices/<game>-<lang>/
instead, so out/voices/<game>/ is the English cast only (a link there into another language's copy is removed)."""
import glob, os, re, collections
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A, V = f"{R}/out/audio", f"{R}/out/voices"

# The voice archives a disc keeps in another language besides the English copy (notes/audio.md "Language"):
# Out of Bounds ga_pc_NN.xb (pc00 and pc07 hold English there too), Open Tee 2 hats/snd/*.xb (.xb1 is English).
LANG = {"oob": lambda p: "ja" if (m := re.search(r"/sound/pc/ga_pc_(\d+)\.xb/", p)) and int(m[1]) not in (0, 7) else None,
        "opentee2": lambda p: "ja" if re.search(r"/hats/snd/[^/]+\.xb/", p) else None}


def lang(g, d):
    """the language of bank dir d's archive copy when it isn't the English one, else None"""
    return LANG.get(g, lambda p: None)(d.replace(os.sep, "/"))


def banks(g):
    for d, ds, fs in os.walk(f"{A}/{g}"):
        if re.search(r"\.(sgd|hd|sgb|sgh)$", d, re.I) and any(f.endswith(".wav") for f in fs):
            ds.clear()
            yield d, sorted(f for f in fs if f.endswith(".wav"))

def who(g, d):
    b = os.path.basename(d).rsplit(".", 1)[0].lower(); p = d.lower()
    if g == "fore":
        m = re.search(r"/sound/voice/(?:pc_game|pc_honor)/([a-z]{3})/", p)
        if m: return m[1]
        m = re.fullmatch(r"mepc_(\d+)[ab]", b)
        return f"#{int(m[1])}" if m else None
    m = re.search(r"npc_([mw])(\d+)", b)
    if m: return f"npc_{m[1]}{m[2]}"
    m = re.search(r"/pc(\d+)[vm]?\.xb\d?/", p) or re.search(r"(?:^|_)pc_?(?:[a-z]{1,2}_)?(\d+)", b) or re.search(r"^hy_(\d+)", b) or re.search(r"mepc(\d+)", b)
    return f"pc{m[1]}" if m else None

def main():
    for g in ["fore", "getagrip", "opentee2", "oob"]:
        if not os.path.isdir(f"{A}/{g}"): continue
        gone = 0
        for t in glob.glob(f"{V}/{g}/*/*.wav"):  # another language's take linked before LANG
            if os.path.islink(t) and lang(g, os.path.normpath(os.path.join(os.path.dirname(t), os.readlink(t)))):
                os.remove(t); gone += 1
        code = {}
        if g == "fore":  # code -> NN from PC/PCNN/
            for d, _ in banks(g):
                m = re.search(r"/PC/PC(\d\d)/.*/sound/voice/pc_game/([a-z]{3})/", d.replace(f"{A}/{g}", ""), re.I)
                if m: code[m[2].lower()] = m[1]
        n = collections.Counter()
        for d, fs in sorted(banks(g)):
            w = who(g, d)
            if not w: continue
            if g == "fore": w = "pc" + (w[1:].zfill(2) if w[0] == "#" else code.get(w, "??" + w))
            ln = lang(g, d)
            out = f"{V}/{g}-{ln}/{w}" if ln else f"{V}/{g}/{w}"; os.makedirs(out, exist_ok=True)
            b = os.path.basename(d).rsplit(".", 1)[0].lower()
            for f in fs:
                t = f"{out}/{b}_{f}"
                if not os.path.lexists(t):
                    os.symlink(os.path.relpath(f"{d}/{f}", out), t); n[w] += 1
            if os.path.exists(f"{d}/names.txt"):  # extra <bank>_<cue name>.wav aliases
                for l in open(f"{d}/names.txt"):
                    k, _, nm = l.rstrip("\n").partition("\t")
                    t = f"{out}/{b}_{nm}.wav"
                    if k.isdigit() and os.path.exists(f"{d}/{k}.wav"):
                        rel = os.path.relpath(f"{d}/{k}.wav", out)
                        if os.path.islink(t) and os.readlink(t) != rel:  # names.txt changed (audio.py cue decode)
                            os.remove(t)
                        if not os.path.lexists(t):
                            os.symlink(rel, t)
        print(g, len(n), "dirs", sum(n.values()), "links", gone, "other-language links moved out")

main()
