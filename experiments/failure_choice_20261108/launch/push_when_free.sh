#!/bin/sh
# Push one measurement kernel once, when Kaggle has a free batch CPU session, then poll it.
#   setsid nohup sh launch/push_when_free.sh NAME < /dev/null > /dev/null 2>&1 &
# Pushes only while the kernel does not exist on Kaggle and only retries after Kaggle's explicit refusal
# "Maximum batch CPU session count"; any other push output stops the script, so a kernel is never pushed twice.
cd /path/to/repository/experiments/failure_choice_20261108
KG=$HOME/.venvs/kaggle-cli/bin/kaggle
N=$1
ID=chimdiwalter/cora-failure-choice-$(echo $N | tr 'A-Z_' 'a-z-')
L=runs/kaggle/push_$N.log
mkdir -p runs/status
printf 'stage pushing\nstart %s\npid %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" > runs/status/push_$N.status
echo "- $(date -u +%Y-%m-%dT%H:%M:%SZ) push-when-free started for kernel $N (pid $$)" >> PROGRESS.md
while :; do
  S=$(timeout 120 $KG kernels status $ID 2>&1 | grep -v outdated | tr -d '\n')
  case "$S" in
    *"has status"*) echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) exists on Kaggle, not pushed again: $S" >> $L; break;;
    *"Not Found"*) ;;
    *) echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) status unclear, retried later: $S" >> $L; sleep 60; continue;;
  esac
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
