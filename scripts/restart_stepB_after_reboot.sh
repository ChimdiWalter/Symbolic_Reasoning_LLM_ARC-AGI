#!/bin/bash
# Relaunch the CORA Level 4 Step B invention run after a reboot.
# Safe to rerun: the runner writes outputs only at the end, so an interrupted
# run leaves no partial artifacts. --require-manifest re-verifies every pin
# (manifest 2beb5069de5c34f1...) before any work starts, and aborts on drift.
# Do NOT edit scripts/cora_level4_stepB_run.py or level4_stepB/candidates.py:
# their hashes are frozen in the manifest.
set -euo pipefail
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate

if pgrep -f "cora_level4_stepB_run.py" > /dev/null; then
    echo "Step B runner already running:"
    pgrep -af "cora_level4_stepB_run.py"
    exit 1
fi
if [ -f outputs/cora_breakthrough/level4_stepB_output_hash.txt ]; then
    echo "level4_stepB_output_hash.txt already exists — Step B finished; do NOT rerun."
    exit 1
fi

nohup python3 scripts/cora_level4_stepB_run.py --workers 20 --require-manifest \
    > logs/level4_stepB_run.log 2>&1 &
echo "relaunched, pid $!"
echo "monitor: tail -f logs/level4_stepB_run.log   (counts only; done at 'STEP B FROZEN')"
