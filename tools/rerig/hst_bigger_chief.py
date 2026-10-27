"""Bigger Chief (opentennis task M11): HST's Big Chief (pc07) 1.5x as big, the roster's best stats, Kent's strokes and
Lola's volleys on his own serve (the hardest of each), running at a fifth of his speed with almost no stamina -> extras/hst_bigger_chief/ (committed: it holds no game data).

Also written to out/mods/hst_bigger_chief/, so a dev's mods/hst-mods link loads him like the packaged mods. He's an
optional mod: players install him from the mod store (or copy extras/hst_bigger_chief into the game's mods folder).

python3 tools/rerig/hst_bigger_chief.py

Only a mod.json: `disc_body` plays pc07's own costumes, faces, racket and voice from the player's disc (standard §6),
`scale`/`run_speed`/`stats`/`shots` do the rest. Nothing from the disc is read or written here.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUTS = [os.path.join(ROOT, d, "hst_bigger_chief") for d in ("extras", "out/mods")]

# bump on any change to the manifest, so the mod store sees an update
VERSION = "7"

MOD = {
    "standard": 1,
    "id": "hst_bigger_chief",
    "name": "Bigger Chief",
    "source": "Hot Shots Tennis (PS2) pc07, grown",
    "disc_body": True,
    "donor": 7,
    "donor_why": "Big Chief himself: his disc body, motions, faces and voice",
    "hand": "right",
    "params": {"base": 7, "override": {"STA": "14", "飛びつき減少/バックハンド減少/スマッシュ減少": "16/8/16"}},
    "params_why": "Big Chief's row; `scale` grows its reach columns (reach, dive, collision), `stats` S takes the roster's best of the rest; tiny stamina, dives, backhands and smashes cost twice a stock one's",
    "ai_row": 7,
    "face": "morph",
    "scale": 1.5,
    "size_why": "1.5x Big Chief's size",
    "run_speed": 0.2,
    "stats": "S",
    "shots": {"stroke": 9, "volley": 10},
    "stats_why": "every cell the roster best (S); Kent strokes and Lola volleys on top of its donor serve, the hardest of each",
    "joke": True,
    "version": VERSION,
}


def main():
    for out in OUTS:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "mod.json"), "w") as f:
            json.dump(MOD, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(out)


if __name__ == "__main__":
    main()
