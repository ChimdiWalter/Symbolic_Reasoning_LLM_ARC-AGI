#!/bin/sh
# Hash-seed check with construction probes (one CPU slot): children with -s -B and PYTHONHASHSEED 0, 1, 2.
cd /path/to/repository/experiments/natural_growth_b_20261105
python3 -I run.py seed_check checks/SEED_CHECK.json; echo "SEED EXIT $?"
echo EXIT
