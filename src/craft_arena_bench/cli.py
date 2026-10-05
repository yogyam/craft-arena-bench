"""Command line: play development matches against a running local server."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from .endpoint import EndpointDecider, make_decider
from .match import MatchRunner
from .tiers import TIERS, tier


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="craft-arena-bench", description="An AI-vs-AI benchmark for Minecraft decision models")
    sub = p.add_subparsers(dest="cmd", required=True)
    play = sub.add_parser("play", help="Play matches between two deciders on the local server")
    play.add_argument("--mode", default="sumo", choices=["sumo", "block_uhc"])
    play.add_argument("--a", default="house", help="'house', 'random', or an endpoint URL such as http://127.0.0.1:9001")
    play.add_argument("--b", default="random", help="same")
    play.add_argument("--tier", type=int, default=5, choices=sorted(TIERS))
    play.add_argument("--seed", type=int, default=0, help="First seed; match i uses seed + i")
    play.add_argument("--matches", type=int, default=1)
    play.add_argument("--out", type=Path, default=Path("runs"), help="Where results and replays go")
    play.add_argument("--no-replay", action="store_true")
    play.add_argument("--verbose", action="store_true", help="Print each side's event counts after every match")
    args = p.parse_args(argv)
    return asyncio.run(_play(args))


async def _play(args) -> int:
    t = tier(args.tier)
    results = []
    da, db = make_decider(args.a, args.seed, args.mode), make_decider(args.b, args.seed + 1000, args.mode)
    for d in (da, db):
        if isinstance(d, EndpointDecider):
            doc = await d.health()
            print(f"{d.url}: health ok, name {doc.get('name')!r}")
    try:
        async with MatchRunner(mode=args.mode) as runner:
            for i in range(args.matches):
                seed = args.seed + i
                r = await runner.play(seed, da, db, t, replay_dir=None if args.no_replay else args.out / "replays")
                results.append(r.to_dict())
                who = {"a": "A", "b": "B", None: "draw"}[r.winner]
                lat = f"A {r.a_stats['median_ms']} ms {r.a_stats['late_fraction']:.0%} late | B {r.b_stats['median_ms']} ms {r.b_stats['late_fraction']:.0%} late"
                print(
                    f"seed {seed:4d}  {who:>4} by {r.reason:<10} {r.seconds:5.1f} s  health {r.a_health:4.1f}/{r.b_health:4.1f}  {r.decisions:4d} decisions  {lat}  {r.wall_seconds:.1f} s wall"
                )
                if args.verbose:
                    print(f"           A events {r.a_events}\n           B events {r.b_events}")
    finally:
        await asyncio.gather(da.close(), db.close())
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"{args.mode}-{_slug(da.name)}-vs-{_slug(db.name)}-{args.tier}hz-{args.seed}.json"
    out.write_text(json.dumps(results, indent=1))
    tally = Counter(r["winner"] for r in results)
    print(f"\nA={da.name} {tally['a']}  B={db.name} {tally['b']}  draws {tally[None]}   written to {out}")
    return 0


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name).strip("-")[:40]
