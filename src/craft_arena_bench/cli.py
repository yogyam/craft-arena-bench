"""Command line: development matches, and the scoring service's commands."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
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
    play.add_argument(
        "--a", default="house", help="'house', 'random', 'circler', or an endpoint URL such as http://127.0.0.1:9001"
    )
    play.add_argument("--b", default="random", help="same")
    play.add_argument("--tier", type=int, default=5, choices=sorted(TIERS))
    play.add_argument("--seed", type=int, default=0, help="First seed; match i uses seed + i")
    play.add_argument("--matches", type=int, default=1)
    play.add_argument("--out", type=Path, default=Path("runs"), help="Where results and replays go")
    play.add_argument("--no-replay", action="store_true")
    play.add_argument("--verbose", action="store_true", help="Print each side's event counts after every match")
    play.set_defaults(func=lambda a: asyncio.run(_play(a)))

    server = sub.add_parser("server", help="Download, start or stop the Paper server (the jar is never committed)")
    server.add_argument("action", choices=["download", "start", "stop", "status"])
    server.set_defaults(func=_server)

    new = sub.add_parser("new-submission", help="Write a manifest for your bot into a submissions folder")
    new.add_argument("--name", required=True)
    new.add_argument("--author", required=True)
    new.add_argument("--github", required=True, help="The GitHub login that will open the pull request")
    new.add_argument("--endpoint", required=True, help="https://... that answers /health and /decide")
    new.add_argument("--tiers", type=int, nargs="+", default=[2, 5])
    new.add_argument("--modes", nargs="+", default=["sumo", "block_uhc"])
    new.add_argument("--description", default="")
    new.add_argument("--homepage", default="")
    new.add_argument("--submissions", default="my_submission")
    new.add_argument("--allow-local", action="store_true", help="Dry runs only: accept an http://127.0.0.1 endpoint")
    new.set_defaults(func=_new_submission)

    verify = sub.add_parser("verify-submission", help="Check submission folders as the pull request check does")
    verify.add_argument("folders", nargs="+")
    verify.add_argument("--submissions", default="submissions")
    verify.add_argument("--github-login", default=None, help="Who opened the pull request; enables the login and limit checks")
    verify.add_argument("--exempt", nargs="*", default=["yogyam"], help="Maintainers, exempt from the limits")
    verify.add_argument("--allow-local", action="store_true", help="Accept http://127.0.0.1 endpoints (dry runs only)")
    verify.add_argument("--no-health", action="store_true", help="Skip calling the endpoint")
    verify.set_defaults(func=lambda a: asyncio.run(_verify(a)))

    pairings = sub.add_parser("pairings", help="List the pairs that still need playing")
    pairings.add_argument("--submissions", default="submissions")
    pairings.add_argument("--duels", default="duels")
    pairings.add_argument("--allow-local", action="store_true", help="Dry runs only")
    pairings.set_defaults(func=_pairings)

    score = sub.add_parser("score", help="Play outstanding pairs against the local server, each in its own process")
    score.add_argument("--submissions", default="submissions")
    score.add_argument("--duels", default="duels")
    score.add_argument("--output", default="new_results")
    score.add_argument("--max-pairs", type=int, default=15)
    score.add_argument(
        "--matches", type=int, default=None, help="Matches per pair (default: the season's number; fewer only for dry runs)"
    )
    score.add_argument("--allow-local", action="store_true")
    score.add_argument("--start-server", action="store_true", help="Download and start the Paper server first, stop it after")
    score.set_defaults(func=lambda a: asyncio.run(_score(a)))

    pp = sub.add_parser("play-pair", help="Used by score: one pair in one process")
    pp.add_argument("--submissions", required=True)
    pp.add_argument("--output", required=True)
    pp.add_argument("--mode", required=True)
    pp.add_argument("--tier", type=int, required=True)
    pp.add_argument("--a", required=True)
    pp.add_argument("--b", required=True)
    pp.add_argument("--matches", type=int, default=None)
    pp.add_argument("--allow-local", action="store_true")
    pp.set_defaults(func=lambda a: asyncio.run(_play_pair(a)))

    validate = sub.add_parser(
        "validate-results", help="Check result files from the scoring job against the repository before publishing"
    )
    validate.add_argument("paths", nargs="+")
    validate.add_argument("--submissions", default="submissions")
    validate.add_argument("--allow-local", action="store_true", help="Dry runs only")
    validate.set_defaults(func=_validate)

    site = sub.add_parser("build-site", help="Build the leaderboard website")
    site.add_argument("--submissions", default="submissions")
    site.add_argument("--duels", default="duels")
    site.add_argument("--replays", default="replays")
    site.add_argument("--flags", default="flags.json")
    site.add_argument("--output", default="site")
    site.add_argument("--allow-local", action="store_true", help="Dry runs only")
    site.set_defaults(func=_build_site)

    args = p.parse_args(argv)
    if getattr(args, "allow_local", False):
        from .service import manifests

        manifests.ALLOW_LOCAL = True
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        return 130


def _echo(*parts) -> None:
    print(*parts, flush=True)


async def _play(args) -> int:
    t = tier(args.tier)
    results = []
    da, db = make_decider(args.a, args.seed, args.mode), make_decider(args.b, args.seed + 1000, args.mode)
    for d in (da, db):
        if isinstance(d, EndpointDecider):
            doc = await d.health()
            _echo(f"{d.url}: health ok, name {doc.get('name')!r}")
    try:
        async with MatchRunner(mode=args.mode) as runner:
            for i in range(args.matches):
                seed = args.seed + i
                r = await runner.play(seed, da, db, t, replay_dir=None if args.no_replay else args.out / "replays")
                results.append(r.to_dict())
                who = {"a": "A", "b": "B", None: "draw"}[r.winner]
                lat = f"A {r.a_stats['median_ms']} ms {r.a_stats['late_fraction']:.0%} late | B {r.b_stats['median_ms']} ms {r.b_stats['late_fraction']:.0%} late"
                _echo(
                    f"seed {seed:4d}  {who:>4} by {r.reason:<10} {r.seconds:5.1f} s  health {r.a_health:4.1f}/{r.b_health:4.1f}  {r.decisions:4d} decisions  {lat}  {r.wall_seconds:.1f} s wall"
                )
                if args.verbose:
                    _echo(f"           A events {r.a_events}\n           B events {r.b_events}")
    finally:
        await asyncio.gather(da.close(), db.close())
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"{args.mode}-{_slug(da.name)}-vs-{_slug(db.name)}-{args.tier}hz-{args.seed}.json"
    out.write_text(json.dumps(results, indent=1))
    tally = Counter(r["winner"] for r in results)
    _echo(f"\nA={da.name} {tally['a']}  B={db.name} {tally['b']}  draws {tally[None]}   written to {out}")
    return 0


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name).strip("-")[:40]


def _server(args) -> int:
    from .server import PaperServer, download_jar, is_running

    if args.action == "download":
        _echo(f"jar at {download_jar()}")
    elif args.action == "status":
        _echo("running" if is_running() else "not running")
    elif args.action == "start":
        if is_running():
            _echo("already running")
            return 0
        s = PaperServer()
        s.start()
        s.proc = None  # leave it running after this command exits
        _echo("started; stop with: craft-arena-bench server stop")
    elif args.action == "stop":
        from .rcon import Rcon
        from .server import RCON_PASSWORD, RCON_PORT

        try:
            with Rcon(port=RCON_PORT, password=RCON_PASSWORD) as rcon:
                _echo(rcon.command("stop").strip() or "stopping")
        except OSError:
            _echo("not running")
    return 0


def _new_submission(args) -> int:
    from .service.manifests import SubmissionError, new_manifest, write_manifest

    try:
        m = new_manifest(
            args.name, args.author, args.github, args.endpoint, args.tiers, args.modes, args.description, args.homepage
        )
    except SubmissionError as e:
        _echo(f"Not acceptable: {e}")
        return 1
    path = write_manifest(m, args.submissions)
    _echo(f"wrote {path}; copy the folder {args.submissions}/{m.slug} into submissions/ in your pull request")
    return 0


async def _verify(args) -> int:
    from .service.manifests import SubmissionError, check_pull_request, health_check, load_manifest

    try:
        if args.github_login:
            manifests = check_pull_request(args.folders, args.github_login, args.submissions, exempt=tuple(args.exempt))
        else:
            manifests = [load_manifest(f) for f in args.folders]
    except SubmissionError as e:
        _echo(f"Refused: {e}")
        return 1
    failed = 0
    for m in manifests:
        if args.no_health:
            _echo(f"{m.slug}: manifest ok (health check skipped)")
            continue
        report = await health_check(m, allow_local=args.allow_local)
        _echo(f"{m.slug}: manifest ok; {report.detail}")
        failed += not report.ok
    return 1 if failed else 0


def _pairings(args) -> int:
    from .service.manifests import load_all
    from .service.pairings import board_name, pairs_to_play

    pending = pairs_to_play(load_all(args.submissions), args.submissions, args.duels)
    for pair in pending:
        _echo(f"{board_name(pair.mode, pair.hz):<16} {pair.a} v {pair.b}")
    _echo(f"{len(pending)} pairs outstanding")
    return 0


async def _score(args) -> int:
    from .service import MATCHES_PER_PAIR
    from .service.scoring import score

    matches = args.matches or MATCHES_PER_PAIR
    if args.start_server:
        from .server import PaperServer

        with PaperServer():
            played = await score(args.submissions, args.duels, args.output, args.max_pairs, args.allow_local, matches)
    else:
        played = await score(args.submissions, args.duels, args.output, args.max_pairs, args.allow_local, matches)
    _echo(f"{len(played)} pairs played")
    return 0


async def _play_pair(args) -> int:
    from .service import MATCHES_PER_PAIR
    from .service.scoring import play_pair_command

    await play_pair_command(
        args.submissions, args.output, args.mode, args.tier, args.a, args.b, args.allow_local, args.matches or MATCHES_PER_PAIR
    )
    return 0


def _validate(args) -> int:
    from .service.manifests import SubmissionError
    from .service.validation import validate_paths

    try:
        validate_paths(args.paths, args.submissions)
    except (SubmissionError, OSError, ValueError) as e:
        _echo(f"Refused: {e}")
        return 1
    _echo(f"{len(args.paths)} files ok")
    return 0


def _build_site(args) -> int:
    from .service.site import build_site

    _echo(f"built {build_site(args.submissions, args.duels, args.replays, args.output, args.flags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
