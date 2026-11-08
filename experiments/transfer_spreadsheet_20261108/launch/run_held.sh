#!/bin/sh
# Test T2: the one detached scored run on the held tasks, after the coordinator's GO (runs/GO_T2).
# Usage: sh launch/run_held.sh
# It uses the project's detached runner (setsid, nohup, one shared CPU slot at nice 19):
#   outputs/detached/t2_held_score/run.status ("START", then "EXIT <code>"), stdout.log, stderr.log.
# The run writes its results into the study folder, runs/held/ (run.status, summary.json, records_B<budget>.jsonl);
# the owner commits that folder right after the run ends.
R=/path/to/repository
S=$R/experiments/transfer_spreadsheet_20261108
test -f "$S/runs/GO_T2" || { echo "no GO file"; exit 1; }
test ! -e "$S/runs/held" || { echo "runs/held exists: one run only"; exit 1; }
cd "$R" && sh scripts/run_detached.sh t2_held_score --slot python3 -I "$S/t2/run.py" "$S" held
