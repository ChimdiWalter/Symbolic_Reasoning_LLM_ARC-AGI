#!/usr/bin/env bash
# Round-2 (GROW + phase-B levers) unattended validation chain.
# Arm DETACHED so it survives SSH/internet loss (NOT reboot):
#   setsid nohup scripts/autochain_round2.sh > logs/round2_autochain.out 2>&1 &
# Every step stamps logs/round2_autochain_status.log — CHECK THAT FILE FIRST
# in a new session.  Resumable: rerun the script; finished steps are skipped
# via their artifact files.
set -u
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate

STATUS=logs/round2_autochain_status.log
stamp() { echo "[$(date -u +%FT%TZ)] $*" >> "$STATUS"; }

DEV19="05f2a901,dc433765,1caeab9d,a1570a43,ae3edfdc,5521c0d9,2c737e39,e76a88a6,88a10436,0a2355a6,6ea4a07e,1acc24af,b2862040,2204b7a8,4852f2fa,358ba94e,2dc579da,25e02866,445eab21"
S30_FILE="configs/s30_ids.json"
PROBE20="103eff5b,2b01abd0,2de01db2,3906de3d,56dc2b01,760b3cac,7ddcd7ec,87ab05b8,8e301a54,9565186b,98c475bf,df8cc377,e40b9e2f,f25ffba3,97239e3d,99306f82,e69241bd,d492a647,b782dc8a,aaef0977"
LIB=outputs/object_reasoning_promotion_v3/library.json

stamp "=== autochain_round2 started (pid $$) ==="

# 0. Wait for any in-flight dev eval to finish (the pre-lever probe run).
while pgrep -f "run_object_dev_eval.py" > /dev/null 2>&1; do sleep 30; done
stamp "step0: no dev-eval process running"

# 1. Full test suite.
if [ ! -f logs/pytest_round2_done ]; then
  stamp "step1: pytest starting"
  python3 -m pytest geocat_arc/object_reasoning/tests/ -q \
    > logs/pytest_round2.log 2>&1
  rc=$?
  tail -1 logs/pytest_round2.log >> "$STATUS"
  if [ $rc -ne 0 ]; then
    stamp "step1: PYTEST FAILED (rc=$rc) — chain STOPPED; fix before evals"
    exit 1
  fi
  touch logs/pytest_round2_done
  stamp "step1: pytest green"
else
  stamp "step1: skipped (done marker present)"
fi

run_eval() {  # name, extra args...
  local name=$1; shift
  local dir=outputs/object_reasoning_dev/$name
  if ls "$dir"/eval_summary_*.json > /dev/null 2>&1; then
    stamp "$name: skipped (summary exists)"
    return 0
  fi
  mkdir -p "$dir"
  cp "$LIB" "$dir/library.json"
  stamp "$name: starting"
  python3 scripts/run_object_dev_eval.py "$@" \
    --budget-s 60 --out-dir "$dir" --tag "$name" --log "logs/$name.log" \
    > "logs/$name.out" 2>&1
  stamp "$name: rc=$? $(python3 - "$dir" <<'EOF'
import glob, json, sys
f = sorted(glob.glob(sys.argv[1] + "/eval_summary_*.json"))
if f:
    s = json.load(open(f[-1]))
    print(f"train_exact={s.get('train_exact')} test_correct={s.get('test_correct')} "
          f"crashes={s.get('crashes')} depth={s.get('mean_composition_depth')}")
else:
    print("NO SUMMARY")
EOF
)"
}

# 2-4. Evals: dev-19, s30 (regression baselines), probe-20 (round-2 target).
run_eval round2_dev19    --tasks "$DEV19"
run_eval round2_s30      --file  "$S30_FILE"
run_eval round2_probe20  --tasks "$PROBE20"

# 5. Regression gates vs libgain (round-3+library baselines).
for pair in "round2_dev19 libgain_dev19" "round2_s30 libgain_s30"; do
  set -- $pair
  new=$1; old=$2
  if python3 scripts/compare_eval_rounds.py \
       outputs/object_reasoning_dev/$old outputs/object_reasoning_dev/$new \
       > logs/round2_gate_$new.log 2>&1; then
    stamp "gate $new vs $old: rc=0 (no regressions)"
  else
    stamp "gate $new vs $old: rc=1 REGRESSION — see logs/round2_gate_$new.log"
  fi
done

stamp "=== autochain_round2 COMPLETE ==="
