#!/usr/bin/env bash
# Waits for the GPU to have >8GB free, then launches TRM training
# detached with checkpointing.  Armed via setsid nohup.
cd "$(dirname "$0")/.."
source ~/.venvs/lesegenv/bin/activate
while true; do
  FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  if [ "${FREE:-0}" -gt 8000 ]; then
    echo "[$(date -u +%FT%TZ)] GPU free (${FREE}MiB) — launching TRM training" >> logs/trm_gpu_watch.log
    python trm/train.py 50 96 cuda >> logs/trm_train.log 2>&1
    echo "[$(date -u +%FT%TZ)] TRM training exited rc=$?" >> logs/trm_gpu_watch.log
    break
  fi
  sleep 600
done
