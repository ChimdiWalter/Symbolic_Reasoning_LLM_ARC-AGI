#!/bin/bash
#SBATCH --job-name=world-model
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --partition=requeue
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --gres=gpu:A100:1

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
PHASE="${1:-all}"
OUTPUT_DIR="${2:-outputs/neural/world_model_gpu}"
SLOT_CKPT="${SLOT_CHECKPOINT:-}"

mkdir -p "${REPO_ROOT}/outputs/slurm_logs"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
echo "phase=${PHASE}"
echo "output_dir=${OUTPUT_DIR}"
python3.11 - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("device_count", torch.cuda.device_count())
PY
nvidia-smi || true

EXTRA_ARGS=""
if [ -n "${SLOT_CKPT}" ]; then
    EXTRA_ARGS="--slot-checkpoint ${SLOT_CKPT}"
fi

python3.11 scripts/train_world_model.py \
    --config configs/world_model_gpu.json \
    --arc-root data/arc \
    --output-dir "${OUTPUT_DIR}" \
    --phase "${PHASE}" \
    ${EXTRA_ARGS}
