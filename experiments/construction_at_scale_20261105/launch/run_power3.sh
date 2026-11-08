#!/bin/sh
# power for the chosen m = 9 (and 8) with 10 and 11 families at S1's motivating share 11/12; design scenario C with
# all five route families (pessimistic) and with only the two cheap routes, trim and upscale (as in S1)
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
case "$1" in
  a) sh $SLOT $PY -m cas.power families power/POWER_S1_EFFECT_F10_F11_M8_M9.json 0.9166667 10,11 8,9 > logs/power3.log 2>&1 ;;
  b) sh $SLOT $PY -m cas.power design power/POWER_DESIGN_C_FIVE_ROUTES.json 0.9091 trim,upscale,dmirror,hupscale,vupscale > logs/power_c5.log 2>&1
     sh $SLOT $PY -m cas.power design power/POWER_DESIGN_C_TWO_ROUTES.json 0.9091 trim,upscale > logs/power_c2.log 2>&1 ;;
esac
