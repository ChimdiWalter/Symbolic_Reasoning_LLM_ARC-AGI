#!/usr/bin/env bash
# v1.9 development pipelines watcher (detached, single instance).
# - Relaunches a pipeline that is gone before its marker (at most 3 times
#   each; the run scripts drop unfinished claims and keep finished rows).
# - When every marker exists: writes logs/v19/V19_DEV_ALL_DONE, removes its
#   own @reboot hook and stops. Performs no git operation.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
cd "$R" || exit 1
W=logs/v19/v19_watch.log
exec 9>logs/v19/v19_watch.lock
if ! flock -n 9; then echo "$(date -u +%FT%TZ) another watcher holds the lock; exiting" >> "$W"; exit 0; fi
echo "$(date -u +%FT%TZ) watcher started pid $$ boot $(cat /proc/sys/kernel/random/boot_id)" >> "$W"
PIPES="run_repair_dev.sh:REPAIR_DEV_DONE run_falseaccept_reduced_dev.sh:FALSEACCEPT_REDUCED_DEV_DONE"
remove_hook() {
    crontab -l 2>/dev/null | grep -v "logs/v19/v19_watch.sh" | crontab - 2>/dev/null
    echo "$(date -u +%FT%TZ) @reboot hook removed" >> "$W"
}
while true; do
    all=1
    for pm in $PIPES; do
        script=${pm%%:*}; marker=${pm##*:}
        [ -e "logs/v19/$marker" ] && continue
        all=0
        if ! ps -eo args | grep -q "^bash logs/v19/$script"; then
            sleep 15
            [ -e "logs/v19/$marker" ] && continue
            ps -eo args | grep -q "^bash logs/v19/$script" && continue
            n=$(cat "logs/v19/restarts_$script" 2>/dev/null || echo 0)
            if [ "$n" -ge 3 ]; then
                echo "$(date -u +%FT%TZ) $script gone, restart budget used ($n); not relaunching" >> "$W"
                touch "logs/v19/GAVE_UP_$script"
                continue
            fi
            echo $((n + 1)) > "logs/v19/restarts_$script"
            echo "$(date -u +%FT%TZ) $script gone without $marker: relaunch $((n + 1))" >> "$W"
            setsid nohup bash "logs/v19/$script" > /dev/null 2>&1 < /dev/null &
            sleep 30
        fi
    done
    if [ "$all" = 1 ]; then
        echo "$(date -u +%FT%TZ) every marker present" >> "$W"
        touch logs/v19/V19_DEV_ALL_DONE
        remove_hook
        exit 0
    fi
    if ls logs/v19/GAVE_UP_* >/dev/null 2>&1; then
        gone=1
        for pm in $PIPES; do
            script=${pm%%:*}; marker=${pm##*:}
            [ -e "logs/v19/$marker" ] || [ -e "logs/v19/GAVE_UP_$script" ] || gone=0
        done
        if [ "$gone" = 1 ]; then echo "$(date -u +%FT%TZ) stopping: a pipeline gave up" >> "$W"; remove_hook; exit 0; fi
    fi
    sleep 60
done
