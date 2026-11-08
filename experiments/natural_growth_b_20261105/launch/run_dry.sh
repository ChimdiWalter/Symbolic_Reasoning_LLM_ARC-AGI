#!/bin/sh
# Phase 1 dry run of the phase 2 code paths on source tasks only (one CPU slot), after the libraries exist.
cd /path/to/repository/experiments/natural_growth_b_20261105
until [ -f logs/after_discovery.done ]; do sleep 5; done
export PYTHONHASHSEED=0
python3 -I run.py dry_run checks/dry_run 2; echo "DRY EXIT $?"
echo EXIT
