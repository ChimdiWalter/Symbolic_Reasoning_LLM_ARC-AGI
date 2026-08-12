#!/bin/bash
set -euo pipefail

REPO_ROOT="/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project"
PARTITION="${1:-}"
MODE="${2:-submit}"

RESUME_FLAG=""
if [[ "${MODE}" == "resume" ]]; then
  RESUME_FLAG="--resume"
fi

SBATCH_ARGS=()
if [[ -n "${PARTITION}" ]]; then
  SBATCH_ARGS+=(--partition "${PARTITION}")
fi

cd "${REPO_ROOT}"
mkdir -p outputs/slurm_logs

if [[ -n "${RESUME_FLAG}" ]]; then
  EXPORT_ARGS=(--export=ALL,RESUME_FLAG="${RESUME_FLAG}")
else
  EXPORT_ARGS=(--export=ALL)
fi

GRID_JEPA_JOB=$(sbatch --parsable "${EXPORT_ARGS[@]}" "${SBATCH_ARGS[@]}" slurm/train_grid_jepa.sbatch configs/grid_jepa_arc_pretrain_gpu_full.json outputs/neural)
PLAIN_RANKER_JOB=$(sbatch --parsable --dependency="afterok:${GRID_JEPA_JOB}" "${EXPORT_ARGS[@]}" "${SBATCH_ARGS[@]}" slurm/train_program_ranker.sbatch configs/program_ranker_grid_gpu_full.json outputs/neural)
JEPA_RANKER_JOB=$(sbatch --parsable --dependency="afterok:${GRID_JEPA_JOB}" "${EXPORT_ARGS[@]}" "${SBATCH_ARGS[@]}" slurm/train_program_ranker.sbatch configs/program_ranker_jepa_gpu_full.json outputs/neural)
TRAIN_REFINE_JOB=$(sbatch --parsable --dependency="afterok:${PLAIN_RANKER_JOB}:${JEPA_RANKER_JOB}" "${EXPORT_ARGS[@]}" "${SBATCH_ARGS[@]}" slurm/run_arc_refinement_gpu.sbatch configs/arc_training_refinement_gpu_full.json outputs/arc_refinement)
EVAL_REFINE_JOB=$(sbatch --parsable --dependency="afterok:${PLAIN_RANKER_JOB}:${JEPA_RANKER_JOB}" "${EXPORT_ARGS[@]}" "${SBATCH_ARGS[@]}" slurm/run_arc_refinement_gpu.sbatch configs/arc_evaluation_refinement_gpu_full.json outputs/arc_refinement)

PIPELINE_PARTITION="${PARTITION}" \
PIPELINE_MODE="${MODE}" \
PIPELINE_RESUME_FLAG="${RESUME_FLAG}" \
GRID_JEPA_JOB_ID="${GRID_JEPA_JOB}" \
PLAIN_RANKER_JOB_ID="${PLAIN_RANKER_JOB}" \
JEPA_RANKER_JOB_ID="${JEPA_RANKER_JOB}" \
TRAIN_REFINE_JOB_ID="${TRAIN_REFINE_JOB}" \
EVAL_REFINE_JOB_ID="${EVAL_REFINE_JOB}" \
python3.11 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "submitted_at": datetime.now(timezone.utc).isoformat(),
    "partition": os.environ.get("PIPELINE_PARTITION", ""),
    "mode": os.environ.get("PIPELINE_MODE", "submit"),
    "resume_flag": os.environ.get("PIPELINE_RESUME_FLAG", ""),
    "jobs": {
        "grid_jepa_job": os.environ.get("GRID_JEPA_JOB_ID", ""),
        "plain_ranker_job": os.environ.get("PLAIN_RANKER_JOB_ID", ""),
        "jepa_ranker_job": os.environ.get("JEPA_RANKER_JOB_ID", ""),
        "train_refine_job": os.environ.get("TRAIN_REFINE_JOB_ID", ""),
        "eval_refine_job": os.environ.get("EVAL_REFINE_JOB_ID", ""),
    },
}
log_dir = Path("${REPO_ROOT}") / "outputs" / "slurm_logs"
log_dir.mkdir(parents=True, exist_ok=True)
json_path = log_dir / "neural_arc_pipeline_submission.json"
md_path = log_dir / "neural_arc_pipeline_submission.md"
json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
md_lines = [
    f"submitted_at: {payload['submitted_at']}",
    f"partition: {payload['partition']}",
    f"mode: {payload['mode']}",
    f"resume_flag: {payload['resume_flag']}",
    "",
]
for key, value in payload["jobs"].items():
    md_lines.append(f"- {key}: {value}")
md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
PY

echo "grid_jepa_job=${GRID_JEPA_JOB}"
echo "plain_ranker_job=${PLAIN_RANKER_JOB}"
echo "jepa_ranker_job=${JEPA_RANKER_JOB}"
echo "train_refine_job=${TRAIN_REFINE_JOB}"
echo "eval_refine_job=${EVAL_REFINE_JOB}"
echo "after refinement, run: python3.11 scripts/analyze_reasoning_manifold.py --config configs/reasoning_manifold_arc_eval_with_training_anchors.json"
