#!/bin/sh
# Neural-CORA v1 pilot, data preparation (no scored run): freeze baselines, generate, audit, targets, features.
# GPU 0 only; at most two low-priority CPU processes at a time (the GPU job's driver + one CPU worker).
set -eu
cd "$(dirname "$0")/.."
PY="$HOME/.venvs/lesegenv/bin/python"
L=outputs/neural_cora_v1/logs
mkdir -p "$L"
echo "started $(date -u +%FT%TZ) pid $$" > "$L/prep.status"
nice -n 10 "$PY" -m cora_neural_v1.pilot freeze > "$L/freeze.log" 2>&1
nice -n 10 "$PY" -m cora_neural_v1.pilot generate > "$L/generate.log" 2>&1
( CUDA_VISIBLE_DEVICES=0 nice -n 10 "$PY" -m cora_neural_v1.pilot features qwen > "$L/features_qwen.log" 2>&1; echo $? > "$L/features_qwen.exit" ) &
GPU_JOB=$!
nice -n 10 "$PY" -m cora_neural_v1.pilot audit > "$L/audit.log" 2>&1
NEURAL_CORA_WORKERS=1 nice -n 10 "$PY" -m cora_neural_v1.pilot targets > "$L/targets.log" 2>&1
nice -n 10 "$PY" -m cora_neural_v1.pilot features hand > "$L/features_hand.log" 2>&1
wait "$GPU_JOB"
echo "PREP_DONE $(date -u +%FT%TZ) qwen_exit $(cat "$L/features_qwen.exit")" >> "$L/prep.status"
