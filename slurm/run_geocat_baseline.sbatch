#!/bin/bash
#SBATCH --job-name=geocat-baseline
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/slurm_logs/%x-%j.err
#SBATCH --partition=requeue
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd "${REPO_ROOT}"

echo "job_id=${SLURM_JOB_ID:-none}"
echo "hostname=$(hostname)"
echo "start_time=$(date -Iseconds)"

python3.11 -m geocat_arc.experiments.run_baseline

echo "end_time=$(date -Iseconds)"
echo "GeoCat baseline complete. Results in geocat_arc/artifacts/geocat_arc/"
