#!/bin/sh
# Amendment 2 checks (one CPU slot): admission tests, object expectation, dry run v3 (arms 5 to 8 included).
cd /path/to/repository/experiments/natural_growth_b_20261105
PY=python3
$PY -I run.py admission_tests > logs/admission_v3.log 2>&1; echo "ADMISSION EXIT $?"
$PY -I run.py power_object power/POWER_OBJECT.json > logs/power_object.log 2>&1; echo "POWER_OBJECT EXIT $?"
rm -rf checks/dry_run_v3
$PY -I run.py dry_run checks/dry_run_v3 2 > logs/dry_v3.log 2>&1; echo "DRY EXIT $?"
echo EXIT
