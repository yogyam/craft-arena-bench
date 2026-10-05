"""Where the repository's non-Python parts are: the body, the arena files, the server folder.

With an editable install they sit two levels above this package. With a normal install (the scoring runner) they do
not, so the working directory is checked first, then `CAB_ROOT`, then the package-relative guess.
"""

from __future__ import annotations

import os
from pathlib import Path

MARKERS = ("body/package.json", "arenas/sumo.json", "server/server.properties")


def repo_root() -> Path:
    env = os.environ.get("CAB_ROOT")
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if all((candidate / m).is_file() for m in MARKERS):
            return candidate
    guess = Path(__file__).resolve().parents[2]
    if all((guess / m).is_file() for m in MARKERS):
        return guess
    raise FileNotFoundError(
        "Cannot find the repository root (body/, arenas/, server/): run from a clone of craft-arena-bench or set CAB_ROOT"
    )
