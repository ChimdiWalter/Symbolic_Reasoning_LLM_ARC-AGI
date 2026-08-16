#!/usr/bin/env bash
# Waits for load <8, then runs the v21 full chain (seals 176).
cd "$(dirname "$0")/.."
LOG=logs/v21_watch.log
echo "[$(date -u +%FT%TZ)] v21 watcher armed (waiting load<8)" >> $LOG
while true; do
  L=$(awk '{print int($1)}' /proc/loadavg)
  if [ "$L" -lt 8 ]; then
    echo "[$(date -u +%FT%TZ)] load $L — launching v21" >> $LOG
    V21=outputs/unified_harness_v21
    rm -rf $V21 && mkdir -p $V21/object
    cp outputs/object_reasoning_promotion_v3/library.json $V21/object/
    cp outputs/learned_verbs/learned_verbs.json $V21/object/
    source ~/.venvs/lesegenv/bin/activate
    export PYTHONPATH=. ARC_GENERATIVE=1 ARC_DIHEDRAL_FRAMES=45 ARC_PATTERN_DERIVE=1
    python3 scripts/run_unified_harness.py --workers 16 \
      --out-dir $V21 --run-id full_v21 > logs/harness_full_1000_v21.log 2>&1
    echo "[$(date -u +%FT%TZ)] v21 rc=$? — see logs/harness_full_1000_v21.log" >> $LOG
    echo V21_WATCH_DONE >> $LOG
    break
  fi
  sleep 600
done
