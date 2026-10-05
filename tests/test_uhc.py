import math

from craft_arena_bench.arena import BlockUhcArena
from craft_arena_bench.policies import HouseUhc, make_policy
from craft_arena_bench.referee import BlockUhcReferee
from craft_arena_bench.state import UHC_ACTIONS, build_request, legal_actions
from craft_arena_bench.tiers import tier

FULL = {"diamond_sword": 1, "bow": 1, "arrow": 16, "water_bucket": 1, "lava_bucket": 1, "cobblestone": 64}


def _snap(pos, health=20.0, inv=None, held="diamond_sword", visible=True, distance=8.0, hazard=None):
    return {
        "self": {
            "pos": pos,
            "yaw": 0.0,
            "pitch": 0.0,
            "velocity": [0.0, 0.0, 0.0],
            "on_ground": True,
            "health": health,
            "food": 20,
            "held": held,
            "inventory": dict(FULL) if inv is None else inv,
            "hazard": hazard,
        },
        "opponent": {"visible": visible, "distance": distance, "blocks_placed_recently": 0},
    }


def _req(me, opp, decision=1, sd=False):
    arena = BlockUhcArena()
    return build_request(
        mode="block_uhc",
        tier=tier(5),
        match_id="m",
        decision=decision,
        tick=4 * decision,
        cap_seconds=180,
        me=me,
        opp=opp,
        platform=arena.bounds,
        history=[],
        last_intent="hold",
        late_answers=0,
        sudden_death=sd,
        floor_y=-60.0,
    )


def test_layout_is_seeded_and_inside_the_walls():
    arena = BlockUhcArena()
    for seed in range(15):
        lay1, lay2 = arena.layout(seed), arena.layout(seed)
        assert lay1 == lay2
        a, b = lay1["spawns"]
        assert math.hypot(a.pos[0] - b.pos[0], a.pos[2] - b.pos[2]) > 15
        for sp in (a, b):
            assert arena.bounds.edge_distance(sp.pos[0], sp.pos[2]) > 1
        assert len(lay1["pillars"]) == arena.spec["pillars"]["count"]
        for x, z, h in lay1["pillars"]:
            assert arena.bounds.min[0] < x < arena.bounds.max[0] and arena.bounds.min[2] < z < arena.bounds.max[2]
            assert 2 <= h <= 3
            assert all(math.hypot(x + 0.5 - sp.pos[0], z + 0.5 - sp.pos[2]) >= 3 for sp in (a, b))
    assert len({arena.layout(s)["spawns"][0].pos for s in range(40)}) >= 8


def test_legal_actions_follow_inventory_and_range():
    legal = legal_actions("block_uhc", _snap([100.5, -60.0, 100.5]), None, floor_y=-60.0)
    assert legal == [x for x in UHC_ACTIONS if x != "bucket_lava"]  # opponent 8 blocks away
    assert "bucket_lava" in legal_actions("block_uhc", _snap([100.5, -60.0, 100.5], distance=3.0), None, floor_y=-60.0)
    empty = _snap([100.5, -60.0, 100.5], inv={"diamond_sword": 1}, visible=False)
    assert legal_actions("block_uhc", empty, None, floor_y=-60.0) == ["rush", "strafe_left", "strafe_right", "retreat", "hold"]
    assert "pillar_up" not in legal_actions("block_uhc", _snap([100.5, -57.0, 100.5]), None, floor_y=-60.0)
    assert "place_wall" not in legal_actions("block_uhc", _snap([100.5, -60.0, 100.5], distance=15.0), None, floor_y=-60.0)


def test_request_has_uhc_fields_and_text():
    me = _snap([100.5, -60.0, 100.5], hazard={"kind": "lava", "distance": 2.2, "direction": "left"})
    opp = _snap([108.5, -60.0, 100.5], health=11.0, held="bow")
    req = _req(me, opp, decision=4, sd=True)
    assert req["sudden_death"] is True
    assert req["opponent"]["charging_bow"] is True and req["opponent"]["health"] == 11.0
    assert req["arena"]["hazards_near"][0]["kind"] == "lava"
    assert "Sudden death" in req["text"] and "Hazard: lava 2.2 blocks left" in req["text"] and "drawing a bow" in req["text"]
    assert [a["id"] for a in req["actions"]] == [x for x in UHC_ACTIONS if x != "bucket_lava"]


def test_referee_death_cap_and_health_tiebreak():
    ref = BlockUhcReferee(cap_seconds=180, sudden_death_seconds=60)

    def s(h):
        return {"self": {"pos": [0, -60, 0], "health": h}}

    assert ref.update(100, s(20), s(20)) is None
    assert not ref.sudden_death(1199) and ref.sudden_death(1200)
    assert ref.update(100, s(0), s(5)).winner == "b"
    assert ref.update(100, s(5), s(5), b_died=True).winner == "a"
    out = ref.update(3600, s(7), s(4))
    assert out.winner == "a" and out.reason == "cap_health"
    assert ref.update(3600, s(7), s(7)).winner is None


def test_house_uhc_is_legal_and_sensible():
    house = HouseUhc()
    assert house.decide(_req(_snap([100.5, -60, 100.5], distance=12.0), _snap([112.5, -60, 100.5]))) == "shoot_bow"
    burning = _req(
        _snap([100.5, -60, 100.5], distance=12.0, hazard={"kind": "lava", "distance": 1.0, "direction": "ahead"}),
        _snap([112.5, -60, 100.5]),
    )
    assert house.decide(burning) == "bucket_water"
    losing_close = _req(_snap([100.5, -60, 100.5], health=6.0, distance=3.0), _snap([103.5, -60, 100.5], health=18.0))
    assert house.decide(losing_close) == "bucket_lava"
    assert house.decide(_req(_snap([100.5, -60, 100.5], distance=2.0), _snap([102.5, -60, 100.5]))) == "rush"
    for d in range(1, 30):
        r = _req(_snap([100.5, -60, 100.5], distance=5.0), _snap([105.5, -60, 100.5]), decision=d)
        assert house.decide(r) in {a["id"] for a in r["actions"]}
    assert make_policy("house", 0, "block_uhc").name == "house-uhc"
    assert make_policy("house", 0, "sumo").name == "house-sumo"
