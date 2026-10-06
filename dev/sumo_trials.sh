#!/bin/sh
cd "$(dirname "$0")/.."
OUT=runs/sumo-v21; rm -rf "$OUT"; mkdir -p "$OUT"
run() { echo "=== $* ==="; .venv/bin/craft-arena-bench play "$@" --out "$OUT" --no-replay 2>&1 | grep -E "^seed|^A="; }
run --mode sumo --tier 5 --a house --b circler --matches 5 --seed 2000
run --mode sumo --tier 5 --a house --b random --matches 3 --seed 2100
run --mode sumo --tier 1 --a house --b http://127.0.0.1:9020 --matches 6 --seed 2300
echo TRIALS_DONE
