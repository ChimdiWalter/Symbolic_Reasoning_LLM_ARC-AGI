#!/bin/bash
#SBATCH --job-name=cumulative-reasoning
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=outputs/slurm_logs/cumulative-reasoning-%j.out
#SBATCH --error=outputs/slurm_logs/cumulative-reasoning-%j.err
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
date

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

mkdir -p outputs/slurm_logs outputs/memory_growth outputs/cross_domain_v2
mkdir -p outputs/oracle_candidate_analysis outputs/reasoning_scaling

echo ""
echo "=== Phase 1: Tests ==="
python3.11 -m pytest tests/ -q --tb=short
if [ $? -ne 0 ]; then
    echo "TESTS FAILED — aborting"
    exit 1
fi

echo ""
echo "=== Phase 2: Memory Growth Curriculum (6 stages, full ARC) ==="
python3.11 -u scripts/run_memory_growth_curriculum.py \
    --arc-root data/arc \
    --output-dir outputs/memory_growth

echo ""
echo "=== Phase 3: Oracle Candidate Analysis (full ARC) ==="
python3.11 -u scripts/analyze_oracle_candidates.py \
    --arc-root data/arc \
    --output-dir outputs/oracle_candidate_analysis

echo ""
echo "=== Phase 4: Cross-Domain Transfer v2 ==="
python3.11 -u scripts/run_cross_domain_v2.py \
    --output-dir outputs/cross_domain_v2

echo ""
echo "=== Phase 5: Reasoning Scaling Analysis ==="
python3.11 -u scripts/analyze_reasoning_scaling.py \
    --input-dir outputs/memory_growth \
    --output-dir outputs/reasoning_scaling

echo ""
echo "=== Phase 6: Breakthrough Report ==="
python3.11 -u scripts/generate_breakthrough_report.py \
    --output outputs/breakthrough_gap_closure_report.md

echo ""
echo "=== Done ==="
date
