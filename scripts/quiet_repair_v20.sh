#!/usr/bin/env bash
# Waits for load <4, then runs the v20 3-task quiet repair.
cd "$(dirname "$0")/.."
LOG=logs/quiet_repair_watch.log
echo "[$(date -u +%FT%TZ)] watcher armed" >> $LOG
while true; do
  L=$(awk '{print int($1)}' /proc/loadavg)
  if [ "$L" -lt 4 ]; then
    echo "[$(date -u +%FT%TZ)] load $L — running quiet repair" >> $LOG
    R=outputs/v20_repair_quiet
    rm -rf $R && mkdir -p $R/object
    cp outputs/object_reasoning_promotion_v3/library.json $R/object/
    cp outputs/learned_verbs/learned_verbs.json $R/object/
    printf '["0ca9ddb6", "868de0fa", "ef26cbf6"]' > $R/subset.json
    source ~/.venvs/lesegenv/bin/activate
    export PYTHONPATH=. ARC_GENERATIVE=1 ARC_DIHEDRAL_FRAMES=45
    python3 scripts/run_unified_harness.py --workers 1 \
      --subset-file $R/subset.json --out-dir $R --run-id v20_repair_quiet \
      > logs/v20_repair_quiet.log 2>&1
    echo "[$(date -u +%FT%TZ)] quiet repair rc=$? — see logs/v20_repair_quiet.log" >> $LOG
    echo QUIET_REPAIR_DONE >> $LOG
    break
  fi
  sleep 600
done
