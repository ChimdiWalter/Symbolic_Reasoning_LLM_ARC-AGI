#!/usr/bin/env bash
# ZERO-INTERVENTION autopilot for everything pending after the current jobs.
# Arm DETACHED: setsid nohup scripts/autopilot_round4.sh > logs/autopilot.out 2>&1 &
# Stamps logs/autopilot_status.log — CHECK FIRST in a new session.
# Steps (each waits for its dependency, skips if artifact exists):
#   1. v8 chain done  -> automated flake repair + delta vs v7
#   2. E2 run done    -> paper E2 analysis (accuracy-vs-precision table)
#   3. promotion done -> read-out stamp (ops registered?)
#   4. always         -> Kaggle submission dry run from the frozen eval run
#                        + training-split submission (sanity-scored)
set -u
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate
STATUS=logs/autopilot_status.log
stamp() { echo "[$(date -u +%FT%TZ)] $*" >> "$STATUS"; }
stamp "=== autopilot armed (pid $$) ==="

# --- 1. v8 repair + delta (waits for the round4c chain's v8 full run) ---
if [ ! -f logs/autopilot_v8_done ]; then
  until grep -q "round4c chain COMPLETE" logs/round4c_status.log 2>/dev/null \
        || grep -q "STOPPED" <(tail -5 logs/round4c_status.log 2>/dev/null); do
    sleep 120
  done
  if [ -f outputs/unified_harness_v8/results.json ]; then
    stamp "v8 landed -> repair+delta"
    python3 scripts/repair_and_delta.py outputs/unified_harness_v8 \
      outputs/unified_harness_v7 > logs/v8_repair_delta.log 2>&1
    stamp "v8 repair rc=$? $(tail -2 logs/v8_repair_delta.log | head -1)"
    stamp "v8 final: $(tail -2 logs/v8_repair_delta.log | tail -1)"
  else
    stamp "round4c chain ended WITHOUT v8 results (gates red or floor) — see logs/round4c_status.log"
  fi
  touch logs/autopilot_v8_done
fi

# --- 2. E2 analysis (waits for the gate-off run) ---
if [ ! -f outputs/paper_e2/report.json ]; then
  until [ -f outputs/unified_harness_e2_gateoff/results.json ] \
        && ! pgrep -f "e2_gate_off_ablation" > /dev/null 2>&1; do
    sleep 120
  done
  stamp "E2 landed -> analysis"
  python3 scripts/paper_e2_analysis.py > logs/paper_e2_analysis.log 2>&1
  stamp "E2 analysis rc=$? $(python3 -c "
import json;r=json.load(open('outputs/paper_e2/report.json'))
g=r['gate_off'];b=r['gate_on_baseline']
print(f\"gate-off accepted={g['accepted']} precision={g['precision']} vs gate-on accepted={b['accepted']} precision={b['precision']}\")" 2>/dev/null)"
fi

# --- 3. promotion v4 read-out ---
if [ ! -f logs/autopilot_promo_done ]; then
  while pgrep -f run_library_promotion > /dev/null 2>&1; do sleep 300; done
  N=$(python3 -c "
import json,glob
f=glob.glob('outputs/object_reasoning_promotion_v4/library.json')
print(len(json.load(open(f[0]))) if f else 0)" 2>/dev/null)
  stamp "promotion v4 finished: $N operators in library (see logs/library_promotion_v4.log)"
  touch logs/autopilot_promo_done
fi

# --- 4. Kaggle submission dry runs ---
if [ ! -f outputs/submissions/submission_eval.json ]; then
  mkdir -p outputs/submissions
  stamp "building eval-split submission (frozen E3 artifacts)"
  python3 scripts/make_submission.py outputs/unified_harness_eval_frozen \
    data/arc/arc-agi_evaluation_challenges.json \
    outputs/submissions/submission_eval.json > logs/submission_eval.log 2>&1
  stamp "eval submission rc=$? $(tail -1 logs/submission_eval.log)"
  # score it against the public eval solutions (best-of-2, Kaggle metric)
  python3 - >> logs/submission_eval.log 2>&1 <<'EOF'
import json
sub=json.load(open('outputs/submissions/submission_eval.json'))
sols=json.load(open('data/arc/arc-agi_evaluation_solutions.json'))
tot=hit=0
for tid,entries in sub.items():
    for i,e in enumerate(entries):
        tot+=1
        gt=sols[tid][i]
        if e["attempt_1"]==gt or e["attempt_2"]==gt: hit+=1
print(f"KAGGLE-METRIC (public eval): {hit}/{tot} = {hit/tot:.4f}")
EOF
  stamp "eval score: $(grep KAGGLE-METRIC logs/submission_eval.log | tail -1)"
fi
BEST=outputs/unified_harness_v8
[ -f "$BEST/results.json" ] || BEST=outputs/unified_harness_v7
if [ ! -f outputs/submissions/submission_training.json ]; then
  stamp "building training-split submission from $BEST"
  python3 scripts/make_submission.py "$BEST" \
    data/arc/arc-agi_training_challenges.json \
    outputs/submissions/submission_training.json > logs/submission_training.log 2>&1
  python3 - >> logs/submission_training.log 2>&1 <<'EOF'
import json, os
best='outputs/unified_harness_v8' if os.path.exists('outputs/unified_harness_v8/results.json') else 'outputs/unified_harness_v7'
sub=json.load(open('outputs/submissions/submission_training.json'))
sols=json.load(open('data/arc/arc-agi_training_solutions.json'))
tot=hit=0
for tid,entries in sub.items():
    for i,e in enumerate(entries):
        tot+=1
        gt=sols[tid][i]
        if e["attempt_1"]==gt or e["attempt_2"]==gt: hit+=1
print(f"KAGGLE-METRIC (training): {hit}/{tot} = {hit/tot:.4f}")
EOF
  stamp "training score: $(grep KAGGLE-METRIC logs/submission_training.log | tail -1)"
fi

stamp "=== autopilot COMPLETE — review logs/v8_repair_delta.log, outputs/paper_e2/, outputs/submissions/ ==="
