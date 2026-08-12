#!/bin/bash
#SBATCH --partition=requeue
#SBATCH --job-name=v2_op_cov
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_operator_coverage_repair/slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_operator_coverage_repair/slurm_%j.err
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00

echo "=== Focused Eval After Operator Coverage Repair ==="
echo "Job ID:  ${SLURM_JOB_ID}"
echo "Started: $(date -Iseconds)"

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

mkdir -p outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_operator_coverage_repair

PYTHONUNBUFFERED=1 PYTHONPATH=src python3.11 scripts/run_full_novel_v2_focused_eval.py \
    --output-dir outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_operator_coverage_repair

echo "=== Finished: $(date -Iseconds), exit=$? ==="
