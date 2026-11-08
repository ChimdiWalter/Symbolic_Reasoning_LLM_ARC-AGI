#!/bin/sh
# revision 2 smoke test of the matched-search driver with the budget rule: one motivating task of S1's own world
# (S1's tasks only), in a copy of the plumbing-check world; keeps the result JSON, removes the copy
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0 CAS_CPU_SCALE=1
rm -rf checks/c7m_budget_smoke && mkdir -p checks/c7m_budget_smoke && cp -r checks/s1_world checks/c7m_budget_smoke/s1_world
rm -f checks/c7m_budget_smoke/s1_world/runs/cas_c7m/c7m_M.json
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.run_world c7m checks/c7m_budget_smoke/s1_world M 1 1 > logs/c7m_smoke.log 2>&1
cp checks/c7m_budget_smoke/s1_world/runs/cas_c7m/c7m_M.json checks/C7M_BUDGET_SMOKE.json
rm -rf checks/c7m_budget_smoke
