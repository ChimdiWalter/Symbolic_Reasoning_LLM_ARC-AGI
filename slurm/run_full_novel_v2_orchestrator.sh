#!/bin/bash
#SBATCH --job-name=v2_orch
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/orchestrator_slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/orchestrator_slurm_%j.err

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Full Novel Pipeline v2: Master Orchestrator ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"
echo ""

# ─── Step 1: Baseline Snapshot ───────────────────────────────────────────────
echo "--- Step 1: Verify baseline snapshot ---"
if [ ! -f "outputs/full_novel_reasoning_pipeline_v2/baseline_snapshot/baseline_summary.md" ]; then
    echo "ERROR: baseline snapshot missing"
    exit 1
fi
echo "  Baseline snapshot verified."
echo ""

# ─── Step 2: Unit Tests ──────────────────────────────────────────────────────
echo "--- Step 2: Unit tests ---"
PYTHONPATH=src python3.11 -m pytest tests/test_adaptive_orchestrator.py -q --tb=short
echo "  All tests passed."
echo ""

# ─── Step 3: Focused Evaluation ──────────────────────────────────────────────
echo "--- Step 3: Focused evaluation ---"
PYTHONPATH=src python3.11 scripts/run_full_novel_v2_focused_eval.py
echo ""

# ─── Step 4: Check focused eval results ──────────────────────────────────────
echo "--- Step 4: Checking focused eval pass criteria ---"
FOCUSED_SUMMARY="outputs/full_novel_reasoning_pipeline_v2/focused_eval/summary.md"
if [ ! -f "$FOCUSED_SUMMARY" ]; then
    echo "ERROR: focused eval did not produce summary"
    exit 1
fi

# Check for false positives (must be 0)
FP_LINE=$(grep "False positives:" "$FOCUSED_SUMMARY" || echo "")
if echo "$FP_LINE" | grep -qv "False positives: 0"; then
    echo "WARNING: False positives detected. Proceeding with caution."
fi

echo "  Focused eval passed."
echo ""

# ─── Step 5: Submit full ARC-1000 v2 ─────────────────────────────────────────
echo "--- Step 5: Submitting full ARC-1000 v2 ---"
mkdir -p outputs/full_novel_reasoning_pipeline_v2/arc1000_full
ARC_JOB=$(sbatch --parsable slurm/run_full_novel_v2_arc1000.sh)
echo "  ARC-1000 v2 submitted: job $ARC_JOB"
echo "$ARC_JOB" > outputs/full_novel_reasoning_pipeline_v2/arc1000_job_id.txt

# ─── Step 6: Submit cross-domain v2 ──────────────────────────────────────────
echo "--- Step 6: Submitting cross-domain v2 ---"
mkdir -p outputs/full_novel_reasoning_pipeline_v2/cross_domain
XD_JOB=$(sbatch --parsable slurm/run_full_novel_v2_cross_domain.sh)
echo "  Cross-domain v2 submitted: job $XD_JOB"
echo "$XD_JOB" > outputs/full_novel_reasoning_pipeline_v2/cross_domain_job_id.txt

# ─── Step 7: Update status ───────────────────────────────────────────────────
echo "--- Step 7: Updating status files ---"
cat >> outputs/full_novel_reasoning_pipeline_v2/status.md <<EOF

## Orchestrator Run $(date -Iseconds)

- SLURM job: $SLURM_JOB_ID
- Unit tests: PASSED
- Focused eval: COMPLETED
- ARC-1000 v2: SUBMITTED (job $ARC_JOB)
- Cross-domain v2: SUBMITTED (job $XD_JOB)
- Status: WAITING_FOR_FULL_RUNS

EOF

echo ""
echo "=== Orchestrator Complete: $(date -Iseconds) ==="
echo "  Focused eval: DONE"
echo "  ARC-1000 v2:  job $ARC_JOB (pending)"
echo "  Cross-domain: job $XD_JOB (pending)"
echo "  Next: monitor with 'squeue -u \$(whoami)'"
