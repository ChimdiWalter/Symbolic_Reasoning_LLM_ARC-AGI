# Appendix

## Exact Vs Proxy Vs Not Claimed

| Contribution area | Status | Implemented as | Artifact path | Boundary |
| --- | --- | --- | --- | --- |
| Bounded DSL shortest program | exact bounded | Exhaustive minimum over `candidate_programs(max_depth, colors)` under exact example equality and declared integer code length. | `outputs/exactness/exactness_report.md`; `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md` | Not exact Kolmogorov complexity or global program minimality. |
| Small-category laws | exact bounded | Objects are enumerated grid states; morphisms are executable programs; equality is finite extensional equality. | `outputs/exactness/exactness_report.md` | Not a general categorical semantics of reasoning. |
| Operator topology | exact bounded | Exhaustive support-mask, component-count, and hole-count audits over bounded domains. | `outputs/exactness/topology_operator_audit.md` | Not a broad topological theorem. |
| H2 falsification | empirical diagnostic | Compute-matched proposer-only versus proposer-falsifier contrasts on constructed ambiguity probes. | `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md` | Conditional support only. |
| H4 compression | proxy plus bounded comparison | MDL-style selector compared against exact bounded DSL minima. | `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md` | Does not establish exact AID or causal discovery. |
| ARC evaluation | external-validity diagnostic | Output accuracy and runtime/budget reporting on local labeled ARC tasks. | `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md` | No ARC benchmark claim; exact solve rate remains zero. |
| Neural-guided executable reasoning | bounded empirical diagnostic | Grid encoders, Grid-JEPA latent prediction, neural candidate ranking, bounded ARC refinement, and REMA-inspired latent failure analysis. | `outputs/arc_status/arc_agi2_status.md`; `outputs/neural/program_ranker_smoke/metrics.json`; `outputs/arc_refinement/arc_refinement_smoke/summary.json` | Implemented and reproducible, but no exact ARC improvement in the current smoke slice. |

## Claim Traceability

The canonical traceability table is `claim_traceability.md`. Exact bounded claims are traced in `exactness_traceability.md`. The paper-facing compact appendix is `outputs/submission_package/appendix/claim_traceability_appendix.md`.

## Submission Package

Final paper-facing figures and tables are collected in `outputs/submission_package`.

- figures: `outputs/submission_package/figures`
- tables: `outputs/submission_package/tables`
- artifact manifest: `outputs/submission_package/artifact_manifest.md`
- reproducibility checklist: `outputs/submission_package/reproducibility_checklist.md`
- qualitative case studies: `outputs/submission_package/tables/table_case_studies.md`
- accepted false-rule examples: `outputs/submission_package/tables/table_h2_accepted_false_rules.md`
- ARC qualitative failures: `outputs/submission_package/tables/table_arc_qualitative_failures.md`
- exact-semantics model-difference examples: `outputs/submission_package/tables/table_exact_semantics_model_difference.md`
