#!/usr/bin/env bash
# v1.9 supplementary development measurement: clause-level safety of the reduced-demonstration trials.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R" || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI"
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
L=logs/v19/clause_safety_pipeline.log
PY=.venv_arc2026/bin/python
W=${W:-3}
exec 9>logs/v19/clause_safety_pipeline.lock
if ! flock -n 9; then echo "$(date -u +%FT%TZ) another pipeline holds the lock" >> $L; exit 0; fi
echo "$(date -u +%FT%TZ) pipeline start pid $$" >> $L
$PY scripts/v19_clause_safety_dev.py reset_claims >> $L 2>&1
pids=""
for w in $(seq 1 $W); do
    $PY scripts/v19_clause_safety_dev.py worker $w >> logs/v19/clause_safety_worker_$w.log 2>&1 &
    pids="$pids $!"
done
echo "$(date -u +%FT%TZ) workers:$pids" >> $L
wait $pids
$PY scripts/v19_clause_safety_dev.py analyze > logs/v19/clause_safety_analyze.log 2>&1
echo "$(date -u +%FT%TZ) analyze exit $?" >> $L
touch logs/v19/CLAUSE_SAFETY_DEV_DONE
