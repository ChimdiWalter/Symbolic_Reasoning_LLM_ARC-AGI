#!/bin/bash
#SBATCH --job-name=arc_module_ablation
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/arc1000_module_causality_audit_2026_06_19/slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/arc1000_module_causality_audit_2026_06_19/slurm_%j.err

echo "=== Module Causality Ablation ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date --iso-8601=seconds)"
echo ""

cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

python3.11 scripts/run_arc1000_solved_task_module_ablation.py

echo ""
echo "=== Finished: $(date --iso-8601=seconds), exit=$? ==="
