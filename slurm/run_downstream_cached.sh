#!/bin/bash
#SBATCH --job-name=rp_downstream
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=14:00:00
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

CACHE_DIR=outputs/cache
if [ ! -f "$CACHE_DIR/near_solved_states.jsonl" ]; then
    echo "[ERROR] Cache not found at $CACHE_DIR. Run slurm/run_build_near_solved_cache.sh first."
    exit 1
fi

mkdir -p outputs/slurm_logs

echo '{"status": "running", "job_id": "'$SLURM_JOB_ID'", "started": "'$(date -Iseconds)'"}' > outputs/downstream_status.json

echo "=== Step 1: Property Invention (from cache) ==="
python3.11 scripts/run_property_invention_eval.py \
    --use-cache "$CACHE_DIR" \
    --output-dir outputs/property_invention_cached \
    --max-tasks 1000

echo "=== Step 2: Sleep Phase (from cache) ==="
python3.11 scripts/run_reasoning_sleep_phase.py \
    --use-cache "$CACHE_DIR" \
    --output-dir outputs/sleep_phase_cached \
    --max-tasks 1000

echo "=== Step 3: Resume Near-Solved (from cache) ==="
python3.11 scripts/run_resume_from_near_solved.py \
    --use-cache "$CACHE_DIR" \
    --output-dir outputs/resume_cached \
    --max-tasks 1000

echo "=== Step 4: Final Experiment (from cache) ==="
python3.11 scripts/run_final_experiment.py \
    --use-cache "$CACHE_DIR" \
    --output-dir outputs/final_eval_cached \
    --max-tasks 200

echo '{"status": "completed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'"}' > outputs/downstream_status.json
