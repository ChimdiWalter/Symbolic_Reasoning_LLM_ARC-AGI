#!/bin/sh
# Reproduce the Neural-CORA v1 pilot end to end (protocol: records/NEURAL_CORA_V1_PILOT_PROTOCOL.md, frozen 081c1d3).
# No network is needed once the NVARC Qwen3-4B checkpoint is in outputs/neural_cora_v0/models/ (its sha256 is in
# records/NEURAL_CORA_V1_FREEZE_MANIFEST.json). GPU 0; at most two CPU workers at nice 10.
#   1. data preparation: freeze, generate, audit, targets, Qwen and hand features
#   2. scored stages: train (L1, L1h, L0s; L0 untrained) -> run (every arm) -> evaluate
#   3. the dev60 expressivity atlas (exposed tasks; a measurement, not a score)
set -eu
cd "$(dirname "$0")/.."
sh scripts/neural_cora_v1_prep.sh
sh scripts/neural_cora_v1_run.sh
sh scripts/neural_cora_v1_atlas.sh
python3 - <<'PY'
import json
d = json.load(open("outputs/neural_cora_v1/evaluator/pilot_v1_eval.json"))["G1_decision"]
print("G1:", d.get("G1"), d.get("classification"))
PY
