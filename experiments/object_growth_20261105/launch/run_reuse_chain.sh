#!/bin/sh
# Reuse computations one after another in one shared CPU slot (nice 19): v2 concept_arc, v2 1d_arc, v1 concept_arc, v1 1d_arc.
cd /path/to/repository/experiments/object_growth_20261105 || exit 1
exec sh ../../scripts/with_cpu_slot.sh sh -c 'for v in v2 v1; do for b in concept_arc 1d_arc; do PYTHONHASHSEED=0 python3 -s -B run.py reuse runs/$v $b; done; done; echo CHAIN_DONE'
