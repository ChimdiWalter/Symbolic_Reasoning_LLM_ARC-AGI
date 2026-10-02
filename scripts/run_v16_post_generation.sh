#!/usr/bin/env bash
# Item-2 v1.6 post-generation sequence, in the order set for v1.5 and kept:
#   1. test responses (CandidateFailureProbe on every admitted test episode);
#   2. integrity only;
#   3. the sealed evaluator twice, byte-compared;
#   4. the dependence sensitivity for gate C.
# Waits for the generation chain to end and never signals it. Runs frozen
# scripts only, stops at the first failure, records no verdict.
# The probe needs the tti root on PYTHONPATH (addendum erratum 1 of v1.5).
set -u
cd "$(dirname "$0")/.." || exit 1
CHAIN_PID=${1:?usage: run_v16_post_generation.sh CHAIN_PID}
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=.venv_arc2026/bin/python
D=logs/v16_postgen
OUT=outputs/tti
mkdir -p "$D"
STATUS=$D/STATUS.txt
say() { echo "$(date -u +%FT%TZ) $*" >> "$STATUS"; }
block() { say "BLOCKED: $*"; echo "$(date -u +%FT%TZ) $*" > logs/V16_POSTGEN_BLOCKED; exit 1; }
chain_alive() { [ -r "/proc/$CHAIN_PID/cmdline" ] &&
  tr '\0' ' ' < "/proc/$CHAIN_PID/cmdline" | grep -q 'run_v16_generation.sh'; }

exec 9> "$D/.runner.lock"
flock -n 9 || { echo "another post-generation runner holds the lock" >&2; exit 1; }
for m in logs/V16_POSTGEN_DONE logs/V16_POSTGEN_BLOCKED; do
  [ -e "$m" ] && { echo "refusing: $m exists" >&2; exit 1; }
done
chain_alive || { echo "refusing: $CHAIN_PID is not the running v1.6 generation chain" >&2; exit 1; }

say "runner pid $$ waiting for generation chain $CHAIN_PID"
while chain_alive; do sleep 300; done
say "chain ended; chain log: $(tail -1 logs/v16_chain.log)"
say "run end: $(tr -d '\n ' < $OUT/v16_test_corpus/full_run_end.json 2>/dev/null)"
[ -f logs/V16_GENERATION_DONE ] || block "no V16_GENERATION_DONE marker: the generator did not exit 0"

PYTHONPATH="$TTI" V16_WORKERS=4 nice -n 19 "$PY" scripts/v16_responses.py test > "$D/1_responses.log" 2>&1
rc=$?
say "1 test responses exit $rc: $(tail -1 "$D/1_responses.log")"
[ "$rc" -eq 0 ] || block "step 1: test responses failed (exit $rc)"

nice -n 19 "$PY" scripts/evaluate_v16_cfr.py --integrity-only > "$D/2_integrity.log" 2>&1
rc=$?
say "2 integrity exit $rc: $(tail -1 "$D/2_integrity.log")"
[ "$rc" -eq 0 ] || block "step 2: integrity failed (exit $rc)"

for pass in 1 2; do
  nice -n 19 "$PY" scripts/evaluate_v16_cfr.py "$OUT/v16_cfr_report_pass$pass.json" > "$D/3_evaluation_pass$pass.log" 2>&1 ||
    block "step 3: evaluator pass $pass failed"
done
if cmp -s "$OUT/v16_cfr_report_pass1.json" "$OUT/v16_cfr_report_pass2.json"; then
  cp "$OUT/v16_cfr_report_pass1.json" "$OUT/v16_cfr_report.json"
  say "3 sealed evaluation: byte-identical"
else
  block "step 3: the two evaluator passes differ (unexplained nondeterminism)"
fi

nice -n 19 "$PY" scripts/v16_supp_dependence.py "$OUT/v16_supp_dependence.json" > "$D/4_dependence.log" 2>&1
rc=$?
say "4 dependence exit $rc: $(tail -1 "$D/4_dependence.log")"
[ "$rc" -eq 0 ] || block "step 4: dependence sensitivity failed (exit $rc); the official report stands"

(cd "$OUT" && sha256sum v16_cfr_report.json v16_cfr_report_pass1.json v16_cfr_report_pass2.json \
  v16_test_responses.json v16_supp_dependence.json) >> "$STATUS"
say "sequence complete; record the official verdict and the supplementary checks separately"
touch logs/V16_POSTGEN_DONE
