#!/bin/sh
# The one detached run of the library-rivals test (after the GO): every arm on every held task, the seal, the scoring.
# Usage (from anywhere): sh experiments/library_rivals_20261108/launch/run_main.sh
cd /path/to/repository
sh scripts/run_detached.sh library_rivals_20261108 --slot python3 -I \
  experiments/library_rivals_20261108/run.py phase all experiments/library_rivals_20261108/runs/main
