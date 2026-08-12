#!/bin/bash
#SBATCH --job-name=breakthrough
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/slurm_logs/breakthrough-%j.out
#SBATCH --error=outputs/slurm_logs/breakthrough-%j.err
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

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

mkdir -p outputs/slurm_logs outputs/memory_growth outputs/oracle_candidate_analysis

echo "=== Stage 1: Memory Growth Curriculum ==="
python3.11 -u scripts/run_memory_growth_curriculum.py \
    --arc-root data/arc \
    --output-dir outputs/memory_growth

echo "=== Stage 2: Oracle Candidate Analysis ==="
python3.11 -u scripts/analyze_oracle_candidates.py \
    --arc-root data/arc \
    --output-dir outputs/oracle_candidate_analysis

echo "=== Stage 3: Tests ==="
python3.11 -m pytest tests/ -q --tb=short

echo "=== Done ==="
