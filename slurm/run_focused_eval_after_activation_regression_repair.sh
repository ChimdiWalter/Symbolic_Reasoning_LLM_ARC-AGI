#!/bin/bash
#SBATCH --job-name=activation-regression-repair
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=18:00:00
#SBATCH --output=outputs/slurm_logs/activation-regression-repair-%j.out
#SBATCH --error=outputs/slurm_logs/activation-regression-repair-%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@300

resubmit() {
    echo "=== Received signal, resubmitting... ==="
    sbatch "$0"
    exit 0
}
trap resubmit USR1

echo "job_id=$SLURM_JOB_ID"
echo "hostname=$(hostname)"
echo "start_time=$(date -Iseconds)"

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

# Phase 1: run tests first
echo "=== Running regression guard tests ==="
PYTHONPATH=src python3.11 -m pytest \
    tests/test_activation_repair_no_f5aa3634_regression.py \
    tests/test_adaptive_orchestrator.py \
    tests/test_full_pipeline_activation.py \
    -q --tb=short || { echo "TESTS FAILED — aborting eval"; exit 1; }

# Phase 2: targeted 3-config eval
echo "=== Running focused eval (3 configs) ==="
PYTHONUNBUFFERED=1 PYTHONPATH=src python3.11 scripts/run_full_novel_v2_focused_eval.py \
    --output-dir outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_activation_regression_repair \
    --configs v2_full_gated_orchestrator,v2_with_frontier_operators,v2_core_only

# Phase 3: remaining 2 configs
echo "=== Running focused eval (remaining 2 configs) ==="
PYTHONUNBUFFERED=1 PYTHONPATH=src python3.11 scripts/run_full_novel_v2_focused_eval.py \
    --output-dir outputs/full_novel_reasoning_pipeline_v2/focused_eval_after_activation_regression_repair \
    --configs v2_with_property_expansion,v2_with_manifold_memory

echo "end_time=$(date -Iseconds)"
echo "=== DONE ==="
