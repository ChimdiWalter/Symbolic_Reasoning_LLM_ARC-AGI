#!/bin/sh
# One arm: system (a = O+ v2, b = H's CORA component, c = O) on one benchmark (concept_arc, mini_arc, 1d_arc) and arm
# (real, shuffled), called exactly as PROTOCOL.md section 2, from systems/<id>/, hashes verified before and after.
set -e
R=/path/to/repository
E=$R/experiments/universality_similar_problems_20261102
DATA=/path/to/benchmark_data
PY=python3
SY=$1; B=$2; ARM=$3
C=$DATA/prepared/$B/$ARM.json
D=$DATA/runs/${SY}_${B}_${ARM}
rm -rf $D && mkdir -p $D
python3 -I $E/scripts/verify_systems.py before_${SY}_${B}_${ARM}
P='[{"name": "cast_v1", "entry": "cast_candidates", "cpu_s": 45, "wall_s": 90, "details": 1}, {"name": "r29_cpu_package_20261101", "entry": "candidates", "cpu_s": 12, "wall_s": 24, "details": 0}]'
case $SY in
  a) cd $E/systems/oplus && PYTHONPATH=$E/systems/oplus $PY -m sfo.driver_plus --challenges $C --out $D/run \
       --submission $D/submission.json --packages "$P" --deadline-s 39600 --grace-s 10 --shards 1 ;;
  b) DL=$(( $(date +%s) + 21600 ))
     cd $E/systems/h && PYTHONPATH=$E/systems/h $PY -m sfb.cast_side --challenges $C --out $D/side \
       --package cast_selective_v2 --entry evaluate --mode evidence --deadline $DL --cpu-s 15 --wall-s 30 \
       --grace-s 10 --nice 10
     PYTHONPATH=$E/systems/h $PY $E/scripts/h_merge.py $C $D ;;
  c) cd $E/systems/o && PYTHONPATH=$E/systems/o $PY -m sfo.driver --challenges $C --out $D/run \
       --submission $D/submission.json --package cast_v1 --entry cast_candidates --cpu-s 15 --wall-s 30 \
       --grace-s 10 --shards 1 --deadline-s 39600 ;;
  *) echo "unknown system $SY"; exit 2 ;;
esac
python3 -I $E/scripts/verify_systems.py after_${SY}_${B}_${ARM}
echo "ARM $SY $B $ARM done"
