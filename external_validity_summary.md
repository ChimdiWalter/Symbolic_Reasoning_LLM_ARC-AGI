# External Validity Summary

## Local Data Availability

`data/arc/` contains local ARC-AGI-style JSON files:

- `data/arc/arc-agi_training_challenges.json`
- `data/arc/arc-agi_training_solutions.json`
- `data/arc/arc-agi_evaluation_challenges.json`
- `data/arc/arc-agi_evaluation_solutions.json`
- `data/arc/arc-agi_test_challenges.json`
- `data/arc/sample_submission.json`

Training and evaluation splits have local solution files. The test split has challenge and sample-submission files but no local ground-truth solution file. The newer audit in `outputs/arc_status/arc_agi2_status.md` and `outputs/arc_status/arc_agi2_status.json` confirms that the files are adapter-compatible but does not justify a clean ARC-AGI-2 provenance claim from filenames alone.

## ARC Diagnostic Status

The local ARC adapter and diagnostic runner are implemented:

- `src/reasoning_project/arc_adapter.py`
- `src/reasoning_project/arc_diagnostic.py`
- `scripts/run_arc_smoke.py`
- `scripts/run_arc_diagnostic.py`
- `configs/arc_smoke_tiny.json`
- `configs/arc_diagnostic_eval.json`
- `configs/arc_diagnostic_eval_learned_quick.json`

Completed diagnostic artifact:

- `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md`
- `outputs/arc_diagnostic_eval_2task_1seed_learned_quick/arc_evaluation_summary.md`
- `outputs/arc_status/arc_local_status.md`
- `outputs/arc_status/arc_agi2_status.md`
- `outputs/arc_status/arc_agi2_status.json`
- `outputs/arc_refinement/arc_refinement_smoke/summary.json`
- `outputs/arc_refinement/arc_refinement_smoke/reasoning_manifold/reasoning_manifold_summary.json`
- `outputs/submission_package/figures/fig_arc_external_validity.png`
- `outputs/submission_package/tables/table_arc_external_validity.md`

Result boundary:

- ARC exact task accuracy is `0.000` for all tested models on the 6-task/3-seed diagnostic.
- Pixel accuracy improves from `0.432` for `direct_io_proxy` to `0.555` for transformation/scientist variants.
- Mean candidate budget is `60.0` for `transformation_library`, `proposer_falsifier`, and `integrated_scientist`, versus `0.0` for `direct_io_proxy`.
- Mean runtime is `1.312` seconds for `transformation_library`, `2.630` for `proposer_falsifier`, and `9.854` for `integrated_scientist`.
- A quick learned-baseline ARC diagnostic over 2 tasks and 1 seed also remained at exact task accuracy `0.000` and pixel accuracy `0.000`, with mean runtime `1.357` seconds versus `3.382` seconds for `transformation_library`.
- This is diagnostic evidence only. It is not an ARC benchmark claim.
- The bounded neural-guided refinement slice over 2 labeled evaluation tasks also remains at exact solve rate `0.000` and pass@2 `0.000` for all methods, including `neural_dsl_ranker`, `grid_jepa_dsl_ranker`, `refinement_loop_tta`, and `integrated_scientist_neural_proposer`.
- On that 2-task slice, mean pixel accuracy is `0.495` for every method because one task is a complete miss and one task is a near-match for all methods.
- The associated REMA-inspired manifold artifact has no solved-task manifold to characterize on this slice.

## Other Local Reasoning Tasks

The current repository inspection found no additional local external reasoning datasets beyond ARC and the existing synthetic hidden-rule framework. The safe extension added in this phase is an expanded synthetic external-validity-style breadth suite rather than a new download:

- `configs/paper_breadth_validation.json`
- `outputs/paper_breadth_validation_5seed_sweep/sweep_summary.md`
- `outputs/paper_breadth_validation_5seed_sweep/stratified_paired_contrasts.md`

This extension broadens synthetic coverage across compositional, distractor-heavy, nuisance-heavy, topology-relevant, causal-vs-spurious, and repair-relevant families. It is still synthetic and cannot replace ARC or other external datasets.
