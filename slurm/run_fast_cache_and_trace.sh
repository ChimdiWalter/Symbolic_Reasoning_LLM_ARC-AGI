#!/bin/bash
#SBATCH --job-name=rp_fast_cache
#SBATCH --output=outputs/slurm_logs/fast_cache-%j.out
#SBATCH --error=outputs/slurm_logs/fast_cache-%j.err
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --account=general
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

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

echo "=== Job $SLURM_JOB_ID started at $(date) ==="
echo "=== Node: $(hostname) ==="

# Stage 1: Build fast cache (1000 tasks)
echo ""
echo "=========================================="
echo "STAGE 1: Fast cache build (1000 tasks)"
echo "=========================================="
python3.11 scripts/build_fast_near_solved_cache.py \
    --max-tasks 1000 \
    --static-first \
    --output-dir outputs/cache_fast

echo ""
echo "=========================================="
echo "STAGE 2: Operator gap trace"
echo "=========================================="
python3.11 scripts/trace_operator_gap_tasks.py \
    --max-tasks 1000 \
    --use-cache outputs/cache_fast \
    --output-dir outputs/operator_gap_analysis

echo ""
echo "=========================================="
echo "STAGE 3: Operator invention microcycle"
echo "=========================================="
python3.11 scripts/test_operator_invention_microcycle.py || true

echo ""
echo "=========================================="
echo "STAGE 4: Resume from cache (200 tasks)"
echo "=========================================="
python3.11 scripts/run_resume_from_near_solved.py \
    --use-cache outputs/cache_fast \
    --max-tasks 200 \
    --output-dir outputs/resume_cached_200

echo ""
echo "=== Job $SLURM_JOB_ID finished at $(date) ==="
