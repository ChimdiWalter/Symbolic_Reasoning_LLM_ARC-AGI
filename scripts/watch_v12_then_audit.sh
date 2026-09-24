#!/usr/bin/env bash
# Wait for the frozen v1.2 corpus generation to finish, then run the audit.
# Polls only; never restarts the generator and never changes the law.
set -u
W=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
PY=$W/.venv_arc2026/bin/python
CORPUS=$W/outputs/tti/v12_corpus
LOG=$W/logs/v12_watch.log
export PYTHONDONTWRITEBYTECODE=1

count() { ls "$CORPUS" 2>/dev/null | grep -c '^slot.*\.json$'; }

echo "$(date -u +%FT%TZ) watcher started, waiting for 450 slots" >> "$LOG"
while true; do
  n=$(count)
  if [ "$n" -ge 450 ]; then
    echo "$(date -u +%FT%TZ) complete at $n slots, auditing" >> "$LOG"
    break
  fi
  if ! pgrep -f "venv_arc2026/bin/python scripts/generate_v12_corpus.py" > /dev/null 2>&1; then
    echo "$(date -u +%FT%TZ) GENERATOR GONE at $n/450 slots, auditing partial" >> "$LOG"
    break
  fi
  sleep 60
done

cd "$W" || exit 1
nice -n 19 "$PY" scripts/audit_v12_corpus.py >> "$LOG" 2>&1
echo "$(date -u +%FT%TZ) audit finished, verdict below" >> "$LOG"
"$PY" - <<'PYEOF' >> "$LOG" 2>&1
import json
d = json.load(open("/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026/outputs/tti/v12_corpus_audit.json"))
print("VERDICT", d["verdict"], "complete", d["complete"])
for c in d["criteria"]:
    print(("PASS " if c["pass"] else "FAIL "), c["criterion"], "=", c["measured"])
PYEOF
touch "$W/logs/V12_AUDIT_DONE"
