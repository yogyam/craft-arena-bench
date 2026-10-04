import pytest

from craft_arena_bench.tiers import TIERS, tier


def test_tiers():
    assert [t.hz for t in TIERS.values()] == [2, 5, 20]
    assert all(t.period_ticks * t.hz == 20 for t in TIERS.values())
    assert all(t.budget_ms < 1000 / t.hz for t in TIERS.values())
    assert sum(1 for t in TIERS.values() if t.open_in_season_1) == 2
    assert tier(5).decision_due(8) and not tier(5).decision_due(7)
    assert tier(20).decision_due(7)
    with pytest.raises(ValueError):
        tier(7)
