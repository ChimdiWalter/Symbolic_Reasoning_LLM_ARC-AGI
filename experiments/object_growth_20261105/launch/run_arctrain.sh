#!/bin/sh
# ARC training development check in one shared CPU slot (nice 19). Usage: sh launch/run_arctrain.sh OUT_DIR N
cd /path/to/repository/experiments/object_growth_20261105 || exit 1
mkdir -p logs
exec sh ../../scripts/with_cpu_slot.sh env PYTHONHASHSEED=0 python3 -I run.py arctrain "$1" --n "$2" --retry
