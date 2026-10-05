"""Referees decide when a match is over and who won. One class per mode."""

from __future__ import annotations

from dataclasses import dataclass

from .tiers import TICKS_PER_SECOND


@dataclass(frozen=True)
class Outcome:
    winner: str | None  # "a", "b" or None for a draw
    reason: str  # "fall", "death", "cap", "both_fell", "forfeit"
    tick: int


class SumoReferee:
    def __init__(self, fall_y: float, cap_seconds: int):
        self.fall_y = fall_y
        self.cap_ticks = cap_seconds * TICKS_PER_SECOND

    def update(self, tick: int, a: dict, b: dict, a_died: bool = False, b_died: bool = False) -> Outcome | None:
        a_fell = a["self"]["pos"][1] < self.fall_y
        b_fell = b["self"]["pos"][1] < self.fall_y
        if a_fell and b_fell:
            return Outcome(None, "both_fell", tick)
        if a_fell:
            return Outcome("b", "fall", tick)
        if b_fell:
            return Outcome("a", "fall", tick)
        a_dead = a["self"]["health"] <= 0 or a_died
        b_dead = b["self"]["health"] <= 0 or b_died
        if a_dead and b_dead:
            return Outcome(None, "death", tick)
        if a_dead:
            return Outcome("b", "death", tick)
        if b_dead:
            return Outcome("a", "death", tick)
        if tick >= self.cap_ticks:
            return Outcome(None, "cap", tick)
        return None


class BlockUhcReferee:
    """Last one standing. Sudden death (Strength II for both) from `sudden_death_seconds`; at the cap, more health wins."""

    def __init__(self, cap_seconds: int, sudden_death_seconds: int):
        self.cap_ticks = cap_seconds * TICKS_PER_SECOND
        self.sudden_death_tick = sudden_death_seconds * TICKS_PER_SECOND

    def sudden_death(self, tick: int) -> bool:
        return tick >= self.sudden_death_tick

    def update(self, tick: int, a: dict, b: dict, a_died: bool = False, b_died: bool = False) -> Outcome | None:
        a_dead = a["self"]["health"] <= 0 or a_died
        b_dead = b["self"]["health"] <= 0 or b_died
        if a_dead and b_dead:
            return Outcome(None, "death", tick)
        if a_dead:
            return Outcome("b", "death", tick)
        if b_dead:
            return Outcome("a", "death", tick)
        if tick >= self.cap_ticks:
            ha, hb = a["self"]["health"], b["self"]["health"]
            if abs(ha - hb) < 1e-6:
                return Outcome(None, "cap", tick)
            return Outcome("a" if ha > hb else "b", "cap_health", tick)
        return None
