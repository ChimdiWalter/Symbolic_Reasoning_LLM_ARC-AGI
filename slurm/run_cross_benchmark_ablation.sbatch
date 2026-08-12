#!/bin/bash
#SBATCH --job-name=xbench-ablation
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --partition=requeue
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:A100:1

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

WM_CKPT="${WM_CKPT:-outputs/neural/world_model_gpu_v3/world_model/world_model_best.pt}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/cross_benchmark_ablation_full}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
echo "wm_checkpoint=${WM_CKPT}"
nvidia-smi || true

python3.11 scripts/run_cross_benchmark_ablation.py \
    --arc-root data/arc \
    --conceptarc-root data/conceptarc \
    --output-dir "${OUTPUT_DIR}" \
    --world-model "${WM_CKPT}" \
    --no-rerank \
    --device cuda
