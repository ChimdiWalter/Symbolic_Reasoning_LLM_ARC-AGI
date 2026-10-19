#!/bin/sh
# Runs the dev60 expressivity atlas AFTER the pilot finished (keeps the pilot's two-CPU-worker cap intact).
set -eu
cd "$(dirname "$0")/.."
PY="$HOME/.venvs/lesegenv/bin/python"
L=outputs/neural_cora_v1/logs
until grep -qE "RUN_DONE|STOP" "$L/run.status" 2>/dev/null; do sleep 60; done
grep -q RUN_DONE "$L/run.status" || { echo "atlas not run: pilot stopped" > "$L/atlas.status"; exit 1; }
nice -n 10 "$PY" scripts/neural_cora_v1_atlas.py solve > "$L/atlas_solve.log" 2>&1
nice -n 10 "$PY" scripts/neural_cora_v1_atlas.py score > "$L/atlas_score.log" 2>&1
echo "ATLAS_DONE $(date -u +%FT%TZ)" > "$L/atlas.status"
