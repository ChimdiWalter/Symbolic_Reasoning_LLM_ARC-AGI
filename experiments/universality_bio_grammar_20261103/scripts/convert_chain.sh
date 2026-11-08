#!/bin/sh
# U5: inputs, intensity images and calibration references (calibration only). Status: work/convert.run.status
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
LP=python3
S=$W/convert.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$ $*"
for DS in "$@"; do
  sh $R/scripts/with_cpu_slot.sh $LP -I $E/scripts/u5data.py convert $DS >> $W/convert_$DS.log 2>&1 && log "CONVERTED $DS" || { log "EXIT 1 convert $DS"; exit 1; }
done
log "EXIT 0"
