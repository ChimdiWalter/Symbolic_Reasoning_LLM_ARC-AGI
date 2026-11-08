#!/bin/sh
# revision 2, chain A: pilot and dry run with the corrected generator loop; power under the dependence-aware rule
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
rm -rf pilot_v3_superseded; mkdir -p pilot_v3_superseded
mv pilot/PILOT_RESULTS.json pilot/pilot_tasks_W*.json pilot_v3_superseded/ 2>/dev/null
sh $SLOT $PY -m cas.pilot config/STUDY_CONFIG.json pilot > logs/pilot4.log 2>&1
rm -rf checks/generator_dry_run_pilot
sh $SLOT $PY -m cas.generate dry_run_pilot checks/DRY_RUN_CONFIG.json checks/generator_dry_run_pilot > logs/dry_run4.log 2>&1
sh $SLOT $PY -m cas.power clustered power/POWER_CLUSTERED_RULE.json 0.9166667 > logs/power_clustered.log 2>&1
mkdir -p power/superseded
mv power/POWER_DESIGN_C_FIVE_ROUTES.json power/superseded/POWER_DESIGN_C_FIVE_ROUTES_11_family_rule.json 2>/dev/null
mv power/POWER_DESIGN_C_TWO_ROUTES.json power/superseded/POWER_DESIGN_C_TWO_ROUTES_11_family_rule.json 2>/dev/null
sh $SLOT $PY -m cas.power design power/POWER_DESIGN_C_CLUSTERED_FIVE_ROUTES.json 0.9091 trim,upscale,dmirror,hupscale,vupscale > logs/power_c5c.log 2>&1
sh $SLOT $PY -m cas.power design power/POWER_DESIGN_C_CLUSTERED_TWO_ROUTES.json 0.9091 trim,upscale > logs/power_c2c.log 2>&1
echo "chain A done" >> logs/power_c2c.log
