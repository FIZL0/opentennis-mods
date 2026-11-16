#!/usr/bin/env python3
"""A packaged mod's voice lines in its source game's other languages (standard §5 `voice_languages`, opentennis M168).

usage: python3 tools/rerig/voice_langs.py [out/mods/<mod> ...]   (default every mod of a game listed in COPIES)

For each take in the mod's `voice/` (as package.py wrote it, English), the same line in another language copy of
the source disc goes into `voice-<lang>/` under the same name, and `mod.json` gets `voice_languages`. A take with no
counterpart is left out of that folder: the game plays the English take there (the fallback). Run standalone, it
bumps the mod's `version` when a language folder changed (opentennis AGENT.md *Mod versions*); package.py calls
`apply` itself after writing `voice/` (its versions are bumped by hand).

Rules, read from the disc at run time (no clip lists):
- Out of Bounds keeps every actor's in-game lines twice (notes/audio.md "Language"): `ga_pc_NN.xb0` English and
  `ga_pc_NN.xb` Japanese, for pc01-06 and 08-14 (pc00 and pc07 hold English in both; pc15+ have no second copy).
  Both banks ga_sg_pcNN play the same cue slots, so a take found in the English bank as a cue slot's main wave (the
  wave voices() takes: the slot's longest note) or as a cue mixed whole (oob_data.results, out/voices/oob_cues/)
  is the Japanese bank's same slot, taken or mixed the same way. Takes the English picks found by transcript in the
  other banks (hit cry, more_voices) have no slot to follow and stay English.
"""
import glob
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)


def _md5(f):
    return hashlib.md5(open(f, "rb").read()).hexdigest()


def _link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


class Oob:
    """Out of Bounds: English ga_sg bank slot -> the Japanese copy's same slot."""
    ENGLISH_BOTH = {0, 7}  # their .xb copy is English too (notes/audio.md "Language")

    def __init__(self):
        import oob_data
        self.d = oob_data

    def _bank(self, pc, ext):
        f = glob.glob(self.d._p(self.d.USR, f"sound/pc/ga_pc_{pc:02d}.{ext}/data/sound/voice/game/pc/ga_sg_pc{pc:02d}.sgd"))
        if not f:
            return None
        return f[0], self.d._p(self.d.AUD, os.path.relpath(f[0], self.d._p(self.d.USR)))

    def _main_wave(self, cue, samples, wd):
        notes = cue[1]
        if not notes:
            return None
        w = max(notes, key=lambda n: samples[n[0]])[0]
        f = os.path.join(wd, f"{w + 1:03d}.wav")
        return f if os.path.exists(f) else None

    def counterparts(self, pc, lang):
        """{md5 of an English take: the `lang` file of the same line}, or {} when the disc has no such copy."""
        if lang != "ja" or pc in self.ENGLISH_BOTH:
            return {}
        en, ja = self._bank(pc, "xb0"), self._bank(pc, "xb")
        if not en or not ja:
            return {}
        (ep, ewd), (jp, jwd) = en, ja
        ecues, esamples = self.d.sgxd(ep)
        jcues, jsamples = self.d.sgxd(jp)
        out = {}
        for slot in sorted(ecues):
            if slot not in jcues:
                continue
            ef, jf = self._main_wave(ecues[slot], esamples, ewd), self._main_wave(jcues[slot], jsamples, jwd)
            if ef and jf:
                out.setdefault(_md5(ef), jf)  # a wave two slots share follows the first
            # a cue mixed whole for a result clip (oob_data.results), mixed again from the Japanese notes
            mixed = self.d._p(self.d.CUES, f"pc{pc:02d}/{slot[0]}_{slot[1]}.wav")
            if os.path.exists(mixed) and jcues[slot][1]:
                dst = self.d._p(self.d.CUES + f"_{lang}", f"pc{pc:02d}/{slot[0]}_{slot[1]}.wav")
                if not os.path.exists(dst):
                    self.d._mix(jcues[slot][1], jwd, dst)
                out.setdefault(_md5(mixed), dst)
        return out


# source game -> {language tag: its rule}; the tags are the game's Voice Language ones (en fr it de es ja)
COPIES = {"oob": {"ja": Oob}}


def apply(game, pc, mod, manifest):
    """Writes `mod`'s voice-<lang>/ folders from its voice/ and sets manifest's voice_language(s); whether any
    language folder's content changed."""
    voice = os.path.join(mod, manifest.get("voice") or "voice/")
    takes = sorted(glob.glob(os.path.join(voice, "*.wav")))
    before, langs = {}, {}
    for d in glob.glob(os.path.join(mod, "voice-*")):
        before[os.path.basename(d)] = {os.path.basename(f): _md5(f) for f in glob.glob(os.path.join(d, "*.wav"))}
        shutil.rmtree(d)
    for lang, rule in COPIES.get(game, {}).items():
        to = rule().counterparts(pc, lang) if takes else {}
        n = 0
        for t in takes:
            src = to.get(_md5(t))
            if src:
                _link(src, os.path.join(mod, f"voice-{lang}", os.path.basename(t)))
                n += 1
        if n:
            langs[lang] = f"voice-{lang}/"
            manifest.setdefault("voice_languages_why", {})[lang] = (
                f"{n} of {len(takes)} takes, the same cue slot in the source disc's {lang} copy (tools/rerig/voice_langs.py); "
                "the rest play the default voice/")
    if langs:
        manifest["voice_language"] = "en"
        manifest["voice_languages"] = langs
    else:
        for k in ("voice_language", "voice_languages", "voice_languages_why"):
            manifest.pop(k, None)
    after = {os.path.basename(d): {os.path.basename(f): _md5(f) for f in glob.glob(os.path.join(d, "*.wav"))}
             for d in glob.glob(os.path.join(mod, "voice-*"))}
    return before != after


def main():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fresh
    fresh.check()  # out/mods is the live folder: never from a branch behind main
    mods = sys.argv[1:] or [d for g in COPIES for d in sorted(glob.glob(os.path.join(ROOT, f"out/mods/{g}_pc*")))]
    for mod in mods:
        mod = mod.rstrip("/")
        game, pc = os.path.basename(mod).split("_")[:2]
        if game not in COPIES or not pc.startswith("pc"):
            continue
        mj = os.path.join(mod, "mod.json")
        manifest = json.load(open(mj))
        changed = apply(game, int(pc[2:]), mod, manifest)
        if changed:
            manifest["version"] = str(int(manifest.get("version", "1")) + 1)
        json.dump(manifest, open(mj, "w"), indent=1, ensure_ascii=False)
        print(os.path.basename(mod), manifest.get("voice_languages", {}), "v" + manifest.get("version", "?"),
              "changed" if changed else "", flush=True)


if __name__ == "__main__":
    main()
