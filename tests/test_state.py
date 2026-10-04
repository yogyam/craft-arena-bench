from craft_arena_bench import INTERFACE_VERSION
from craft_arena_bench.arena import SumoArena
from craft_arena_bench.state import SUMO_ACTIONS, build_request, render_text
from craft_arena_bench.tiers import tier


def _snap(pos, health=20.0, opp_distance=5.0):
    return {
        "self": {
            "pos": pos,
            "yaw": 0.0,
            "pitch": 0.0,
            "velocity": [0.0, 0.0, 0.0],
            "on_ground": True,
            "health": health,
            "food": 20,
            "held": None,
            "inventory": {},
        },
        "opponent": {"visible": True, "distance": opp_distance},
    }


def test_request_shape_and_exact_opponent_health():
    arena = SumoArena()
    req = build_request(
        mode="sumo",
        tier=tier(5),
        match_id="abc",
        decision=3,
        tick=12,
        cap_seconds=60,
        me=_snap([0.5, -49.0, 0.5]),
        opp=_snap([4.5, -49.0, 0.5], health=7.5),
        platform=arena.platform,
        history=[{"tick": 1, "event": "took_damage", "amount": 1.0, "source": "melee"}, {"tick": -50, "event": "old"}],
        last_intent="rush",
        late_answers=1,
    )
    assert req["interface_version"] == INTERFACE_VERSION
    assert req["tier_hz"] == 5 and req["decision"] == 3 and req["tick"] == 12
    assert req["seconds_left"] == 59.4
    assert req["opponent"]["health"] == 7.5
    assert [a["id"] for a in req["actions"]] == SUMO_ACTIONS
    assert req["arena"]["my_edge_distance"] == 9.5
    assert [e["tick"] for e in req["history"]] == [1]
    assert req["self"]["last_intent"] == "rush" and req["self"]["late_answers"] == 1
    text = render_text(req)
    assert "Sumo, 5 decisions per second" in text
    assert "7.5/20 health" in text
    assert "Choose one: rush, strafe_left" in text
