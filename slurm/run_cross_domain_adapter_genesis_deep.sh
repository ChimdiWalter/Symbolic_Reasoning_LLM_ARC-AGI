#!/bin/bash
#SBATCH --job-name=adapter_genesis_deep
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/deep_project_completion/cross_domain_adapter_genesis/slurm_%j.out
#SBATCH --error=outputs/deep_project_completion/cross_domain_adapter_genesis/slurm_%j.err
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

OUTPUT_DIR=outputs/deep_project_completion/cross_domain_adapter_genesis
mkdir -p "$OUTPUT_DIR"

echo "=== Phase B: Cross-Domain AdapterGenesis Deep Eval ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node:   $(hostname)"
echo "Start:  $(date -Iseconds)"

echo '{"status":"running","job_id":"'$SLURM_JOB_ID'","started":"'$(date -Iseconds)'"}' > "$OUTPUT_DIR/status.json"

PYTHONPATH=src python3.11 scripts/audit_cross_domain_capabilities.py \
    --output-dir "$OUTPUT_DIR" 2>&1 | tee -a "$OUTPUT_DIR/run.log"

PYTHONPATH=src python3.11 scripts/run_adapter_genesis_deep_eval.py \
    --output-dir "$OUTPUT_DIR" \
    --resume 2>&1 | tee -a "$OUTPUT_DIR/run.log"

PYTHONPATH=src python3.11 scripts/run_cross_domain_structural_reasoner_eval.py \
    --output-dir "$OUTPUT_DIR" 2>&1 | tee -a "$OUTPUT_DIR/run.log"

echo '{"status":"completed","job_id":"'$SLURM_JOB_ID'","finished":"'$(date -Iseconds)'"}' > "$OUTPUT_DIR/status.json"
echo "=== Done: $(date -Iseconds) ==="
