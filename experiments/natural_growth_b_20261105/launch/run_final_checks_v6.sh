#!/bin/sh
# Final checks on the final code (one CPU slot): admission tests and dry run v6.
cd /path/to/repository/experiments/natural_growth_b_20261105
PY=python3
$PY -I run.py admission_tests > logs/admission_v6.log 2>&1; echo "ADMISSION EXIT $?"
rm -rf checks/dry_run_v6
$PY -I run.py dry_run checks/dry_run_v6 2 > logs/dry_v6.log 2>&1; echo "DRY EXIT $?"
echo EXIT
