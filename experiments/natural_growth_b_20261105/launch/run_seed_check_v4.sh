#!/bin/sh
# Hash-seed check on the rehearsed candidate code (one CPU slot): children with -s -B and PYTHONHASHSEED 0, 1, 2.
cd /path/to/repository/experiments/natural_growth_b_20261105
sha256sum FREEZE.json ngb/*.py run.py > checks/SEED_CHECK_V4_code.txt
python3 -I run.py seed_check checks/SEED_CHECK_V4.json; echo "SEED EXIT $?"
echo EXIT
