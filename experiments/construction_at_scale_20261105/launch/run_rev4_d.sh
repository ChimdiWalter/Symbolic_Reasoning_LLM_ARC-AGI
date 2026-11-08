#!/bin/sh
# revision 4: the plumbing check on S1's world with the revision 4 code
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
rm -rf checks/s1_world checks/s1_world_controller checks/EQUIVALENCE.json checks/ANALYSIS.json checks/INCOMPLETE.json
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.equivalence checks > logs/equivalence6.log 2>&1
echo "chain rev4 done" >> logs/equivalence6.log
