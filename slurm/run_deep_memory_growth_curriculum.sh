#!/bin/bash
#SBATCH --job-name=mem_growth_deep
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/deep_project_completion/memory_growth_deep/slurm_%j.out
#SBATCH --error=outputs/deep_project_completion/memory_growth_deep/slurm_%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@300
#SBATCH --mail-type=END,FAIL,REQUEUE
#SBATCH --mail-user=cnptp@missouri.edu

resubmit() {
    echo "=== Received signal, resubmitting... ==="
    sbatch "$0"
    exit 0
}
trap resubmit USR1

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

OUTPUT_DIR=outputs/deep_project_completion/memory_growth_deep
mkdir -p "$OUTPUT_DIR/certificates"

echo "=== Phase D: Deep Memory Growth Curriculum ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node:   $(hostname)"
echo "Start:  $(date -Iseconds)"

echo '{"status":"running","job_id":"'$SLURM_JOB_ID'","started":"'$(date -Iseconds)'"}' > "$OUTPUT_DIR/status.json"

PYTHONPATH=src python3.11 scripts/run_deep_memory_growth_curriculum.py \
    --output-dir "$OUTPUT_DIR" \
    --arc-root data/arc \
    --max-tasks-per-stage 200 \
    --resume 2>&1 | tee "$OUTPUT_DIR/run.log"

echo '{"status":"completed","job_id":"'$SLURM_JOB_ID'","finished":"'$(date -Iseconds)'"}' > "$OUTPUT_DIR/status.json"
echo "=== Done: $(date -Iseconds) ==="
