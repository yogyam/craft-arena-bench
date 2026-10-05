"""Checks on what the scoring job produced, before anything is published: the right shape, numbers that agree with
each other, and a match with the repository (the manifests on main, this season's settings)."""

from __future__ import annotations

import gzip
import json
import os
import re

from .. import INTERFACE_VERSION, MODE_SET_VERSION
from ..tiers import TIERS
from . import MATCHES_PER_PAIR, REPLAYS_PER_PAIR, SEASON
from .manifests import MODES, SLUG_PATTERN, SubmissionError, load_all, manifest_digest
from .pairings import REPLAYS_SUFFIX, board_name, pair_name, pair_seeds

MAX_REPLAY_FRAMES = 3700  # 180 s at 20 Hz plus a little
MAX_TEXT = 120
PAIR_FIELDS = {
    "a",
    "b",
    "mode",
    "tier_hz",
    "a_manifest_sha256",
    "b_manifest_sha256",
    "season",
    "interface_version",
    "mode_set_version",
    "matches_per_pair",
    "seeds",
    "played_at",
    "benchmark_version",
    "server",
    "libraries",
    "a_points",
    "b_points",
    "a_wins",
    "b_wins",
    "draws",
    "a_latency",
    "b_latency",
    "matches",
}
MATCH_FIELDS = {
    "seed",
    "a_on_spawn",
    "winner",
    "reason",
    "seconds",
    "decisions",
    "a_health",
    "b_health",
    "a_stats",
    "b_stats",
    "a_events",
    "b_events",
}
REASONS = {"fall", "both_fell", "death", "cap", "cap_health", "forfeit"}


def _slug(value) -> None:
    if not isinstance(value, str) or not SLUG_PATTERN.match(value):
        raise SubmissionError("A pair result names a bot with a bad slug")


def _number(value, lo=0.0, hi=1e9) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and lo <= value <= hi


def validate_pair_document(document: dict) -> None:
    if not isinstance(document, dict):
        raise SubmissionError("A pair result must be a JSON object")
    if set(document) != PAIR_FIELDS:
        raise SubmissionError(f"A pair result has the wrong fields: {sorted(set(document) ^ PAIR_FIELDS)}")
    _slug(document["a"])
    _slug(document["b"])
    if document["a"] >= document["b"]:
        raise SubmissionError("A pair must name the bots in alphabetical order")
    if document["mode"] not in MODES:
        raise SubmissionError("A pair result names an unknown mode")
    hz = document["tier_hz"]
    if type(hz) is not int or hz not in TIERS or not TIERS[hz].open_in_season_1:
        raise SubmissionError("A pair result names a tier that is not open")
    for name in ("a_manifest_sha256", "b_manifest_sha256"):
        if not isinstance(document[name], str) or not re.fullmatch(r"[0-9a-f]{64}", document[name]):
            raise SubmissionError(f"'{name}' must be a SHA-256")
    for name in ("played_at", "benchmark_version"):
        if not isinstance(document[name], str) or not (1 <= len(document[name]) <= 64):
            raise SubmissionError(f"'{name}' is missing or not short text")
    if (document["season"], document["interface_version"], document["mode_set_version"]) != (
        SEASON,
        INTERFACE_VERSION,
        MODE_SET_VERSION,
    ):
        raise SubmissionError("The pair is from another season or version")
    n = document["matches_per_pair"]
    if n != MATCHES_PER_PAIR:
        raise SubmissionError(f"A published pair must have {MATCHES_PER_PAIR} matches")
    if document["seeds"] != pair_seeds(document["mode"], hz, n):
        raise SubmissionError("The seeds are not this season's seeds for the board")
    if not isinstance(document["server"], dict) or not isinstance(document["libraries"], dict):
        raise SubmissionError("'server' and 'libraries' must be objects")
    matches = document["matches"]
    if not isinstance(matches, list) or len(matches) != n:
        raise SubmissionError("A pair result must hold exactly its matches")
    a_wins = b_wins = draws = 0
    for i, m in enumerate(matches):
        if not isinstance(m, dict) or set(m) != MATCH_FIELDS:
            raise SubmissionError("A match has the wrong fields")
        if m["seed"] != document["seeds"][i] or m["a_on_spawn"] != ("A" if i % 2 == 0 else "B"):
            raise SubmissionError("Matches must follow the seeds in order, alternating spawn sides")
        if m["winner"] not in ("a", "b", None) or m["reason"] not in REASONS:
            raise SubmissionError("A match has a bad winner or reason")
        if not _number(m["seconds"], 0, 600) or type(m["decisions"]) is not int or m["decisions"] < 0:
            raise SubmissionError("A match has bad timing numbers")
        for name in ("a_health", "b_health"):
            if not _number(m[name], 0, 40):
                raise SubmissionError("A match has a bad health value")
        for name in ("a_stats", "b_stats", "a_events", "b_events"):
            if not isinstance(m[name], dict):
                raise SubmissionError(f"'{name}' must be an object")
        a_wins += m["winner"] == "a"
        b_wins += m["winner"] == "b"
        draws += m["winner"] is None
    if (document["a_wins"], document["b_wins"], document["draws"]) != (a_wins, b_wins, draws):
        raise SubmissionError("Win counts do not match the matches")
    if (document["a_points"], document["b_points"]) != (a_wins + 0.5 * draws, b_wins + 0.5 * draws):
        raise SubmissionError("Points do not match the matches")
    for name in ("a_latency", "b_latency"):
        lat = document[name]
        if not isinstance(lat, dict) or set(lat) != {"median_ms", "late_fraction", "asked"}:
            raise SubmissionError(f"'{name}' has the wrong fields")
        if lat["median_ms"] is not None and not _number(lat["median_ms"], 0, 1e6):
            raise SubmissionError(f"'{name}' has a bad median")
        if not _number(lat["late_fraction"], 0, 1) or type(lat["asked"]) is not int:
            raise SubmissionError(f"'{name}' has bad numbers")


