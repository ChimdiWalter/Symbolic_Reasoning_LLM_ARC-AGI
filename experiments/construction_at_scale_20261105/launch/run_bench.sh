#!/bin/sh
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.bench bench/BENCH_ATHE_REFERENCE.json > logs/bench.log 2>&1
