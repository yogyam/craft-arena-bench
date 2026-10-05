"""Summarises a folder of match results and replays: outcomes, lengths, stuck matches, seed determinism of spawns."""

import glob
import gzip
import json
import statistics
import sys
from collections import Counter, defaultdict

folder = sys.argv[1] if len(sys.argv) > 1 else "runs/check"
for path in sorted(glob.glob(f"{folder}/*.json")):
    results = json.load(open(path))
    if not results:
        continue
    r0 = results[0]
    secs = [r["seconds"] for r in results]
    print(f"\n{path}: {r0['a']} vs {r0['b']} at {r0['tier_hz']} Hz, {len(results)} matches")
    print("  winners:", dict(Counter({"a": r0["a"], "b": r0["b"], None: "draw"}[r["winner"]] for r in results)))
    print("  reasons:", dict(Counter(r["reason"] for r in results)))
    print(
        f"  length: min {min(secs):.1f} s  median {statistics.median(secs):.1f} s  max {max(secs):.1f} s;  decisions median {statistics.median(r['decisions'] for r in results)}"
    )
    print(
        f"  wall per match: median {statistics.median(r['wall_seconds'] for r in results):.1f} s; overhead median {statistics.median(r['wall_seconds'] - r['seconds'] for r in results):.1f} s"
    )
    if r0["mode"] == "sumo":
        print(f"  health at end always 20/20: {all(r['a_health'] == 20 and r['b_health'] == 20 for r in results)}")
    else:
        print(
            f"  health at end: A mean {statistics.mean(r['a_health'] for r in results):.1f}, B mean {statistics.mean(r['b_health'] for r in results):.1f}"
        )
        for side in ("a", "b"):
            total = Counter()
            for r in results:
                total.update(r.get(f"{side}_events", {}))
            print(f"  {side.upper()} events over all matches: {dict(sorted(total.items()))}")
        failed = sum(
            r.get("a_events", {}).get("action_failed", 0) + r.get("b_events", {}).get("action_failed", 0) for r in results
        )
        print(
            f"  action_failed total: {failed}; matches reaching sudden death: {sum(1 for r in results if r['seconds'] > 60)}; at cap: {sum(1 for r in results if r['reason'] in ('cap', 'cap_health'))}"
        )

# Spawn determinism: the first frame of every replay for a seed must have the same positions.
first_frames = defaultdict(set)
for path in glob.glob(f"{folder}/replays/*.json.gz"):
    d = json.load(gzip.open(path, "rt"))
    f = d["frames"][0]
    first_frames[(d["meta"]["mode"], d["meta"]["seed"])].add((tuple(f[1][:3]), tuple(f[2][:3])))
repeated = {k: v for k, v in first_frames.items() if len(v) > 1}
print(
    f"\nreplays: {sum(len(v) for v in first_frames.values())} across {len(first_frames)} seeds; seeds with inconsistent spawns: {len(repeated)}"
)
distinct_spawns = {next(iter(v)) for v in first_frames.values()}
print(f"distinct spawn layouts across seeds: {len(distinct_spawns)}")