def validate_published_pair(path: str, submissions_folder: str) -> dict:
    """A pair file about to be published must sit in its board's folder, be named after its pair, and describe
    both bots as they are in the repository, both entered on that board."""
    with open(path, encoding="utf-8") as f:
        document = json.load(f)
    validate_pair_document(document)
    board = board_name(document["mode"], document["tier_hz"])
    if (
        os.path.basename(os.path.dirname(path)) != board
        or os.path.basename(path) != pair_name(document["a"], document["b"]) + ".json"
    ):
        raise SubmissionError(f"A pair file must be at <duels>/{board}/{pair_name(document['a'], document['b'])}.json")
    manifests = load_all(submissions_folder)
    for side in ("a", "b"):
        slug = document[side]
        if slug not in manifests:
            raise SubmissionError(f"'{slug}' has no valid manifest in the repository")
        if document[f"{side}_manifest_sha256"] != manifest_digest(os.path.join(submissions_folder, slug)):
            raise SubmissionError(f"The pair is not for the manifest of '{slug}' in the repository")
        if not manifests[slug].plays(document["mode"], document["tier_hz"]):
            raise SubmissionError(f"'{slug}' did not enter {board}")
    return document


def validate_replays_document(document: dict) -> None:
    if not isinstance(document, dict) or set(document) != {"pair", "a", "b", "mode", "tier_hz", "season", "arena", "replays"}:
        raise SubmissionError("A replays file has the wrong fields")
    _slug(document["a"])
    _slug(document["b"])
    if document["pair"] != pair_name(document["a"], document["b"]) or document["season"] != SEASON:
        raise SubmissionError("The replays file does not match its pair or season")
    if not isinstance(document["arena"], dict) or set(document["arena"]) != {"min", "max", "kind"}:
        raise SubmissionError("A replays file has a bad arena")
    replays = document["replays"]
    if not isinstance(replays, list) or len(replays) > REPLAYS_PER_PAIR:
        raise SubmissionError("Too many replays for a pair")
    for replay in replays:
        if not isinstance(replay, dict) or set(replay) != {"meta", "outcome", "frame_fields", "frames"}:
            raise SubmissionError("A replay has the wrong fields")
        frames = replay["frames"]
        if not isinstance(frames, list) or not (1 <= len(frames) <= MAX_REPLAY_FRAMES):
            raise SubmissionError("A replay has no frames or too many")
        for frame in frames:
            if not isinstance(frame, list) or len(frame) != 4 or len(frame[1]) != 6 or len(frame[2]) != 6:
                raise SubmissionError("A replay frame has the wrong shape")
            for v in [frame[0], *frame[1], *frame[2]]:
                if not _number(v, -1e5, 1e5):
                    raise SubmissionError("A replay frame holds something that is not a sensible number")
            if not all(isinstance(s, str) and len(s) <= 32 for s in frame[3]):
                raise SubmissionError("A replay frame has bad intents")


def validate_published_replays(path: str) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        document = json.load(f)
    validate_replays_document(document)
    board = board_name(document["mode"], document["tier_hz"])
    if os.path.basename(os.path.dirname(path)) != board or os.path.basename(path) != document["pair"] + REPLAYS_SUFFIX:
        raise SubmissionError(f"A replays file must be at <replays>/{board}/{document['pair']}{REPLAYS_SUFFIX}")
    return document


def validate_paths(paths: list[str], submissions_folder: str) -> None:
    """Every file the scoring job produced, by kind. Raises on the first problem."""
    for path in paths:
        if path.endswith(REPLAYS_SUFFIX):
            validate_published_replays(path)
        elif path.endswith(".json"):
            validate_published_pair(path, submissions_folder)
        else:
            raise SubmissionError(f"Not a result file: {path}")
