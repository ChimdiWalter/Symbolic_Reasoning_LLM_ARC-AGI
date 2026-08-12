#!/bin/bash
#SBATCH --job-name=rp_build_cache
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=2-00:00:00
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
mkdir -p "$CACHE_DIR" outputs/slurm_logs

echo '{"status": "running", "job_id": "'$SLURM_JOB_ID'", "started": "'$(date -Iseconds)'"}' > "$CACHE_DIR/status.json"

python3.11 scripts/build_near_solved_cache.py \
    --build-cache \
    --cache-dir "$CACHE_DIR" \
    --timeout 30 \
    --loop-iters 2

echo '{"status": "completed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'"}' > "$CACHE_DIR/status.json"

python3.11 scripts/build_near_solved_cache.py --verify --cache-dir "$CACHE_DIR"
