# Resume Instructions

Use this file if the VSCode session, terminal, or Codex process is interrupted.

## Environment

```bash
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
```

All current commands should be run with `python3.11`.

## Resume / Regenerate Current Artifacts

The latest validated artifact set is built from the commands below. They are safe to rerun for regeneration and recovery.

```bash
python3.11 scripts/run_seed_sweep.py --config configs/paper_breadth_validation.json --output-dir outputs --sweep-name paper_breadth_validation_5seed_sweep --seeds 2030 2031 2032 2033 2034
python3.11 scripts/run_seed_sweep.py --config configs/h2_family_validation.json --output-dir outputs --sweep-name h2_family_validation_10seed_sweep --seeds 1300 1301 1302 1303 1304 1305 1306 1307 1308 1309
python3.11 scripts/analyze_h2_family_balance.py --sweep-dir outputs/h2_family_validation_10seed_sweep --max-examples 40
python3.11 scripts/analyze_sweep_failures.py --sweep-dir outputs/h2_family_validation_10seed_sweep --contrast proposer_falsifier_minus_proposer_only --metric false_rule_accepted
python3.11 scripts/analyze_h4_sweep.py --sweep-dir outputs/paper_breadth_validation_5seed_sweep
python3.11 scripts/run_arc_diagnostic.py --config configs/arc_diagnostic_eval_learned_quick.json --output-dir outputs
python3.11 scripts/build_submission_package.py --repo-root /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project --breadth-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep --h2-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/h2_family_validation_10seed_sweep --h4-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment
python3.11 -m pytest
```

Notes:

- The two sweep commands resume from child-run checkpoints and rewrite aggregate summaries.
- `analyze_h2_family_balance.py`, `analyze_sweep_failures.py`, `analyze_h4_sweep.py`, and `build_submission_package.py` are deterministic regenerators.
- The active ARC learned-baseline check is the quick 2-task / 1-seed diagnostic. The larger learned ARC config was intentionally not kept as the paper-facing artifact because runtime was high and the quick run already preserved the negative result.

## Inspect Progress

For the current synthetic breadth sweep:

```bash
python3.11 -c 'import json, pathlib; p=pathlib.Path("outputs/paper_breadth_validation_5seed_sweep/child_runs.json"); print("child_runs_exists", p.exists()); print(p.read_text()[:800] if p.exists() else "missing")'
```

For the current H2 validation sweep:

```bash
python3.11 -c 'import json, pathlib; p=pathlib.Path("outputs/h2_family_validation_10seed_sweep/child_runs.json"); print("child_runs_exists", p.exists()); print(p.read_text()[:800] if p.exists() else "missing")'
```

For the latest full test result:

```bash
python3.11 -m pytest
```

## Regenerate Submission Views Only

If the underlying artifacts already exist and only the paper package needs rebuilding:

```bash
python3.11 scripts/build_submission_package.py --repo-root /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project --breadth-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep --h2-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/h2_family_validation_10seed_sweep --h4-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment
```

## GeoCat-ARC Baseline

```bash
# Run GeoCat-ARC baseline (10 tasks, 10 iters)
python3.11 -m geocat_arc.experiments.run_baseline

# Run full test suite
python3.11 -m pytest geocat_arc/tests/ -v

# Submit to SLURM
sbatch slurm/run_geocat_baseline.sbatch
```

Results: `geocat_arc/artifacts/geocat_arc/baseline_results.json`

## Important Checkpoint Files

- `outputs/paper_breadth_validation_5seed_sweep/resume_instructions.json`
- `outputs/paper_breadth_validation_5seed_sweep/sweep_summary.md`
- `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`
- `outputs/paper_breadth_validation_5seed_sweep/stratified_paired_contrasts.md`
- `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/resume_instructions.json`
- `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md`
- `outputs/h2_family_validation_10seed_sweep/resume_instructions.json`
- `outputs/h2_family_validation_10seed_sweep/sweep_summary.md`
- `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md`
- `outputs/h2_family_validation_10seed_sweep/failure_taxonomy.md`
- `outputs/h2_family_validation_10seed_sweep/accepted_false_rule_examples.md`
- `outputs/h2_family_validation_10seed_sweep/falsifier_counterexample_traces.json`
- `outputs/arc_diagnostic_eval_2task_1seed_learned_quick/resume_instructions.json`
- `outputs/arc_diagnostic_eval_2task_1seed_learned_quick/arc_evaluation_summary.md`
- `outputs/arc_diagnostic_eval_2task_1seed_learned_quick/qualitative_failures.md`
- `outputs/submission_package/submission_overview.md`
- `outputs/submission_package/artifact_manifest.md`
- `outputs/submission_package/appendix/claim_traceability_appendix.md`
- `outputs/submission_package/tables/table_h1_structural_transfer.md`
- `outputs/submission_package/tables/table_h2_family_balanced.md`
- `outputs/submission_package/tables/table_h4_alignment.md`
- `outputs/submission_package/tables/table_h5_integrated_stack.md`
- `outputs/submission_package/tables/table_arc_external_validity.md`
- `outputs/submission_package/figures/fig_h1_structural_transfer.png`
- `outputs/submission_package/figures/fig_h2_family_balanced.png`
- `outputs/submission_package/figures/fig_h4_alignment.png`
- `outputs/submission_package/figures/fig_h5_integrated_stack.png`
- `outputs/submission_package/figures/fig_arc_external_validity.png`
- `paper/manuscript_draft.md`
- `paper/reproduce_paper_artifacts.md`
- `claim_traceability.md`
- `exactness_traceability.md`
- `results_summary.md`
- `limitations.md`
- `external_validity_summary.md`
- `PROCESS_LOG.md`
- `RUN_HISTORY.md`
