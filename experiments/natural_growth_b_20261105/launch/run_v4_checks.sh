#!/bin/sh
# Version 4 candidate checks (one CPU slot): admission tests, dry run v8, package check with the smoke test.
cd /path/to/repository/experiments/natural_growth_b_20261105
PY=python3
$PY -I run.py admission_tests > logs/admission_v8.log 2>&1; echo "ADMISSION EXIT $?"
rm -rf checks/dry_run_v8
$PY -I run.py dry_run checks/dry_run_v8 2 > logs/dry_v8.log 2>&1; echo "DRY EXIT $?"
python3 -I ngb/kaggle_build.py check > logs/package_check_v8.log 2>&1; echo "PACKAGE EXIT $?"
echo EXIT
