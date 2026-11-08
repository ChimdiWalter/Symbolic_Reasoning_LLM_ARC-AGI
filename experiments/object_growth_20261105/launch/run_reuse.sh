#!/bin/sh
# Reuse of the grown grammar on one benchmark's source half, in one shared CPU slot (nice 19).
# Usage: sh launch/run_reuse.sh OUT_DIR BENCH   (log: logs/reuse_<OUT>_<BENCH>.log)
cd /path/to/repository/experiments/object_growth_20261105 || exit 1
exec sh ../../scripts/with_cpu_slot.sh env PYTHONHASHSEED=0 python3 -I run.py reuse "$1" "$2"
