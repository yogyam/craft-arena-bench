"""Plays one match: arena, bodies, tier clock, policies, referee, replay."""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import INTERFACE_VERSION, MODE_SET_VERSION
from .arena import SumoArena
from .body import Body
from .policies import Policy
from .rcon import Rcon
from .referee import Outcome, SumoReferee
from .replay import ReplayRecorder
from .state import build_request
from .tiers import TICKS_PER_SECOND, Tier

COUNTDOWN_TICKS = 3 * TICKS_PER_SECOND
SETTLE_TICKS = 10
BOT_NAMES = ("BotA", "BotB")


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
    a_late: int
    b_late: int
    wall_seconds: float
    interface_version: int = INTERFACE_VERSION
    mode_set_version: int = MODE_SET_VERSION
    replay: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


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
        if mode != "sumo":
            raise ValueError("only sumo is implemented so far")
        self.mode = mode
        self.arena = SumoArena()
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
        self, seed: int, policy_a: Policy, policy_b: Policy, tier: Tier, replay_dir: Path | None = None
    ) -> MatchResult:
        t0 = time.monotonic()
        match_id = secrets.token_hex(8)
        a, b = self.bodies
        await asyncio.gather(a.reset(), b.reset())
        self.arena.build(self.rcon)
        self.arena.place_bots(self.rcon, BOT_NAMES, seed)
        platform = self.arena.platform.to_message()
        await asyncio.gather(a.configure(platform=platform), b.configure(platform=platform))

        # Let the teleport land, then hold both bots frozen for the countdown.
        for _ in range(SETTLE_TICKS + COUNTDOWN_TICKS):
            await a.next_state()
        await asyncio.gather(a.freeze(False), b.freeze(False))

        referee = SumoReferee(self.arena.fall_y, self.arena.cap_seconds)
        recorder = ReplayRecorder(
            {
                "match_id": match_id,
                "mode": self.mode,
                "tier_hz": tier.hz,
                "seed": seed,
                "a": policy_a.name,
                "b": policy_b.name,
                "interface_version": INTERFACE_VERSION,
                "mode_set_version": MODE_SET_VERSION,
            }
        )
        intents = ["hold", "hold"]
        history: list[list[dict]] = [[], []]
        last_health = [a.latest["self"]["health"], b.latest["self"]["health"]]
        decisions = 0
        tick = 0
        deaths_at_start = (a.deaths, b.deaths)
        outcome: Outcome | None = None

        while outcome is None:
            sa = await a.next_state()
            sb = b.latest
            tick += 1
            # Damage events, from exact health (the bodies' own clients).
            for i, s in enumerate((sa, sb)):
                h = s["self"]["health"]
                if h < last_health[i] - 1e-6:
                    history[i].append(
                        {"tick": tick, "event": "took_damage", "amount": round(last_health[i] - h, 2), "source": "melee"}
                    )
                    history[1 - i].append(
                        {"tick": tick, "event": "dealt_damage", "amount": round(last_health[i] - h, 2), "source": "melee"}
                    )
                last_health[i] = h
            if tier.decision_due(tick):
                decisions += 1
                for i, (me, opp, policy, body) in enumerate(((sa, sb, policy_a, a), (sb, sa, policy_b, b))):
                    req = build_request(
                        mode=self.mode,
                        tier=tier,
                        match_id=match_id,
                        decision=decisions,
                        tick=tick,
                        cap_seconds=self.arena.cap_seconds,
                        me=me,
                        opp=opp,
                        platform=self.arena.platform,
                        history=history[i],
                        last_intent=intents[i],
                        late_answers=0,
                    )
                    choice = policy.decide(req)
                    if choice not in {x["id"] for x in req["actions"]}:
                        raise ValueError(f"{policy.name} chose an illegal action {choice!r}")
                    if choice != intents[i]:
                        intents[i] = choice
                        await body.set_intent(choice)
            recorder.record(tick, sa, sb, (intents[0], intents[1]))
            outcome = referee.update(tick, sa, sb, a.deaths > deaths_at_start[0], b.deaths > deaths_at_start[1])

        await asyncio.gather(a.freeze(True), b.freeze(True))
        result = MatchResult(
            match_id=match_id,
            mode=self.mode,
            tier_hz=tier.hz,
            seed=seed,
            a=policy_a.name,
            b=policy_b.name,
            winner=outcome.winner,
            reason=outcome.reason,
            ticks=outcome.tick,
            seconds=round(outcome.tick / TICKS_PER_SECOND, 2),
            a_health=a.latest["self"]["health"],
            b_health=b.latest["self"]["health"],
            decisions=decisions,
            a_late=0,
            b_late=0,
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
