#!/bin/sh
# U2b detached chain: HOLD until runs/GO_U2B exists or 2026-11-02T18:00:00Z passes without runs/HOLD_U2B; verify code and
# systems; six blind-search passes (REAL then SHUFFLED; ConceptARC, Mini-ARC, 1D-ARC), each in a CPU slot; analysis;
# commit results/U2B_*. Status: runs/u2b.run.status.
#   setsid nohup sh experiments/universality_similar_problems_20261102/scripts/u2b_chain.sh > /dev/null 2>&1 < /dev/null &
R=/path/to/repository
E=$R/experiments/universality_similar_problems_20261102
RUN=/path/to/benchmark_data/runs
PY=python3
SLOT="sh $R/scripts/with_cpu_slot.sh"
S=$RUN/u2b.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
fail() { log "EXIT 1 $*"; exit 1; }
mkdir -p $RUN; log "START pid=$$"
DL=$(date -d 2026-11-02T18:00:00Z +%s)
until [ -f $RUN/GO_U2B ] || { [ $(date +%s) -ge $DL ] && [ ! -f $RUN/HOLD_U2B ]; }; do sleep 300; done
if [ -f $RUN/GO_U2B ]; then log "GO flag"; else log "GO deadline passed"; fi
(cd $E && sha256sum -c --quiet U2B_CODE_FREEZE.sha256) >> $RUN/u2b_verify.log 2>&1 || fail "code changed after its freeze"
python3 -I $E/scripts/verify_systems.py U2B_before >> $RUN/u2b_verify.log 2>&1 || fail "systems hash mismatch"
for V in real shuffled; do
  for B in concept_arc mini_arc 1d_arc; do
    [ -f $RUN/u2b_${B}_${V}/DONE ] && continue
    used=$(python3 -I -c "import json,glob;print(int(sum(json.load(open(p)).get('child_cpu_s',0) for p in glob.glob('$RUN/u2b_*/status.json'))))")
    if [ "$used" -gt 21600 ]; then log "NOT_RUN_BUDGET $B $V (used ${used} CPU-s)"; continue; fi
    log "PASS_START $B $V"
    if $SLOT $PY -I $E/scripts/u2b_blind.py $B $V >> $RUN/u2b_${B}_${V}.log 2>&1; then touch $RUN/u2b_${B}_${V}/DONE; log "PASS_DONE $B $V"; else log "PASS_FAIL $B $V"; fi
  done
done
python3 -I $E/scripts/verify_systems.py U2B_after >> $RUN/u2b_verify.log 2>&1 || fail "systems hash mismatch after"
$PY -I $E/scripts/u2b_analysis.py >> $RUN/u2b_analysis.log 2>&1 || fail analysis
log ANALYZED
cd $R && for i in 1 2 3; do git add $E/results/U2B_RESULTS.json $E/results/U2B_SUMMARY.md && git commit -q -m "U2b: results written by the detached chain" -- $E/results/U2B_RESULTS.json $E/results/U2B_SUMMARY.md && break; sleep 20; done
log "EXIT 0"
