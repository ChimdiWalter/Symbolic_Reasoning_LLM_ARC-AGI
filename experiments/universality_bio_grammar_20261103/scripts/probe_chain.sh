#!/bin/sh
# U5 probes of the frozen component on one dataset's induction parents (calibration only), in a CPU slot.
#   setsid nohup sh probe_chain.sh DS &      Status: work/probe_DS.run.status
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
DS=$1
S=$W/probe_$DS.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
python3 -I $E/scripts/verify_systems_u5.py before_probes_$DS >> $W/probe_$DS.log 2>&1 || { log "EXIT 1 systems changed"; exit 1; }
sh $R/scripts/with_cpu_slot.sh python3 -I -B $E/scripts/u5probe.py run $DS induction >> $W/probe_$DS.log 2>&1 || { log "EXIT 1 run"; exit 1; }
python3 -I $E/scripts/verify_systems_u5.py after_probes_$DS >> $W/probe_$DS.log 2>&1 || { log "EXIT 1 systems changed"; exit 1; }
python3 -I $E/scripts/u5probe.py summarize $DS induction >> $W/probe_$DS.log 2>&1 || { log "EXIT 1 summarize"; exit 1; }
log "EXIT 0"
