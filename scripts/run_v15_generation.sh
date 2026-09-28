#!/usr/bin/env bash
# Item-2 v1.5: generate the frozen independent-input test corpus until the
# frozen number of unique groups or a cap. Generation only. Detached, one
# writer; the evaluator runs afterwards through run_v15_evaluation.sh.
set -u
cd "$(dirname "$0")/.." || exit 1
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=.venv_arc2026/bin/python
LOG=logs/v15_chain.log
echo "v1.5 generation start $(date -u +%FT%TZ) pid $$" >> "$LOG"
nice -n 19 "$PY" scripts/generate_v15_pairs.py full >> logs/v15_generation.log 2>&1
rc=$?
echo "generator exit $rc $(date -u +%FT%TZ)" >> "$LOG"
[ "$rc" -eq 0 ] && touch logs/V15_GENERATION_DONE
exit "$rc"
