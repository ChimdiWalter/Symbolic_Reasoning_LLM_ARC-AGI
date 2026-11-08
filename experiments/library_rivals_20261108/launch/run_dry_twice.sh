#!/bin/sh
# Dry run twice in separate interpreters (different hash seeds under -I) on 5 source tasks per benchmark, then the
# determinism comparison (checks/DETERMINISM.json). One CPU slot. Before the freeze only (refuses if FREEZE.json exists).
cd /path/to/repository/experiments/library_rivals_20261108
PY=python3
[ -f FREEZE.json ] && { echo "refusing: FREEZE.json exists; the dry runs and the determinism record are frozen"; echo EXIT; exit 2; }
rm -rf checks/dry_run checks/dry_run_repeat
$PY -I run.py phase dry checks/dry_run 5 > logs/dry_a.log 2>&1; echo "DRY A $?"
$PY -I run.py phase dry checks/dry_run_repeat 5 > logs/dry_b.log 2>&1; echo "DRY B $?"
$PY -I run.py determinism checks/dry_run checks/dry_run_repeat; echo "DET $?"
echo EXIT
