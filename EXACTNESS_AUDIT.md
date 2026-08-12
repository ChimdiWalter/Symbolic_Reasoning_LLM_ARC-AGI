# Exactness Audit

This audit separates exact bounded claims from proxy or impossible unbounded claims. Every exact statement here is scoped to a named finite domain, DSL, coding scheme, search bound, equality notion, and check method.

Primary generated artifact: `outputs/exactness/exactness_report.md`.

## Proposition-Style Exact Claims

Proposition 1, exact bounded DSL minimality:
For finite candidate set `C = candidate_programs(max_depth, colors)`, finite example set `E`, exact grid equality, and declared integer code length `L`, `bounded_exact_dsl_minimum` returns the exact minimum `L` among programs in `C` that match every example in `E`. This is an exhaustive finite optimization statement, not exact Kolmogorov complexity.

Proposition 2, exact finite small-category laws:
For a supplied finite grid domain and supplied finite morphism set, `check_finite_category_laws` exactly checks identity, associativity, well-defined composition, and optional closure by extensional equality over the domain. This is a finite small-category check, not a general categorical semantics of reasoning.

Proposition 3, exact operator-specific topology classification:
For a supplied finite grid domain, supplied operator instances, and declared support/component/hole invariants, `audit_operator_topology_suite` exactly classifies each operator instance and stores finite counterexamples for invariant failures. This is not a broad topological theorem.

| Area | Status | Bounded Claim | Domain / Bound | Code / Check | Non-Claim |
| --- | --- | --- | --- | --- | --- |
| DSL program search | can be upgraded to exact bounded form | The project can compute the exact shortest program among `candidate_programs(max_depth, colors)` that exactly matches supplied examples. | `max_depth=1`, `colors=[1,2]` in the generated report; general function accepts configured finite bounds. | `src/reasoning_project/formal.py::bounded_exact_dsl_minimum`; `tests/test_formal.py` | Not a search over all possible programs. |
| MDL scoring | can be upgraded to exact bounded form | The project has an exact integer code length under the declared DSL coding scheme. | Operator base cost scaled by 20, plus 3 units per parameter key, plus 1 unit per parameter-value character. | `src/reasoning_project/formal.py::program_code_length_units`; `outputs/exactness/exactness_report.json` | Not exact Kolmogorov complexity. |
| Finite category laws | already exact in bounded form, now stated more precisely | Identity, associativity, well-defined composition, and closure can be checked exactly over supplied finite grids and morphisms. | `outputs/exactness`: all binary 2x2 grids; morphisms `identity`, `reflect_horizontal`, `reflect_vertical`, `rotate_180`. | `src/reasoning_project/formal.py::check_finite_category_laws`; `tests/test_formal.py` | Not a general categorical semantics of reasoning. |
| Operator equality | already exact in bounded form | Program equality is exact extensional equality over every grid in the supplied finite domain. | Any enumerated finite domain passed to `programs_extensionally_equal`. | `src/reasoning_project/formal.py::programs_extensionally_equal` | Not global equality over all grids unless that full domain is enumerated. |
| Path/equivalence witnesses | already exact in bounded form | A path witness exactly classifies syntactic identity, finite extensional equivalence, or non-equivalence on a supplied finite domain. | Test domain in `tests/test_formal.py`; generated formal reports use finite task examples. | `src/reasoning_project/formal.py::finite_path_witness` | Not HoTT identity types or univalence. |
| Topology-preserving operator checks | can be upgraded to exact bounded form | Operators can be classified by exact support-mask, component-count, and hole-count preservation over a finite grid domain. | `outputs/exactness`: all binary 3x3 grids plus selected colored 3x3 probes. | `src/reasoning_project/formal.py::audit_operator_topology_suite`; `outputs/exactness/topology_operator_audit.md` | Not a broad topological invariant theorem over all grids/operators. |
| ARC boundaries | cannot be made exact without changing scope | ARC output accuracy is exact when local solutions exist. ARC latent-rule recovery is not available. | Local ARC training/evaluation solution files only. | `src/reasoning_project/arc_adapter.py`; `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md` | No ARC latent programs, no leaderboard claim. |

## Current Exact Bounded Results

From `outputs/exactness/exactness_report.md`:

- Exact bounded DSL minimum, identity case: 31 candidates, 7 exact-fitting candidates, minimum 4 code units, unique minimum `identity`.
- Exact bounded DSL minimum, reflection case: 31 candidates, 1 exact-fitting candidate, minimum 20 code units, unique minimum `reflect_vertical`.
- Exact small-category check: identity, associativity, composition well-definedness, and closure all hold for the four supplied reflection-group morphisms over all binary 2x2 grids.
- Topology audit: exact operator-specific classifications are reported for 31 DSL operator instances over all binary 3x3 grids plus selected colored 3x3 probes.

## Impossible Or Still Proxy-Based

- Exact Kolmogorov complexity remains impossible in general and is not claimed.
- A general categorical semantics of reasoning is not implemented.
- HoTT identity types, univalence, and machine-checked proof terms are not implemented.
- General topological invariant theorems over all operators and all grids are not claimed.
- AID remains a finite-difference / MDL-style proxy outside the exact bounded DSL code-length layer.

## Exact Vs Proxy Vs Not Claimed

| Item | Status | Active Wording |
| --- | --- | --- |
| Bounded DSL shortest program | exact bounded | Exact minimum over `candidate_programs(max_depth, colors)` under declared code length and exact example equality. |
| DSL code length | exact bounded | Exact integer code length under the project coding scheme. |
| Small-category laws | exact bounded | Exact identity/associativity/well-definedness/closure checks over supplied finite domains and morphisms. |
| Program equality/path witness | exact bounded | Exact finite extensional equality or non-equivalence over supplied domains. |
| Operator topology | exact bounded | Exact support/component/hole invariant classification over audited finite domains. |
| Compression selector | proxy | MDL-style/intervention/nuisance proxy; can be compared to bounded DSL minima where feasible. |
| AID | proxy | Finite-difference complexity/intervention profiles only. |
| ARC scoring | exact output scoring only | Exact output accuracy where local solutions exist; no latent-rule recovery. |
| Kolmogorov complexity | not claimed | Impossible in general and not computed. |
| Full category theory / HoTT | not claimed | No univalence, proof terms, universal properties, or general semantics. |
| Broad topology theorem | not claimed | No theorem over all grids/operators. |
