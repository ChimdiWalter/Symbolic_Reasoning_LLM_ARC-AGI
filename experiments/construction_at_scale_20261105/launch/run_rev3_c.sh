#!/bin/sh
# revision 3, chain C: the generator dry run on the pilot pool with motivating sources disjoint across worlds, then
# the package-mode smoke test (scratchpad) on the dry-run worlds
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
rm -rf checks/generator_dry_run_pilot
sh $SLOT $PY -m cas.generate dry_run_pilot checks/DRY_RUN_CONFIG.json checks/generator_dry_run_pilot > logs/dry_run5.log 2>&1
SCR=/tmp/scratch
rm -rf $SCR/smoke3 && mkdir -p $SCR/smoke3
sh $SLOT $PY $SCR/pkg_smoke.py $SCR/smoke3 > $SCR/smoke3.log 2>&1
echo "chain C done" >> logs/dry_run5.log
