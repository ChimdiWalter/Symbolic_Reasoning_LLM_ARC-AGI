#!/bin/bash
#SBATCH --job-name=v2_xdomain
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/cross_domain/slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/cross_domain/slurm_%j.err

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Full Novel Pipeline v2: Cross-Domain Evaluation ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"
echo ""

PYTHONPATH=src python3.11 scripts/run_full_novel_v2_cross_domain.py

echo ""
echo "=== Finished: $(date -Iseconds), exit=0 ==="
