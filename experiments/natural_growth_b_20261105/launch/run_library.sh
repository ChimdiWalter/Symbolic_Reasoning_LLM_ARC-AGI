#!/bin/sh
# Stage S on source halves (one CPU slot): sh launch/run_library.sh BENCH [BENCH ...]
cd /path/to/repository/experiments/natural_growth_b_20261105
PY=python3
export PYTHONHASHSEED=0
for B in "$@"; do $PY -I ngb/run.py library feasibility/library $B; echo "BENCH $B EXIT $?"; done
echo EXIT
