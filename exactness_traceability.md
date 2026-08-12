# Exactness Traceability

| Exact Bounded Claim | Code Module | Test | Generated Artifact | Domain / Bound | Status |
| --- | --- | --- | --- | --- | --- |
| Exact shortest program in finite DSL search space | `src/reasoning_project/formal.py::bounded_exact_dsl_minimum` | `tests/test_formal.py::test_bounded_exact_dsl_minimum_finds_identity_program`, `tests/test_formal.py::test_bounded_exact_dsl_minimum_finds_reflection_program` | `outputs/exactness/exactness_report.md` | `candidate_programs(max_depth=1, colors=[1,2])`; exact array equality on supplied examples | implemented and tested |
| Exact integer code length under declared DSL coding scheme | `src/reasoning_project/formal.py::program_code_length_units` | `tests/test_formal.py::test_bounded_exact_dsl_minimum_finds_identity_program` | `outputs/exactness/exactness_report.json` | base operator costs scaled by 20, plus parameter key/value units | implemented and tested |
| Exact small-category law checks over finite grids | `src/reasoning_project/formal.py::check_finite_category_laws` | `tests/test_formal.py::test_exact_small_category_closure_for_reflection_group` | `outputs/exactness/exactness_report.md` | all binary 2x2 grids; four reflection-group morphisms; extensional equality | implemented and tested |
| Exact finite extensional program equality | `src/reasoning_project/formal.py::programs_extensionally_equal` | `tests/test_formal.py::test_finite_path_witness_distinguishes_equivalence_scope` | `outputs/formal_boundary/formal_report.json`, `outputs/exactness/exactness_report.json` | supplied finite domain only | implemented and tested |
| Exact finite path/equivalence witness | `src/reasoning_project/formal.py::finite_path_witness` | `tests/test_formal.py::test_finite_path_witness_distinguishes_equivalence_scope` | `outputs/formal_boundary/formal_report.json` | supplied finite domain only | implemented and tested |
| Exact operator-specific topology invariant audit | `src/reasoning_project/formal.py::audit_operator_topology_suite` | `tests/test_formal.py::test_operator_topology_audit_preserves_and_finds_counterexamples` | `outputs/exactness/topology_operator_audit.md`, `outputs/exactness/topology_operator_audit.json` | all binary 3x3 grids plus selected colored 3x3 probes | implemented and tested |
| ARC exact output scoring when solutions exist | `src/reasoning_project/arc_adapter.py::evaluate_arc_prediction` | `tests/test_arc_adapter.py` | `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md` | labeled ARC training/evaluation splits only | implemented and bounded |
| H4 comparison of proxy MDL to exact bounded minima | `src/reasoning_project/h4_analysis.py::write_h4_bounded_compression_analysis` | `tests/test_h4_analysis.py` | `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md` | finite run candidate set from `configs/paper_breadth_smoke.json`; exact train-example equality | implemented and tested |

Manuscript table: `exact_vs_proxy_table.md`.

## Claims Kept Proxy-Based

- Exact Kolmogorov complexity: impossible in general; not claimed.
- Exact AID: not implemented; current AID profile remains finite-difference proxy.
- General categorical semantics of reasoning: not implemented.
- Broad topology theorem over all grids/operators: not implemented.
- ARC latent-rule recovery: unavailable because ARC files do not provide latent programs.
