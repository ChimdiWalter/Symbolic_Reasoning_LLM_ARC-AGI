#!/bin/sh
# Dry run of the amended phase 2 code paths on source tasks only (one CPU slot), into a fresh folder.
cd /path/to/repository/experiments/natural_growth_b_20261105
python3 -I run.py dry_run checks/dry_run_v2 2; echo "DRY EXIT $?"
echo EXIT
