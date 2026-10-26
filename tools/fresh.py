"""Refuse to package from a branch that is behind main.

out/ is shared: a worktree links it to the main checkout's, and out/mods is the user's live mods folder. Packaging
from a branch that lacks main's newer commits rebuilds every mod it touches without them (2026-10-26: an Out of Bounds
run from a stale worktree dropped main's sit-on-a-seat take from all 20 mods). Merge main into the branch first.
"""
import os
import subprocess
import sys


def check():
    here = os.path.dirname(os.path.abspath(__file__))
    behind = subprocess.run(["git", "-C", here, "merge-base", "--is-ancestor", "main", "HEAD"], capture_output=True)
    if behind.returncode == 1:  # 0: up to date with main; 128: no main to compare against
        sys.exit("this branch is behind main: `git merge main` first, or packaging overwrites out/mods without main's changes")
