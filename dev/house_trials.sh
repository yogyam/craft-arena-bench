#!/bin/sh
# House bot trials against the reference bots and the two local model endpoints. Results in runs/house-v2/.
cd "$(dirname "$0")/.."
OUT=runs/house-v2; rm -rf "$OUT"; mkdir -p "$OUT"
run() { echo "=== $* ==="; .venv/bin/craft-arena-bench play "$@" --out "$OUT" --no-replay 2>&1 | grep -E "^seed|^A="; }
run --mode sumo --tier 5 --a house --b circler --matches 5 --seed 1000
run --mode sumo --tier 5 --a house --b random --matches 5 --seed 1100
run --mode sumo --tier 2 --a house --b http://127.0.0.1:9010 --matches 5 --seed 1200
run --mode sumo --tier 1 --a house --b http://127.0.0.1:9020 --matches 5 --seed 1300
run --mode block_uhc --tier 1 --a house --b http://127.0.0.1:9020 --matches 6 --seed 1400
run --mode block_uhc --tier 2 --a house --b http://127.0.0.1:9010 --matches 6 --seed 1500
run --mode block_uhc --tier 5 --a house --b random --matches 6 --seed 1600
echo TRIALS_DONE
