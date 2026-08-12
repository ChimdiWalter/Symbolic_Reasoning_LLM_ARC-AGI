#!/usr/bin/env bash
# Round-2c (GROW + levers + PatternExpr MDL fix) gate-conditional chain to v5.
# Arm DETACHED (survives SSH/internet loss, NOT reboot):
#   setsid nohup scripts/autochain_round2c_to_v5.sh > logs/round2c_chain.out 2>&1 &
# Stamps logs/round2c_status.log at every step — CHECK THAT FILE FIRST.
# Resumable: rerun; finished steps skip via artifacts/markers.
# Chain: pytest -> round2c_dev19+gate -> round2c_s30+gate ->
#        (gates green) 60-task smoke -> full 1000-task v5 run.
set -u
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate

STATUS=logs/round2c_status.log
stamp() { echo "[$(date -u +%FT%TZ)] $*" >> "$STATUS"; }

DEV19="05f2a901,dc433765,1caeab9d,a1570a43,ae3edfdc,5521c0d9,2c737e39,e76a88a6,88a10436,0a2355a6,6ea4a07e,1acc24af,b2862040,2204b7a8,4852f2fa,358ba94e,2dc579da,25e02866,445eab21"
LIB=outputs/object_reasoning_promotion_v3/library.json

stamp "=== round2c chain started (pid $$) ==="

# 1. Full suite (expected 352 = 350 + 2 MDL regression tests).
if [ ! -f logs/pytest_round2c_done ]; then
  stamp "pytest starting"
  python3 -m pytest geocat_arc/object_reasoning/tests/ -q \
    > logs/pytest_round2c.log 2>&1 || {
      tail -1 logs/pytest_round2c.log >> "$STATUS"
      stamp "PYTEST FAILED — chain STOPPED"; exit 1; }
  tail -1 logs/pytest_round2c.log >> "$STATUS"
  touch logs/pytest_round2c_done
  stamp "pytest green"
else
  stamp "pytest skipped (marker)"
fi

run_eval() {
  local name=$1; shift
  local dir=outputs/object_reasoning_dev/$name
  if ls "$dir"/eval_summary_*.json > /dev/null 2>&1; then
    stamp "$name: skipped (summary exists)"; return 0
  fi
  mkdir -p "$dir"; cp "$LIB" "$dir/library.json"
  stamp "$name: starting"
  python3 scripts/run_object_dev_eval.py "$@" \
    --budget-s 60 --out-dir "$dir" --tag "$name" --log "logs/$name.log" \
    > "logs/$name.out" 2>&1
  stamp "$name: rc=$? $(python3 - "$dir" <<'EOF'
import glob, json, sys
f = sorted(glob.glob(sys.argv[1] + "/eval_summary_*.json"))
if f:
    s = json.load(open(f[-1]))
    print(f"train_exact={s.get('train_exact')} test_correct={s.get('test_correct')} crashes={s.get('crashes')}")
else:
    print("NO SUMMARY")
EOF
)"
}

run_eval round2c_dev19 --tasks "$DEV19"
run_eval round2c_s30   --file configs/s30_ids.json

GATES_OK=1
for pair in "round2c_dev19 libgain_dev19" "round2c_s30 libgain_s30"; do
  set -- $pair
  old_sum=$(ls outputs/object_reasoning_dev/$2/eval_summary_*.json | tail -1)
  new_sum=$(ls outputs/object_reasoning_dev/$1/eval_summary_*.json | tail -1)
  if python3 scripts/compare_eval_rounds.py "$old_sum" "$new_sum" \
       > logs/round2c_gate_$1.log 2>&1; then
    stamp "gate $1 vs $2: rc=0"
  else
    stamp "gate $1 vs $2: rc=1 REGRESSION — see logs/round2c_gate_$1.log"
    GATES_OK=0
  fi
done
if [ "$GATES_OK" -ne 1 ]; then
  stamp "GATES RED — chain STOPPED before smoke/full run"; exit 1
fi

# 2. 60-task 3-layer smoke (v5 engine, library-seeded).
SMOKE=outputs/unified_harness_v5_smoke
if [ ! -f "$SMOKE/results.json" ]; then
  mkdir -p "$SMOKE/object"; cp "$LIB" "$SMOKE/object/library.json"
  stamp "v5 smoke starting"
  python3 scripts/run_unified_harness.py --subset-file configs/smoke60_ids.json \
    --workers 6 --out-dir "$SMOKE" --run-id v5_smoke \
    > logs/harness_v5_smoke.log 2>&1
  stamp "v5 smoke rc=$? $(python3 - <<'EOF'
import json
r = json.load(open("outputs/unified_harness_v5_smoke/results.json"))
print(f"solved={r['total_solved']}/60 by_origin={r['by_origin']}")
EOF
)"
else
  stamp "v5 smoke skipped (results exist)"
fi
N_SMOKE=$(python3 -c "import json;print(json.load(open('$SMOKE/results.json'))['total_solved'])")
if [ "$N_SMOKE" -lt 34 ]; then
  stamp "SMOKE BELOW FLOOR ($N_SMOKE < 34) — chain STOPPED before full run"
  exit 1
fi

# 3. Full 1000-task v5 run (library-seeded, resumable).
V5=outputs/unified_harness_v5
mkdir -p "$V5/object"; cp "$LIB" "$V5/object/library.json" 2>/dev/null || true
stamp "v5 FULL RUN starting (16 workers)"
python3 scripts/run_unified_harness.py --workers 16 \
  --out-dir "$V5" --run-id full_v5_round2 \
  > logs/harness_full_1000_v5.log 2>&1
stamp "v5 full run rc=$? $(python3 - <<'EOF'
import json
r = json.load(open("outputs/unified_harness_v5/results.json"))
print(f"solved={r['total_solved']}/1000 by_origin={r['by_origin']} induced={r['induced_fraction']:.3f}")
EOF
)"
stamp "=== round2c chain COMPLETE — review v5 delta vs v4 (151), repair contention flakes per documented remedy ==="
