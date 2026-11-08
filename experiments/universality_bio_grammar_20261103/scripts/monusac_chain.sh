#!/bin/sh
# U5 Amendment 4: MoNuSAC calibration (convert, segment, strong native, gate, probes), then, once the main policy
# freeze exists, freeze_target monusac. Status: work/monusac_chain.run.status
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
LP=python3
SLOT="sh $R/scripts/with_cpu_slot.sh"
S=$W/monusac_chain.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
grep -q "CONVERTED monusac" $W/convert.run.status 2>/dev/null || { sh $E/scripts/convert_chain.sh monusac || { log "EXIT 1 convert"; exit 1; }; }
grep -q "EXIT 0" $W/seg_monusac_cal.run.status 2>/dev/null || { sh $E/scripts/seg_chain.sh monusac cal || { log "EXIT 1 segment"; exit 1; }; }
[ -f $W/monusac/seg/STRONG_NATIVE_RULE.json ] || { $SLOT $LP -I -c "import sys; sys.path.insert(0,'$E/scripts'); import u5run as RN; RN.strong_native('monusac','calibration')" >> $W/monusac_chain.log 2>&1 || { log "EXIT 1 strong_native"; exit 1; }; }
$SLOT $LP -I $E/scripts/u5induce.py gate monusac >> $W/monusac_chain.log 2>&1 || { log "EXIT 1 gate"; exit 1; }
log "GATE $(tail -1 $W/monusac_chain.log | cut -c1-200)"
if [ ! -f $W/monusac/probes/induction/FAILURE_RECORDS.json ]; then
  $SLOT $LP -I $E/scripts/u5probe.py build monusac induction >> $W/monusac_chain.log 2>&1 || { log "EXIT 1 probe build"; exit 1; }
  sh $E/scripts/probe_chain.sh monusac || { log "EXIT 1 probes"; exit 1; }
fi
log PROBED
until grep -q "POLICY_FROZEN" $W/cal_chain.run.status 2>/dev/null; do sleep 120; done    # Amendment 6: no race
$SLOT $LP -I $E/scripts/u5eval.py freeze_target monusac >> $W/monusac_chain.log 2>&1 || { log "EXIT 1 freeze_target"; exit 1; }
log "TARGET_FROZEN $(tail -1 $W/monusac_chain.log | cut -c1-300)"
log "EXIT 0"
