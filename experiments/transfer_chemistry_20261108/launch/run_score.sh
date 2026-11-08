#!/bin/sh
# The one scored rerun of T3 (PROTOCOL.md section 7, Amendments 1 and 2). Start it only after the coordinator has
# committed runs/GO_AMENDMENT2. No argument: the run derives its salt from the original committed runs/GO and refuses
# unless every check passes.
# Usage (from any directory):
#   sh /path/to/repository/experiments/transfer_chemistry_20261108/launch/run_score.sh
# It runs fully detached through scripts/run_detached.sh, inside a shared CPU slot (nice 19, idle I/O); the slot
# queue can be long, and waiting for a slot costs no CPU. The launcher's log and START and EXIT lines go to
# outputs/detached/transfer_chemistry_held_a2/ (attempt 1's are kept in runs/score_attempt1/launcher/); the run's
# status and results go to runs/score/, and a refusal goes to runs/refusals.log.
R=/path/to/repository
cd "$R/experiments/transfer_chemistry_20261108" || exit 1
exec sh "$R/scripts/run_detached.sh" transfer_chemistry_held_a2 --slot python3 -I t3chem/run.py --mode score
