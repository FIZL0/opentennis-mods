"""Bigger Chief (opentennis task M11): HST's Big Chief (pc07) twice as big, swinging twice as fast, running at a
quarter of his speed -> extras/hst_bigger_chief/ (committed: it holds no game data).

Not in out/mods on purpose: he's an optional mod, so a dev's mods/hst-mods link doesn't load him by default. Install
him from the mod store, or copy extras/hst_bigger_chief into the game's mods folder.

python3 tools/rerig/hst_bigger_chief.py

Only a mod.json: `disc_body` plays pc07's own costumes, faces, racket and voice from the player's disc (standard §6),
`scale`/`swing_speed`/`run_speed` do the rest. Nothing from the disc is read or written here.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "extras/hst_bigger_chief")

# bump on any change to the manifest, so the mod store sees an update
VERSION = "1"

MOD = {
    "standard": 1,
    "id": "hst_bigger_chief",
    "name": "Bigger Chief",
    "source": "Hot Shots Tennis (PS2) pc07, grown",
    "disc_body": True,
    "donor": 7,
    "donor_why": "Big Chief himself: his disc body, motions, faces and voice",
    "hand": "right",
    "params": {"base": 7, "override": {}},
    "params_why": "Big Chief's row; `scale` doubles its size-bound columns (reach, heights, collision)",
    "ai_row": 7,
    "face": "morph",
    "scale": 2,
    "size_why": "twice Big Chief's size",
    "swing_speed": 2,
    "run_speed": 0.25,
    "version": VERSION,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "mod.json"), "w") as f:
        json.dump(MOD, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(OUT)


if __name__ == "__main__":
    main()
