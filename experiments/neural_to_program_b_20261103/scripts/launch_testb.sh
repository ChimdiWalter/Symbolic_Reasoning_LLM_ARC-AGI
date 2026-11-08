#!/bin/sh
# Launch the Test B inference run (PROTOCOL.md section 5) detached, in one shared CPU slot (nice 19, ionice idle),
# with BLAS threads 1. The driver itself refuses without an exact runs/GO_B, and runs/RUN_CLAIM.json makes it one use.
# Progress: runs/run.status. After a forced interruption: python -I testb/driver.py close (never a second run).
set -eu
REPO=/path/to/repository
EXP=$REPO/experiments/neural_to_program_b_20261103
test -f "$EXP/runs/GO_B" || { echo "no runs/GO_B: the run is not released" >&2; exit 1; }
test ! -e "$EXP/runs/RUN_CLAIM.json" || { echo "runs/RUN_CLAIM.json exists: GO_B is one use" >&2; exit 1; }
cd "$REPO"
setsid nohup sh scripts/with_cpu_slot.sh env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 python3 -I "$EXP/testb/driver.py" run \
  > "$EXP/runs/driver.log" 2>&1 < /dev/null &
echo "launched Test B driver (pid $!); progress in $EXP/runs/run.status"
