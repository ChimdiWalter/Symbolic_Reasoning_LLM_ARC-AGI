#!/bin/bash
#SBATCH --job-name=vit_probe
#SBATCH --partition=requeue
#SBATCH --account=general
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:A100:1
#SBATCH --time=0-04:00:00
#SBATCH --output=outputs/vit_vlm_advisory_probe/slurm_%j.out
#SBATCH --error=outputs/vit_vlm_advisory_probe/slurm_%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@300

resubmit() {
    echo "=== Received signal, resubmitting... ==="
    sbatch "$0"
    exit 0
}
trap resubmit USR1

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project

mkdir -p outputs/vit_vlm_advisory_probe

python3.11 scripts/run_vit_vlm_advisory_probe.py \
    --output-dir outputs/vit_vlm_advisory_probe \
    --max-tasks 50 \
    2>&1 | tee outputs/vit_vlm_advisory_probe/run.log
