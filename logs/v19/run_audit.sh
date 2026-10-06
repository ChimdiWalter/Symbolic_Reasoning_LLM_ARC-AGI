#!/usr/bin/env bash
# v1.9 engine acceptance stability audit: development diagnosis pipeline.
# Detached; restartable (prepare is skipped once the corpus exists; claims of
# unfinished tasks and jobs are dropped at start). One pipeline at a time.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R" || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI"
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
L=logs/v19/audit_pipeline.log
PY=.venv_arc2026/bin/python
W=${W:-3}
exec 9>logs/v19/pipeline.lock
if ! flock -n 9; then echo "$(date -u +%FT%TZ) another pipeline holds the lock" >> $L; exit 0; fi
echo "$(date -u +%FT%TZ) pipeline start pid $$ boot $(cat /proc/sys/kernel/random/boot_id)" >> $L
if [ ! -e outputs/tti/v19_dev_corpus.json ]; then
    $PY scripts/v19_audit_dev.py prepare >> $L 2>&1 || { echo "$(date -u +%FT%TZ) prepare failed" >> $L; exit 1; }
fi
$PY scripts/v19_audit_dev.py reset_claims >> $L 2>&1
pids=""
for w in $(seq 1 $W); do
    $PY scripts/v19_audit_dev.py worker $w >> logs/v19/worker_$w.log 2>&1 &
    pids="$pids $!"
done
echo "$(date -u +%FT%TZ) phase 1 workers:$pids" >> $L
wait $pids
echo "$(date -u +%FT%TZ) phase 1 done" >> $L
if [ ! -e outputs/tti/v19_dev_phase2_jobs.json ]; then
    $PY scripts/v19_audit_dev.py plan2 >> $L 2>&1 || { echo "$(date -u +%FT%TZ) plan2 failed" >> $L; exit 1; }
fi
pids=""
for w in $(seq 1 $W); do
    $PY scripts/v19_audit_dev.py repeat $w >> logs/v19/repeat_$w.log 2>&1 &
    pids="$pids $!"
done
echo "$(date -u +%FT%TZ) phase 2 workers:$pids" >> $L
wait $pids
echo "$(date -u +%FT%TZ) phase 2 done" >> $L
$PY scripts/v19_audit_dev.py analyze > logs/v19/analyze.log 2>&1
echo "$(date -u +%FT%TZ) analyze exit $?" >> $L
touch logs/v19/AUDIT_DONE
