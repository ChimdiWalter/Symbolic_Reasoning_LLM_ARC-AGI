#!/usr/bin/env bash
# Overnight sequence: wait DRM ep0 -> record -> dev-19 baseline -> v18 1000-task
set -e
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate
export PYTHONPATH=.

LOG=logs/overnight_sequence.log
echo "[$(date -u +%FT%TZ)] OVERNIGHT SEQUENCE START" >> $LOG

# 1. Wait for DRM epoch 0 to finish
echo "[$(date -u +%FT%TZ)] Waiting for DRM epoch 0..." >> $LOG
until grep -q "EPOCH 0:" logs/trm_train_drm.log 2>/dev/null; do
    sleep 120
done
DRM_LINE=$(grep "EPOCH 0:" logs/trm_train_drm.log | tail -1)
echo "[$(date -u +%FT%TZ)] DRM EP0: $DRM_LINE" >> $LOG

# 2. Pause DRM training (save GPU for clean evals)
touch trm/STOP_AFTER_EPOCH
echo "[$(date -u +%FT%TZ)] DRM stop-file placed, waiting for pause..." >> $LOG
until grep -q "PAUSED\|EPOCH 1:" logs/trm_train_drm.log 2>/dev/null; do
    sleep 60
done
sleep 30  # let GPU memory release
echo "[$(date -u +%FT%TZ)] DRM paused or ep1 done, GPU should be free" >> $LOG

# 3. Rerun dev-19 baseline on quiet GPU (confirm historical 9/8)
DEV="05f2a901,dc433765,1caeab9d,a1570a43,ae3edfdc,5521c0d9,2c737e39,e76a88a6,88a10436,0a2355a6,6ea4a07e,1acc24af,b2862040,2204b7a8,4852f2fa,358ba94e,2dc579da,25e02866,445eab21"
echo "[$(date -u +%FT%TZ)] Running dev-19 baseline (quiet GPU)..." >> $LOG
python scripts/run_object_dev_eval.py --tasks $DEV \
    --out-dir outputs/guide_gate_baseline_dev19 \
    --tag baseline_quiet >> $LOG 2>&1

python3 -c "
import json
d=json.load(open('outputs/guide_gate_baseline_dev19/eval_summary_baseline_quiet.json'))
te=sum(1 for r in d['per_task'] if r.get('train_exact'))
tc=sum(1 for r in d['per_task'] if r.get('test_correct'))
print(f'BASELINE_QUIET dev-19: {te}te/{tc}tc out of {len(d[\"per_task\"])}')
" >> $LOG 2>&1

# 4. Launch v18 1000-task run with ARC_GUIDE=1
echo "[$(date -u +%FT%TZ)] Launching v18 1000-task ARC_GUIDE=1..." >> $LOG
export ARC_GUIDE=1 ARC_DIHEDRAL_FRAMES=45
python harness/run_harness.py \
    --out-dir outputs/unified_harness_v18_guide \
    --tag v18_guide >> logs/v18_guide_run.log 2>&1
echo "[$(date -u +%FT%TZ)] v18 DONE rc=$?" >> $LOG

# 5. Extract v18 headline numbers
python3 -c "
import json, glob
results = {}
for f in glob.glob('outputs/unified_harness_v18_guide/results*.json'):
    results.update(json.load(open(f)))
solved = sum(1 for v in results.values() if v.get('solved'))
print(f'V18 RESULT: {solved}/1000')
" >> $LOG 2>&1

echo "[$(date -u +%FT%TZ)] OVERNIGHT SEQUENCE COMPLETE" >> $LOG
