#!/bin/bash
#SBATCH --job-name=v2_arc1000
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=2-00:00:00
#SBATCH --output=outputs/full_novel_reasoning_pipeline_v2/arc1000_after_stable_baseline_2026_06_16/slurm_%j.out
#SBATCH --error=outputs/full_novel_reasoning_pipeline_v2/arc1000_after_stable_baseline_2026_06_16/slurm_%j.err
#SBATCH --signal=B:USR1@120

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

# USR1 signal handler for requeue auto-resume
_requeue() {
    echo "=== USR1 received, requeueing: $(date -Iseconds) ==="
    scontrol requeue "$SLURM_JOB_ID"
}
trap '_requeue' USR1

echo "=== Full Novel Pipeline v2: ARC-1000 ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"
echo ""

PYTHONPATH=src python3.11 scripts/run_full_novel_v2_arc1000.py &
wait $!

echo ""
echo "=== Finished: $(date -Iseconds), exit=$? ==="
