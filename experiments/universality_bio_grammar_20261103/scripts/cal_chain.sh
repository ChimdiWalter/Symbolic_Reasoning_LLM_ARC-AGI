#!/bin/sh
# U5 calibration-only chain (detached): for each dataset, once its calibration segmentation has finished: strong native,
# gate, probes of the frozen package; then roles, A's induction (CORA, FAILURE_BLIND x5, SHUFFLED x5), and the
# policy freeze (in-domain induction on B and C, final fits, ALL_ON, MATCHED_SEARCH). Status: work/cal_chain.run.status
#   setsid nohup sh cal_chain.sh > /dev/null 2>&1 < /dev/null &
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
LP=python3
SLOT="sh $R/scripts/with_cpu_slot.sh"
S=$W/cal_chain.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
for DS in nuinsseg livecell; do                    # Amendment 3: FNC ineligible at the animal level
  until grep -q "EXIT" $W/seg_${DS}_cal.run.status 2>/dev/null; do sleep 60; done
  grep -q "EXIT 0" $W/seg_${DS}_cal.run.status || { log "SKIP $DS segmentation failed"; continue; }
  [ -f $W/$DS/seg/STRONG_NATIVE_RULE.json ] || { $SLOT $LP -I -c "import sys; sys.path.insert(0,'$E/scripts'); import u5run as RN; RN.strong_native('$DS','calibration')" >> $W/cal_chain.log 2>&1 || { log "EXIT 1 strong_native $DS"; exit 1; }; }
  $SLOT $LP -I $E/scripts/u5induce.py gate $DS >> $W/cal_chain.log 2>&1 || { log "EXIT 1 gate $DS"; exit 1; }
  log "GATE $DS $(tail -1 $W/cal_chain.log | cut -c1-200)"
  if [ -f $W/probe_$DS.run.status ]; then
    until grep -q "EXIT" $W/probe_$DS.run.status; do sleep 60; done
  fi
  if [ ! -f $W/$DS/probes/induction/FAILURE_RECORDS.json ]; then
    $SLOT $LP -I $E/scripts/u5probe.py build $DS induction >> $W/cal_chain.log 2>&1 || { log "EXIT 1 probe build $DS"; exit 1; }
    sh $E/scripts/probe_chain.sh $DS || { log "EXIT 1 probes $DS"; exit 1; }
  fi
  log "PROBED $DS"
done
$LP -I $E/scripts/u5eval.py roles >> $W/cal_chain.log 2>&1 || { log "EXIT 1 roles"; exit 1; }
A=$($LP -I -c "import json; print(json.load(open('$W/ROLES.json'))['A'])")
log "ROLES $(cat $W/ROLES.json | tr -d '\n' | cut -c1-300)"
[ -f $W/$A/INDUCTION.json ] || { $SLOT $LP -I $E/scripts/u5induce.py induce $A >> $W/cal_chain.log 2>&1 || { log "EXIT 1 induce $A"; exit 1; }; }
log "INDUCED $A $(tail -1 $W/cal_chain.log | cut -c1-300)"
$SLOT $LP -I $E/scripts/u5eval.py freeze >> $W/cal_chain.log 2>&1 || { log "EXIT 1 freeze"; exit 1; }
log "POLICY_FROZEN $(tail -1 $W/cal_chain.log | cut -c1-300)"
log "EXIT 0"
