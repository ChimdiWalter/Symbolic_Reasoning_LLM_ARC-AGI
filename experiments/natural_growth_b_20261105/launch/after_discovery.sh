#!/bin/sh
# Waits for both discovery shards, then runs the library stage (two slots), the shuffled libraries and power.
cd /path/to/repository/experiments/natural_growth_b_20261105
until grep -q "^EXIT" logs/discover_shard0.log && grep -q "^EXIT" logs/discover_shard1.log; do sleep 5; done
W=/path/to/repository/scripts/with_cpu_slot.sh
sh $W sh launch/run_library.sh mini_arc concept_arc > logs/library_mc.log 2>&1 &
sh $W sh launch/run_library.sh 1d_arc > logs/library_1d.log 2>&1 &
wait
export PYTHONHASHSEED=0
PY=python3
nice -n 19 $PY -I run.py library feasibility/library shuffle > logs/shuffle.log 2>&1; echo "SHUFFLE EXIT $?" >> logs/shuffle.log
nice -n 19 $PY -I run.py power feasibility/library power/POWER.json > logs/power.log 2>&1; echo "POWER EXIT $?" >> logs/power.log
echo ALL DONE > logs/after_discovery.done
