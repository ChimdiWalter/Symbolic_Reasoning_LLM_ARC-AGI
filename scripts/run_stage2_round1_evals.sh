#!/usr/bin/env bash
# Stage-2 round-1 dev-eval ablation grid (STAGE2_REQUIREMENTS.md 3.3):
# cells {depth-3, depth-1} x {ranker, no-ranker} on dev-19 and sample-30,
# sequential (contention-free = authoritative), library seeded from promotion v3.
# Every step stamped in logs/stage2_round1_status.log. Resumable: cells whose
# summary JSON already exists are skipped.
set -u
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate

DEV19="05f2a901,dc433765,1caeab9d,a1570a43,ae3edfdc,5521c0d9,2c737e39,e76a88a6,88a10436,0a2355a6,6ea4a07e,1acc24af,b2862040,2204b7a8,4852f2fa,358ba94e,2dc579da,25e02866,445eab21"
S30_FILE="configs/s30_ids.json"
LIB="outputs/object_reasoning_promotion_v3/library.json"
STATUS="logs/stage2_round1_status.log"

stamp() { echo "[$(date -u +%FT%TZ)] $*" >> "$STATUS"; }

run_cell() { # $1=tag  $2=taskflag  $3=taskval  $4...=extra flags
  local tag="$1" tflag="$2" tval="$3"; shift 3
  local dir="outputs/object_reasoning_dev/$tag"
  if [ -f "$dir/eval_summary_$tag.json" ]; then stamp "SKIP $tag (summary exists)"; return 0; fi
  mkdir -p "$dir"
  cp "$LIB" "$dir/library.json"
  stamp "START $tag ($*)"
  python3 scripts/run_object_dev_eval.py "$tflag" "$tval" \
      --out-dir "$dir" --tag "$tag" --log "logs/object_engine_$tag.log" "$@" \
      > "logs/${tag}.out" 2>&1
  stamp "DONE $tag rc=$? summary=$dir/eval_summary_$tag.json"
}

stamp "=== stage2 round1 eval grid launched (pid $$) ==="

# headline cells first
run_cell stage2r1_dev19            --tasks "$DEV19"
run_cell stage2r1_s30              --file  "$S30_FILE"
# ablations
run_cell stage2r1_dev19_depth1     --tasks "$DEV19" --depth-1
run_cell stage2r1_dev19_noranker   --tasks "$DEV19" --no-ranker
run_cell stage2r1_s30_depth1       --file  "$S30_FILE" --depth-1
run_cell stage2r1_s30_noranker     --file  "$S30_FILE" --no-ranker
run_cell stage2r1_dev19_d1_nr      --tasks "$DEV19" --depth-1 --no-ranker
run_cell stage2r1_s30_d1_nr        --file  "$S30_FILE" --depth-1 --no-ranker

# regression gates vs libgain baselines (identical to round-3 numbers)
stamp "REGRESSION GATES"
python3 scripts/compare_eval_rounds.py \
    outputs/object_reasoning_dev/libgain_dev19/eval_summary_libgain_dev19.json \
    outputs/object_reasoning_dev/stage2r1_dev19/eval_summary_stage2r1_dev19.json \
    > logs/stage2r1_gate_dev19.log 2>&1
stamp "gate dev19 rc=$? (log logs/stage2r1_gate_dev19.log)"
python3 scripts/compare_eval_rounds.py \
    outputs/object_reasoning_dev/libgain_s30/eval_summary_libgain_s30.json \
    outputs/object_reasoning_dev/stage2r1_s30/eval_summary_stage2r1_s30.json \
    > logs/stage2r1_gate_s30.log 2>&1
stamp "gate s30 rc=$? (log logs/stage2r1_gate_s30.log)"
stamp "=== stage2 round1 eval grid COMPLETE ==="
