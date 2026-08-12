#!/bin/bash
#SBATCH --job-name=integrated-eval
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --partition=requeue
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:A100:1

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
WM_CHECKPOINT="${1:-outputs/neural/world_model_gpu_v3/world_model/world_model_best.pt}"

mkdir -p "${REPO_ROOT}/outputs/slurm_logs"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
echo "wm_checkpoint=${WM_CHECKPOINT}"
nvidia-smi || true

python3.11 scripts/run_integrated_evaluation.py \
    --arc-root data/arc \
    --output-dir outputs/integrated_eval \
    --world-model "${WM_CHECKPOINT}" \
    --device cuda
