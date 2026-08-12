#!/bin/bash
#SBATCH --job-name=prop-invention
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=outputs/slurm_logs/prop_invention_%j.out
#SBATCH --error=outputs/slurm_logs/prop_invention_%j.err
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
export PYTHONPATH=src

echo "=== Tests ==="
python3.11 -m pytest tests/ -q --tb=short

echo ""
echo "=== Property Gap Analysis ==="
python3.11 -u scripts/run_property_gap_analysis.py \
    --output-dir outputs/property_gap_analysis

echo ""
echo "=== Property Invention Evaluation ==="
python3.11 -u scripts/run_property_invention_eval.py \
    --output-dir outputs/property_invention

echo ""
echo "=== Memory Growth Curriculum v2 ==="
python3.11 -u scripts/run_memory_growth_curriculum.py \
    --output-dir outputs/memory_growth_v2

echo ""
echo "=== Reasoning Scaling v2 ==="
python3.11 -u scripts/analyze_reasoning_scaling.py \
    --output-dir outputs/reasoning_scaling_v2

echo ""
echo "=== Breakthrough Report v2 ==="
python3.11 -u scripts/generate_breakthrough_report.py \
    --output outputs/breakthrough_gap_closure_report_v2.md

echo ""
echo "=== Done ==="
