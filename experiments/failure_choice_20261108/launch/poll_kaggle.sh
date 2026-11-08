#!/bin/sh
# Poll private measurement kernels until each has finished; download each one's output when it has (transient CLI
# errors are retried; nothing is pushed or changed on Kaggle).   setsid nohup sh launch/poll_kaggle.sh NAME... &
# Writes runs/kaggle/poll.log, runs/kaggle/STATUS_<NAME>.txt, runs/status/poll_<first NAME>.status and the output
# into runs/kaggle/download/<NAME>/ (untrusted until its digest is checked). Appends start and end lines to PROGRESS.md.
cd /path/to/repository/experiments/failure_choice_20261108
KG=$HOME/.venvs/kaggle-cli/bin/kaggle
R=runs/kaggle
mkdir -p $R runs/status
ST=runs/status/poll_$1.status
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'stage polling\nstart %s\npid %s\nkernels %s\n' "$START" "$$" "$*" > $ST
echo "- $START poller started (pid $$) for kernels $*" >> PROGRESS.md
PENDING="$*"
while [ -n "$PENDING" ]; do
  NEXT=""
  for K in $PENDING; do
    ID=chimdiwalter/cora-failure-choice-$(echo $K | tr 'A-Z_' 'a-z-')
    S=$(timeout 120 $KG kernels status $ID 2>&1 | grep -v outdated | tr -d '\n')
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $K $S" >> $R/poll.log
    case "$S" in
      *COMPLETE*|*ERROR*|*CANCEL*)
        echo "$S" > $R/STATUS_$K.txt
        mkdir -p $R/download/$K
        for i in 1 2 3 4 5; do
          timeout 1800 $KG kernels output $ID -p $R/download/$K > $R/download_$K.log 2>&1 && break
          sleep 120
        done
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) DOWNLOADED $K" >> $R/poll.log
        echo "- $(date -u +%Y-%m-%dT%H:%M:%SZ) kernel $K finished ($S), output downloaded to runs/kaggle/download/$K/" >> PROGRESS.md;;
      *) NEXT="$NEXT $K";;
    esac
  done
  PENDING=$(echo $NEXT)
  [ -n "$PENDING" ] && sleep 120
done
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'stage done\nstart %s\nend %s\npid %s\nkernels %s\n' "$START" "$END" "$$" "$*" > $ST
echo "$END POLL DONE $*" >> $R/poll.log
