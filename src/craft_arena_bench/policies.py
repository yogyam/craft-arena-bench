"""In-process policies for development and for the house bot. A policy sees exactly what an endpoint would see."""

from __future__ import annotations

import random
from typing import Protocol


class Policy(Protocol):
    name: str

    def decide(self, request: dict) -> str: ...


class RandomPolicy:
    """Picks a legal action uniformly at random. The floor every real model must beat."""

    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def decide(self, request: dict) -> str:
        return self.rng.choice([a["id"] for a in request["actions"]])


class HouseSumo:
    """The scripted Sumo house bot: charge when close, sidestep when the opponent charges, stay off the edge."""

    name = "house-sumo"

    def decide(self, request: dict) -> str:
        me, opp, arena = request["self"], request["opponent"], request["arena"]
        dist = opp["distance"] if opp["distance"] is not None else 99.0
        # Near the edge with the opponent in reach: step sideways rather than trade knockback.
        if arena["my_edge_distance"] < 1.5 and dist < 3.5:
            return "strafe_left" if (request["decision"] // 2) % 2 == 0 else "strafe_right"
        # The opponent is coming at us fast: sidestep so their sprint hit misses.
        closing = _closing_speed(me, opp)
        if closing > 0.15 and dist < 4.0:
            return "strafe_right" if request["decision"] % 2 == 0 else "strafe_left"
        if dist <= 3.0:
            return "rush"
        if dist < 6.0:
            return "feint" if request["decision"] % 5 == 0 else "rush"
        return "rush"


def _closing_speed(me: dict, opp: dict) -> float:
    """Positive when the opponent moves towards us, in blocks per tick."""
    dx = me["pos"][0] - opp["pos"][0]
    dz = me["pos"][2] - opp["pos"][2]
    norm = (dx * dx + dz * dz) ** 0.5 or 1.0
    return (opp["velocity"][0] * dx + opp["velocity"][2] * dz) / norm


class Circler:
    """Always circles. The simplest competent movement; a 3B language model at 2 Hz converged on exactly this, and the house bot could not push it off."""

    name = "circler"

    def decide(self, request: dict) -> str:
        return "strafe_right"


class HouseUhc:
    """The scripted Block UHC house bot: water when burning, bow at range, lava when losing up close, wall when hurt, otherwise sword."""

    name = "house-uhc"

    def decide(self, request: dict) -> str:
        legal = {a["id"] for a in request["actions"]}
        me, opp, arena = request["self"], request["opponent"], request["arena"]
        dist = opp["distance"] if opp["distance"] is not None else 99.0
        hazards = arena.get("hazards_near") or []
        if "bucket_water" in legal and hazards and hazards[0]["kind"] in ("lava", "fire") and hazards[0]["distance"] <= 1.5:
            return "bucket_water"
        if "bucket_lava" in legal and me["health"] + 4 < opp["health"]:
            return "bucket_lava"
        if "place_wall" in legal and me["health"] <= 8 and dist > 5 and opp.get("charging_bow"):
            return "place_wall"
        if "shoot_bow" in legal and dist >= 9 and not request["sudden_death"]:
            return "shoot_bow"
        if dist <= 3.0:
            return "rush"
        if dist < 6 and request["decision"] % 3 == 0:
            return "strafe_left" if (request["decision"] // 3) % 2 == 0 else "strafe_right"
        return "rush"


POLICIES = {
    "random": lambda seed, mode: RandomPolicy(seed),
    "house": lambda seed, mode: HouseUhc() if mode == "block_uhc" else HouseSumo(),
    "circler": lambda seed, mode: Circler(),
}


def make_policy(name: str, seed: int = 0, mode: str = "sumo") -> Policy:
    try:
        return POLICIES[name](seed, mode)
    except KeyError:
        raise ValueError(f"unknown policy {name}; choose from {sorted(POLICIES)}") from None
