"""Plays one match: arena, bodies, tier clock, deciders (endpoints or in-process policies), referee, replay.

The decision clock never waits for an answer. At a decision tick the request goes out as a task; the body keeps
executing the last intent; when the answer arrives inside the budget it becomes the new intent, otherwise it is
counted as late and dropped. More than FORFEIT_LATE_FRACTION late or missing answers in a match forfeits it.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import INTERFACE_VERSION, MODE_SET_VERSION
from .arena import BlockUhcArena, SumoArena, make_arena
from .body import Body
from .endpoint import Decider, Decision
from .rcon import Rcon
from .referee import BlockUhcReferee, Outcome, SumoReferee
from .replay import ReplayRecorder
from .state import build_request
from .tiers import TICKS_PER_SECOND, Tier

COUNTDOWN_TICKS = 3 * TICKS_PER_SECOND
SETTLE_TICKS = 10
BOT_NAMES = ("BotA", "BotB")
FORFEIT_LATE_FRACTION = 0.20
MIN_DECISIONS_FOR_FORFEIT = 30  # judged from the 30th decision on: a short match is never forfeited on a handful of late answers
BODY_EVENTS_IN_HISTORY = (
    "shot_arrow",
    "placed_water",
    "placed_lava",
    "bucket_guard",
    "dodged_arrow",
    "action_failed",
)


@dataclass
class MatchResult:
    match_id: str
    mode: str
    tier_hz: int
    seed: int
    a: str
    b: str
    winner: str | None
    reason: str
    ticks: int
    seconds: float
    a_health: float
    b_health: float
    decisions: int
    a_stats: dict = field(default_factory=dict)
    b_stats: dict = field(default_factory=dict)
    a_events: dict = field(default_factory=dict)  # counts of history events: took_damage:melee, shot_arrow, placed_water, ...
    b_events: dict = field(default_factory=dict)
    wall_seconds: float = 0.0
    interface_version: int = INTERFACE_VERSION
    mode_set_version: int = MODE_SET_VERSION
    replay: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class _Side:
    """Per-bot bookkeeping during a match."""

    def __init__(self, body: Body, decider: Decider):
        self.body = body
        self.decider = decider
        self.intent = "hold"
        self.history: list[dict] = []
        self.pending: asyncio.Task | None = None
        self.asked = 0
        self.late = 0  # late, missing or illegal answers this match
        self.applied = 0


class MatchRunner:
    """Owns the server connection and two bodies for a series of matches."""

    def __init__(
        self,
        *,
        mode: str = "sumo",
        rcon_port: int = 25575,
        rcon_password: str = "local-dev-only",
        ws_ports: tuple[int, int] = (8701, 8702),
    ):
        self.mode = mode
        self.arena = make_arena(mode)
        self.rcon = Rcon(port=rcon_port, password=rcon_password)
        self.bodies = (
            Body(BOT_NAMES[0], BOT_NAMES[1], ws_ports[0], mode=mode),
            Body(BOT_NAMES[1], BOT_NAMES[0], ws_ports[1], mode=mode),
        )

    async def __aenter__(self):
        await asyncio.gather(*(b.start() for b in self.bodies))
        self.arena.apply_gamerules(self.rcon)
        return self

    async def __aexit__(self, *exc):
        await asyncio.gather(*(b.stop() for b in self.bodies))
        self.rcon.close()

    async def play(
        self, seed: int, decider_a: Decider, decider_b: Decider, tier: Tier, replay_dir: Path | None = None
    ) -> MatchResult:
        t0 = time.monotonic()
        match_id = secrets.token_hex(8)
        a, b = self.bodies
        sides = (_Side(a, decider_a), _Side(b, decider_b))
        await asyncio.gather(a.reset(), b.reset())
        self.arena.build(self.rcon, seed)
        self.arena.place_bots(self.rcon, BOT_NAMES, seed)
        if isinstance(self.arena, SumoArena):
            bounds, floor_y, config = self.arena.platform, None, {"platform": self.arena.platform.to_message()}
            referee = SumoReferee(self.arena.fall_y, self.arena.cap_seconds)
            uhc: BlockUhcArena | None = None
        else:
            bounds, floor_y, config = self.arena.bounds, self.arena.floor_y, {"arena": self.arena.to_message()}
            referee = BlockUhcReferee(self.arena.cap_seconds, self.arena.sudden_death_seconds)
            uhc = self.arena
        await asyncio.gather(a.configure(**config), b.configure(**config))

        # Endpoints open their connections now, during the settle, so decision 1 is not slowed by a handshake.
        await asyncio.gather(decider_a.warm_up(), decider_b.warm_up())
        # Let the teleport land, then hold both bots frozen for the countdown. The first states after a reset can lag.
        await a.next_state(timeout=10.0)
        for _ in range(SETTLE_TICKS + COUNTDOWN_TICKS - 1):
            await a.next_state()
        await asyncio.gather(a.freeze(False), b.freeze(False))

        recorder = ReplayRecorder(
            {
                "match_id": match_id,
                "mode": self.mode,
                "tier_hz": tier.hz,
                "seed": seed,
                "a": decider_a.name,
                "b": decider_b.name,
                "interface_version": INTERFACE_VERSION,
                "mode_set_version": MODE_SET_VERSION,
            }
        )
        last_health = [a.latest["self"]["health"], b.latest["self"]["health"]]
        decisions = 0
        tick = 0
        deaths_at_start = (a.deaths, b.deaths)
        deaths_seen = deaths_at_start
        sudden_death_announced = False
        outcome: Outcome | None = None

        while outcome is None:
            sa = await a.next_state()
            sb = b.latest
            tick += 1
            snaps = (sa, sb)
            sudden_death = uhc is not None and referee.sudden_death(tick)
            if sudden_death and not sudden_death_announced:
                sudden_death_announced = True
                for name, side in zip(BOT_NAMES, sides, strict=True):
                    # Sudden death: Strength II for both, so a sword hit does 13 instead of 7 and two hits kill.
                    # (Mirroring damage with /damage was tried; the command is refused inside the 10-tick invulnerability window.)
                    for effect in uhc.spec["sudden_death_effects"]:
                        self.rcon.command(f"effect give {name} {effect}")
                    side.history.append({"tick": tick, "event": "sudden_death_started"})
            # Damage events, from exact health (the bodies' own clients). The body says what hit it.
            deaths_now = (a.deaths, b.deaths)
            for i, s in enumerate(snaps):
                h = s["self"]["health"]
                if deaths_now[i] > deaths_seen[i]:
                    # The killing blow: the bot respawned with full health inside the tick, so the drop is what was left.
                    deaths_seen = deaths_now
                    h = 0.0
                if h < last_health[i] - 1e-6:
                    amount = round(last_health[i] - h, 2)
                    source = next(
                        (e.get("source", "other") for e in reversed(s.get("events", [])) if e["event"] == "hurt"), "melee"
                    )
                    sides[i].history.append({"tick": tick, "event": "took_damage", "amount": amount, "source": source})
                    sides[1 - i].history.append({"tick": tick, "event": "dealt_damage", "amount": amount, "source": source})
                last_health[i] = s["self"]["health"] if h > 0 else 0.0
                for e in s.get("events", []):
                    if e["event"] in BODY_EVENTS_IN_HISTORY:
                        sides[i].history.append(
                            {"tick": tick, "event": e["event"], **({"error": e["error"]} if "error" in e else {})}
                        )
                        if e["event"] == "shot_arrow":
                            sides[1 - i].history.append({"tick": tick, "event": "opponent_shot"})
            # Answers that have arrived since the last tick become intents.
            for side in sides:
                if side.pending is not None and side.pending.done():
                    await self._apply(side, side.pending.result())
                    side.pending = None
            if tier.decision_due(tick):
                decisions += 1
                for i, side in enumerate(sides):
                    if side.pending is not None:
                        # The previous answer is still outstanding (only possible if the budget exceeds the period). Count it late.
                        side.pending.cancel()
                        side.pending = None
                        side.late += 1
                    req = build_request(
                        mode=self.mode,
                        tier=tier,
                        match_id=match_id,
                        decision=decisions,
                        tick=tick,
                        cap_seconds=self.arena.cap_seconds,
                        me=snaps[i],
                        opp=snaps[1 - i],
                        platform=bounds,
                        history=side.history,
                        last_intent=side.intent,
                        late_answers=side.late,
                        sudden_death=sudden_death,
                        floor_y=floor_y,
                    )
                    side.asked += 1
                    side.pending = asyncio.create_task(side.decider.decide(req, tier.budget_ms))
            recorder.record(tick, sa, sb, (sides[0].intent, sides[1].intent))
            outcome = referee.update(tick, sa, sb, a.deaths > deaths_at_start[0], b.deaths > deaths_at_start[1])
            if outcome is None and decisions >= MIN_DECISIONS_FOR_FORFEIT:
                outcome = self._forfeit(tick, sides)

        for side in sides:
            if side.pending is not None:
                side.pending.cancel()
                side.pending = None
        await asyncio.gather(a.freeze(True), b.freeze(True))
        result = MatchResult(
            match_id=match_id,
            mode=self.mode,
            tier_hz=tier.hz,
            seed=seed,
            a=decider_a.name,
            b=decider_b.name,
            winner=outcome.winner,
            reason=outcome.reason,
            ticks=outcome.tick,
            seconds=round(outcome.tick / TICKS_PER_SECOND, 2),
            a_health=0.0 if outcome.reason == "death" and outcome.winner != "a" else sa["self"]["health"],
            b_health=0.0 if outcome.reason == "death" and outcome.winner != "b" else sb["self"]["health"],
            decisions=decisions,
            a_stats=self._side_stats(sides[0]),
            b_stats=self._side_stats(sides[1]),
            a_events=self._event_counts(sides[0]),
            b_events=self._event_counts(sides[1]),
            wall_seconds=round(time.monotonic() - t0, 2),
        )
        if replay_dir is not None:
            path = recorder.save(
                replay_dir / f"{self.mode}-{tier.hz}hz-{seed}-{match_id}.json.gz",
                {"winner": outcome.winner, "reason": outcome.reason, "tick": outcome.tick},
            )
            result.replay = str(path)
        errors = [f"{body.username} {e}" for body in self.bodies for e in body.errors]
        if errors:
            raise RuntimeError("body errors during match: " + "; ".join(errors))
        return result

    async def _apply(self, side: _Side, d: Decision) -> None:
        if d.status != "ok":
            side.late += 1
            return
        side.applied += 1
        if d.choice != side.intent:
            side.intent = d.choice
            await side.body.set_intent(d.choice)

    @staticmethod
    def _forfeit(tick: int, sides: tuple[_Side, _Side]) -> Outcome | None:
        over = [s.asked and s.late / s.asked > FORFEIT_LATE_FRACTION for s in sides]
        if over[0] and over[1]:
            return Outcome(None, "forfeit", tick)
        if over[0]:
            return Outcome("b", "forfeit", tick)
        if over[1]:
            return Outcome("a", "forfeit", tick)
        return None

    @staticmethod
    def _event_counts(side: _Side) -> dict:
        counts: dict[str, int] = {}
        for e in side.history:
            key = f"{e['event']}:{e['source']}" if "source" in e else e["event"]
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _side_stats(side: _Side) -> dict:
        stats = side.decider.stats
        return {
            "asked": side.asked,
            "applied": side.applied,
            "late_or_missing": side.late,
            "late_fraction": round(side.late / side.asked, 4) if side.asked else 0.0,
            "median_ms": stats.median_ms(),
            "p90_ms": stats.p90_ms(),
        }
