#!/bin/bash
#SBATCH --job-name=og_pilot
#SBATCH --partition=requeue
#SBATCH --requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/operator_genesis_v2_2026_06_22/slurm_pilot_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/operator_genesis_v2_2026_06_22/slurm_pilot_%j.err

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

echo "=== OperatorGenesis Pilot ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Started: $(date --iso-8601=seconds)"

PYTHONPATH=src python3.11 scripts/run_operator_genesis_pilot.py --slurm 2>&1

echo "=== Finished: $(date --iso-8601=seconds), exit=$? ==="
