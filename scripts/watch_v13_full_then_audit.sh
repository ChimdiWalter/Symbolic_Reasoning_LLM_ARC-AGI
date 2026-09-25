#!/usr/bin/env bash
# Wait for the 1,200-slot v1.3 full generation to finish, verify completion
# mechanically, then run the sealed auditor twice: once for the result and
# once for reproduction from the same stored corpus.
#
# It launches no generator, regenerates nothing, and changes no frozen law.
set -u
W=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
PY=$W/.venv_arc2026/bin/python
LOG=$W/logs/v13_audit_chain.log
COR=$W/outputs/tti/v13_contrastive_corpus
PATTERN="venv_arc2026/bin/python -u scripts/generate_v13_contrastive_corpus.py"
export PYTHONDONTWRITEBYTECODE=1

echo "$(date -u +%FT%TZ) audit chain watcher started" >> "$LOG"
while pgrep -f "$PATTERN" > /dev/null 2>&1; do sleep 120; done
n=$(ls "$COR" 2>/dev/null | grep -c '^full0')
echo "$(date -u +%FT%TZ) generator exited with $n full slot records" >> "$LOG"

if [ "$n" -lt 1200 ]; then
  echo "$(date -u +%FT%TZ) INCOMPLETE: $n of 1200. Not auditing." >> "$LOG"
  touch "$W/logs/V13_FULL_INCOMPLETE"
  exit 1
fi

cd "$W" || exit 1
echo "$(date -u +%FT%TZ) running the sealed auditor, pass 1" >> "$LOG"
nice -n 19 "$PY" -u scripts/audit_v13_contrastive_corpus.py >> "$LOG" 2>&1
cp "$W/outputs/tti/v13_contrastive_audit.json" \
   "$W/outputs/tti/v13_contrastive_audit_pass1.json" 2>/dev/null

echo "$(date -u +%FT%TZ) running the sealed auditor, pass 2 for reproduction" >> "$LOG"
nice -n 19 "$PY" -u scripts/audit_v13_contrastive_corpus.py >> "$LOG" 2>&1
cp "$W/outputs/tti/v13_contrastive_audit.json" \
   "$W/outputs/tti/v13_contrastive_audit_pass2.json" 2>/dev/null

if cmp -s "$W/outputs/tti/v13_contrastive_audit_pass1.json" \
          "$W/outputs/tti/v13_contrastive_audit_pass2.json"; then
  echo "$(date -u +%FT%TZ) reproduction: byte-identical" >> "$LOG"
else
  echo "$(date -u +%FT%TZ) reproduction: DIFFERS, inspect before reporting" >> "$LOG"
fi
touch "$W/logs/V13_AUDIT_DONE"
echo "$(date -u +%FT%TZ) audit chain complete" >> "$LOG"
