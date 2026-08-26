#!/bin/bash
# Relaunch the CORA Level 4 Step B invention run after a reboot or crash.
#
# Safe to rerun. The runner keeps an append-only fsynced journal
# (outputs/cora_breakthrough/level4_stepB_journal.jsonl): every completed unit is
# recorded as it finishes, a restart REPLAYS those results byte-for-byte and
# computes only the missing units, and the journal is deleted when the run
# completes. A reboot therefore costs only the units that were in flight.
#
# The journal's header pins the runner sha, the run manifest sha and every input
# sha; a journal written by any other configuration ABORTS the run rather than
# being mixed in. --require-manifest re-verifies every pin (manifest
# 8476b211400f1c3f...) before any work starts and aborts on drift.
#
# Do NOT edit scripts/cora_level4_stepB_run.py or level4_stepB/candidates.py:
# their hashes are frozen in the manifest, and the journal header would reject
# an existing journal.
#
# The journal holds proposal records mid-run: it falls under the same discipline
# as the outputs. Do NOT inspect it before "STEP B FROZEN" and the pinned hash.
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
if [ -f outputs/cora_breakthrough/level4_stepB_journal.jsonl ]; then
    echo "journal found: $(( $(wc -l < outputs/cora_breakthrough/level4_stepB_journal.jsonl) - 1 )) completed units will be replayed"
fi

nohup python3 scripts/cora_level4_stepB_run.py --workers 20 --require-manifest \
    >> logs/level4_stepB_run.log 2>&1 &
echo "relaunched, pid $!"
echo "monitor: tail -f logs/level4_stepB_run.log   (counts only; done at 'STEP B FROZEN')"
