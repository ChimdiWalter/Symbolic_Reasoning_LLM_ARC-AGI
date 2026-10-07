#!/usr/bin/env bash
# Commit the running native census rows to git every 15 minutes, and once
# more when the census marker appears; then exit. Detached and finite.
# Commits only the census files (git commit -- paths), retrying on a lock.
cd "$(dirname "$0")/.."
FILES="outputs/reach_v1/census_rows.jsonl outputs/reach_v1/census_programs logs/reach_v1/census_0_start.json"
while true; do
  final=0
  [ -f logs/reach_v1/CENSUS_0_DONE ] && final=1 && FILES="$FILES logs/reach_v1/CENSUS_0_DONE logs/reach_v1/census_0_record.json"
  n=$(wc -l < outputs/reach_v1/census_rows.jsonl 2>/dev/null || echo 0)
  for i in 1 2 3 4 5; do
    git add -f $FILES 2>/dev/null
    if git diff --cached --quiet -- $FILES; then break; fi
    if git commit -q -m "Updating the real-task reach native census checkpoint ($n of 60 rows)" -- $FILES; then
      echo "$(date -u +%FT%TZ) committed $n rows" >> logs/reach_v1/checkpoint.log; break
    fi
    sleep 20
  done
  [ $final = 1 ] && echo "$(date -u +%FT%TZ) final checkpoint, exiting" >> logs/reach_v1/checkpoint.log && exit 0
  if ! kill -0 3382121 2>/dev/null; then
    sleep 60
    if [ ! -f logs/reach_v1/CENSUS_0_DONE ]; then
      git add -f $FILES 2>/dev/null
      git diff --cached --quiet -- $FILES || git commit -q -m "Updating the real-task reach native census checkpoint ($n of 60 rows, coordinator stopped without its marker)" -- $FILES
      echo "$(date -u +%FT%TZ) coordinator gone without marker; last checkpoint, exiting" >> logs/reach_v1/checkpoint.log
      exit 0
    fi
    continue
  fi
  sleep 900
done
