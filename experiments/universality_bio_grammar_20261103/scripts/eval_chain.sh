#!/bin/sh
# U5 evaluation chain (detached; Amendment 6). Waits for the policy freeze (main chain and the MoNuSAC target), then
# HOLDS until work/GO_EVALUATION exists or 2026-11-04T12:00:00Z passes without work/HOLD_FOR_AMENDMENT; checks the code
# freeze; segments the evaluation images of A and the targets in parallel (two CPU slots), applies the strong native
# filter; decides and freezes the PRIMARY arms, opens the evaluator, commits results/; then decides and freezes the
# SECONDARY arms and scores them into the secondary results.
#   setsid nohup sh eval_chain.sh > /dev/null 2>&1 < /dev/null &      Status: work/eval_chain.run.status
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
LP=python3
SLOT="sh $R/scripts/with_cpu_slot.sh"
S=$W/eval_chain.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
until grep -q "POLICY_FROZEN" $W/cal_chain.run.status 2>/dev/null; do sleep 60; done
if [ -f $W/monusac_chain.run.status ]; then
  until grep -q "TARGET_FROZEN\|EXIT 1" $W/monusac_chain.run.status; do sleep 60; done
fi
log POLICY_READY
DL=$(date -d 2026-11-04T12:00:00Z +%s)
until [ -f $W/GO_EVALUATION ] || { [ $(date +%s) -ge $DL ] && [ ! -f $W/HOLD_FOR_AMENDMENT ]; }; do sleep 30; done
if [ -f $W/GO_EVALUATION ]; then log "GO flag"; else log "GO deadline 2026-11-04T12:00:00Z passed"; fi
python3 -I $E/scripts/verify_code.py >> $W/eval_chain.log 2>&1 || { log "EXIT 1 code changed after its freeze"; exit 1; }
DSS=$($LP -I -c "import json; r=json.load(open('$W/ROLES.json')); print(' '.join([r['A']]+r['targets']))")
log "DATASETS $DSS"
for DS in $DSS; do                                    # segmentation in parallel; seg_chain takes a CPU slot each
  [ -f $W/$DS/seg/MANIFEST_eval.json ] || sh $E/scripts/seg_chain.sh $DS eval &
done
wait
for DS in $DSS; do
  [ -f $W/$DS/seg/MANIFEST_eval.json ] || { log "EXIT 1 segment eval $DS"; exit 1; }
  $SLOT $LP -I $E/scripts/u5eval.py strong_eval $DS >> $W/eval_chain.log 2>&1 || { log "EXIT 1 strong_eval $DS"; exit 1; }
  log "SEGMENTED_EVAL $DS"
done
[ -f $W/DECISIONS_FROZEN.json ] || { $SLOT $LP -I $E/scripts/u5eval.py decide primary >> $W/eval_chain.log 2>&1 || { log "EXIT 1 decide primary"; exit 1; }; }
log DECISIONS_FROZEN_PRIMARY
$SLOT $LP -I $E/scripts/u5eval.py evaluate primary >> $W/eval_chain.log 2>&1 || { log "EXIT 1 evaluate primary"; exit 1; }
log EVALUATED_PRIMARY
cd $R && for i in 1 2 3; do git add $E/results && git commit -q -m "U5 universality study: primary results written by the detached chain" -- $E/results && break; sleep 20; done
log COMMITTED_PRIMARY
[ -f $W/DECISIONS_FROZEN_SECONDARY.json ] || { $SLOT $LP -I $E/scripts/u5eval.py decide secondary >> $W/eval_chain.log 2>&1 || { log "EXIT 1 decide secondary"; exit 1; }; }
log DECISIONS_FROZEN_SECONDARY
$SLOT $LP -I $E/scripts/u5eval.py evaluate secondary >> $W/eval_chain.log 2>&1 || { log "EXIT 1 evaluate secondary"; exit 1; }
log EVALUATED_SECONDARY
cd $R && for i in 1 2 3; do git add $E/results && git commit -q -m "U5 universality study: secondary results written by the detached chain" -- $E/results && break; sleep 20; done
log "EXIT 0"
