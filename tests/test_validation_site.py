import copy
import gzip
import json
import os

import pytest

from craft_arena_bench import INTERFACE_VERSION, MODE_SET_VERSION
from craft_arena_bench.service import MATCHES_PER_PAIR, SEASON
from craft_arena_bench.service.manifests import SubmissionError, manifest_digest, new_manifest, write_manifest
from craft_arena_bench.service.pairings import pair_seeds
from craft_arena_bench.service.site import build_site, render
from craft_arena_bench.service.validation import (
    validate_pair_document,
    validate_paths,
    validate_published_pair,
    validate_replays_document,
)


def _subs(tmp_path, names=("alpha", "beta", "gamma")):
    subs = str(tmp_path / "submissions")
    manifests = {}
    for n in names:
        if n == "alpha":
            m = new_manifest("House bot", "CAB", "yogyam", "local:house", [2, 5], ["sumo", "block_uhc"], house=True)
            m.slug = "alpha"
        else:
            m = new_manifest(
                n.capitalize(), n, n, f"https://{n}.example.org/bot", [2, 5], ["sumo", "block_uhc"], description=f"{n}'s model"
            )
        write_manifest(m, subs)
        manifests[m.slug] = m
    return subs, manifests


def _pair_doc(subs, a, b, mode="sumo", hz=5, a_wins=12, b_wins=6, draws=2):
    seeds = pair_seeds(mode, hz)
    outcomes = ["a"] * a_wins + ["b"] * b_wins + [None] * draws
    matches = []
    for i, seed in enumerate(seeds):
        w = outcomes[i]
        matches.append(
            {
                "seed": seed,
                "a_on_spawn": "A" if i % 2 == 0 else "B",
                "winner": w,
                "reason": "fall" if w else "cap",
                "seconds": 12.5,
                "decisions": 62,
                "a_health": 20.0,
                "b_health": 20.0,
                "a_stats": {"asked": 62, "late_or_missing": 0, "median_ms": 0.0},
                "b_stats": {"asked": 62, "late_or_missing": 1, "median_ms": 48.0},
                "a_events": {},
                "b_events": {},
            }
        )
    return {
        "a": a,
        "b": b,
        "mode": mode,
        "tier_hz": hz,
        "a_manifest_sha256": manifest_digest(os.path.join(subs, a)),
        "b_manifest_sha256": manifest_digest(os.path.join(subs, b)),
        "season": SEASON,
        "interface_version": INTERFACE_VERSION,
        "mode_set_version": MODE_SET_VERSION,
        "matches_per_pair": MATCHES_PER_PAIR,
        "seeds": seeds,
        "played_at": "2026-10-04T00:00:00Z",
        "benchmark_version": "0.0.1",
        "server": {"minecraft": "26.1.2"},
        "libraries": {},
        "a_points": a_wins + 0.5 * draws,
        "b_points": b_wins + 0.5 * draws,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "a_latency": {"median_ms": 0.0, "late_fraction": 0.0, "asked": 62 * 20},
        "b_latency": {"median_ms": 48.0, "late_fraction": 0.016, "asked": 62 * 20},
        "matches": matches,
    }


def test_pair_document_validates_and_refuses(tmp_path):
    subs, _ = _subs(tmp_path)
    doc = _pair_doc(subs, "alpha", "beta")
    validate_pair_document(doc)
    bad = [
        (lambda d: d.update(a_points=99), "Points"),
        (lambda d: d.update(a_wins=1), "Win counts"),
        (lambda d: d.update(season=SEASON + 1), "season"),
        (lambda d: d.update(matches_per_pair=19), "20 matches"),
        (lambda d: d.update(seeds=[0] * MATCHES_PER_PAIR), "seeds"),
        (lambda d: d["matches"][0].update(winner="c"), "winner"),
        (lambda d: d["matches"][1].update(a_on_spawn="A"), "alternating"),
        (lambda d: d.update(a="zeta"), "alphabetical"),
        (lambda d: d.update(extra=1), "wrong fields"),
        (lambda d: d.update(tier_hz=20), "not open"),
    ]
    for mutate, message in bad:
        d = copy.deepcopy(doc)
        mutate(d)
        with pytest.raises(SubmissionError, match=message):
            validate_pair_document(d)


