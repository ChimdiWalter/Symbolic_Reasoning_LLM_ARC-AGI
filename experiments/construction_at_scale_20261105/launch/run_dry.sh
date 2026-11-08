#!/bin/sh
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.generate dry_run_pilot checks/DRY_RUN_CONFIG.json checks/generator_dry_run_pilot > logs/dry_run.log 2>&1
