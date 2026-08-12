#!/bin/bash
set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
PARTITION="${1:-gpu}"

cd "${REPO_ROOT}"
exec slurm/submit_arc_expanded_pipeline.sh "${PARTITION}" resume
