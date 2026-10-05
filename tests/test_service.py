import datetime
import json
import os

import pytest

from craft_arena_bench import INTERFACE_VERSION
from craft_arena_bench.service import MATCHES_PER_PAIR, SEASON
from craft_arena_bench.service.manifests import (
    Manifest,
    SubmissionError,
    check_pull_request,
    load_manifest,
    new_manifest,
    write_manifest,
)
from craft_arena_bench.service.pairings import Pair, boards, pair_name, pair_seeds, pairs_to_play
from craft_arena_bench.service.rating import bootstrap_ratings, expected_share, opponents, points_from_matches, ratings


def _manifest(
    name="My Bot", github="alice", endpoint="https://bots.example.org/mybot", tiers=(2, 5), modes=("sumo", "block_uhc"), **kw
):
    return new_manifest(name, "Alice", github, endpoint, list(tiers), list(modes), **kw)


def test_manifest_round_trip_and_defaults():
    m = _manifest()
    d = m.to_dict()
    assert "house" not in d and d["interface_version"] == INTERFACE_VERSION and d["slug"] == "my-bot"
    assert Manifest.from_dict(d) == m


@pytest.mark.parametrize(
    "change, message",
    [
        ({"endpoint": "http://bots.example.org/x"}, "https"),
        ({"endpoint": "https://bots.example.org/x?token=1"}, "query"),
        ({"tiers": [20]}, "not open"),
        ({"tiers": [3]}, "may only hold"),
        ({"tiers": []}, "non-empty"),
        ({"modes": ["parkour"]}, "may only hold"),
        ({"interface_version": 99}, "Interface version"),
        ({"github": "-bad-"}, "GitHub login"),
        ({"submitted": "yesterday"}, "date"),
        ({"name": " padded"}, "spaces at the ends"),
        ({"house": True}, "local:"),
    ],
)
def test_manifest_refuses(change, message):
    d = _manifest().to_dict()
    d.update(change)
    with pytest.raises(SubmissionError, match=message):
        Manifest.from_dict(d)


def test_unknown_and_missing_fields():
    d = _manifest().to_dict()
    d["extra"] = 1
    with pytest.raises(SubmissionError, match="not allowed"):
        Manifest.from_dict(d)
    del d["extra"]
    del d["endpoint"]
    with pytest.raises(SubmissionError, match="missing"):
        Manifest.from_dict(d)


def test_house_manifest():
    m = new_manifest("House bot", "CraftArenaBench", "yogyam", "local:house", [2, 5], ["sumo", "block_uhc"], house=True)
    assert m.house and m.to_dict()["house"] is True


def test_load_manifest_checks_folder(tmp_path):
    subs = tmp_path / "submissions"
    path = write_manifest(_manifest(), str(subs))
    assert load_manifest(os.path.dirname(path)).slug == "my-bot"
    (subs / "my-bot" / "extra.txt").write_text("x")
    with pytest.raises(SubmissionError, match="may only hold"):
        load_manifest(str(subs / "my-bot"))
    os.remove(subs / "my-bot" / "extra.txt")
    os.rename(subs / "my-bot", subs / "other-slug")
    with pytest.raises(SubmissionError, match="slug"):
        load_manifest(str(subs / "other-slug"))


def test_pull_request_checks(tmp_path):
    subs = str(tmp_path / "submissions")
    folder = os.path.dirname(write_manifest(_manifest(), subs))
    assert check_pull_request([folder], "alice", subs)[0].slug == "my-bot"
    assert check_pull_request([folder], "ALICE", subs)  # logins compare case-insensitively
    with pytest.raises(SubmissionError, match="pull request is from"):
        check_pull_request([folder], "bob", subs)
    # a copy of the endpoint, or of the name, under another slug
    copy = os.path.dirname(write_manifest(_manifest(name="Other Bot", github="bob"), subs))
    with pytest.raises(SubmissionError, match="already submitted"):
        check_pull_request([copy], "bob", subs)
    same_name = _manifest(name="My Bot", github="bob", endpoint="https://x.example.org/y")
    same_name.slug = "bobs-bot"  # a hand-written slug that dodges the folder collision but not the name check
    copy2 = os.path.dirname(write_manifest(same_name, subs))
    with pytest.raises(SubmissionError, match="already used"):
        check_pull_request([copy2], "bob", subs)
    # limits: three bots per person, three submissions per 30 days
    for s in ("Bot Two", "Bot Three"):
        write_manifest(_manifest(name=s, endpoint=f"https://bots.example.org/{s.lower().replace(' ', '')}"), subs)
    fourth = os.path.dirname(write_manifest(_manifest(name="Bot Four", endpoint="https://bots.example.org/four"), subs))
    with pytest.raises(SubmissionError, match="bots on the board"):
        check_pull_request([fourth], "alice", subs)
    # the maintainers are exempt, and only they may add a house bot
    house = os.path.dirname(
        write_manifest(new_manifest("House", "CAB", "yogyam", "local:house", [2, 5], ["sumo"], house=True), subs)
    )
    assert check_pull_request([house], "yogyam", subs, exempt=("yogyam",))
    with pytest.raises(SubmissionError, match="only the maintainers"):
        check_pull_request([house], "yogyam", subs)


