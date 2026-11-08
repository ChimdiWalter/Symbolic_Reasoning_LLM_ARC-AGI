#!/bin/sh
# Push one NEW kernel once, when Kaggle has a free batch CPU session, then poll it (revision 2).
#   setsid nohup sh launch/push_when_free.sh NAME < /dev/null > /dev/null 2>&1 &
# The kernel must not exist yet. The push is retried only after Kaggle's explicit refusal "Maximum batch CPU session
# count"; a success ends the loop, and any other output (or a timeout) stops the script without retrying, so the
# kernel is never pushed twice. (Kaggle answers a status query for a kernel that does not exist with "Cannot access
# kernel", which revision 1's script read as unclear; this one does not query the status.)
cd /path/to/repository/experiments/failure_choice_r2_20261108
KG=$HOME/.venvs/kaggle-cli/bin/kaggle
N=$1
L=runs/kaggle/push_$N.log
mkdir -p runs/status
printf 'stage pushing\nstart %s\npid %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" > runs/status/push_$N.status
echo "- $(date -u +%Y-%m-%dT%H:%M:%SZ) push-when-free started for kernel $N (pid $$)" >> PROGRESS.md
while :; do
  OUT=$(timeout 300 $KG kernels push -p runs/kaggle/$N 2>&1 | grep -v outdated | tr -d '\n')
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) push: $OUT" >> $L
  case "$OUT" in
    *"successfully pushed"*) break;;
    *"Maximum batch CPU session count"*) sleep 120;;
    *) echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) STOPPED: unexpected push output; nothing retried" >> $L; exit 1;;
  esac
done
printf 'stage pushed\npid %s\n' "$$" > runs/status/push_$N.status
sleep 30
sh launch/poll_kaggle.sh $N
