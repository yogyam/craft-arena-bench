"""Command line: play development matches against a running local server."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from .match import MatchRunner
from .policies import POLICIES, make_policy
from .tiers import TIERS, tier


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="craft-arena-bench", description="An AI-vs-AI benchmark for Minecraft decision models")
    sub = p.add_subparsers(dest="cmd", required=True)
    play = sub.add_parser("play", help="Play matches between two in-process policies on the local server")
    play.add_argument("--mode", default="sumo", choices=["sumo"])
    play.add_argument("--a", default="house", choices=sorted(POLICIES))
    play.add_argument("--b", default="random", choices=sorted(POLICIES))
    play.add_argument("--tier", type=int, default=5, choices=sorted(TIERS))
    play.add_argument("--seed", type=int, default=0, help="First seed; match i uses seed + i")
    play.add_argument("--matches", type=int, default=1)
    play.add_argument("--out", type=Path, default=Path("runs"), help="Where results and replays go")
    play.add_argument("--no-replay", action="store_true")
    args = p.parse_args(argv)
    return asyncio.run(_play(args))


async def _play(args) -> int:
    t = tier(args.tier)
    results = []
    async with MatchRunner(mode=args.mode) as runner:
        for i in range(args.matches):
            seed = args.seed + i
            pa, pb = make_policy(args.a, seed), make_policy(args.b, seed + 1000)
            r = await runner.play(seed, pa, pb, t, replay_dir=None if args.no_replay else args.out / "replays")
            results.append(r.to_dict())
            who = {"a": args.a, "b": args.b, None: "draw"}[r.winner]
            print(
                f"seed {seed:4d}  {who:>10}  by {r.reason:<9} at {r.seconds:5.1f} s   health {r.a_health:4.1f} / {r.b_health:4.1f}   {r.decisions} decisions   {r.wall_seconds:.1f} s wall"
            )
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"{args.mode}-{args.a}-vs-{args.b}-{args.tier}hz-{args.seed}.json"
    out.write_text(json.dumps(results, indent=1))
    tally = Counter(r["winner"] for r in results)
    print(f"\n{args.a} {tally['a']}  {args.b} {tally['b']}  draws {tally[None]}   written to {out}")
    return 0
