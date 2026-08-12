#!/bin/bash
#SBATCH --job-name=perception-heads
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --gres=gpu:A100:1
#SBATCH --partition=requeue

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
JEPA_CHECKPOINT="${1:-outputs/neural/grid_jepa_arc_gpu/checkpoint.pt}"
ARC_ROOT="${2:-data/arc}"
OUTPUT_DIR="${3:-outputs/neural/perception_heads}"
EPOCHS="${4:-100}"

mkdir -p "${REPO_ROOT}/outputs/slurm_logs"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
echo "jepa_checkpoint=${JEPA_CHECKPOINT}"
nvidia-smi || true

python3.11 scripts/train_perception_heads.py \
    --jepa-checkpoint "${JEPA_CHECKPOINT}" \
    --arc-root "${ARC_ROOT}" \
    --output-dir "${OUTPUT_DIR}" \
    --epochs "${EPOCHS}" \
    --batch-size 32 \
    --lr 1e-3 \
    --seed 42
