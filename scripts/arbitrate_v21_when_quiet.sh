#!/usr/bin/env bash
# Waits for load <8, then solo-arbitrates the 4 v21 tasks in question.
cd "$(dirname "$0")/.."
LOG=logs/v21_arb_watch.log
echo "[$(date -u +%FT%TZ)] arbitration watcher armed (load<8)" >> $LOG
while true; do
  L=$(awk '{print int($1)}' /proc/loadavg)
  if [ "$L" -lt 8 ]; then
    echo "[$(date -u +%FT%TZ)] load $L — arbitrating" >> $LOG
    R=outputs/v21_arbitration
    rm -rf $R && mkdir -p $R/object
    cp outputs/object_reasoning_promotion_v3/library.json $R/object/
    cp outputs/learned_verbs/learned_verbs.json $R/object/
    printf '["0ca9ddb6", "868de0fa", "ef26cbf6", "d8c310e9"]' > $R/subset.json
    source ~/.venvs/lesegenv/bin/activate
    export PYTHONPATH=. ARC_GENERATIVE=1 ARC_DIHEDRAL_FRAMES=45 ARC_PATTERN_DERIVE=1
    python3 scripts/run_unified_harness.py --workers 1 \
      --subset-file $R/subset.json --out-dir $R --run-id v21_arbitration \
      > logs/v21_arbitration.log 2>&1
    echo "[$(date -u +%FT%TZ)] arbitration rc=$?" >> $LOG
    echo V21_ARB_DONE >> $LOG
    break
  fi
  sleep 600
done
