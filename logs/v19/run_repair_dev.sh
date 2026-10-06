#!/usr/bin/env bash
# v1.9 repair K*-4: development ablation pipeline (protocol section 15).
# Detached; restartable (claims of unfinished tasks and jobs are dropped at
# start, finished rows kept). One pipeline at a time.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R" || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI"
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
L=logs/v19/repair_pipeline.log
PY=.venv_arc2026/bin/python
W=${W:-4}
exec 9>logs/v19/repair_pipeline.lock
if ! flock -n 9; then echo "$(date -u +%FT%TZ) another pipeline holds the lock" >> $L; exit 0; fi
echo "$(date -u +%FT%TZ) pipeline start pid $$ boot $(cat /proc/sys/kernel/random/boot_id)" >> $L
$PY scripts/v19_repair_dev.py reset_claims >> $L 2>&1
pids=""
for w in $(seq 1 $W); do
    $PY scripts/v19_repair_dev.py worker $w >> logs/v19/repair_worker_$w.log 2>&1 &
    pids="$pids $!"
done
echo "$(date -u +%FT%TZ) phase 1 workers:$pids" >> $L
wait $pids
echo "$(date -u +%FT%TZ) phase 1 done" >> $L
pids=""
for w in $(seq 1 $W); do
    $PY scripts/v19_repair_dev.py repeat $w >> logs/v19/repair_repeat_$w.log 2>&1 &
    pids="$pids $!"
done
echo "$(date -u +%FT%TZ) phase 2 workers:$pids" >> $L
wait $pids
echo "$(date -u +%FT%TZ) phase 2 done" >> $L
$PY scripts/v19_repair_dev.py analyze > logs/v19/repair_analyze.log 2>&1
echo "$(date -u +%FT%TZ) analyze exit $?" >> $L
touch logs/v19/REPAIR_DEV_DONE
