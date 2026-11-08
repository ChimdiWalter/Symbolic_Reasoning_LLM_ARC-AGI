#!/bin/sh
# A detached, resumable chain over the protocol's order (REAL then SHUFFLED; ConceptARC, Mini-ARC, 1D-ARC) for the given
# systems, one arm at a time through scripts/with_cpu_slot.sh. Usage: sh chain.sh NAME "SYSTEMS"
#   setsid nohup sh .../chain.sh chain1 "c a" > /dev/null 2>&1 < /dev/null &
#   setsid nohup sh .../chain.sh chain2 "b"   > /dev/null 2>&1 < /dev/null &
R=/path/to/repository
E=$R/experiments/universality_similar_problems_20261102
DATA=/path/to/benchmark_data
N=$1; SYSS=$2
mkdir -p $DATA/runs
S=$DATA/runs/$N.run.status
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> $S; }
log "START pid=$$ systems=$SYSS"
for ARM in real shuffled; do
  for B in concept_arc mini_arc 1d_arc; do
    for SY in $SYSS; do
      RD=$DATA/runs/${SY}_${B}_${ARM}
      [ -f $RD/DONE ] && continue
      python3 -I $E/scripts/score.py budget >> $DATA/runs/budget.log 2>&1
      rc=$?
      if [ $rc -eq 2 ]; then log "STOP_HARD_CAP before $SY $B $ARM"; log "EXIT 0"; exit 0; fi
      if [ $rc -eq 1 ]; then log "NOT_RUN_SOFT_CAP $SY $B $ARM"; continue; fi
      log "ARM_START $SY $B $ARM"
      if sh $R/scripts/with_cpu_slot.sh sh $E/scripts/run_arm.sh $SY $B $ARM >> $DATA/runs/${SY}_${B}_${ARM}.log 2>&1; then
        touch $RD/DONE; log "ARM_DONE $SY $B $ARM"
      else
        log "ARM_FAIL $SY $B $ARM"
      fi
    done
  done
done
log "EXIT 0"
