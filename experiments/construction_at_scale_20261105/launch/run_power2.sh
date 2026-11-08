#!/bin/sh
# power after the boundary: scenarios A, B, N for 8 and 11 families at S1's motivating share 11/12, then the
# design-based scenario C at the pilot's share Q with the families that have a G0 route at matched-search depth
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
Q=$1
ROUTES=$2
sh $SLOT $PY -m cas.power families power/POWER_S1_EFFECT_F8_F11.json 0.9166667 8,11 > logs/power2.log 2>&1
sh $SLOT $PY -m cas.power design power/POWER_DESIGN_SCENARIO_C.json $Q $ROUTES > logs/power_c.log 2>&1
