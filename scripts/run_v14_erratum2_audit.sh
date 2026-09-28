#!/usr/bin/env bash
# Item-2 v1.4 erratum 2: the integrity gate, then the sealed auditor twice
# on the same records, a byte comparison, and new versioned outputs. The
# blocked first-run reports are never written to.
set -u
cd "$(dirname "$0")/.." || exit 1
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
PY=.venv_arc2026/bin/python
LOG=logs/v14_erratum2_chain.log
OUT=outputs/tti
nice -n 19 "$PY" scripts/check_v14_integrity.py post >> logs/v14_erratum2_integrity.log 2>&1
rc=$?
echo "integrity post exit $rc $(date -u +%FT%TZ)" >> "$LOG"
[ "$rc" -eq 0 ] || exit "$rc"
for pass in 1 2; do
  nice -n 19 "$PY" scripts/audit_v14_localization.py \
    "$OUT/v14_localization_audit_erratum2_pass$pass.json" >> logs/v14_erratum2_audit.log 2>&1 || exit 1
done
if cmp -s "$OUT/v14_localization_audit_erratum2_pass1.json" "$OUT/v14_localization_audit_erratum2_pass2.json"; then
  cp "$OUT/v14_localization_audit_erratum2_pass1.json" "$OUT/v14_localization_audit_erratum2.json"
  echo "reproduction: byte-identical" >> "$LOG"
else
  echo "reproduction: DIFFERENT" >> "$LOG"
fi
touch logs/V14_ERRATUM2_AUDIT_DONE
echo "audit end $(date -u +%FT%TZ)" >> "$LOG"
