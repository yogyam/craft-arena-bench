import craft_arena_bench as cab


def test_versions_are_positive_integers():
    assert cab.INTERFACE_VERSION >= 1
    assert cab.MODE_SET_VERSION >= 1
    assert cab.PAPER_BUILD >= 1
    assert cab.MINECRAFT_VERSION.count(".") >= 1
