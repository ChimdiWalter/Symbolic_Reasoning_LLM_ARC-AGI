#!/bin/sh
# Calibration-side chain, before GO (no PUMA image is opened): the frozen policies of STRICT, TOLERANT and CALIBRATED
# on all 12 NuInsSeg calibration organs, MATCHED_SEARCH on CALIBRATED's measured CPU, then the development run
# (induction organs as demonstrations, validation organs as queries) and its scoring. Run in one CPU slot:
#   sh scripts/run_detached.sh cal_calacc_chain --slot sh <this file>
ROOT=/path/to/repository/experiments/calibrated_acceptance_20261108
PY=python3
H=$ROOT/scripts/caharness.py
S=$ROOT/data/work/cal_chain.run.status
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p $ROOT/data/work
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
if [ ! -f $ROOT/data/work/cal/final/CALIBRATED.json ] || [ ! -f $ROOT/data/work/cal/final/STRICT.json ] || [ ! -f $ROOT/data/work/cal/final/TOLERANT.json ]; then
  $PY -I -B $H pool final CALIBRATED STRICT TOLERANT || { log "EXIT 1 final pool"; exit 1; }
fi
log FINAL_DONE
[ -f $ROOT/data/work/cal/final/MATCHED_SEARCH.json ] || $PY -I -B $H matched final || { log "EXIT 1 matched final"; exit 1; }
log MATCHED_FINAL_DONE
$PY -I -B $H pool dev CALIBRATED STRICT TOLERANT CAL_BLIND_1 CAL_BLIND_2 CAL_BLIND_3 CAL_BLIND_4 CAL_BLIND_5 CAL_SHUFFLED_1 CAL_SHUFFLED_2 CAL_SHUFFLED_3 CAL_SHUFFLED_4 CAL_SHUFFLED_5 || log "dev pool: some arm failed"
log DEV_POOL_DONE
$PY -I -B $H matched dev || log "matched dev failed"
log MATCHED_DEV_DONE
$PY -I -B $H dev_score || { log "EXIT 1 dev_score"; exit 1; }
log "EXIT 0"
