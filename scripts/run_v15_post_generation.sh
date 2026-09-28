#!/usr/bin/env bash
# Item-2 v1.5 post-generation sequence, in the order set on 2026-09-28:
#   1. integrity only;
#   2. the three-valued verification diagnostic (FIT / NO_FIT / ERROR);
#   3. the frozen sealed evaluation (run_v15_evaluation.sh: integrity gate,
#      the evaluator twice, byte comparison);
#   4. the preregistered dependence sensitivity for gate C.
# It waits for the generation chain to end and never signals it. It runs
# frozen scripts only and records no verdict: the official result and the
# supplementary checks are recorded separately afterwards. It stops at the
# first failure, so no score is computed after a failed earlier step.
# Step 2 gets the tti root on PYTHONPATH (records/ITEM2_V15_DELIVERY_ADDENDUM_ERRATUM_01.md).
set -u
cd "$(dirname "$0")/.." || exit 1
CHAIN_PID=${1:?usage: run_v15_post_generation.sh CHAIN_PID}
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=.venv_arc2026/bin/python
D=logs/v15_postgen
OUT=outputs/tti
mkdir -p "$D"
STATUS=$D/STATUS.txt
say() { echo "$(date -u +%FT%TZ) $*" >> "$STATUS"; }
block() { say "BLOCKED: $*"; echo "$(date -u +%FT%TZ) $*" > logs/V15_POSTGEN_BLOCKED; exit 1; }
chain_alive() { [ -r "/proc/$CHAIN_PID/cmdline" ] &&
  tr '\0' ' ' < "/proc/$CHAIN_PID/cmdline" | grep -q 'run_v15_generation.sh'; }

exec 9> "$D/.runner.lock"
flock -n 9 || { echo "another post-generation runner holds the lock" >&2; exit 1; }
for m in logs/V15_POSTGEN_DONE logs/V15_POSTGEN_BLOCKED logs/V15_EVALUATION_DONE; do
  [ -e "$m" ] && { echo "refusing: $m exists" >&2; exit 1; }
done
chain_alive || { echo "refusing: $CHAIN_PID is not the running v1.5 generation chain" >&2; exit 1; }

say "runner pid $$ waiting for generation chain $CHAIN_PID"
while chain_alive; do sleep 300; done
say "chain ended; chain log: $(tail -1 logs/v15_chain.log)"
say "run end: $(tr -d '\n ' < $OUT/v15_test_corpus/full_run_end.json 2>/dev/null)"
[ -f logs/V15_GENERATION_DONE ] || block "no V15_GENERATION_DONE marker: the generator did not exit 0"

nice -n 19 "$PY" scripts/evaluate_v15_selection.py --integrity-only > "$D/1_integrity.log" 2>&1
rc=$?
say "1 integrity exit $rc: $(tail -1 "$D/1_integrity.log")"
[ "$rc" -eq 0 ] || block "step 1: integrity failed (exit $rc)"

PYTHONPATH="$TTI" nice -n 19 "$PY" scripts/v15_supp_verification.py \
  "$OUT/v15_supp_verification.json" > "$D/2_verification.log" 2>&1
rc=$?
say "2 verification exit $rc: $(tail -1 "$D/2_verification.log")"
[ "$rc" -eq 0 ] || block "step 2: verification diagnostic failed (exit $rc); repair before any score"

bash scripts/run_v15_evaluation.sh > "$D/3_evaluation.log" 2>&1
rc=$?
say "3 sealed evaluation exit $rc; $(grep '^reproduction' logs/v15_chain.log | tail -1)"
[ "$rc" -eq 0 ] || block "step 3: sealed evaluation failed (exit $rc)"
tail -3 logs/v15_chain.log | grep -q '^reproduction: byte-identical' ||
  block "step 3: the two evaluator passes differ (unexplained nondeterminism)"
cmp -s "$OUT/v15_selection_report_pass1.json" "$OUT/v15_selection_report.json" ||
  block "step 3: the official report is missing"

nice -n 19 "$PY" scripts/v15_supp_dependence.py "$OUT/v15_supp_dependence.json" > "$D/4_dependence.log" 2>&1
rc=$?
say "4 dependence exit $rc: $(tail -1 "$D/4_dependence.log")"
[ "$rc" -eq 0 ] || block "step 4: dependence sensitivity failed (exit $rc); the official report stands"

(cd "$OUT" && sha256sum v15_selection_report.json v15_selection_report_pass1.json \
  v15_selection_report_pass2.json v15_supp_verification.json v15_supp_dependence.json) >> "$STATUS"
say "sequence complete; record the official verdict and the supplementary checks separately"
touch logs/V15_POSTGEN_DONE
