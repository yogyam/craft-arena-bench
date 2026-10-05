"""Decision-rate tiers. A tier fixes how often the model is asked and how long it has to answer."""

from __future__ import annotations

from dataclasses import dataclass

TICKS_PER_SECOND = 20


@dataclass(frozen=True)
class Tier:
    hz: int
    period_ticks: int
    budget_ms: int
    open_in_season_1: bool

    def decision_due(self, tick: int) -> bool:
        return tick % self.period_ticks == 0


TIERS: dict[int, Tier] = {
    # For models behind a remote API, often with a tunnel in the path: a hosted model from a laptop measured ~800 ms.
    1: Tier(hz=1, period_ticks=20, budget_ms=900, open_in_season_1=True),
    2: Tier(hz=2, period_ticks=10, budget_ms=400, open_in_season_1=True),
    5: Tier(hz=5, period_ticks=4, budget_ms=150, open_in_season_1=True),
    # Built and measured, but not open until an entrant asks for it and the runner is shown to hold the clock.
    20: Tier(hz=20, period_ticks=1, budget_ms=40, open_in_season_1=False),
}


def tier(hz: int) -> Tier:
    try:
        return TIERS[hz]
    except KeyError:
        raise ValueError(f"no such tier: {hz} Hz; tiers are {sorted(TIERS)}") from None
