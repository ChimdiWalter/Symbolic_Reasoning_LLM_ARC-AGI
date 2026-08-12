#!/bin/bash
#SBATCH --job-name=v2_focused
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/focused_eval/slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/focused_eval/slurm_%j.err

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Full Novel Pipeline v2: Focused Evaluation ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"
echo ""

# Step 1: Run unit tests
echo "--- Step 1: Unit Tests ---"
PYTHONPATH=src python3.11 -m pytest tests/test_adaptive_orchestrator.py tests/test_v2_preserves_v1_behavior.py -q --tb=short
echo "Tests passed."
echo ""

# Step 2: Run focused evaluation
echo "--- Step 2: Focused Evaluation ---"
PYTHONPATH=src python3.11 scripts/run_full_novel_v2_focused_eval.py

echo ""
echo "=== Finished: $(date -Iseconds), exit=0 ==="
