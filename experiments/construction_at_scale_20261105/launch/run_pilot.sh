#!/bin/sh
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
case "$1" in
  pilot) sh $SLOT $PY -m cas.pools config/POOLS.json > logs/pools.log 2>&1
         sh $SLOT $PY -m cas.pilot config/STUDY_CONFIG.json pilot > logs/pilot.log 2>&1 ;;
  feas2) sh $SLOT $PY -m cas.feasibility W2_all_dihedral feasibility/W2_all_dihedral.json > logs/feas_W2all.log 2>&1
         sh $SLOT $PY -m cas.feasibility deep feasibility/deep_macro_search.json > logs/feas_deep.log 2>&1 ;;
esac
# power: queued behind the slots
