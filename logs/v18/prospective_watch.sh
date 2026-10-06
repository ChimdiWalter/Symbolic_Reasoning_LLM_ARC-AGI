#!/usr/bin/env bash
# Item-2 v1.8 prospective test watcher (detached).
# - If the writer is gone with the start record present and neither report
#   nor marker exists, relaunch it ONCE with --resume (protocol section 14);
#   a flag file makes the resume happen at most once, ever.
# - When the marker exists, run the independent terminal verifier once and
#   save its output, then remove this watcher's @reboot hook and stop.
# - A lock file keeps a single watcher; the writer is matched exactly by its
#   arguments, so no second writer is ever started.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R" || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI"
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
W=logs/v18/prospective_watch.log
exec 9>logs/v18/prospective_watch.lock
if ! flock -n 9; then
    echo "$(date -u +%FT%TZ) another watcher holds the lock; exiting" >> "$W"
    exit 0
fi
echo "$(date -u +%FT%TZ) watcher started pid $$ boot $(cat /proc/sys/kernel/random/boot_id)" >> "$W"

writer_pid() {
    ps -eo pid=,args= | awk '$2 ~ /bin\/python$/ && $3 == "scripts/v18_prospective.py" {print $1; exit}'
}

remove_hook() {
    crontab -l 2>/dev/null | grep -v "prospective_watch.sh" | crontab - 2>/dev/null
    echo "$(date -u +%FT%TZ) @reboot hook removed" >> "$W"
}

while true; do
    if [ -e logs/V18_PROSPECTIVE_DONE ]; then
        if [ ! -e logs/v18/verify_prospective.json ]; then
            echo "$(date -u +%FT%TZ) marker present ($(cat logs/V18_PROSPECTIVE_DONE)): running the verifier" >> "$W"
            .venv_arc2026/bin/python logs/v18/verify_prospective.py > logs/v18/verify_prospective.json 2> logs/v18/verify_prospective.err
            echo "$(date -u +%FT%TZ) verifier exit $?" >> "$W"
        fi
        touch logs/v18/PROSPECTIVE_WATCH_DONE
        remove_hook
        exit 0
    fi
    if [ -z "$(writer_pid)" ]; then
        sleep 10
        [ -e logs/V18_PROSPECTIVE_DONE ] && continue
        [ -n "$(writer_pid)" ] && continue
        if [ -e logs/v18/prospective_start.json ] && [ ! -e outputs/tti/v18_prospective_report.json ] \
                && [ ! -e logs/v18/prospective_resumed_once ]; then
            echo "$(date -u +%FT%TZ) writer gone without report or marker: resuming ONCE with --resume" >> "$W"
            date -u +%FT%TZ > logs/v18/prospective_resumed_once
            setsid nohup .venv_arc2026/bin/python scripts/v18_prospective.py --resume \
                >> logs/v18/prospective.log 2>&1 < /dev/null &
            sleep 60
            echo "$(date -u +%FT%TZ) resumed writer pid $(writer_pid)" >> "$W"
        else
            echo "$(date -u +%FT%TZ) writer gone; resume not allowed (already resumed, or no start record, or report present); stopping" >> "$W"
            touch logs/v18/PROSPECTIVE_WATCH_STOPPED
            remove_hook
            exit 0
        fi
    fi
    sleep 30
done
