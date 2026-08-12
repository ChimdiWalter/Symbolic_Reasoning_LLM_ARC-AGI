#!/bin/bash
#SBATCH --job-name=world-model-v3
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --partition=requeue
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --gres=gpu:A100:1

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
nvidia-smi || true

# Reuse v2 slot pretrain checkpoint to skip Phase 1
python3.11 scripts/train_world_model.py \
    --config configs/world_model_v3_gpu.json \
    --arc-root data/arc \
    --output-dir outputs/neural/world_model_gpu_v3 \
    --phase all \
    --slot-checkpoint outputs/neural/world_model_gpu_v2/slot_pretrain/slot_model.pt
