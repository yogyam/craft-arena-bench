import math

from craft_arena_bench.arena import GAMERULES, SumoArena


def test_spawns_are_deterministic_and_opposite():
    arena = SumoArena()
    for seed in range(20):
        a1, b1 = arena.spawns(seed)
        a2, b2 = arena.spawns(seed)
        assert (a1, b1) == (a2, b2)
        cx, _, cz = arena.spec["origin"]
        d_a = math.hypot(a1.pos[0] - cx - 0.5, a1.pos[2] - cz - 0.5)
        d_b = math.hypot(b1.pos[0] - cx - 0.5, b1.pos[2] - cz - 0.5)
        assert abs(d_a - arena.spec["spawn_distance"]) < 1e-2  # positions are rounded to 3 decimals
        assert abs(d_b - arena.spec["spawn_distance"]) < 1e-2
        assert arena.platform.edge_distance(a1.pos[0], a1.pos[2]) > 0.5
        assert arena.platform.edge_distance(b1.pos[0], b1.pos[2]) > 0.5


def test_seeds_vary_the_spawn_axis_and_sides():
    arena = SumoArena()
    positions = {arena.spawns(seed)[0].pos for seed in range(40)}
    assert len(positions) >= 8


def test_edge_distance():
    arena = SumoArena()
    p = arena.platform
    centre_x = (p.min[0] + p.max[0] + 1) / 2
    centre_z = (p.min[2] + p.max[2] + 1) / 2
    assert p.edge_distance(centre_x, centre_z) == 9.5
    assert p.edge_distance(p.min[0], centre_z) == 0.0
    assert p.edge_distance(p.min[0] - 1, centre_z) < 0


def test_gamerules_use_26_1_names():
    for name in GAMERULES:
        assert name == name.lower() and " " not in name, name
