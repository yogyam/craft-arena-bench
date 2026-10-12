"""The LAN demo: exhibition matches people can watch from spectator mode, and a challenge mode where a person fights a bot.

Runs against the local server. Everyone who joins is put into spectator mode above the arena; a title announces each
match and its result; a sidebar keeps the running score. Nothing here touches ratings: results go to a separate file.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
import re
import time
from pathlib import Path

from .arena import SumoArena
from .body import Body
from .endpoint import Decider, Decision, LatencyStats, make_decider
from .match import BOT_NAMES, MatchResult, MatchRunner
from .rcon import Rcon
from .tiers import Tier

HUMAN_TAG = "cab_human"
BOT_TAG = "cab_bot"
DEATHS_OBJECTIVE = "cab_deaths"
SCORE_OBJECTIVE = "cab_score"


def _text(s: str, color: str | None = None, bold: bool = False) -> str:
    doc = {"text": s}
    if color:
        doc["color"] = color
    if bold:
        doc["bold"] = True
    return json.dumps(doc)


class Announcer:
    """Titles, chat lines and the sidebar, for the humans only."""

    def __init__(self, rcon: Rcon):
        self.rcon = rcon
        self.humans = f"@a[tag=!{BOT_TAG}]"

    def setup(self) -> None:
        self.rcon.command("defaultgamemode spectator")
        self.rcon.command(f"scoreboard objectives add {DEATHS_OBJECTIVE} deathCount")
        self.rcon.command(f"scoreboard objectives add {SCORE_OBJECTIVE} dummy {_text('CraftArenaBench', 'gold', True)}")
        self.rcon.command(f"scoreboard objectives setdisplay sidebar {SCORE_OBJECTIVE}")
        self.rcon.command(f"title {self.humans} times 5 70 10")

    def tag_bot(self, uuid: str) -> None:
        self.rcon.command(f"tag {uuid} add {BOT_TAG}")

    def spectate(self, center: tuple[float, float, float], height: float = 14.0, exclude: str | None = None) -> None:
        sel = self.humans if not exclude else f"@a[tag=!{BOT_TAG},name=!{exclude}]"
        self.rcon.command(f"gamemode spectator {sel}")
        self.rcon.command(f"tp {sel} {center[0]} {center[1] + height} {center[2]} 0 90")

    def title(self, main: str, sub: str = "", color: str = "white") -> None:
        self.rcon.command(f"title {self.humans} subtitle {_text(sub, 'gray')}")
        self.rcon.command(f"title {self.humans} title {_text(main, color, True)}")

    def say(self, line: str, color: str = "gray") -> None:
        self.rcon.command(f"tellraw @a {_text(line, color)}")

    def score(self, name: str, value: int) -> None:
        self.rcon.command(f'scoreboard players set "{name[:40]}" {SCORE_OBJECTIVE} {value}')


class HumanOpponent:
    """Stands in for a body: a person on the server, seen through the bot's eyes plus a little polling.

    Position, facing and velocity come from the bot body's view of its opponent (the game sends those for every
    player). Health and deaths are not sent to other clients, so they are read from the server over RCON a few times a
    second. Everything the match runner calls on a body exists here; the ones that drive a bot do nothing.
    """

    def __init__(self, username: str, eyes: Body, rcon: Rcon, poll_health: bool = True):
        self.username = username
        self.uuid: str | None = None  # addressed by name: a LAN demo in offline mode has no better handle
        self.eyes = eyes
        self.rcon = rcon
        self.poll_health = poll_health
        self.health = 20.0
        self.deaths = 0
        self._deaths_base = 0
        self.errors: list[str] = []
        self.spawn: list | None = None
        self._last_seen: dict | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self.rcon.command(f"tag {self.username} add {HUMAN_TAG}")
        self._deaths_base = self._read_deaths()
        self.deaths = 0
        self._task = asyncio.create_task(self._poll())

    async def _poll(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                if self.poll_health:
                    self.health = await loop.run_in_executor(None, self._read_health)
                self.deaths = await loop.run_in_executor(None, self._read_deaths) - self._deaths_base
            except Exception as e:  # the person may have left; the match ends on the next check
                self.errors.append(f"poll: {type(e).__name__}")
                return
            await asyncio.sleep(0.25)

    def _read_health(self) -> float:
        reply = self.rcon.command(f"data get entity {self.username} Health")
        m = re.search(r"([0-9.]+)f", reply)
        return float(m.group(1)) if m else self.health

    def _read_deaths(self) -> int:
        reply = self.rcon.command(f"scoreboard players get {self.username} {DEATHS_OBJECTIVE}")
        m = re.search(r"has (\d+)", reply)
        return int(m.group(1)) if m else 0

    @property
    def latest(self) -> dict | None:
        # A spectator is invisible to other clients, so during the countdown (and for a tick after it) the bot sees
        # nobody: fall back to the last position seen, or the spawn point before anything has been seen.
        seen = (self.eyes.latest or {}).get("opponent")
        if seen and seen.get("pos"):
            self._last_seen = seen
        elif self._last_seen:
            seen = self._last_seen
        elif self.spawn:
            seen = {"pos": list(self.spawn)}
        else:
            return None
        return {
            "type": "state",
            "tick": (self.eyes.latest or {}).get("tick", 0),
            "intent": "human",
            "self": {
                "pos": seen["pos"],
                "yaw": seen.get("yaw", 0.0),
                "pitch": seen.get("pitch", 0.0),
                "velocity": seen.get("velocity", [0, 0, 0]),
                "on_ground": seen.get("on_ground", True),
                "health": self.health,
                "food": 20,
                "held": seen.get("held"),
                "inventory": {},
                "effects": [],
            },
            "opponent": None,
            "events": [],
        }

    async def reset(self) -> None:
        pass

    async def configure(self, **kwargs) -> None:
        # Called after the kit and teleport: the person waits out the countdown in spectator mode, where nothing they
        # do can touch the frozen bot (a sprint hit would push it off the platform before the match starts).
        self.spawn = kwargs.get("spawn")
        self.rcon.command(f"gamemode spectator {self.username}")

    async def freeze(self, value: bool) -> None:
        if value:
            self.rcon.command(f"gamemode spectator {self.username}")
        else:
            if self.spawn:
                x, y, z = self.spawn
                self.rcon.command(f"tp {self.username} {x} {y} {z}")
            self.rcon.command(f"gamemode survival {self.username}")

    async def set_intent(self, intent: str) -> None:
        pass

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        with contextlib.suppress(Exception):
            self.rcon.command(f"tag {self.username} remove {HUMAN_TAG}")


class HumanDecider(Decider):
    """The 'model' behind a person: never asked anything that matters."""

    def __init__(self, username: str):
        self.name = username
        self.stats = LatencyStats()

    async def decide(self, request: dict, budget_ms: int) -> Decision:
        d = Decision("hold", "ok", 0.0)
        self.stats.record(d)
        return d


def _append_result(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text()) if path.is_file() else []
    rows.append(record)
    path.write_text(json.dumps(rows, indent=1))


def _record(kind: str, mode: str, tier: Tier, a: str, b: str, r: MatchResult) -> dict:
    return {
        "time": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
        "mode": mode,
        "tier_hz": tier.hz,
        "a": a,
        "b": b,
        "winner": r.winner,
        "reason": r.reason,
        "seconds": r.seconds,
        "a_health": r.a_health,
        "b_health": r.b_health,
        "replay": r.replay,
    }


async def exhibition(
    modes: list[str],
    tier: Tier,
    fighters: dict[str, str],
    results: Path,
    interval: float = 8.0,
    cycles: int | None = None,
    replay_dir: Path | None = None,
) -> None:
    """Round-robin exhibition: every fighter against every other, in each mode, forever (or for `cycles` rounds)."""
    names = list(fighters)
    pairs = [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]
    if not pairs:
        raise ValueError("need at least two fighters, e.g. --vs house --vs qwen=http://127.0.0.1:9010")
    wins: dict[str, int] = dict.fromkeys(names, 0)
    seed = int(time.time()) % 100_000
    done = 0
    while cycles is None or done < cycles:
        for mode in modes:
            async with MatchRunner(mode=mode) as runner:
                ann = Announcer(runner.rcon)
                ann.setup()
                for body in runner.bodies:
                    ann.tag_bot(body.uuid or body.username)
                for name in names:
                    ann.score(name, wins[name])
                center = _center(runner)
                for a, b in pairs:
                    da, db = make_decider(fighters[a], seed, mode), make_decider(fighters[b], seed + 1, mode)
                    da.name, db.name = a, b
                    ann.spectate(center)
                    ann.title(f"{a} vs {b}", f"{_mode_name(mode)} · {tier.hz} decisions per second", "yellow")
                    ann.say(f"Next: {a} vs {b}, {_mode_name(mode)} at {tier.hz} Hz. Bots are red and blue; watch from above.")
                    try:
                        r = await runner.play(seed, da, db, tier, replay_dir=replay_dir)
                    finally:
                        await asyncio.gather(da.close(), db.close())
                    seed += 1
                    winner = {"a": a, "b": b, None: None}[r.winner]
                    if winner:
                        wins[winner] += 1
                        ann.score(winner, wins[winner])
                    ann.title(
                        f"{winner} wins" if winner else "Draw",
                        f"by {r.reason} after {r.seconds:.0f} s",
                        "green" if winner else "gray",
                    )
                    ann.say(f"Result: {winner + ' wins' if winner else 'draw'} by {r.reason} after {r.seconds:.0f} s.")
                    _append_result(results, _record("exhibition", mode, tier, a, b, r))
                    print(f"{mode} {tier.hz}Hz  {a} vs {b}: {winner or 'draw'} by {r.reason} in {r.seconds:.0f} s", flush=True)
                    await asyncio.sleep(interval)
        done += 1


async def challenge(
    username: str, mode: str, tier: Tier, opponent: str, results: Path, replay_dir: Path | None = None
) -> MatchResult:
    """One match: the bot `opponent` (house, random, circler or a URL) against the person `username`, who must be on the server."""
    async with MatchRunner(mode=mode) as runner:
        ann = Announcer(runner.rcon)
        ann.setup()
        a = runner.bodies[0]
        await runner.bodies[1].stop()  # the second body is not needed; the person takes its place
        ann.tag_bot(a.uuid or a.username)
        if "There are" not in runner.rcon.command("list") or username not in runner.rcon.command("list"):
            raise RuntimeError(f"{username} is not on the server; join first (the address is this machine's LAN IP, port 25565)")
        # The bot's body must look for the person, not the other bot.
        await a.stop()
        a = Body(BOT_NAMES[0], username, 8701, mode=mode, mc_port=runner.bodies[0].mc_port)
        await a.start()
        ann.tag_bot(a.uuid or a.username)
        human = HumanOpponent(username, a, runner.rcon, poll_health=mode != "sumo")
        await human.start()
        decider = make_decider(opponent, int(time.time()) % 100_000, mode)
        center = _center(runner)
        ann.spectate(center, exclude=username)
        ann.title(f"{username} vs {decider.name}", f"{_mode_name(mode)} · get ready", "yellow")
        ann.say(f"{username} is fighting {decider.name} in {_mode_name(mode)}. Everyone else: spectate from above.")
        try:
            r = await runner.play(
                int(time.time()) % 100_000, decider, HumanDecider(username), tier, replay_dir=replay_dir, bodies=(a, human)
            )
        finally:
            await asyncio.gather(decider.close(), human.stop(), a.stop())
        winner = {"a": decider.name, "b": username, None: None}[r.winner]
        ann.title(
            f"{winner} wins" if winner else "Draw",
            f"by {r.reason} after {r.seconds:.0f} s",
            "green" if winner == username else "red" if winner else "gray",
        )
        ann.say(f"Result: {winner + ' wins' if winner else 'draw'} by {r.reason} after {r.seconds:.0f} s.")
        runner.rcon.command(f"gamemode spectator {username}")
        _append_result(results, _record("challenge", mode, tier, decider.name, username, r))
        print(
            f"challenge {mode} {tier.hz}Hz  {decider.name} vs {username}: {winner or 'draw'} by {r.reason} in {r.seconds:.0f} s",
            flush=True,
        )
        return r


def _center(runner: MatchRunner) -> tuple[float, float, float]:
    arena = runner.arena
    b = arena.platform if isinstance(arena, SumoArena) else arena.bounds
    return ((b.min[0] + b.max[0] + 1) / 2, b.min[1] + 1, (b.min[2] + b.max[2] + 1) / 2)


def _mode_name(mode: str) -> str:
    return {"sumo": "Sumo", "block_uhc": "Block UHC"}[mode]
