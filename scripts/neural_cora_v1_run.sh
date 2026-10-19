#!/bin/sh
# Neural-CORA v1 pilot, scored stages: train -> run -> evaluate.
# Refuses to start unless data preparation finished cleanly and the protocol is committed, unchanged, and free of
# placeholders (records/NEURAL_CORA_V1_PILOT_PROTOCOL.md is frozen BEFORE training).
set -eu
cd "$(dirname "$0")/.."
PY="$HOME/.venvs/lesegenv/bin/python"
L=outputs/neural_cora_v1/logs
P=records/NEURAL_CORA_V1_PILOT_PROTOCOL.md
echo "waiting $(date -u +%FT%TZ) pid $$" >> "$L/run.status"
until grep -q PREP_DONE "$L/prep.status" 2>/dev/null; do
  kill -0 "$(sed -n 's/.*pid \([0-9]*\).*/\1/p' "$L/prep.status" | head -1)" 2>/dev/null || { echo "STOP: prep driver gone without PREP_DONE" >> "$L/run.status"; exit 1; }
  sleep 30
done
grep -q "qwen_exit 0" "$L/prep.status" || { echo "STOP: Qwen features failed" >> "$L/run.status"; exit 1; }
if grep -q "{{" "$P"; then echo "STOP: protocol has placeholders" >> "$L/run.status"; exit 1; fi
git ls-files --error-unmatch "$P" >/dev/null 2>&1 && git diff --quiet HEAD -- "$P" || { echo "STOP: protocol not committed" >> "$L/run.status"; exit 1; }
echo "protocol commit $(git log -1 --format=%h -- "$P")" >> "$L/run.status"
echo "train start $(date -u +%FT%TZ)" >> "$L/run.status"
CUDA_VISIBLE_DEVICES=0 nice -n 10 "$PY" -m cora_neural_v1.pilot train > "$L/train.log" 2>&1
echo "run start $(date -u +%FT%TZ)" >> "$L/run.status"
NEURAL_CORA_WORKERS=2 "$PY" -m cora_neural_v1.pilot run > "$L/run.log" 2>&1     # workers renice themselves to 10
echo "evaluate start $(date -u +%FT%TZ)" >> "$L/run.status"
nice -n 10 "$PY" -m cora_neural_v1.evaluate > "$L/evaluate.log" 2>&1
echo "RUN_DONE $(date -u +%FT%TZ)" >> "$L/run.status"
