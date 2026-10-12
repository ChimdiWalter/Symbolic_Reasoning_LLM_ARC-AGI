#!/usr/bin/env bash
# Commit the running LOO-diagnosis rows to git every 15 minutes, and once
# more when the marker appears; then exit. Detached and finite.
# Commits only the diagnosis files (git commit -- paths), retrying on a lock.
# usage: loo_v1_checkpoint.sh PHASE COORDINATOR_PID
cd "$(dirname "$0")/.."
PHASE=${1:?phase}
COORD=${2:?coordinator pid}
EXTRA=""
FILES="outputs/loo_v1/${PHASE}_rows.jsonl $EXTRA logs/loo_v1/${PHASE}_0_start.json"
while true; do
  final=0
  MARK=logs/loo_v1/$(echo $PHASE | tr a-z A-Z)_0_DONE
  [ -f $MARK ] && final=1 && FILES="$FILES $MARK logs/loo_v1/${PHASE}_0_record.json"
  n=$(wc -l < outputs/loo_v1/${PHASE}_rows.jsonl 2>/dev/null || echo 0)
  for i in 1 2 3 4 5; do
    git add -f $FILES 2>/dev/null
    if git diff --cached --quiet -- $FILES; then break; fi
    if git commit -q -m "Updating the real-task LOO stability $PHASE checkpoint ($n of 18 units)" -- $FILES; then
      echo "$(date -u +%FT%TZ) committed $n rows" >> logs/loo_v1/checkpoint.log; break
    fi
    sleep 20
  done
  [ $final = 1 ] && echo "$(date -u +%FT%TZ) final checkpoint, exiting" >> logs/loo_v1/checkpoint.log && exit 0
  if ! kill -0 $COORD 2>/dev/null; then
    sleep 60
    if [ ! -f $MARK ]; then
      git add -f $FILES 2>/dev/null
      git diff --cached --quiet -- $FILES || git commit -q -m "Updating the real-task LOO stability $PHASE checkpoint ($n of 18 units, coordinator stopped without its marker)" -- $FILES
      echo "$(date -u +%FT%TZ) coordinator gone without marker; last checkpoint, exiting" >> logs/loo_v1/checkpoint.log
      exit 0
    fi
    continue
  fi
  sleep 900
done
