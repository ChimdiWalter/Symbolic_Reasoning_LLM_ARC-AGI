#!/bin/bash
#SBATCH --job-name=fd_ablation
#SBATCH --partition=requeue
#SBATCH --requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/failure_driven_adaptergenesis_v2_2026_06_21/slurm_ablation_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/failure_driven_adaptergenesis_v2_2026_06_21/slurm_ablation_%j.err

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

echo "=== Failure-Driven Ablation ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Started: $(date --iso-8601=seconds)"

PYTHONPATH=src python3.11 scripts/run_failure_driven_ablation.py --slurm 2>&1

echo "=== Finished: $(date --iso-8601=seconds), exit=$? ==="
