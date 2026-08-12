#!/bin/bash
#SBATCH --job-name=loo_gate
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/loo_replace_v5b_2026_06_28/slurm_%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/loo_replace_v5b_2026_06_28/slurm_%j.err

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
export PYTHONPATH=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/src

python3.11 -u /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/scripts/run_loo_gated_eval.py
