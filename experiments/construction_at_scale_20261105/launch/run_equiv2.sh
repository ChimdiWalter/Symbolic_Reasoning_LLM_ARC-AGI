#!/bin/sh
# plumbing check re-run with the final code (fresh folders; S1's own tasks only)
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
rm -rf checks/s1_world checks/s1_world_controller checks/EQUIVALENCE.json checks/ANALYSIS.json
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.equivalence checks > logs/equivalence2.log 2>&1
