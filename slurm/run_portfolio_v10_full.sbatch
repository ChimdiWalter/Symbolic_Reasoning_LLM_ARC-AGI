#!/bin/bash
#SBATCH --job-name=portfolio-v10
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --partition=requeue
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

OUTPUT_DIR="${OUTPUT_DIR:-outputs/portfolio_v10_full}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"

python3.11 scripts/run_portfolio_arc.py \
    --arc-root data/arc \
    --output-dir "${OUTPUT_DIR}" \
    --skip-dsl

echo "=== No-DSL complete ==="

python3.11 scripts/run_portfolio_arc.py \
    --arc-root data/arc \
    --output-dir "${OUTPUT_DIR}_with_dsl"

echo "=== With-DSL complete ==="

python3.11 scripts/run_cross_benchmark_ablation.py \
    --arc-root data/arc \
    --conceptarc-root data/conceptarc \
    --output-dir "${OUTPUT_DIR}_ablation" \
    --no-rerank

echo "=== Ablation complete ==="
