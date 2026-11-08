#!/bin/sh
# Athe report of Kaggle rehearsal N (one CPU slot): rehearsal mode (GO = rehearsal/REHEARSAL_GO, which must be
# rehearsal N's), the source-only data root, source outputs decoded in place from the prepared files; claim markers go
# to checks/kaggle_rehearsal/. Usage: sh scripts/with_cpu_slot.sh sh launch/run_rehearsal_report.sh N
cd /path/to/repository/experiments/natural_growth_b_20261105
O=checks/kaggle_rehearsal/rehearsal_$1/extracted
cmp -s rehearsal/REHEARSAL_GO checks/kaggle_rehearsal/rehearsal_$1/REHEARSAL_GO || { echo "REHEARSAL_GO is not rehearsal $1's"; echo EXIT; exit 2; }
NGB_REHEARSAL=1 NG_DATA="$PWD/rehearsal/data" \
NGB_SOLUTIONS_ROOT=/path/to/benchmark_data/prepared \
  python3 -I run.py report "$O/RA" "$O/RB" "$O/RC" > logs/rehearsal_report_$1.log 2>&1
echo "REPORT EXIT $?"
echo EXIT
