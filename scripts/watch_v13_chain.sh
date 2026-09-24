#!/usr/bin/env bash
# Wait for the running v1.3 Phase A to finish, then run the 40-group pilot.
# Polls only. Never starts a second writer, never changes the frozen law.
set -u
W=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
PY=$W/.venv_arc2026/bin/python
LOG=$W/logs/v13_chain.log
export PYTHONDONTWRITEBYTECODE=1

alive() { pgrep -f "venv_arc2026/bin/python -u scripts/generate_v13_contrastive_corpus.py" \
          | grep -qv "^$$\$"; }

echo "$(date -u +%FT%TZ) chain watcher started" >> "$LOG"
while pgrep -f "venv_arc2026/bin/python -u scripts/generate_v13_contrastive_corpus.py" > /dev/null 2>&1; do
  sleep 60
done
echo "$(date -u +%FT%TZ) phase A finished" >> "$LOG"

if [ ! -f "$W/outputs/tti/v13_calibration/calibration.json" ]; then
  echo "$(date -u +%FT%TZ) no calibration artifact; stopping" >> "$LOG"
  touch "$W/logs/V13_CHAIN_STOPPED"; exit 1
fi

cd "$W" || exit 1
echo "$(date -u +%FT%TZ) launching the 40-group pilot" >> "$LOG"
nice -n 19 "$PY" -u scripts/generate_v13_contrastive_corpus.py pilot >> "$LOG" 2>&1
echo "$(date -u +%FT%TZ) pilot finished" >> "$LOG"
touch "$W/logs/V13_PILOT_DONE"
