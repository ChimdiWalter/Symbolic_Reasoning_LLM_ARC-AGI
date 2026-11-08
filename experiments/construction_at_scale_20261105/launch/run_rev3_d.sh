#!/bin/sh
# revision 3, chain D: the plumbing check on S1's world with the revision 3 code (commit holds the grown searches)
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
rm -rf checks/s1_world checks/s1_world_controller checks/EQUIVALENCE.json checks/ANALYSIS.json checks/INCOMPLETE.json
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.equivalence checks > logs/equivalence5.log 2>&1
echo "chain D done" >> logs/equivalence5.log
