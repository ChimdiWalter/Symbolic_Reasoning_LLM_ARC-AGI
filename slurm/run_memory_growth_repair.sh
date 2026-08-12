#!/bin/bash
#SBATCH --job-name=mem_repair
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/deep_project_completion/mechanism_repair_pass/memory_growth/slurm_%j.out
#SBATCH --error=outputs/deep_project_completion/mechanism_repair_pass/memory_growth/slurm_%j.err

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Memory Growth Repair Pass ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"

echo "--- Phase B1: Diagnosis ---"
PYTHONPATH=src python3.11 scripts/diagnose_memory_growth_failures.py

echo "--- Phase B2: Microcycle ---"
PYTHONPATH=src python3.11 scripts/test_memory_growth_microcycle.py

echo "=== Finished: $(date -Iseconds) ==="
