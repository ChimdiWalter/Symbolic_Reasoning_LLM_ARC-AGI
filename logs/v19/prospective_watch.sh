#!/usr/bin/env bash
# v1.9 prospective test watcher (detached, single instance).
# - If the coordinator is gone with the start record present, neither report
#   nor marker present, and no recorded coordinator/worker pid alive, resume
#   ONCE with --resume (protocol section 16; a flag makes it happen at most once).
# - When the marker exists, run the independent terminal verifier once,
#   save its output, remove this watcher's @reboot hook and stop.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R" || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI"
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
W=logs/v19/prospective_watch.log
exec 9>logs/v19/prospective_watch.lock
if ! flock -n 9; then echo "$(date -u +%FT%TZ) another watcher holds the lock; exiting" >> "$W"; exit 0; fi
echo "$(date -u +%FT%TZ) watcher started pid $$ boot $(cat /proc/sys/kernel/random/boot_id)" >> "$W"
coordinator_pid() {
    ps -eo pid=,args= | awk '$2 ~ /bin\/python$/ && $3 == "scripts/v19_prospective.py" && $4 != "--worker" {print $1; exit}'
}
recorded_alive() {
    [ -e logs/v19/prospective_workers.json ] || return 1
    for p in $(python3 -c "import json;d=json.load(open('logs/v19/prospective_workers.json'));print(' '.join(str(x) for x in [d.get('coordinator')]+d.get('workers',[]) if x))"); do
        kill -0 "$p" 2>/dev/null && return 0
    done
    return 1
}
remove_hook() {
    crontab -l 2>/dev/null | grep -v "logs/v19/prospective_watch.sh" | crontab - 2>/dev/null
    echo "$(date -u +%FT%TZ) @reboot hook removed" >> "$W"
}
while true; do
    if [ -e logs/V19_PROSPECTIVE_DONE ]; then
        if [ ! -e logs/v19/verify_prospective.json ]; then
            echo "$(date -u +%FT%TZ) marker present ($(cat logs/V19_PROSPECTIVE_DONE)): running the verifier" >> "$W"
            .venv_arc2026/bin/python logs/v19/verify_prospective.py > logs/v19/verify_prospective.json 2> logs/v19/verify_prospective.err
            echo "$(date -u +%FT%TZ) verifier exit $?" >> "$W"
        fi
        touch logs/v19/PROSPECTIVE_WATCH_DONE
        remove_hook
        exit 0
    fi
    if [ -z "$(coordinator_pid)" ]; then
        sleep 15
        [ -e logs/V19_PROSPECTIVE_DONE ] && continue
        [ -n "$(coordinator_pid)" ] && continue
        if recorded_alive; then
            echo "$(date -u +%FT%TZ) coordinator gone but a recorded worker is alive; waiting" >> "$W"
            sleep 60; continue
        fi
        if [ -e logs/v19/prospective_start.json ] && [ ! -e outputs/tti/v19_prospective_report.json ] \
                && [ ! -e logs/v19/prospective_resumed_once ]; then
            echo "$(date -u +%FT%TZ) coordinator gone without report or marker: resuming ONCE with --resume" >> "$W"
            date -u +%FT%TZ > logs/v19/prospective_resumed_once
            setsid nohup .venv_arc2026/bin/python scripts/v19_prospective.py --resume \
                >> logs/v19/prospective.log 2>&1 < /dev/null &
            sleep 60
            echo "$(date -u +%FT%TZ) resumed coordinator pid $(coordinator_pid)" >> "$W"
        else
            echo "$(date -u +%FT%TZ) coordinator gone; resume not allowed (already resumed, no start record, or report present); stopping" >> "$W"
            touch logs/v19/PROSPECTIVE_WATCH_STOPPED
            remove_hook
            exit 0
        fi
    fi
    sleep 30
done
