#!/bin/sh
# Gated growth on one benchmark's source half in one of the two shared CPU slots (nice 19).
# Usage: sh launch/run_grow.sh OUT_DIR BENCH [extra args]   (log: logs/grow_<BENCH>.log)
cd /path/to/repository/experiments/object_growth_20261105 || exit 1
OUT=$1; B=$2; shift 2
mkdir -p logs
exec sh ../../scripts/with_cpu_slot.sh env PYTHONHASHSEED=0 python3 -I run.py grow "$OUT" "$B" "$@"
