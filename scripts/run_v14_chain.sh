#!/usr/bin/env bash
# Item-2 v1.4 chain: full twin generation, then the sealed auditor twice and
# a byte comparison. Run only after the freeze commit, detached, single
# writer. The generator itself refuses to start unless every frozen hash
# matches.
set -u
cd "$(dirname "$0")/.." || exit 1
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
unset ARC_OVERLAY ARC_DIHEDRAL_FRAMES
PY=.venv_arc2026/bin/python
LOG=logs/v14_chain.log
OUT=outputs/tti
echo "chain start $(date -u +%FT%TZ) pid $$" >> "$LOG"
nice -n 19 "$PY" scripts/generate_v14_twins.py full >> logs/v14_generation.log 2>&1
rc=$?
echo "generator exit $rc $(date -u +%FT%TZ)" >> "$LOG"
[ "$rc" -eq 0 ] || exit "$rc"
for pass in 1 2; do
  nice -n 19 "$PY" scripts/audit_v14_localization.py \
    "$OUT/v14_localization_audit_pass$pass.json" >> logs/v14_audit.log 2>&1 || exit 1
done
if cmp -s "$OUT/v14_localization_audit_pass1.json" "$OUT/v14_localization_audit_pass2.json"; then
  cp "$OUT/v14_localization_audit_pass1.json" "$OUT/v14_localization_audit.json"
  echo "reproduction: byte-identical" >> "$LOG"
else
  echo "reproduction: DIFFERENT" >> "$LOG"
fi
touch logs/V14_AUDIT_DONE
echo "chain end $(date -u +%FT%TZ)" >> "$LOG"
