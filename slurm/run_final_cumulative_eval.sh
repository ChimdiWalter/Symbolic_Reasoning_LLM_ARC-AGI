#!/bin/bash
#SBATCH --job-name=rp_final_eval
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=1-00:00:00
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

OUTPUT_DIR=outputs/final_eval
mkdir -p "$OUTPUT_DIR" outputs/slurm_logs

echo '{"status": "running", "job_id": "'$SLURM_JOB_ID'", "started": "'$(date -Iseconds)'"}' > "$OUTPUT_DIR/status.json"

# Run the actual script (limit to 100 tasks: 9 configs × 100 tasks × ~36s ≈ 9h)
PYTHONPATH=src python3.11 scripts/run_final_experiment.py \
    --max-tasks 100 \
    --output-dir "$OUTPUT_DIR" 2>&1 | tee "$OUTPUT_DIR/run.log"
EXIT_CODE=${PIPESTATUS[0]}

# Write final status
if [ $EXIT_CODE -eq 0 ]; then
    echo '{"status": "completed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": 0}' > "$OUTPUT_DIR/status.json"
else
    echo '{"status": "failed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": '$EXIT_CODE'}' > "$OUTPUT_DIR/status.json"
fi

exit $EXIT_CODE
