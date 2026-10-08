#!/usr/bin/env bash
# Commit the running native census rows to git every 15 minutes, and once
# more when the census marker appears; then exit. Detached and finite.
# Commits only the census files (git commit -- paths), retrying on a lock.
# usage: reach_v1_checkpoint.sh [PHASE] [COORDINATOR_PID]   (default: census 3382121)
cd "$(dirname "$0")/.."
PHASE=${1:-census}
COORD=${2:-3382121}
case $PHASE in
  census) EXTRA="outputs/reach_v1/census_programs" ;;
  instances|instances2) EXTRA="outputs/reach_v1/$PHASE" ;;
  *) EXTRA="" ;;
esac
FILES="outputs/reach_v1/${PHASE}_rows.jsonl $EXTRA logs/reach_v1/${PHASE}_0_start.json"
while true; do
  final=0
  MARK=logs/reach_v1/$(echo $PHASE | tr a-z A-Z)_0_DONE
  [ -f $MARK ] && final=1 && FILES="$FILES $MARK logs/reach_v1/${PHASE}_0_record.json"
  n=$(wc -l < outputs/reach_v1/${PHASE}_rows.jsonl 2>/dev/null || echo 0)
  for i in 1 2 3 4 5; do
    git add -f $FILES 2>/dev/null
    if git diff --cached --quiet -- $FILES; then break; fi
    if git commit -q -m "Updating the real-task reach $PHASE checkpoint ($n of 60 rows)" -- $FILES; then
      echo "$(date -u +%FT%TZ) committed $n rows" >> logs/reach_v1/checkpoint.log; break
    fi
    sleep 20
  done
  [ $final = 1 ] && echo "$(date -u +%FT%TZ) final checkpoint, exiting" >> logs/reach_v1/checkpoint.log && exit 0
  if ! kill -0 $COORD 2>/dev/null; then
    sleep 60
    if [ ! -f $MARK ]; then
      git add -f $FILES 2>/dev/null
      git diff --cached --quiet -- $FILES || git commit -q -m "Updating the real-task reach $PHASE checkpoint ($n of 60 rows, coordinator stopped without its marker)" -- $FILES
      echo "$(date -u +%FT%TZ) coordinator gone without marker; last checkpoint, exiting" >> logs/reach_v1/checkpoint.log
      exit 0
    fi
    continue
  fi
  sleep 900
done
