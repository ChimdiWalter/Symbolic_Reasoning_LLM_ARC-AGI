#!/usr/bin/env bash
# Item-2 v1.7: launch the one compiler acceptance test, detached, under the
# K* environment (PYTHONHASHSEED=0, no ARC_* variable; kstar() sets its
# own pair). Refuses if it was started before (pid record) or finished
# (marker); scripts/v17_acceptance.py refuses again on its own outputs, on
# the environment and on any freeze problem.
set -euo pipefail
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R"
mkdir -p logs/v17
if [ -e logs/V17_ACCEPTANCE_DONE ] || [ -e logs/v17/acceptance.pid ]; then
    echo "acceptance already started or finished; refusing" >&2
    exit 1
fi
if env | grep -q '^ARC_'; then
    echo "an ARC_* variable is set; refusing" >&2
    exit 1
fi
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI" \
    setsid nohup .venv_arc2026/bin/python scripts/v17_acceptance.py \
    > logs/v17/acceptance.log 2>&1 < /dev/null &
echo "$! $(date -u +%Y-%m-%dT%H:%M:%SZ) load:$(cut -d' ' -f1-3 /proc/loadavg) cpus:$(nproc)" > logs/v17/acceptance.pid
cat logs/v17/acceptance.pid
