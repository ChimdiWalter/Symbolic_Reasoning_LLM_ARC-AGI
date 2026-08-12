#!/bin/bash
#SBATCH --job-name=ag_repair
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/deep_project_completion/mechanism_repair_pass/adapter_genesis/slurm_%j.out
#SBATCH --error=outputs/deep_project_completion/mechanism_repair_pass/adapter_genesis/slurm_%j.err

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== AdapterGenesis Repair Pass ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"

echo "--- Phase A1: Diagnosis ---"
PYTHONPATH=src python3.11 scripts/diagnose_adapter_genesis_failures.py

echo "--- Phase A2: Microcycle ---"
PYTHONPATH=src python3.11 scripts/test_adapter_genesis_microcycle.py

echo "--- Phase A4: Ablation ---"
PYTHONPATH=src python3.11 scripts/run_adapter_genesis_ablation.py

echo "=== Finished: $(date -Iseconds) ==="
