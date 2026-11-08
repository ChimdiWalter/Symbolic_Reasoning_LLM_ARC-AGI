#!/bin/sh
# Stage 1 on every SOURCE task, one shard per CPU slot: sh launch/run_discover.sh I  (I = 0 or 1)
cd /path/to/repository/experiments/natural_growth_b_20261105
python3 -I run.py discover feasibility/discover_shard$1.jsonl --shard $1/2
echo EXIT $?
