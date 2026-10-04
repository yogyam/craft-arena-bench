from craft_arena_bench.arena import SumoArena
from craft_arena_bench.policies import HouseSumo, RandomPolicy, make_policy
from craft_arena_bench.state import SUMO_ACTIONS, build_request
from craft_arena_bench.tiers import tier


def _req(me_pos, opp_pos, opp_vel=(0.0, 0.0, 0.0), decision=1):
    arena = SumoArena()
    me = {
        "self": {
            "pos": list(me_pos),
            "yaw": 0.0,
            "pitch": 0.0,
            "velocity": [0.0, 0.0, 0.0],
            "on_ground": True,
            "health": 20.0,
            "food": 20,
            "held": None,
            "inventory": {},
        },
        "opponent": {"visible": True, "distance": ((me_pos[0] - opp_pos[0]) ** 2 + (me_pos[2] - opp_pos[2]) ** 2) ** 0.5},
    }
    opp = {
        "self": {
            "pos": list(opp_pos),
            "yaw": 0.0,
            "pitch": 0.0,
            "velocity": list(opp_vel),
            "on_ground": True,
            "health": 20.0,
            "food": 20,
            "held": None,
            "inventory": {},
        },
        "opponent": {"visible": True, "distance": me["opponent"]["distance"]},
    }
    return build_request(
        mode="sumo",
        tier=tier(5),
        match_id="x",
        decision=decision,
        tick=4 * decision,
        cap_seconds=60,
        me=me,
        opp=opp,
        platform=arena.platform,
        history=[],
        last_intent="hold",
        late_answers=0,
    )


def test_random_is_legal_and_seeded():
    req = _req([0.5, -49, 0.5], [5.5, -49, 0.5])
    pa, pb = RandomPolicy(1), RandomPolicy(1)
    a = [pa.decide(req) for _ in range(50)]
    b = [pb.decide(req) for _ in range(50)]
    assert a == b and set(a) <= set(SUMO_ACTIONS) and len(set(a)) > 1


def test_house_bot_charges_sidesteps_and_respects_the_edge():
    house = HouseSumo()
    assert house.decide(_req([0.5, -49, 0.5], [8.5, -49, 0.5])) == "rush"
    # Opponent sprinting straight at us from 3 blocks: sidestep.
    assert house.decide(_req([0.5, -49, 0.5], [3.5, -49, 0.5], opp_vel=(-0.28, 0, 0))).startswith("strafe_")
    # On the edge with the opponent close: sidestep rather than trade.
    assert house.decide(_req([-8.6, -49, 0.5], [-6.0, -49, 0.5])).startswith("strafe_")  # 0.4 from the -x edge at -9
    for d in range(1, 40):
        assert house.decide(_req([0.5, -49, 0.5], [3.0, -49, 0.5], decision=d)) in SUMO_ACTIONS


def test_make_policy():
    assert make_policy("house").name == "house-sumo"
    assert make_policy("random", 3).name == "random"
    assert make_policy("circler").decide(_req([0.5, -49, 0.5], [3.5, -49, 0.5])) == "strafe_right"
