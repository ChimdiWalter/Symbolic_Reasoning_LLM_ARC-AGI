#!/bin/bash
#SBATCH --job-name=grid-jepa
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --gres=gpu:1

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
CONFIG="${1:-configs/grid_jepa_arc_pretrain_gpu_full.json}"
OUTPUT_DIR="${2:-outputs/neural}"
RESUME_FLAG="${RESUME_FLAG:-}"

mkdir -p "${REPO_ROOT}/outputs/slurm_logs"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
echo "config=${CONFIG}"
echo "output_dir=${OUTPUT_DIR}"
python3.11 - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("device_count", torch.cuda.device_count())
PY
nvidia-smi || true

python3.11 scripts/train_grid_jepa.py --config "${CONFIG}" --output-dir "${OUTPUT_DIR}" ${RESUME_FLAG}
