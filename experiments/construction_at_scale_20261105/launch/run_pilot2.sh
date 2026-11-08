#!/bin/sh
# pilot re-run with the final configuration (family order), capacity, then the generator dry run
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
sh $SLOT $PY -m cas.capacity pilot/POOL_CAPACITY.json > logs/capacity.log 2>&1
rm -rf pilot_v1_superseded; mkdir -p pilot_v1_superseded; mv pilot/PILOT_RESULTS.json pilot/pilot_tasks_W*.json pilot_v1_superseded/ 2>/dev/null
sh $SLOT $PY -m cas.pilot config/STUDY_CONFIG.json pilot > logs/pilot2.log 2>&1
rm -rf checks/generator_dry_run_pilot
sh $SLOT $PY -m cas.generate dry_run_pilot checks/DRY_RUN_CONFIG.json checks/generator_dry_run_pilot > logs/dry_run2.log 2>&1
