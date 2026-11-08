#!/bin/sh
# U5 baseline segmentation of one dataset's calibration (cal) or evaluation (eval) images, in a CPU slot.
#   setsid nohup sh seg_chain.sh DS cal|eval &      Status: work/seg_DS_MODE.run.status
R=/path/to/repository
E=$R/experiments/universality_bio_grammar_20261103
W=/path/to/bio_data/work
DS=$1; MODE=$2
S=$W/seg_${DS}_${MODE}.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$"
if [ "$MODE" = eval ] && [ ! -f $W/GO_EVALUATION ]; then
  DL=$(date -d 2026-11-04T12:00:00Z +%s)
  if [ $(date +%s) -lt $DL ] || [ -f $W/HOLD_FOR_AMENDMENT ]; then log "EXIT 2 evaluation is held"; exit 2; fi
fi
case $DS in
  nuinsseg) CMD="$R/outputs/universality_v2/venv_stardist/bin/python -I $E/scripts/seg_stardist.py $DS 2D_versatile_he $MODE" ;;
  fnc) CMD="$R/outputs/universality_v2/venv_stardist/bin/python -I $E/scripts/seg_stardist.py $DS 2D_versatile_fluo $MODE" ;;
  monusac) CMD="$R/outputs/universality_v2/venv_stardist/bin/python -I $E/scripts/seg_stardist.py $DS 2D_versatile_he $MODE" ;;
  livecell) CMD="python3 -I $E/scripts/seg_cellpose.py $DS $MODE" ;;
  fluoecoli) CMD="python3 -I $E/scripts/seg_cellpose.py $DS $MODE" ;;
esac
sh $R/scripts/with_cpu_slot.sh $CMD >> $W/seg_${DS}_${MODE}.log 2>&1 && log "SEGMENTED" || { log "EXIT 1 segment"; exit 1; }
log "EXIT 0"
