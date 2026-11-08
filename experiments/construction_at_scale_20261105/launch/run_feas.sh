#!/bin/sh
# Feasibility checks (evaluator side), two CPU-slot processes at nice 19.
cd /path/to/repository/experiments/construction_at_scale_20261105
PY=python3
SLOT=/path/to/repository/scripts/with_cpu_slot.sh
export PYTHONHASHSEED=0
case "$1" in
  a) sh $SLOT $PY -m cas.feasibility W1_s1 feasibility/W1_s1.json > logs/feas_W1.log 2>&1
     sh $SLOT $PY -m cas.feasibility W3_stretch_swap feasibility/W3_stretch_swap.json > logs/feas_W3.log 2>&1 ;;
  b) sh $SLOT $PY -m cas.feasibility W2_orientation feasibility/W2_orientation.json > logs/feas_W2.log 2>&1
     sh $SLOT $PY -m cas.feasibility alternatives feasibility/alternatives.json > logs/feas_alt.log 2>&1 ;;
esac
