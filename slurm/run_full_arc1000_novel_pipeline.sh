#!/bin/bash
#SBATCH --job-name=arc1000_novel
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=2-00:00:00
#SBATCH --output=outputs/full_arc1000_novel_pipeline/slurm_%j.out
#SBATCH --error=outputs/full_arc1000_novel_pipeline/slurm_%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@300
#SBATCH --mail-type=END,FAIL,REQUEUE
#SBATCH --mail-user=cnptp@missouri.edu

# Auto-resubmit on walltime signal (5 min before limit)
resubmit() {
    echo "=== Received signal, resubmitting... ==="
    sbatch "$0"
    exit 0
}
trap resubmit USR1

set -euo pipefail

cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

OUTPUT_DIR=outputs/full_arc1000_novel_pipeline
mkdir -p "$OUTPUT_DIR" "$OUTPUT_DIR/certificates"

echo '{"status": "running", "job_id": "'$SLURM_JOB_ID'", "started": "'$(date -Iseconds)'", "hostname": "'$(hostname)'"}' > "$OUTPUT_DIR/status.json"

echo "=== ARC-1000 Novel Pipeline ==="
echo "Job ID:    $SLURM_JOB_ID"
echo "Node:      $(hostname)"
echo "Started:   $(date -Iseconds)"
echo "==============================="

# Run the full pipeline with --resume for automatic checkpoint recovery
PYTHONPATH=src python3.11 scripts/run_full_arc1000_novel_pipeline.py \
    --arc-root data/arc \
    --output-dir "$OUTPUT_DIR" \
    --timeout-per-config 60 \
    --resume 2>&1 | tee "$OUTPUT_DIR/run.log"
EXIT_CODE=${PIPESTATUS[0]}

# Write final status
if [ $EXIT_CODE -eq 0 ]; then
    echo '{"status": "completed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": 0}' > "$OUTPUT_DIR/status.json"
else
    echo '{"status": "failed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": '$EXIT_CODE'}' > "$OUTPUT_DIR/status.json"
fi

echo "=== Finished: $(date -Iseconds), exit=$EXIT_CODE ==="
exit $EXIT_CODE
