#!/bin/sh
# U5 CORA_TOLERANT secondary arm (Amendment 8; detached). Waits for A's tolerant induction and the protocol's policy
# freeze; freezes the tolerant policy on A and both targets; after GO and after the primary results are committed
# (primary arms first), decides and freezes the tolerant arms, scores them into results/RESULTS_TOLERANT.json.
#   setsid nohup sh tolerant_chain.sh > /dev/null 2>&1 < /dev/null &      Status: work/tolerant_chain.run.status
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
LP=python3
SLOT="sh $R/scripts/with_cpu_slot.sh"
S=$W/tolerant_chain.run.status
L=$W/tolerant_chain.log
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
until grep -q "INDUCED_TOLERANT\|EXIT 1" $W/tolerant_induction.run.status 2>/dev/null; do sleep 60; done
grep -q "INDUCED_TOLERANT" $W/tolerant_induction.run.status || { log "EXIT 1 tolerant induction failed"; exit 1; }
until grep -q "POLICY_FROZEN\|EXIT 1" $W/cal_chain.run.status 2>/dev/null; do sleep 60; done
grep -q "POLICY_FROZEN" $W/cal_chain.run.status || { log "EXIT 1 policy freeze failed"; exit 1; }
python3 -I $E/scripts/verify_code.py >> $L 2>&1 || { log "EXIT 1 code changed after its freeze"; exit 1; }
[ -f $W/POLICY_FREEZE_TOLERANT.json ] || { $SLOT $LP -I $E/scripts/u5eval.py freeze_tolerant >> $L 2>&1 || { log "EXIT 1 freeze tolerant"; exit 1; }; }
log "FROZEN_TOLERANT $(tail -1 $L | cut -c1-300)"
cd $R && for i in 1 2 3; do git add $E/POLICY_FREEZE_TOLERANT.json && git commit -q -m "U5 universality study: tolerant secondary arm policy frozen by the detached chain (calibration only)" -- $E/POLICY_FREEZE_TOLERANT.json && break; sleep 20; done
DL=$(date -d 2026-11-04T12:00:00Z +%s)
until [ -f $W/GO_EVALUATION ] || { [ $(date +%s) -ge $DL ] && [ ! -f $W/HOLD_FOR_AMENDMENT ]; }; do sleep 30; done
log GO
until grep -q "COMMITTED_PRIMARY\|EXIT 1" $W/eval_chain.run.status 2>/dev/null; do sleep 60; done        # primary first
grep -q "COMMITTED_PRIMARY" $W/eval_chain.run.status || { log "EXIT 1 the primary evaluation failed"; exit 1; }
python3 -I $E/scripts/verify_code.py >> $L 2>&1 || { log "EXIT 1 code changed after its freeze"; exit 1; }
[ -f $W/DECISIONS_FROZEN_TOLERANT.json ] || { $SLOT $LP -I $E/scripts/u5eval.py decide tolerant >> $L 2>&1 || { log "EXIT 1 decide tolerant"; exit 1; }; }
log DECISIONS_FROZEN_TOLERANT
$SLOT $LP -I $E/scripts/u5eval.py evaluate tolerant >> $L 2>&1 || { log "EXIT 1 evaluate tolerant"; exit 1; }
log EVALUATED_TOLERANT
cd $R && for i in 1 2 3; do git add $E/results && git commit -q -m "U5 universality study: tolerant secondary arm results written by the detached chain" -- $E/results && break; sleep 20; done
log "EXIT 0"
