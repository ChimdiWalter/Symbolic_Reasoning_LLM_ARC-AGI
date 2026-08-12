# Resume Recovery Playbook

This note records the current restartable paths for long neural and refinement runs.

## Reliable Resume Artifacts

Verified repo-local reliability checks:

- Ranker:
  - `outputs/reliability_checks/neural/program_ranker_smoke/`
  - Key files:
    - `run_state.json`
    - `status.txt`
    - `progress.jsonl`
    - `dataset_chunks/`
    - `dataset_cache.npz`
    - `ranker_training_checkpoint.pt`
    - `resume_instructions.json`
- Refinement:
  - `outputs/reliability_checks/arc_refinement/arc_refinement_smoke/`
  - Key files:
    - `run_state.json`
    - `status.txt`
    - `progress.jsonl`
    - `completed_rows.json`
    - `rows.json`
    - `refinement_records.json`
    - `qualitative_failures.json`
    - `resume_instructions.json`

## Resume Commands

Ranker smoke:

```bash
python3.11 scripts/train_program_ranker.py --config configs/program_ranker_smoke.json --output-dir outputs/reliability_checks/neural --resume
```

Refinement smoke:

```bash
python3.11 scripts/run_arc_refinement.py --config configs/arc_refinement_smoke.json --output-dir outputs/reliability_checks/arc_refinement --resume
```

Full Slurm pipeline resubmission with resume flag propagation:

```bash
slurm/resume_neural_arc_pipeline.sh gpu
```

Equivalent explicit submit path:

```bash
slurm/submit_neural_arc_pipeline.sh gpu resume
```

## Slurm Inspection

Queue:

```bash
squeue -u "$(whoami)" -o "%i %P %j %T %M %R"
```

Accounting for the prior GPU run set:

```bash
sacct -j 13188612,13188613,13188614,13188615 --format=JobID,JobName%24,State,ExitCode,Elapsed,NodeList -P
```

Submission metadata log:

- `outputs/slurm_logs/neural_arc_pipeline_submission.json`
- `outputs/slurm_logs/neural_arc_pipeline_submission.md`

## Important Caveat

The earlier full refinement outputs:

- `outputs/arc_refinement/arc_training_refinement_gpu_full/`
- `outputs/arc_refinement/arc_evaluation_refinement_gpu_full/`

completed before the new row-level resume bundle was verified. They contain final summaries and rows, but not the newer `run_state.json`, `status.txt`, `progress.jsonl`, or `completed_rows.json` files now emitted by the hardened script path.

If we want the full GPU refinement runs themselves to have the new resumability bundle, rerun them in a fresh output root or archive the historical outputs first.
