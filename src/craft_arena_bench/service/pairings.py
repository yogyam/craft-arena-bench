"""Pairings: which pairs still need playing in each mode and tier, and the pair document that records a played pair.

A pair result is `duels/<mode>-<hz>hz/<a>__<b>.json`, slugs in alphabetical order. It records both manifest
digests, so a bot that is updated plays everyone again, and the season and versions, so a season change does too.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .. import INTERFACE_VERSION, MODE_SET_VERSION
from ..tiers import TIERS
from . import MATCHES_PER_PAIR, SEASON
from .manifests import MODES, Manifest, manifest_digest

REPLAYS_SUFFIX = ".replays.json.gz"


def pair_name(a: str, b: str) -> str:
    a, b = sorted((a, b))
    return f"{a}__{b}"


def board_name(mode: str, hz: int) -> str:
    return f"{mode}-{hz}hz"


def boards() -> list[tuple[str, int]]:
    """Every (mode, tier) that is open this season."""
    return [(mode, hz) for mode in MODES for hz, t in TIERS.items() if t.open_in_season_1]


def pair_seeds(mode: str, hz: int, n: int = MATCHES_PER_PAIR) -> list[int]:
    """The seeds every pair plays on a board this season. Match i has the first-named bot on spawn A when i is even."""
    base = SEASON * 100_000 + MODES.index(mode) * 10_000 + hz * 100
    return [base + i for i in range(n)]


@dataclass(frozen=True)
class Pair:
    mode: str
    hz: int
    a: str
    b: str

    @property
    def name(self) -> str:
        return pair_name(self.a, self.b)

    def path(self, duels_folder: str) -> str:
        return os.path.join(duels_folder, board_name(self.mode, self.hz), self.name + ".json")

    def replays_path(self, replays_folder: str) -> str:
        return os.path.join(replays_folder, board_name(self.mode, self.hz), self.name + REPLAYS_SUFFIX)


def _current(document: dict, digests: dict, a: str, b: str) -> bool:
    return (
        document.get("a_manifest_sha256") == digests[a]
        and document.get("b_manifest_sha256") == digests[b]
        and document.get("season") == SEASON
        and document.get("interface_version") == INTERFACE_VERSION
        and document.get("mode_set_version") == MODE_SET_VERSION
        and document.get("matches_per_pair") == MATCHES_PER_PAIR
    )


def pairs_to_play(
    manifests: dict[str, Manifest], submissions_folder: str, duels_folder: str, only: set[str] | None = None
) -> list[Pair]:
    """Pairs of entrants on each board with no current result. `only` restricts to bots whose endpoint answered the health check."""
    digests = {slug: manifest_digest(os.path.join(submissions_folder, slug)) for slug in manifests}
    pending = []
    for mode, hz in boards():
        slugs = sorted(slug for slug, m in manifests.items() if m.plays(mode, hz) and (only is None or slug in only))
        for i, a in enumerate(slugs):
            for b in slugs[i + 1 :]:
                pair = Pair(mode, hz, a, b)
                path = pair.path(duels_folder)
                if os.path.isfile(path):
                    try:
                        with open(path, encoding="utf-8") as f:
                            existing = json.load(f)
                    except (OSError, json.JSONDecodeError):
                        existing = {}
                    if _current(existing, digests, a, b):
                        continue
                pending.append(pair)
    return pending


def load_pair_documents(duels_folder: str) -> list[dict]:
    documents = []
    if not os.path.isdir(duels_folder):
        return documents
    for board in sorted(os.listdir(duels_folder)):
        folder = os.path.join(duels_folder, board)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".json"):
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    documents.append(json.load(f))
    return documents


def current_documents(documents: list[dict], manifests: dict[str, Manifest], submissions_folder: str) -> list[dict]:
    """Only the pair results that describe both bots as they are in the repository now, this season."""
    digests = {slug: manifest_digest(os.path.join(submissions_folder, slug)) for slug in manifests}
    return [d for d in documents if d["a"] in digests and d["b"] in digests and _current(d, digests, d["a"], d["b"])]


def matches_by_board(documents: list[dict]) -> dict[tuple[str, int], dict]:
    """{(mode, hz): {(a, b): [1, 0, 0.5, ...]}} from a's side, for the rating."""
    out: dict[tuple[str, int], dict] = {}
    for d in documents:
        board = out.setdefault((d["mode"], d["tier_hz"]), {})
        outcomes = []
        for m in d["matches"]:
            outcomes.append(1.0 if m["winner"] == "a" else 0.0 if m["winner"] == "b" else 0.5)
        board[(d["a"], d["b"])] = outcomes
    return out
