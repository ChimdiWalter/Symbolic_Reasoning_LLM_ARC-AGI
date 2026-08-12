#!/bin/bash
#SBATCH --job-name=claim_audit
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=1:00:00
#SBATCH --output=outputs/deep_project_completion/final_claim_audit/slurm_%j.out
#SBATCH --error=outputs/deep_project_completion/final_claim_audit/slurm_%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@300
#SBATCH --mail-type=END,FAIL,REQUEUE
#SBATCH --mail-user=cnptp@missouri.edu

resubmit() {
    echo "=== Received signal, resubmitting... ==="
    sbatch "$0"
    exit 0
}
trap resubmit USR1

set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

OUTPUT_DIR=outputs/deep_project_completion/final_claim_audit
mkdir -p "$OUTPUT_DIR"

echo "=== Phase K: Final Claim Audit ==="
PYTHONPATH=src python3.11 scripts/build_final_deep_project_claim_audit.py \
    --output-dir "$OUTPUT_DIR" 2>&1 | tee "$OUTPUT_DIR/run.log"

echo "=== Done: $(date -Iseconds) ==="
