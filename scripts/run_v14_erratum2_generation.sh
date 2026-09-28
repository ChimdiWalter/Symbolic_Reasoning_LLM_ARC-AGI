#!/usr/bin/env bash
# Item-2 v1.4 erratum 2: resume the SAME run from the first unfilled slot
# until 42 unique group digests or an original cap (400 slots, 24 h from the
# first start). Generation only: the integrity gate and the sealed audit run
# afterwards through run_v14_erratum2_audit.sh. Detached, single writer.
set -u
cd "$(dirname "$0")/.." || exit 1
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 ARC_META_BUDGET_S=8
PY=.venv_arc2026/bin/python
LOG=logs/v14_erratum2_chain.log
echo "erratum-2 generation start $(date -u +%FT%TZ) pid $$" >> "$LOG"
nice -n 19 "$PY" scripts/generate_v14_twins.py full >> logs/v14_erratum2_generation.log 2>&1
rc=$?
echo "generator exit $rc $(date -u +%FT%TZ)" >> "$LOG"
[ "$rc" -eq 0 ] && touch logs/V14_ERRATUM2_GENERATION_DONE
exit "$rc"
