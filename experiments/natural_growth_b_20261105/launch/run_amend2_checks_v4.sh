#!/bin/sh
# Amendment 2 checks after the two reviews (one CPU slot): admission tests, dry run v4 (arms 5 to 8, review fixes).
cd /path/to/repository/experiments/natural_growth_b_20261105
PY=python3
$PY -I run.py admission_tests > logs/admission_v4.log 2>&1; echo "ADMISSION EXIT $?"
rm -rf checks/dry_run_v4
$PY -I run.py dry_run checks/dry_run_v4 2 > logs/dry_v4.log 2>&1; echo "DRY EXIT $?"
echo EXIT
