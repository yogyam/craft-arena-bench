from craft_arena_bench.referee import SumoReferee


def _state(y=-49.0, health=20.0):
    return {"self": {"pos": [0.0, y, 0.0], "health": health}}


def test_fall_death_cap_and_draws():
    ref = SumoReferee(fall_y=-52.0, cap_seconds=60)
    assert ref.update(10, _state(), _state()) is None
    assert ref.update(10, _state(y=-53), _state()).winner == "b"
    assert ref.update(10, _state(), _state(y=-53)).winner == "a"
    assert ref.update(10, _state(y=-53), _state(y=-60)).winner is None
    assert ref.update(10, _state(health=0), _state()).winner == "b"
    assert ref.update(10, _state(), _state(), a_died=True).winner == "b"
    assert ref.update(10, _state(), _state(), b_died=True).winner == "a"
    out = ref.update(1200, _state(), _state())
    assert out.winner is None and out.reason == "cap"
    assert ref.update(1199, _state(), _state()) is None


def test_sumo_cap_tiebreak_rewards_holding_the_centre():
    ref = SumoReferee(fall_y=-52.0, cap_seconds=60, centre=(0.5, 0.5))

    def at(x, z):
        return {"self": {"pos": [x, -49.0, z], "health": 20.0}}

    # a sits near the centre, b near the rim, for the whole match: a wins at the cap.
    for t in range(1, 1200):
        assert ref.update(t, at(1.0, 0.5), at(7.0, 0.5)) is None
    out = ref.update(1200, at(1.0, 0.5), at(7.0, 0.5))
    assert out.winner == "a" and out.reason == "cap_centre"
    # a dash to the centre in the last second does not overturn ten seconds outside.
    ref = SumoReferee(fall_y=-52.0, cap_seconds=60, centre=(0.5, 0.5))
    for t in range(1, 1181):
        ref.update(t, at(7.0, 0.5), at(1.0, 0.5))
    for t in range(1181, 1200):
        ref.update(t, at(0.5, 0.5), at(1.0, 0.5))
    assert ref.update(1200, at(0.5, 0.5), at(1.0, 0.5)).winner == "b"
    # within half a block: a draw.
    ref = SumoReferee(fall_y=-52.0, cap_seconds=60, centre=(0.5, 0.5))
    for t in range(1, 1200):
        ref.update(t, at(2.0, 0.5), at(2.3, 0.5))
    out = ref.update(1200, at(2.0, 0.5), at(2.3, 0.5))
    assert out.winner is None and out.reason == "cap"
    # without a centre (old callers) the cap is still a draw.
    ref = SumoReferee(fall_y=-52.0, cap_seconds=60)
    assert ref.update(1200, at(0.5, 0.5), at(7.0, 0.5)).reason == "cap"
