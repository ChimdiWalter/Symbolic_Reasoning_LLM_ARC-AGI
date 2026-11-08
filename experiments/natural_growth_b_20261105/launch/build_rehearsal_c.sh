#!/bin/sh
# Build rehearsal kernel RC of rehearsal N (one CPU slot) from that rehearsal's RA and RB outputs, which the build
# verifies first (manifests; stage records under rehearsal/REHEARSAL_GO, which is not rewritten here).
# Usage: sh scripts/with_cpu_slot.sh sh launch/build_rehearsal_c.sh N
cd /path/to/repository/experiments/natural_growth_b_20261105
X=checks/kaggle_rehearsal/rehearsal_$1/extracted
cmp -s rehearsal/REHEARSAL_GO checks/kaggle_rehearsal/rehearsal_$1/REHEARSAL_GO || { echo "REHEARSAL_GO is not rehearsal $1's"; echo EXIT; exit 2; }
python3 -I ngb/kaggle_build.py rehearsal_arc2 "$X/RA" "$X/RB" > logs/build_rehearsal_c_$1.log 2>&1; echo "BUILD EXIT $?"
echo EXIT
