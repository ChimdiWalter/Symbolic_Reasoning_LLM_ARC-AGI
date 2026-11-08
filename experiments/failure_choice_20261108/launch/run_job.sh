#!/bin/sh
# Detached job runner of the failure-guided choice test (the author asks that long jobs run detached).
#   setsid nohup sh launch/run_job.sh NAME COMMAND [ARGS...] < /dev/null > /dev/null 2>&1 &
# Runs COMMAND from this folder in one of the project's two CPU slots (scripts/with_cpu_slot.sh, nice 19), with
# PYTHONHASHSEED=0 and PYTHONPATH=., logging to logs/NAME.log. Writes runs/status/NAME.status (stage, start, end,
# exit code, pid) and appends one line at the start and one at the end to PROGRESS.md (append only).
cd /path/to/repository/experiments/failure_choice_20261108
NAME=$1
shift
mkdir -p runs/status logs
ST=runs/status/$NAME.status
if [ -e "$ST" ] && grep -q "^stage running" "$ST"; then
  PID=$(sed -n 's/^pid //p' "$ST")
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) job $NAME already running (pid $PID): not started twice" >> PROGRESS.md
    exit 3
  fi
fi
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'stage running\nstart %s\npid %s\ncommand %s\n' "$START" "$$" "$*" > "$ST"
echo "- $START job $NAME started (pid $$, log logs/$NAME.log): $*" >> PROGRESS.md
PYTHONHASHSEED=0 PYTHONPATH=. sh ../../scripts/with_cpu_slot.sh "$@" > logs/$NAME.log 2>&1
RC=$?
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'stage done\nstart %s\nend %s\nexit %s\npid %s\ncommand %s\n' "$START" "$END" "$RC" "$$" "$*" > "$ST"
echo "- $END job $NAME ended with exit code $RC (started $START)" >> PROGRESS.md
