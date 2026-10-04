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
