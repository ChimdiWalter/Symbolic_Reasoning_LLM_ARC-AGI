#!/bin/bash
# Autonomous chain: wait for library-promotion cluster invention (pid $PROMO_PID)
# -> seed final library.json into a fresh harness out-dir
# -> full 1000-task 3-layer run
# -> delta report vs outputs/unified_harness_v2 (151/1000 baseline).
#
# Launched detached (setsid + nohup) so it survives SSH sign-out / internet loss.
# Does NOT survive machine reboot; resume instructions in RESUME_STAGE1.md.
# All progress stamped to logs/autochain_status.log.

set -u
PROJECT=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project
cd "$PROJECT"
source /home/cnptp/.venvs/lesegenv/bin/activate

PROMO_PID=${1:?usage: autochain_lib_harness.sh PROMO_PID}
LIB_SRC=outputs/object_reasoning_promotion_v3/library.json
OUT=outputs/unified_harness_v3_lib
STATUS=logs/autochain_status.log

stamp() { echo "[$(date '+%F %T')] $*" >> "$STATUS"; }

stamp "autochain started (pid $$), waiting on promotion pid $PROMO_PID"

# ---- 1. Wait for the promotion process to exit (poll; PID-reuse-safe) ----
while [ -d "/proc/$PROMO_PID" ] && grep -q run_library_promotion "/proc/$PROMO_PID/cmdline" 2>/dev/null; do
    sleep 60
done
stamp "promotion pid $PROMO_PID exited"
sleep 5  # let final file writes land

if tail -5 logs/library_promotion_v3.log | grep -q "promote_and_validate registered"; then
    stamp "promotion completed CLEANLY: $(tail -3 logs/library_promotion_v3.log | tr '\n' ' | ')"
else
    stamp "WARNING: promotion log lacks completion line (crash/kill?) — proceeding with library.json as-is"
fi

if [ ! -s "$LIB_SRC" ]; then
    stamp "FATAL: $LIB_SRC missing/empty — aborting chain"
    exit 1
fi
N_OPS=$(python3 -c "import json;print(len(json.load(open('$LIB_SRC')).get('operators',[])))" 2>/dev/null || echo "?")
stamp "final library: $N_OPS operators ($LIB_SRC)"
cp "$LIB_SRC" outputs/object_reasoning_promotion_v3/library_final_snapshot.json

# ---- 2. Seed library into fresh harness out-dir ----
mkdir -p "$OUT/object"
cp "$LIB_SRC" "$OUT/object/library.json"
stamp "seeded library into $OUT/object/library.json"

# ---- 3. Full 1000-task 3-layer run (resumable via progress.jsonl) ----
stamp "launching full 1000-task harness (16 workers) -> $OUT"
python3 -u scripts/run_unified_harness.py --workers 16 \
    --out-dir "$OUT" --run-id full_lib_2026_07_05 \
    > logs/harness_full_1000_v3_lib.log 2>&1
RC=$?
stamp "harness exited rc=$RC"
if [ ! -s "$OUT/results.json" ]; then
    stamp "FATAL: $OUT/results.json missing — rerun resumes from progress.jsonl:"
    stamp "  python3 scripts/run_unified_harness.py --workers 16 --out-dir $OUT --run-id full_lib_2026_07_05"
    exit 1
fi

# ---- 4. Delta report vs unified_harness_v2 ----
python3 - <<'PY' > logs/lib_delta_vs_v2.log 2>&1
import json
old = json.load(open('outputs/unified_harness_v2/results.json'))
new = json.load(open('outputs/unified_harness_v3_lib/results.json'))
os_, ns = set(old['solved']), set(new['solved'])
delta = {
    'old_total': len(os_), 'new_total': len(ns),
    'gained': sorted(ns - os_), 'lost': sorted(os_ - ns),
    'by_origin_old': old.get('by_origin'), 'by_origin_new': new.get('by_origin'),
    'object_layer_old': old.get('object_layer'), 'object_layer_new': new.get('object_layer'),
}
json.dump(delta, open('outputs/unified_harness_v3_lib/delta_vs_v2.json', 'w'), indent=2)
print(f"solved {len(os_)} -> {len(ns)}  (+{len(ns-os_)} gained, -{len(os_-ns)} lost)")
print("gained:", sorted(ns - os_))
print("lost (check for contention flakes before calling regression):", sorted(os_ - ns))
PY
stamp "delta report written: outputs/unified_harness_v3_lib/delta_vs_v2.json — $(head -1 logs/lib_delta_vs_v2.log)"
stamp "autochain DONE. Next (manual review): review delta, record in RUN_HISTORY.md, then Stage 2 implementation (docs/STAGE2_REQUIREMENTS.md)."
