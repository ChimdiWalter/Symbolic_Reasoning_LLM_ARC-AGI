#!/bin/sh
# Object expectation with the measured-static scenario from rehearsal 2 (one CPU slot).
cd /path/to/repository/experiments/natural_growth_b_20261105
python3 -I run.py power_object power/POWER_OBJECT.json > logs/power_object_v5.log 2>&1; echo "POWER EXIT $?"
echo EXIT
