#!/bin/sh
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.feasibility deep_switch feasibility/deep_macro_search_switch_colour0.json > logs/feas_deep_switch.log 2>&1