def test_published_pair_checks_repository(tmp_path):
    subs, _ = _subs(tmp_path)
    doc = _pair_doc(subs, "alpha", "beta")
    folder = tmp_path / "new" / "duels" / "sumo-5hz"
    folder.mkdir(parents=True)
    path = folder / "alpha__beta.json"
    path.write_text(json.dumps(doc))
    validate_published_pair(str(path), subs)
    wrong = folder / "alpha__gamma.json"
    wrong.write_text(json.dumps(doc))
    with pytest.raises(SubmissionError, match="must be at"):
        validate_published_pair(str(wrong), subs)
    doc2 = dict(doc, a_manifest_sha256="0" * 64)
    path.write_text(json.dumps(doc2))
    with pytest.raises(SubmissionError, match="not for the manifest"):
        validate_published_pair(str(path), subs)
    # a board the bot did not enter
    with pytest.raises(SubmissionError, match="did not enter"):
        m = new_manifest("Delta", "delta", "delta", "https://delta.example.org/bot", [2], ["sumo"])
        write_manifest(m, subs)
        d3 = _pair_doc(subs, "beta", "delta")
        p3 = folder / "beta__delta.json"
        p3.write_text(json.dumps(d3))
        validate_published_pair(str(p3), subs)


def test_replays_document_and_paths(tmp_path):
    subs, _ = _subs(tmp_path)
    rep = {
        "pair": "alpha__beta",
        "a": "alpha",
        "b": "beta",
        "mode": "sumo",
        "tier_hz": 5,
        "season": SEASON,
        "arena": {"min": [-9, -50, -9], "max": [9, -50, 9], "kind": "platform"},
        "replays": [
            {
                "meta": {"seed": 1},
                "outcome": {"winner": "a", "reason": "fall", "tick": 40},
                "frame_fields": [],
                "frames": [[t, [0.5, -49, 0.5, 90, 0, 20], [3.5, -49, 0.5, -90, 0, 20], ["rush", "hold"]] for t in range(1, 41)],
            }
        ],
    }
    validate_replays_document(rep)
    bad = copy.deepcopy(rep)
    bad["replays"][0]["frames"][3][1][0] = "x"
    with pytest.raises(SubmissionError, match="sensible number"):
        validate_replays_document(bad)
    folder = tmp_path / "new" / "replays" / "sumo-5hz"
    folder.mkdir(parents=True)
    rp = folder / "alpha__beta.replays.json.gz"
    with gzip.open(rp, "wt") as f:
        json.dump(rep, f)
    dfolder = tmp_path / "new" / "duels" / "sumo-5hz"
    dfolder.mkdir(parents=True)
    dp = dfolder / "alpha__beta.json"
    dp.write_text(json.dumps(_pair_doc(subs, "alpha", "beta")))
    validate_paths([str(dp), str(rp)], subs)
    with pytest.raises(SubmissionError, match="Not a result file"):
        validate_paths([str(tmp_path / "x.txt")], subs)


def test_site_renders_and_builds(tmp_path):
    subs, manifests = _subs(tmp_path)
    docs = [
        _pair_doc(subs, "alpha", "beta"),
        _pair_doc(subs, "alpha", "gamma", a_wins=15, b_wins=5, draws=0),
        _pair_doc(subs, "beta", "gamma", a_wins=10, b_wins=10, draws=0),
    ]
    page = render(manifests, docs, {"gamma": "https://github.com/yogyam/craft-arena-bench/issues/1"})
    assert "Sumo at 5 decisions per second" in page and "house" in page and "Flagged" in page
    assert "needs 3 opponents" in page  # three bots, two opponents each: no rating shown yet
    assert "gamma&#x27;s model" in page or "gamma's model" in page  # descriptions are escaped and shown
    assert '<script src="site.js">' in page and "Content-Security-Policy" in page
    # with a fourth bot everyone has three opponents and ratings appear
    m = new_manifest("Delta", "delta", "delta", "https://delta.example.org/bot", [5], ["sumo"])
    write_manifest(m, subs)
    manifests["delta"] = m
    docs += [
        _pair_doc(subs, "alpha", "delta"),
        _pair_doc(subs, "beta", "delta"),
        _pair_doc(subs, "delta", "gamma", a_wins=4, b_wins=16, draws=0),
    ]
    page = render(manifests, docs, {})
    assert "needs 3 opponents" not in page.split('id="sumo-5hz"')[1].split("<h2")[0]
    # build: duels and replays on disk, site in output
    duels = tmp_path / "duels" / "sumo-5hz"
    duels.mkdir(parents=True)
    for d in docs:
        (duels / f"{d['a']}__{d['b']}.json").write_text(json.dumps(d))
    out = build_site(subs, str(tmp_path / "duels"), str(tmp_path / "replays"), str(tmp_path / "site"))
    assert (
        os.path.isfile(out)
        and os.path.isfile(tmp_path / "site" / "replay.html")
        and os.path.isfile(tmp_path / "site" / "replay.js")
    )
    assert "<script" not in (tmp_path / "site" / "replay.html").read_text().replace('<script src="replay.js"></script>', "")
