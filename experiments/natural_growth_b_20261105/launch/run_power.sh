#!/bin/sh
# Power and expectation from the frozen libraries (one CPU slot).
cd /path/to/repository/experiments/natural_growth_b_20261105
export PYTHONHASHSEED=0
python3 -I run.py power feasibility/library power/POWER.json; echo "POWER EXIT $?"
