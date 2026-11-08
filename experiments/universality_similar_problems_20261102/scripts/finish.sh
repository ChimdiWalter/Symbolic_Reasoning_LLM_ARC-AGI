#!/bin/sh
# Waits for both chains to exit, scores once (score.py is the only reader of the solutions), commits results/.
R=/path/to/repository
E=$R/experiments/universality_similar_problems_20261102
DATA=/path/to/benchmark_data
S=$DATA/runs/finish.run.status
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) START pid=$$" >> $S
until grep -q "EXIT" $DATA/runs/chain1.run.status 2>/dev/null && grep -q "EXIT" $DATA/runs/chain2.run.status 2>/dev/null; do sleep 300; done
python3 -I $E/scripts/score.py score > $DATA/runs/score.log 2>&1 || { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) EXIT 1 score" >> $S; exit 1; }
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SCORED" >> $S
cd $R && for i in 1 2 3; do git add $E/results && git commit -q -m "U2 universality study: results written by the detached chain" -- $E/results && break; sleep 20; done
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) EXIT 0" >> $S