def test_submission_rate_limit(tmp_path):
    subs = str(tmp_path / "submissions")
    today = datetime.date(2026, 10, 4)
    for i, age in enumerate((1, 2)):
        m = _manifest(name=f"Old {i}", endpoint=f"https://bots.example.org/old{i}")
        m.submitted = (today - datetime.timedelta(days=age)).isoformat()
        write_manifest(m, subs)
    new = os.path.dirname(write_manifest(_manifest(name="New", endpoint="https://bots.example.org/new"), subs))
    assert check_pull_request([new], "alice", subs, today=today)  # three in the window is the limit
    m = _manifest(name="Old 0", endpoint="https://bots.example.org/old0")
    m.submitted = (today - datetime.timedelta(days=40)).isoformat()
    write_manifest(m, subs)  # an old one ages out of the window
    assert check_pull_request([new], "alice", subs, today=today)


def test_rating_basics():
    points = {("a", "b"): 8, ("b", "a"): 2, ("b", "c"): 7, ("c", "b"): 3, ("a", "c"): 9, ("c", "a"): 1}
    r = ratings(points)
    assert r["a"] > r["b"] > r["c"]
    assert abs(sum(r.values()) / 3 - 1000) < 1
    assert 0.49 < expected_share(1000, 1000) < 0.51 and expected_share(1400, 1000) > 0.9


def test_points_bootstrap_and_opponents():
    matches = {("a", "b"): [1, 1, 1, 0.5, 0, 1, 1, 1], ("b", "c"): [1, 0, 1, 1, 0.5, 1], ("a", "c"): [1, 1, 1, 1, 1, 1]}
    points = points_from_matches(matches)
    assert points[("a", "b")] == 6.5 and points[("b", "a")] == 1.5
    boot = bootstrap_ratings(matches, samples=40)
    assert set(boot) == {"a", "b", "c"}
    for v in boot.values():
        assert v["low"] <= v["rating"] <= v["high"]
    assert boot["a"]["rating"] > boot["c"]["rating"]
    assert bootstrap_ratings(matches, samples=40) == boot  # seeded
    assert opponents(matches) == {"a": 2, "b": 2, "c": 2}


def test_boards_and_seeds():
    assert boards() == [("sumo", 2), ("sumo", 5), ("block_uhc", 2), ("block_uhc", 5)]
    s = pair_seeds("sumo", 5)
    assert len(s) == MATCHES_PER_PAIR and len(set(s)) == MATCHES_PER_PAIR and s == pair_seeds("sumo", 5)
    assert not set(s) & set(pair_seeds("sumo", 2)) and not set(s) & set(pair_seeds("block_uhc", 5))
    assert all(x // 100_000 == SEASON for x in s)
    assert pair_name("zeta", "alpha") == "alpha__zeta"


def test_pairs_to_play(tmp_path):
    subs, duels = str(tmp_path / "submissions"), str(tmp_path / "duels")
    manifests = {}
    for name, modes in (("Alpha", ["sumo", "block_uhc"]), ("Beta", ["sumo"]), ("Gamma", ["sumo", "block_uhc"])):
        m = _manifest(name=name, endpoint=f"https://bots.example.org/{name.lower()}", modes=modes, tiers=[5])
        write_manifest(m, subs)
        manifests[m.slug] = m
    pending = pairs_to_play(manifests, subs, duels)
    assert len(pending) == 3 + 1  # three Sumo pairs at 5 Hz, one Block UHC pair
    assert Pair("block_uhc", 5, "alpha", "gamma") in pending
    assert pairs_to_play(manifests, subs, duels, only={"alpha", "gamma"}) == [
        Pair("sumo", 5, "alpha", "gamma"),
        Pair("block_uhc", 5, "alpha", "gamma"),
    ]
    # a current document removes its pair; a stale one (manifest changed) does not
    from craft_arena_bench import INTERFACE_VERSION, MODE_SET_VERSION
    from craft_arena_bench.service.manifests import manifest_digest

    p = Pair("sumo", 5, "alpha", "beta")
    os.makedirs(os.path.dirname(p.path(duels)))
    doc = {
        "a_manifest_sha256": manifest_digest(os.path.join(subs, "alpha")),
        "b_manifest_sha256": manifest_digest(os.path.join(subs, "beta")),
        "season": SEASON,
        "interface_version": INTERFACE_VERSION,
        "mode_set_version": MODE_SET_VERSION,
        "matches_per_pair": MATCHES_PER_PAIR,
    }
    json.dump(doc, open(p.path(duels), "w"))
    assert p not in pairs_to_play(manifests, subs, duels)
    doc["a_manifest_sha256"] = "0" * 64
    json.dump(doc, open(p.path(duels), "w"))
    assert p in pairs_to_play(manifests, subs, duels)
