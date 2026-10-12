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
    """Falling loses. At the cap, the bot that stayed nearer the centre on average over the last ten seconds wins;
    within half a block of each other it is a draw. A last-second dash to the centre does not help."""

    TIEBREAK_WINDOW_TICKS = 10 * TICKS_PER_SECOND
    TIEBREAK_MARGIN = 0.5  # blocks

    def __init__(self, fall_y: float, cap_seconds: int, centre: tuple[float, float] | None = None):
        self.fall_y = fall_y
        self.cap_ticks = cap_seconds * TICKS_PER_SECOND
        self.centre = centre
        self._dist: tuple[list[float], list[float]] = ([], [])

    def _track(self, a: dict, b: dict) -> None:
        if self.centre is None:
            return
        for i, s in enumerate((a, b)):
            x, _, z = s["self"]["pos"]
            self._dist[i].append(((x - self.centre[0]) ** 2 + (z - self.centre[1]) ** 2) ** 0.5)
            if len(self._dist[i]) > self.TIEBREAK_WINDOW_TICKS:
                del self._dist[i][0]

    def centre_averages(self) -> tuple[float, float] | None:
        if self.centre is None or not self._dist[0] or not self._dist[1]:
            return None
        return (sum(self._dist[0]) / len(self._dist[0]), sum(self._dist[1]) / len(self._dist[1]))

    def update(self, tick: int, a: dict, b: dict, a_died: bool = False, b_died: bool = False) -> Outcome | None:
        self._track(a, b)
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
            averages = self.centre_averages()
            if averages is not None:
                da, db = averages
                if abs(da - db) >= self.TIEBREAK_MARGIN:
                    return Outcome("a" if da < db else "b", "cap_centre", tick)
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
