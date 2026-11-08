#!/bin/sh
# revision 4 (with our reviewer's findings): plumbing check, generator dry run, then the matched-search driver smoke
# test with the memory-rerun stage (S1's own task t83286f67 only)
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
case "$1" in
  plumbing)
    rm -rf checks/s1_world checks/s1_world_controller checks/EQUIVALENCE.json checks/ANALYSIS.json checks/INCOMPLETE.json
    sh $SLOT $PY -m cas.equivalence checks > logs/equivalence7.log 2>&1
    # the matched-search driver with the budget rule, then the memory-rerun stage on a simulated memory failure
    rm -rf checks/c7m_budget_smoke && mkdir -p checks/c7m_budget_smoke && cp -r checks/s1_world checks/c7m_budget_smoke/s1_world
    rm -f checks/c7m_budget_smoke/s1_world/runs/cas_c7m/c7m_M.json
    CAS_CPU_SCALE=1 sh $SLOT $PY -m cas.run_world c7m checks/c7m_budget_smoke/s1_world M 1 1 > logs/c7m_smoke2.log 2>&1
    cp checks/c7m_budget_smoke/s1_world/runs/cas_c7m/c7m_M.json checks/C7M_BUDGET_SMOKE.json
    $PY -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); t=sorted(d)[0]; d[t]=dict(fit=False, memory_capped=True, preds=[], budget_cpu_s=d[t]['budget_cpu_s'], note='simulated memory failure for the rerun test'); json.dump(d, open(p,'w'))" checks/c7m_budget_smoke/s1_world/runs/cas_c7m/c7m_M.json
    CAS_CPU_SCALE=1 sh $SLOT $PY -m cas.run_world c7m_rerun checks/c7m_budget_smoke/s1_world > logs/c7m_rerun_smoke.log 2>&1
    cp checks/c7m_budget_smoke/s1_world/runs/cas_c7m/c7m_M.json checks/C7M_RERUN_SMOKE.json
    rm -rf checks/c7m_budget_smoke
    echo "plumbing chain done" >> logs/equivalence7.log ;;
  dryrun)
    rm -rf checks/generator_dry_run_pilot
    sh $SLOT $PY -m cas.generate dry_run_pilot checks/DRY_RUN_CONFIG.json checks/generator_dry_run_pilot > logs/dry_run6.log 2>&1
    echo "dry run chain done" >> logs/dry_run6.log ;;
esac
