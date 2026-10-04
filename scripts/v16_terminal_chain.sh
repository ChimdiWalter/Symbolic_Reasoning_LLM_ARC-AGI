#!/usr/bin/env bash
# Item-2 v1.6: after the frozen post-generation runner ends, run the terminal
# verifier once (DONE), or record the frozen blocker (BLOCKED). Waits on the
# runner's markers only; never signals any process; records no verdict.
# Idempotent: refuses if a terminal marker exists; one chain at a time (flock).
set -u
cd "$(dirname "$0")/.." || exit 1
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
for v in $(compgen -e | grep '^ARC_'); do unset "$v"; done
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
D=logs/v16_terminal
mkdir -p "$D"
S=$D/STATUS.txt
say() { echo "$(date -u +%FT%TZ) $*" >> "$S"; }
exec 9> "$D/.chain.lock"
flock -n 9 || { echo "another terminal chain holds the lock" >&2; exit 1; }
for m in logs/V16_TERMINAL_VERIFIED logs/V16_TERMINAL_DISCREPANCY logs/V16_TERMINAL_BLOCKED_SEEN; do
  [ -e "$m" ] && { say "refusing: $m exists"; exit 0; }
done
say "terminal chain pid $$ waiting for logs/V16_POSTGEN_DONE or logs/V16_POSTGEN_BLOCKED"
while [ ! -e logs/V16_POSTGEN_DONE ] && [ ! -e logs/V16_POSTGEN_BLOCKED ]; do sleep 300; done
if [ -e logs/V16_POSTGEN_BLOCKED ]; then
  say "post-generation BLOCKED: $(cat logs/V16_POSTGEN_BLOCKED); the verifier is not run"
  cp logs/V16_POSTGEN_BLOCKED logs/V16_TERMINAL_BLOCKED_SEEN
  exit 0
fi
say "post-generation DONE; running the terminal verifier"
PYTHONPATH="$TTI" nice -n 19 .venv_arc2026/bin/python scripts/v16_terminal_verify.py > "$D/verify.log" 2>&1
rc=$?
say "verifier exit $rc: $(tail -1 "$D/verify.log")"
(cd outputs/tti && sha256sum v16_terminal_verification.json v16_result_table.csv v16_result_figure_data.json 2>/dev/null) >> "$S"
say "terminal chain done; read logs/V16_TERMINAL_VERIFIED or logs/V16_TERMINAL_DISCREPANCY, then record the verdict in a session"
