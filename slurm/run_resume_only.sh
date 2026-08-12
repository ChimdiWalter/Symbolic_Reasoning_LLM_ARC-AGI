#!/bin/bash
#SBATCH --job-name=rp_resume
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/slurm_logs/%x_%j.out
#SBATCH --error=outputs/slurm_logs/%x_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=cnptp@missouri.edu
#SBATCH --requeue
#SBATCH --signal=B:USR1@300

resubmit() {
    echo "=== Received signal, resubmitting... ==="
    sbatch "$0"
    exit 0
}
trap resubmit USR1

set -euo pipefail

cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

OUTPUT_DIR=outputs/resume
mkdir -p "$OUTPUT_DIR" outputs/slurm_logs

echo '{"status": "running", "job_id": "'$SLURM_JOB_ID'", "started": "'$(date -Iseconds)'"}' > "$OUTPUT_DIR/status.json"

# Run standalone resume script (loads ARC tasks, builds near-solved states, invents concepts, resumes)
PYTHONPATH=src python3.11 scripts/run_resume_from_near_solved.py \
    --arc-root data/arc \
    --output-dir "$OUTPUT_DIR" \
    --max-tasks 200 2>&1 | tee "$OUTPUT_DIR/run.log"
EXIT_CODE=${PIPESTATUS[0]}

# Write final status
if [ $EXIT_CODE -eq 0 ]; then
    echo '{"status": "completed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": 0}' > "$OUTPUT_DIR/status.json"
else
    echo '{"status": "failed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": '$EXIT_CODE'}' > "$OUTPUT_DIR/status.json"
fi

exit $EXIT_CODE
