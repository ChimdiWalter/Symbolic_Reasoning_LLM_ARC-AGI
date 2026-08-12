#!/bin/bash
#SBATCH --job-name=ag_arc_triage
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/adaptergenesis_arc1000_rejected_triage_2026_06_20/slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/adaptergenesis_arc1000_rejected_triage_2026_06_20/slurm_%j.err

echo "=== AdapterGenesis ARC-1000 Rejected-Task Triage ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date --iso-8601=seconds)"
echo ""

cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

PYTHONPATH=src python3.11 -u scripts/run_adaptergenesis_rejected_task_triage.py

echo ""
echo "=== Finished: $(date --iso-8601=seconds), exit=$? ==="
