# Exact Vs Proxy Vs Not Claimed

| Contribution Area | Status | Implemented As | Artifact Path | Boundary |
| --- | --- | --- | --- | --- |
| Bounded DSL shortest program | exact bounded | Exhaustive minimum over `candidate_programs(max_depth, colors)` under exact example equality and declared integer code length. | `outputs/exactness/exactness_report.md`; `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md` | Not exact Kolmogorov complexity or global program minimality. |
| DSL code length | exact bounded | `operator_base_cost * 20 + 3 per parameter key + parameter-value character count`. | `outputs/exactness/exactness_report.json` | Coding-scheme dependent. |
| Small-category laws | exact bounded | Objects are enumerated grid states; morphisms are executable programs; equality is finite extensional equality. | `outputs/exactness/exactness_report.md` | Not a general categorical semantics of reasoning. |
| Path/equivalence witness | exact bounded | Syntactic identity, finite extensional equivalence, or non-equivalence over supplied domains. | `outputs/formal_boundary/formal_report.json`; `exactness_traceability.md` | Not HoTT identity types or univalence. |
| Operator topology | exact bounded | Exhaustive support-mask, component-count, and hole-count audits over bounded grid domains. | `outputs/exactness/topology_operator_audit.md` | Not a broad topological theorem. |
| H2 falsification | empirical diagnostic | Compute-matched proposer-only versus proposer-falsifier contrasts on constructed ambiguity probes. | `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md` | Conditional support only; one H2 family shows no gain. |
| H4 compression | proxy plus bounded comparison | MDL-style selector compared against exact bounded DSL minima where feasible; multi-seed alignment is summarized separately. | `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md`; `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md` | Does not establish exact AID or causal discovery. |
| ARC evaluation | external-validity diagnostic | Output accuracy and runtime/budget reporting on local labeled ARC evaluation tasks. | `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md` | No ARC benchmark claim; exact solve rate remains zero in current diagnostic. |
| AGI/path-to-AGI | not claimed | Not implemented. | `FORMAL_BOUNDARIES.md` | Out of scope. |
