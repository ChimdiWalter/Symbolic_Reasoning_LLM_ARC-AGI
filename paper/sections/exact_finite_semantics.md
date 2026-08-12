# Exact Finite Semantics

The exact layer is the cleanest formal contribution. Every exact claim names a finite domain, candidate set, equality notion, coding scheme, and artifact path.

**Proposition 1: Exact bounded DSL minimality.** For a finite candidate set `C = candidate_programs(max_depth, colors)`, finite examples `E`, exact grid equality, and declared integer code length `L`, exhaustive enumeration returns the exact minimum `L(p)` among programs `p in C` that match every example in `E`. Evidence: `src/reasoning_project/formal.py::bounded_exact_dsl_minimum`, `tests/test_formal.py`, and `outputs/exactness/exactness_report.md`.

**Proposition 2: Exact small-category laws on finite domains.** For a supplied finite grid domain, supplied executable morphism set, identity map, sequential composition, and extensional equality over all grids in the domain, identity, associativity, well-defined composition, and closure are decidable by exhaustive evaluation. Evidence: `src/reasoning_project/formal.py::check_finite_category_laws` and `outputs/exactness/exactness_report.md`.

**Proposition 3: Exact operator-specific topology audit.** For supplied operator instances, a finite grid domain, and declared support-mask, 4-connected component-count, and hole-count invariants, exhaustive evaluation exactly classifies whether each operator preserves the invariants on that domain and stores counterexamples for failures. Evidence: `src/reasoning_project/formal.py::audit_operator_topology_suite` and `outputs/exactness/topology_operator_audit.md`.

These propositions are exact only in their declared finite systems. They are not exact Kolmogorov complexity, a general categorical semantics of reasoning, full HoTT, exact unbounded AID, or broad topology theorems.
