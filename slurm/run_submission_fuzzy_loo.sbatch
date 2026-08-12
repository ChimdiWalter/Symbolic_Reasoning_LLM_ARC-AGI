#!/bin/bash
#SBATCH --job-name=sub_fuzzy
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/submission_fuzzy_loo_2026_06_27/slurm_%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/submission_fuzzy_loo_2026_06_27/slurm_%j.err

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
export PYTHONPATH=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/src

python3.11 -u /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/scripts/run_submission_fuzzy_loo.py
