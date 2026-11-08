#!/bin/sh
# design-based scenario C with six route families (switch is a route too, finding 6's re-check), clustered rule
cd /path/to/repository/experiments/construction_at_scale_20261105
export PYTHONHASHSEED=0
sh /path/to/repository/scripts/with_cpu_slot.sh python3 -m cas.power design power/POWER_DESIGN_C_CLUSTERED_SIX_ROUTES.json 0.9091 trim,upscale,dmirror,hupscale,vupscale,switch > logs/power_c6c.log 2>&1
echo "c6 done" >> logs/power_c6c.log
