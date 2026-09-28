#!/usr/bin/env bash
# Item-2 v1.5: the integrity gate, then the sealed evaluator twice on the
# same records with single-threaded BLAS, a byte comparison, and the report.
set -u
cd "$(dirname "$0")/.." || exit 1
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=.venv_arc2026/bin/python
LOG=logs/v15_chain.log
OUT=outputs/tti
nice -n 19 "$PY" scripts/evaluate_v15_selection.py --integrity-only >> logs/v15_integrity.log 2>&1
rc=$?
echo "integrity exit $rc $(date -u +%FT%TZ)" >> "$LOG"
[ "$rc" -eq 0 ] || exit "$rc"
for pass in 1 2; do
  nice -n 19 "$PY" scripts/evaluate_v15_selection.py "$OUT/v15_selection_report_pass$pass.json" >> logs/v15_evaluation.log 2>&1 || exit 1
done
if cmp -s "$OUT/v15_selection_report_pass1.json" "$OUT/v15_selection_report_pass2.json"; then
  cp "$OUT/v15_selection_report_pass1.json" "$OUT/v15_selection_report.json"
  echo "reproduction: byte-identical" >> "$LOG"
else
  echo "reproduction: DIFFERENT" >> "$LOG"
fi
touch logs/V15_EVALUATION_DONE
echo "evaluation end $(date -u +%FT%TZ)" >> "$LOG"
