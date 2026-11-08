#!/bin/sh
# Test U3b detached chain (u3b_list_functions/PROTOCOL.md, section 7). HELD unless runs/GO_U3B, written by the
# coordinator, has as its first two lines exactly "protocol_sha256 <sha256 of u3b_list_functions/PROTOCOL.md>" and
# "freeze_sha256 <sha256 of u3b_list_functions/PROTOCOL_FREEZE.json>" (runs/HOLD_U3B marks the hold; no deadline
# fallback). At the start and before every stage, cgrow/u3/u3b_gate.py recomputes both digests from the live files,
# compares the two lines exactly and re-verifies every frozen hash; before the arms, the evaluation and the save it
# also verifies the generated build manifest (exactly the required outputs), then the arms and evaluation freezes.
# A stage whose freeze exists is verified, never rerun.
# Exit lines: "EXIT 1 <reason>" for a gate or research-stage failure (nothing later runs); "EXIT 2 SAVE_FAILED ..."
# when every stage passed and is frozen on disk but the git commit failed 3 times (sh resume_u3b.sh then verifies
# the freezes and retries only the save); "EXIT 0 chain done" only when every stage passed and the results are
# committed.
E=/path/to/repository/experiments/capability_growth_20261027
REPO=/path/to/repository
R=u3b_list_functions
cd $E || exit 1
mkdir -p runs/u3b_chain runs/u3b_build runs/u3b_arms runs/u3b_eval
S=$E/runs/u3b_chain/run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
fail() { log "EXIT 1 $*"; exit 1; }
gate() {
  G=$(python3 -I cgrow/u3/u3b_gate.py "$1" 2>&1); rc=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $G" >> $E/runs/u3b_chain/gate.log
  [ $rc -eq 0 ] || fail "gate before $1: $G"
  log "gate before $1: $G"
}
CPU="sh $REPO/scripts/with_cpu_slot.sh env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 python3 -m cgrow.runjob"
log "start pid $$"
gate start
if [ -e $R/build/BUILD_MANIFEST.json ]; then
  log "construction finished earlier: verified at the next gate, not redone"
else
  gate build
  $CPU u3b_build prep -- cgrow.u3.run_u3b build >> runs/u3b_build/log 2>&1 || fail "build failed"
  log "build ok"
fi
if [ -e $R/arms/ARMS_FREEZE.json ]; then
  log "arms frozen earlier: verified at the next gate, not rerun"
else
  gate arms
  $CPU u3b_arms screen -- cgrow.u3.run_u3b arms >> runs/u3b_arms/log 2>&1 || fail "arms failed"
  log "arms ok"
fi
if [ -e $R/eval/EVAL_FREEZE.json ]; then
  log "evaluation frozen earlier: verified at the next gate, not rerun"
else
  gate eval
  $CPU u3b_eval eval -- cgrow.u3.run_u3b evaluate >> runs/u3b_eval/log 2>&1 || fail "evaluation failed"
  log "eval ok"
fi
gate save
# save: only the U3b output paths (those present) are staged and committed; other staged work is left alone
X=experiments/capability_growth_20261027
OUT=
for p in $R/build $R/arms $R/eval reports/TEST_U3B_REPORT.md runs/u3b_chain runs/u3b_build runs/u3b_arms runs/u3b_eval; do
  [ -n "$(ls -A $p 2>/dev/null)" ] && OUT="$OUT $X/$p"
done
GL=$E/runs/u3b_chain/git.log
SAVED=
cd $REPO || fail "repository folder missing"
for i in 1 2 3; do
  if git add -- $OUT >> $GL 2>&1; then
    if git diff --cached --quiet -- $OUT; then SAVED="already committed"; break; fi
    if git commit -q -m "Test U3b: results written by the detached chain (build, arms, evaluation, report)" -- $OUT >> $GL 2>&1
    then SAVED="committed $(git rev-parse --short HEAD)"; break; fi
  fi
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) save attempt $i failed" >> $GL
  sleep 20
done
cd $E || exit 1
[ -n "$SAVED" ] || { log "EXIT 2 SAVE_FAILED: every stage passed and is frozen on disk, but the git commit failed 3 times (runs/u3b_chain/git.log); sh resume_u3b.sh verifies the freezes and retries only the save"; exit 2; }
log "save ok: $SAVED"
log "EXIT 0 chain done"
