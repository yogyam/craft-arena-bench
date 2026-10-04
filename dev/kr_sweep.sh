#!/bin/sh
# Sweep knockback resistance in arenas/sumo.json with house vs circler; restores the file afterwards.
cd "$(dirname "$0")/.."
cp arenas/sumo.json /tmp/sumo.json.bak
for kr in 0.5 0.25 0.0; do
  python3 -c "import json,sys; p='arenas/sumo.json'; d=json.load(open(p)); d['attributes']['minecraft:knockback_resistance']=float(sys.argv[1]); json.dump(d, open(p,'w'), indent=2)" "$kr"
  echo "=== knockback_resistance $kr ==="
  .venv/bin/craft-arena-bench play --a house --b circler --tier 5 --matches 3 --seed 600 --out "runs/kr-$kr" --no-replay 2>&1 | grep -E "^seed|^A="
done
cp /tmp/sumo.json.bak arenas/sumo.json
echo SWEEP_DONE
