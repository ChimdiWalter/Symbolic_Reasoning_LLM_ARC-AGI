#!/usr/bin/env bash
# v1.9 prospective test watcher, v2 (detached, single instance).
# User instruction 2026-10-07: run even when interrupted and detached.
# - Never touches a running coordinator (no restart because progress is slow).
# - If the coordinator is gone with the start record present, report and
#   marker absent, and no recorded coordinator/worker process alive (alive =
#   the pid exists AND runs scripts/v19_prospective.py, so a reused pid does
#   not count), launch --resume. At most 3 resumes in all, counted from the
#   frozen script's own log logs/v19/prospective_resumes.jsonl; a refused or
#   failed attempt is counted apart (logs/v19/prospective_resume_attempts),
#   and after 5 such attempts the watcher stops and flags it.
# - When the marker exists, run the independent terminal verifier once, save
#   its output, remove this watcher's @reboot hook and stop. No git operation.
R=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
TTI=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
cd "$R" || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TTI"
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
W=logs/v19/prospective_watch.log
MAX_RESUMES=3
MAX_FAILED_ATTEMPTS=5
exec 9>logs/v19/prospective_watch.lock
if ! flock -n 9; then echo "$(date -u +%FT%TZ) another watcher holds the lock; exiting" >> "$W"; exit 0; fi
echo "$(date -u +%FT%TZ) watcher v2 started pid $$ boot $(cat /proc/sys/kernel/random/boot_id)" >> "$W"
coordinator_pid() {
    ps -eo pid=,args= | awk '$2 ~ /bin\/python$/ && $3 == "scripts/v19_prospective.py" && $4 != "--worker" {print $1; exit}'
}
is_run_process() {
    [ -n "$1" ] && [ -r "/proc/$1/cmdline" ] && tr '\0' ' ' < "/proc/$1/cmdline" | grep -q "scripts/v19_prospective.py"
}
recorded_alive() {
    [ -e logs/v19/prospective_workers.json ] || return 1
    for p in $(python3 -c "import json;d=json.load(open('logs/v19/prospective_workers.json'));print(' '.join(str(x) for x in [d.get('coordinator')]+d.get('workers',[]) if x))" 2>/dev/null); do
        is_run_process "$p" && return 0
    done
    return 1
}
resumes_done() { if [ -e logs/v19/prospective_resumes.jsonl ]; then grep -c . logs/v19/prospective_resumes.jsonl; else echo 0; fi; }
failed_attempts() { cat logs/v19/prospective_resume_attempts 2>/dev/null || echo 0; }
remove_hook() {
    crontab -l 2>/dev/null | grep -v "logs/v19/prospective_watch.sh" | crontab - 2>/dev/null
    echo "$(date -u +%FT%TZ) @reboot hook removed" >> "$W"
}
stop_flag() {
    echo "$(date -u +%FT%TZ) STOPPING: $1" >> "$W"
    touch logs/v19/PROSPECTIVE_WATCH_STOPPED
    remove_hook
    exit 0
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
            echo "$(date -u +%FT%TZ) coordinator gone but a recorded run process is alive; waiting" >> "$W"
            sleep 60; continue
        fi
        if [ ! -e logs/v19/prospective_start.json ]; then stop_flag "no start record"; fi
        if [ -e outputs/tti/v19_prospective_report.json ]; then stop_flag "report present without marker (manual check needed)"; fi
        n=$(resumes_done); f=$(failed_attempts)
        [ "$n" -ge "$MAX_RESUMES" ] && stop_flag "resume budget used ($n resumes)"
        [ "$f" -ge "$MAX_FAILED_ATTEMPTS" ] && stop_flag "$f refused or failed resume attempts"
        echo "$(date -u +%FT%TZ) coordinator gone without report or marker (resumes so far $n): launching --resume" >> "$W"
        setsid nohup .venv_arc2026/bin/python scripts/v19_prospective.py --resume \
            >> logs/v19/prospective.log 2>&1 < /dev/null &
        sleep 90
        if [ -n "$(coordinator_pid)" ] || [ "$(resumes_done)" -gt "$n" ] || [ -e logs/V19_PROSPECTIVE_DONE ]; then
            echo "$(date -u +%FT%TZ) resume started: coordinator pid $(coordinator_pid), resumes now $(resumes_done)" >> "$W"
        else
            echo $((f + 1)) > logs/v19/prospective_resume_attempts
            echo "$(date -u +%FT%TZ) resume attempt refused or failed (attempt $((f + 1)); see logs/v19/prospective.log)" >> "$W"
            sleep 120
        fi
    fi
    sleep 30
done
