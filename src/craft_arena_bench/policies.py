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
    """The scripted Sumo house bot, version 2.1: constant sprint pressure.

    Pushing wins Sumo slowly (a circling opponent is pushed a little on every hit), and whoever stops sprinting loses
    the push battle, so the bot rushes whenever the opponent is in reach, wherever it stands. The one exception: a
    charge that has not arrived yet, with the rim at our back, is sidestepped towards the centre so the sprint hit
    misses. Version 2 strafed in reach at the rim and was pushed off by a rusher 12 times in 20.
    """

    name = "house-sumo"

    def decide(self, request: dict) -> str:
        me, opp, arena = request["self"], request["opponent"], request["arena"]
        dist = opp["distance"] if opp["distance"] is not None else 99.0
        my_edge, opp_edge = arena["my_edge_distance"], arena["opponent_edge_distance"]
        inside = my_edge >= opp_edge + 0.5
        if my_edge < 3.0 and not inside and 3.5 < dist < 5.0 and _closing_speed(me, opp) > 0.15:
            return _strafe_towards_centre(me, opp, arena)
        return "rush"


def _strafe_towards_centre(me: dict, opp: dict, arena: dict) -> str:
    """The body faces the opponent, so a strafe moves us sideways; pick the side that brings us nearer the centre."""
    fx, fz = opp["pos"][0] - me["pos"][0], opp["pos"][2] - me["pos"][2]
    norm = (fx * fx + fz * fz) ** 0.5 or 1.0
    fx, fz = fx / norm, fz / norm
    left = (fz, -fx)  # facing +z (yaw 0) puts our left hand towards +x
    to_centre = (arena["center"][0] - me["pos"][0], arena["center"][2] - me["pos"][2])
    return "strafe_left" if left[0] * to_centre[0] + left[1] * to_centre[1] >= 0 else "strafe_right"


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
    """The scripted Block UHC house bot, version 2.

    Lessons from the first entrants: never draw the bow while a sprinting opponent is closing, never strafe in melee
    (sprint hits win trades), pour lava only as a trap in a charging opponent's path, and get out of our own fire.
    """

    name = "house-uhc"

    def decide(self, request: dict) -> str:
        legal = {a["id"] for a in request["actions"]}
        me, opp, arena = request["self"], request["opponent"], request["arena"]
        dist = opp["distance"] if opp["distance"] is not None else 99.0
        hazards = arena.get("hazards_near") or []
        hazard = hazards[0] if hazards else None
        closing = _closing_speed(me, opp)
        behind = me["health"] < opp["health"]
        # Burning, or standing next to lava: water first, whatever else is going on.
        if "bucket_water" in legal and hazard and hazard["kind"] in ("lava", "fire") and hazard["distance"] <= 1.0:
            return "bucket_water"
        # Fire or lava close by and the fight is not on top of us: step away from it before anything else.
        if hazard and hazard["kind"] in ("lava", "fire") and hazard["distance"] <= 2.0 and dist > 3.0:
            return "retreat" if hazard["direction"] == "ahead" else "rush"
        # A trap for a charger: lava in their path at 2.5 to 4 blocks, while they are still coming. The first charge
        # of the match is the one to trap, whatever the health; later ones only when we are behind.
        if (
            "bucket_lava" in legal
            and 2.5 <= dist <= 4.0
            and closing > 0.1
            and (behind or me["health"] >= 19 or me["health"] <= 12)
        ):
            return "bucket_lava"
        # In reach: sprint hits, nothing fancy.
        if dist <= 3.5:
            return "rush"
        # Mid range with an opponent drawing on us while we are hurt: wall off.
        if "place_wall" in legal and me["health"] <= 8 and opp.get("charging_bow") and dist > 5:
            return "place_wall"
        # Shoot only when they are far and not coming, and never in the first seconds: at decision 1 nobody has a velocity yet,
        # and a bow draw takes a second during which we neither move nor swing.
        if "shoot_bow" in legal and dist >= 10 and closing <= 0.1 and request["decision"] > 3 and not request["sudden_death"]:
            return "shoot_bow"
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
