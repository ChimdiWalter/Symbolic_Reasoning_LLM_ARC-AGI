#!/usr/bin/env bash
# Item-2 v1.6: generate the frozen prospective test corpus until the frozen
# number of unique groups or a cap. Generation only; detached; one writer;
# resumable from the first missing slot by rerunning this script after a
# reboot (the generator reads existing records and never rewrites them; the
# wall cap counts from the first start). The post-generation runner follows.
set -u
cd "$(dirname "$0")/.." || exit 1
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=.venv_arc2026/bin/python
LOG=logs/v16_chain.log
mkdir -p logs
echo "v1.6 generation start $(date -u +%FT%TZ) pid $$" >> "$LOG"
nice -n 19 "$PY" scripts/generate_v16_pairs.py full >> logs/v16_generation.log 2>&1
rc=$?
echo "generator exit $rc $(date -u +%FT%TZ)" >> "$LOG"
[ "$rc" -eq 0 ] && touch logs/V16_GENERATION_DONE
exit "$rc"
