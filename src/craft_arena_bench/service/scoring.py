"""Playing the pairs the service owes: health checks, one subprocess per pair with a time limit, the pair document.

A pair is never half-published: if anything fails during its matches, nothing is written for it and it is retried
next run.
"""

from __future__ import annotations

import asyncio
import datetime
import gzip
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import INTERFACE_VERSION, MINECRAFT_VERSION, MODE_SET_VERSION, PAPER_BUILD, __version__
from ..arena import make_arena
from ..endpoint import Decider, EndpointDecider, LocalDecider
from ..match import MatchRunner
from ..policies import make_policy
from ..tiers import tier
from . import MATCHES_PER_PAIR, REPLAYS_PER_PAIR, SEASON
from .manifests import HOUSE_ENDPOINT_PREFIX, Manifest, SubmissionError, health_check, load_all, manifest_digest
from .pairings import Pair, board_name, pair_seeds, pairs_to_play


def library_versions() -> dict:
    versions = {"python": platform.python_version(), "platform": platform.system().lower()}
    for name in ("httpx", "websockets", "numpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unknown"
    try:
        body = json.loads((Path(__file__).resolve().parents[3] / "body" / "package-lock.json").read_text())
        versions["mineflayer"] = body["packages"]["node_modules/mineflayer"]["version"]
    except (OSError, KeyError, ValueError):
        versions["mineflayer"] = "unknown"
    return versions


def make_decider_for(manifest: Manifest, mode: str, allow_local: bool = False) -> Decider:
    if manifest.house:
        return LocalDecider(make_policy(manifest.endpoint[len(HOUSE_ENDPOINT_PREFIX) :], 0, mode))
    return EndpointDecider(manifest.endpoint, manifest.slug)


async def healthy_bots(manifests: dict[str, Manifest], allow_local: bool = False) -> tuple[set[str], dict[str, str]]:
    """Slugs whose endpoint answers the health check, and why the others did not."""
    reports = await asyncio.gather(*(health_check(m, allow_local) for m in manifests.values()))
    ok, why = set(), {}
    for slug, report in zip(manifests, reports, strict=True):
        if report.ok:
            ok.add(slug)
        else:
            why[slug] = report.detail
    return ok, why


async def play_pair(
    pair: Pair,
    manifests: dict[str, Manifest],
    submissions_folder: str,
    allow_local: bool = False,
    matches: int = MATCHES_PER_PAIR,
    replays_n: int = REPLAYS_PER_PAIR,
) -> tuple[dict, dict]:
    """Plays every seeded match of a pair, alternating spawn sides. Returns the pair document and its replays document."""
    t = tier(pair.hz)
    ma, mb = manifests[pair.a], manifests[pair.b]
    da, db = make_decider_for(ma, pair.mode, allow_local), make_decider_for(mb, pair.mode, allow_local)
    seeds = pair_seeds(pair.mode, pair.hz, matches)
    arena = make_arena(pair.mode)
    records, replays = [], []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            async with MatchRunner(mode=pair.mode) as runner:
                for i, seed in enumerate(seeds):
                    a_first = i % 2 == 0
                    first, second = (da, db) if a_first else (db, da)
                    r = await runner.play(seed, first, second, t, replay_dir=Path(tmp) if i < replays_n else None)
                    # Everything in the result is from the first-named bot's view; fold it back to a's view.
                    flip = {"a": "b", "b": "a", None: None}
                    winner = r.winner if a_first else flip[r.winner]
                    a_stats, b_stats = (r.a_stats, r.b_stats) if a_first else (r.b_stats, r.a_stats)
                    a_events, b_events = (r.a_events, r.b_events) if a_first else (r.b_events, r.a_events)
                    a_health, b_health = (r.a_health, r.b_health) if a_first else (r.b_health, r.a_health)
                    records.append(
                        {
                            "seed": seed,
                            "a_on_spawn": "A" if a_first else "B",
                            "winner": winner,
                            "reason": r.reason,
                            "seconds": r.seconds,
                            "decisions": r.decisions,
                            "a_health": a_health,
                            "b_health": b_health,
                            "a_stats": a_stats,
                            "b_stats": b_stats,
                            "a_events": a_events,
                            "b_events": b_events,
                        }
                    )
                    if r.replay:
                        with gzip.open(r.replay, "rt") as f:
                            doc = json.load(f)
                        doc["meta"]["a"], doc["meta"]["b"] = (pair.a, pair.b) if a_first else (pair.b, pair.a)
                        doc["meta"]["a_on_spawn"] = "A" if a_first else "B"
                        replays.append(doc)
    finally:
        await asyncio.gather(da.close(), db.close())

    def points(side):
        return sum(1.0 if m["winner"] == side else 0.5 if m["winner"] is None else 0.0 for m in records)

    def latency(key):
        stats = [m[key] for m in records if m[key].get("asked")]
        medians = sorted(s["median_ms"] for s in stats if s.get("median_ms") is not None)
        asked = sum(s["asked"] for s in stats)
        late = sum(s["late_or_missing"] for s in stats)
        return {
            "median_ms": medians[len(medians) // 2] if medians else None,
            "late_fraction": round(late / asked, 4) if asked else 0.0,
            "asked": asked,
        }

    bounds = arena.platform if pair.mode == "sumo" else arena.bounds
    document = {
        "a": pair.a,
        "b": pair.b,
        "mode": pair.mode,
        "tier_hz": pair.hz,
        "a_manifest_sha256": manifest_digest(os.path.join(submissions_folder, pair.a)),
        "b_manifest_sha256": manifest_digest(os.path.join(submissions_folder, pair.b)),
        "season": SEASON,
        "interface_version": INTERFACE_VERSION,
        "mode_set_version": MODE_SET_VERSION,
        "matches_per_pair": matches,
        "seeds": seeds,
        "played_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "benchmark_version": __version__,
        "server": {"minecraft": MINECRAFT_VERSION, "paper_build": PAPER_BUILD},
        "libraries": library_versions(),
        "a_points": points("a"),
        "b_points": points("b"),
        "a_wins": sum(1 for m in records if m["winner"] == "a"),
        "b_wins": sum(1 for m in records if m["winner"] == "b"),
        "draws": sum(1 for m in records if m["winner"] is None),
        "a_latency": latency("a_stats"),
        "b_latency": latency("b_stats"),
        "matches": records,
    }
    replays_document = {
        "pair": pair.name,
        "a": pair.a,
        "b": pair.b,
        "mode": pair.mode,
        "tier_hz": pair.hz,
        "season": SEASON,
        "arena": {"min": list(bounds.min), "max": list(bounds.max), "kind": "platform" if pair.mode == "sumo" else "walls"},
        "replays": replays,
    }
    return document, replays_document


def write_pair(document: dict, replays_document: dict, output_folder: str) -> tuple[str, str]:
    pair = Pair(document["mode"], document["tier_hz"], document["a"], document["b"])
    duel_path = pair.path(os.path.join(output_folder, "duels"))
    replay_path = pair.replays_path(os.path.join(output_folder, "replays"))
    os.makedirs(os.path.dirname(duel_path), exist_ok=True)
    os.makedirs(os.path.dirname(replay_path), exist_ok=True)
    with open(duel_path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=1)
        f.write("\n")
    with gzip.open(replay_path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(replays_document, f, separators=(",", ":"))
    return duel_path, replay_path


def pair_timeout_seconds(mode: str, matches: int = MATCHES_PER_PAIR) -> int:
    cap = make_arena(mode).cap_seconds
    return matches * (cap + 15) + 120


def run_pair_in_subprocess(
    pair: Pair, submissions_folder: str, output_folder: str, allow_local: bool = False, matches: int = MATCHES_PER_PAIR
) -> bool:
    """One pair in a child process with a time limit, so a hang or crash costs one pair, not the run."""
    cmd = [
        sys.executable,
        "-m",
        "craft_arena_bench.cli",
        "play-pair",
        "--submissions",
        submissions_folder,
        "--output",
        output_folder,
        "--mode",
        pair.mode,
        "--tier",
        str(pair.hz),
        "--a",
        pair.a,
        "--b",
        pair.b,
        "--matches",
        str(matches),
    ]
    if allow_local:
        cmd.append("--allow-local")
    try:
        completed = subprocess.run(cmd, timeout=pair_timeout_seconds(pair.mode, matches), check=False)
    except subprocess.TimeoutExpired:
        print(f"{pair.name} on {board_name(pair.mode, pair.hz)}: timed out, nothing written", flush=True)
        return False
    if completed.returncode != 0:
        print(
            f"{pair.name} on {board_name(pair.mode, pair.hz)}: failed with exit code {completed.returncode}, nothing written",
            flush=True,
        )
        return False
    return True


async def score(
    submissions_folder: str,
    duels_folder: str,
    output_folder: str,
    max_pairs: int,
    allow_local: bool = False,
    matches: int = MATCHES_PER_PAIR,
) -> list[Pair]:
    """Health-checks every entrant, then plays up to `max_pairs` outstanding pairs, each in its own process."""
    manifests = load_all(submissions_folder)
    healthy, why = await healthy_bots(manifests, allow_local)
    for slug, reason in sorted(why.items()):
        print(f"{slug}: skipped this run, {reason}", flush=True)
    pending = pairs_to_play(manifests, submissions_folder, duels_folder, only=healthy)
    print(f"{len(pending)} pairs outstanding, playing up to {max_pairs}", flush=True)
    played = []
    for pair in pending[:max_pairs]:
        print(f"playing {pair.a} v {pair.b} on {board_name(pair.mode, pair.hz)} ({matches} matches)", flush=True)
        if run_pair_in_subprocess(pair, submissions_folder, output_folder, allow_local, matches):
            played.append(pair)
    return played


async def play_pair_command(
    submissions_folder: str, output_folder: str, mode: str, hz: int, a: str, b: str, allow_local: bool, matches: int
) -> None:
    manifests = load_all(submissions_folder)
    for slug in (a, b):
        if slug not in manifests:
            raise SubmissionError(f"{slug} has no valid manifest")
    pair = Pair(mode, hz, *sorted((a, b)))
    document, replays_document = await play_pair(pair, manifests, submissions_folder, allow_local, matches)
    duel_path, _ = write_pair(document, replays_document, output_folder)
    print(f"{pair.name}: {document['a_wins']}-{document['b_wins']}-{document['draws']} written to {duel_path}", flush=True)
