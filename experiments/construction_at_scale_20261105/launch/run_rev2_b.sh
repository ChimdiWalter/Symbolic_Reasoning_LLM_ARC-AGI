#!/bin/sh
# revision 2, chain B: the plumbing check on S1's world with the final code, then the matched-search driver smoke test
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
rm -rf checks/s1_world checks/s1_world_controller checks/EQUIVALENCE.json checks/ANALYSIS.json checks/INCOMPLETE.json
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.equivalence checks > logs/equivalence4.log 2>&1
sh launch/run_c7m_smoke.sh
echo "chain B done" >> logs/c7m_smoke.log
