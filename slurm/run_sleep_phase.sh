#!/bin/bash
#SBATCH --job-name=sleep-phase
#SBATCH --partition=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=outputs/slurm_logs/sleep_phase_%j.out
#SBATCH --error=outputs/slurm_logs/sleep_phase_%j.err
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

mkdir -p outputs/slurm_logs

echo "=== Tests ==="
python3.11 -m pytest tests/ -q --tb=short

echo ""
echo "=== Sleep/Consolidation Phase ==="
python3.11 -u scripts/run_reasoning_sleep_phase.py \
    --output-dir outputs/sleep_phase

echo ""
echo "=== Final Experiment ==="
python3.11 -u scripts/run_final_experiment.py \
    --output-dir outputs/final_experiment

echo ""
echo "=== Done ==="
