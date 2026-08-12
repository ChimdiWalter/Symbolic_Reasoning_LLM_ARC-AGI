#!/bin/bash
#SBATCH --job-name=activation-repair-eval
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/slurm_logs/activation-repair-eval-%j.out
#SBATCH --error=outputs/slurm_logs/activation-repair-eval-%j.err
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
echo "start_time=$(date -Iseconds)"

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

PYTHONPATH=src python3.11 scripts/run_full_novel_v2_focused_eval.py \
    --output-dir outputs/full_novel_reasoning_pipeline_v2/full_pipeline_activation_repair/focused_eval_after_activation

echo "end_time=$(date -Iseconds)"
echo "=== DONE ==="
