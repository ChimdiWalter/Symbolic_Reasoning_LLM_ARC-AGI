#!/bin/bash
#SBATCH --job-name=repair_audit
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=outputs/deep_project_completion/mechanism_repair_pass/slurm_audit_%j.out
#SBATCH --error=outputs/deep_project_completion/mechanism_repair_pass/slurm_audit_%j.err
#SBATCH --dependency=afterany

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Mechanism Repair Claim Audit ==="
echo "Job ID:  $SLURM_JOB_ID"
echo "Started: $(date -Iseconds)"

PYTHONPATH=src python3.11 scripts/build_mechanism_repair_claim_audit.py

echo "=== Finished: $(date -Iseconds) ==="
