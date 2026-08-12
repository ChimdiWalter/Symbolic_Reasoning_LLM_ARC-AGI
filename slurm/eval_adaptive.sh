#!/bin/bash
#SBATCH --job-name=adaptive-eval
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/slurm_logs/adaptive-eval-%j.out
#SBATCH --error=outputs/slurm_logs/adaptive-eval-%j.err
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

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

python3.11 scripts/eval_adaptive_loop.py
