#!/bin/bash
#SBATCH --job-name=dom_morphism
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/domain_morphism_learning/slurm_%j.out
#SBATCH --error=outputs/domain_morphism_learning/slurm_%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@300
#SBATCH --mail-type=END,FAIL,REQUEUE
#SBATCH --mail-user=cnptp@missouri.edu

set -euo pipefail

cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

OUTPUT_DIR=outputs/domain_morphism_learning
mkdir -p "$OUTPUT_DIR"

echo '{"status": "running", "job_id": "'$SLURM_JOB_ID'", "started": "'$(date -Iseconds)'", "hostname": "'$(hostname)'"}' > "$OUTPUT_DIR/status.json"

echo "=== Domain Morphism Learning Pass ==="
echo "Job ID:    $SLURM_JOB_ID"
echo "Node:      $(hostname)"
echo "Started:   $(date -Iseconds)"
echo "======================================="

run_phase() {
    local phase=$1
    local script=$2
    echo ""
    echo "--- Phase $phase: $script ---"
    echo "Started: $(date -Iseconds)"
    PYTHONPATH=src python3.11 "scripts/$script" 2>&1
    echo "Finished: $(date -Iseconds)"
}

{
    run_phase "4" "test_domain_morphism_microcycle.py"
    run_phase "5" "analyze_existing_cross_domain_as_morphisms.py"
    run_phase "6" "test_morphism_memory_microcycle.py"
    run_phase "7" "test_neural_morphism_proposal_microcycle.py"
    run_phase "8" "test_adapter_genesis_signature_compiler.py"
    run_phase "9" "build_domain_morphism_claim_audit.py"
} 2>&1 | tee "$OUTPUT_DIR/run.log"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo '{"status": "completed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": 0}' > "$OUTPUT_DIR/status.json"
else
    echo '{"status": "failed", "job_id": "'$SLURM_JOB_ID'", "finished": "'$(date -Iseconds)'", "exit_code": '$EXIT_CODE'}' > "$OUTPUT_DIR/status.json"
fi

echo "=== Finished: $(date -Iseconds), exit=$EXIT_CODE ==="
exit $EXIT_CODE
