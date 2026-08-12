# Process Log

This file records the current restart-safe commands and the latest completed long runs.
All commands assume:

```bash
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
```

## Resume Principle

- Single-run experiments checkpoint to `outputs/<run_name>/run_state.json` when supported.
- Seed sweeps checkpoint each child run independently and can be resumed by rerunning the same sweep command.
- Aggregate analyses rewrite markdown/JSON summaries deterministically from completed child outputs.
- Submission-package generation is deterministic and can be rerun safely.

## Active / Last Known Long Process

### `paper_breadth_validation_5seed_sweep`

Command:

```bash
python3.11 scripts/run_seed_sweep.py --config configs/paper_breadth_validation.json --output-dir outputs --sweep-name paper_breadth_validation_5seed_sweep --seeds 2030 2031 2032 2033 2034
```

Restart command after disruption:

```bash
python3.11 scripts/run_seed_sweep.py --config configs/paper_breadth_validation.json --output-dir outputs --sweep-name paper_breadth_validation_5seed_sweep --seeds 2030 2031 2032 2033 2034
```

Final status:

- Completed with 40 seed-model records across 5 seeds.
- Resume metadata: `outputs/paper_breadth_validation_5seed_sweep/resume_instructions.json`
- Main artifacts:
  - `outputs/paper_breadth_validation_5seed_sweep/sweep_summary.md`
  - `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`
  - `outputs/paper_breadth_validation_5seed_sweep/stratified_paired_contrasts.md`
  - `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md`

## Completed Processes

### Risk-Reduction Validation Pass

Commands:

```bash
python3.11 -m pytest tests/test_models.py tests/test_paper_package.py
python3.11 scripts/run_seed_sweep.py --config configs/paper_breadth_validation.json --output-dir outputs --sweep-name paper_breadth_validation_5seed_sweep --seeds 2030 2031 2032 2033 2034
python3.11 scripts/run_seed_sweep.py --config configs/h2_family_validation.json --output-dir outputs --sweep-name h2_family_validation_10seed_sweep --seeds 1300 1301 1302 1303 1304 1305 1306 1307 1308 1309
python3.11 scripts/analyze_h2_family_balance.py --sweep-dir outputs/h2_family_validation_10seed_sweep --max-examples 40
python3.11 scripts/analyze_sweep_failures.py --sweep-dir outputs/h2_family_validation_10seed_sweep --contrast proposer_falsifier_minus_proposer_only --metric false_rule_accepted
python3.11 scripts/analyze_h4_sweep.py --sweep-dir outputs/paper_breadth_validation_5seed_sweep
python3.11 scripts/run_arc_diagnostic.py --config configs/arc_diagnostic_eval_learned_quick.json --output-dir outputs
python3.11 scripts/build_submission_package.py --repo-root /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project --breadth-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep --h2-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/h2_family_validation_10seed_sweep --h4-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment
python3.11 -m pytest
```

Status:

- Completed.
- Final full suite after the pass: `33 passed in 17.85s`.

Main artifacts:

- Breadth validation:
  - `outputs/paper_breadth_validation_5seed_sweep/sweep_summary.md`
  - `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`
  - `outputs/paper_breadth_validation_5seed_sweep/stratified_paired_contrasts.md`
- H2 validation:
  - `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md`
  - `outputs/h2_family_validation_10seed_sweep/failure_taxonomy.md`
  - `outputs/h2_family_validation_10seed_sweep/accepted_false_rule_examples.md`
  - `outputs/h2_family_validation_10seed_sweep/falsifier_counterexample_traces.json`
- H4 alignment:
  - `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md`
- ARC quick learned-baseline diagnostic:
  - `outputs/arc_diagnostic_eval_2task_1seed_learned_quick/arc_evaluation_summary.md`
  - `outputs/arc_diagnostic_eval_2task_1seed_learned_quick/qualitative_failures.md`
- Submission package:
  - `outputs/submission_package/submission_overview.md`
  - `outputs/submission_package/artifact_manifest.md`
  - `outputs/submission_package/appendix/claim_traceability_appendix.md`

Key bounded outcomes recorded in this pass:

- H1 strengthened on synthetic breadth diagnostics, including against the added `learned_task_mlp` baseline.
- H2 strengthened only inside compute-matched ambiguity/composition regimes.
- H4 remained weak/inconclusive as causal compression, even though exact bounded alignment was repeatedly observed.
- H5 remained weak/inconclusive as broad integrated-stack superiority.
- ARC remained a diagnostic with zero exact solve rate in the active local evaluations.

### Optional But Not Active: Full ARC Learned-Baseline Diagnostic

Command attempted:

```bash
python3.11 scripts/run_arc_diagnostic.py --config configs/arc_diagnostic_eval_learned.json --output-dir outputs
```

Status:

- Not kept as the active artifact for the paper pass.
- The run was stopped during validation because it was too slow relative to its expected value and did not improve the paper claim set.
- Use `configs/arc_diagnostic_eval_learned_quick.json` for the reproducible quick negative check unless a dedicated ARC runtime pass is started explicitly.

## Historical Note

Earlier smoke, exactness, ARC, and manuscript-hardening runs remain preserved under `outputs/` and are summarized in `RUN_HISTORY.md`. This file is now optimized for the current restart path rather than for complete historical coverage.
