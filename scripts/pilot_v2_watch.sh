#!/usr/bin/env bash
# Growth-repair pilot v2 watcher (protocol section 14): wait for the reasoner
# marker, then run the blind evaluator and the terminal verifier, each in its
# own process, then exit. Detached and finite; administrative only. If the
# coordinator stops without its marker, record that and exit (the pilot is
# then resumable by the documented rule; nothing is scored).
# usage: pilot_v2_watch.sh COORDINATOR_PID
cd "$(dirname "$0")/.."
COORD=${1:?coordinator pid}
LOGF=logs/pilot_v2/watch.log
PY=.venv_arc2026/bin/python
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.:src:/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
while [ ! -f logs/PILOT_V2_REASONER_DONE ]; do
  if ! kill -0 "$COORD" 2>/dev/null; then
    sleep 60
    [ -f logs/PILOT_V2_REASONER_DONE ] && break
    echo "$(date -u +%FT%TZ) coordinator $COORD gone without the reasoner marker; nothing scored" >> $LOGF
    exit 0
  fi
  echo "$(date -u +%FT%TZ) alive rows native=$(wc -l < outputs/pilot_v2/native_rows.jsonl 2>/dev/null || echo 0) instances=$(wc -l < outputs/pilot_v2/instances_rows.jsonl 2>/dev/null || echo 0) cora=$(wc -l < outputs/pilot_v2/cora_rows.jsonl 2>/dev/null || echo 0)" >> $LOGF
  sleep 600
done
echo "$(date -u +%FT%TZ) reasoner marker $(cat logs/PILOT_V2_REASONER_DONE); evaluating" >> $LOGF
$PY scripts/pilot_v2_evaluate.py >> $LOGF 2>&1
echo "$(date -u +%FT%TZ) evaluator exit $?; verifying" >> $LOGF
$PY scripts/pilot_v2_verify.py >> $LOGF 2>&1
echo "$(date -u +%FT%TZ) verifier exit $?; watcher done" >> $LOGF
