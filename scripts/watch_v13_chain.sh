#!/usr/bin/env bash
# Wait for the running v1.3 Phase A to finish, then STOP.
#
# REPAIRED 2026-09-24. The previous version launched the 40-group pilot as
# soon as calibration.json existed. Existence is not provenance: the frozen
# protocol requires the calibration artifact to be COMMITTED before any
# Phase B group is generated. This watcher therefore only signals, and the
# pilot is launched by hand after the calibration commit.
#
# It changes no Phase-A data, no calibration formula, no descriptor, no
# feature set, no group law, no threshold, no seed, no epsilon_demo, no q
# formula and no gate.
set -u
W=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
LOG=$W/logs/v13_chain.log
PATTERN="venv_arc2026/bin/python -u scripts/generate_v13_contrastive_corpus.py"

echo "$(date -u +%FT%TZ) repaired watcher started; it will NOT launch the pilot" >> "$LOG"
while pgrep -f "$PATTERN" > /dev/null 2>&1; do
  sleep 60
done
echo "$(date -u +%FT%TZ) phase A generator exited" >> "$LOG"
n=$(ls "$W/outputs/tti/v13_calibration" 2>/dev/null | grep -c '^ep')
echo "$(date -u +%FT%TZ) admitted calibration episodes: $n" >> "$LOG"
if [ -f "$W/outputs/tti/v13_calibration/calibration.json" ]; then
  echo "$(date -u +%FT%TZ) calibration artifact written; AWAITING COMMIT before any pilot" >> "$LOG"
  touch "$W/logs/V13_CALIBRATION_READY"
else
  echo "$(date -u +%FT%TZ) no calibration artifact" >> "$LOG"
  touch "$W/logs/V13_PHASEA_INCOMPLETE"
fi
