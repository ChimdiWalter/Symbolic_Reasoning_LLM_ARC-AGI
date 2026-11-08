#!/bin/sh
# after the boundary (5 Nov, about 20:25Z): new W2 feasibility, pilot (all worlds), dry run | deep check, power
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
case "$1" in
  a) sh $SLOT $PY -m cas.feasibility W2_quarter_turn feasibility/W2_quarter_turn.json > logs/feas_W2q.log 2>&1
     rm -rf pilot_v2_superseded; mkdir -p pilot_v2_superseded; mv pilot/PILOT_RESULTS.json pilot/pilot_tasks_W*.json pilot_v2_superseded/ 2>/dev/null
     sh $SLOT $PY -m cas.pilot config/STUDY_CONFIG.json pilot > logs/pilot3.log 2>&1
     rm -rf checks/generator_dry_run_pilot
     sh $SLOT $PY -m cas.generate dry_run_pilot checks/DRY_RUN_CONFIG.json checks/generator_dry_run_pilot > logs/dry_run3.log 2>&1 ;;
  b) sh $SLOT $PY -m cas.feasibility deep feasibility/deep_macro_search_W2_quarter_turn.json W2_quarter_turn > logs/feas_deep_W2q.log 2>&1 ;;
esac
