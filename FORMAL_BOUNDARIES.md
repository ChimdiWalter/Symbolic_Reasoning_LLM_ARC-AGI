# Formal Boundaries

This project does not fully operationalize category theory, HoTT, or algorithmic information dynamics in their complete mathematical forms. It also does not beat all ARC systems outright or prove a path to AGI.

What the project now implements is a finite, auditable formal boundary layer in `src/reasoning_project/formal.py`. Some claims are exact, but only after the finite domain, DSL, coding scheme, search bound, equality notion, and invariant definition are fixed.

Summary table: `exact_vs_proxy_table.md`.

## Description-Length Scope

Implemented:

- Exact integer code length under the project's declared finite DSL coding scheme.
- Exact shortest-program search over `candidate_programs(max_depth, colors)` for supplied examples.
- Exact output equality checks on every supplied input-output example.
- Generated evidence in `outputs/exactness/exactness_report.md`.

Current bounded claim:

- For the exactness report, the search is over `candidate_programs(max_depth=1, colors=[1,2])`.
- The description domain is all binary 2x2 grids.
- The code length is `operator_base_cost * 20 + 3 * parameter_key_count + parameter_value_character_count`.

Not implemented:

- Exact Kolmogorov complexity.
- A search over all possible programs or all computable functions.
- Proof that a selected program is globally minimal outside the generated finite DSL space.

## Category-Theoretic Scope

Implemented:

- Objects are finite typed grid states in an explicitly enumerated domain.
- Morphisms are executable grid programs supplied to the checker.
- Program composition is sequential execution.
- Identity is the `identity` operator.
- Equality is extensional equality over every grid in the supplied finite domain.
- Identity, associativity, well-defined composition, and optional closure can be checked exactly over the supplied finite system.

Current bounded claim:

- `outputs/exactness/exactness_report.md` checks the four-morphism reflection group over all binary 2x2 grids.
- Identity, associativity, well-defined composition, and closure hold for that supplied finite category candidate.

Not implemented:

- A general categorical semantics of reasoning.
- Universal properties, adjunctions, enriched categories, toposes, or categorical proofs.
- Proof that the discovered rules are canonical outside the tested finite domain.

## HoTT / Path Scope

Implemented:

- Exact finite path witnesses between programs on a supplied finite domain.
- A distinction between syntactic identity, finite extensional equivalence, and non-equivalence on a supplied domain.
- Operational support for the path-repair hypothesis: wrong-signature programs may still be behaviorally equivalent or repairable.

Not implemented:

- Full identity types.
- Univalence.
- Higher inductive types.
- Machine-checked proof terms.
- A formal HoTT semantics for grid reasoning.

## Algorithmic Information Dynamics Scope

Implemented:

- Program description-length proxies.
- Exact bounded DSL code length and shortest-program reports under the declared finite DSL coding scheme.
- Grid complexity proxies based on support, color diversity, and shape.
- Finite-difference intervention profiles that measure how small input perturbations change output complexity and output behavior.

Not implemented:

- Exact Kolmogorov complexity.
- Exact algorithmic probability.
- Formal causal discovery guarantees from AID.
- Proof that the selected program is globally minimal outside the generated finite DSL search space.

## Topology Scope

Implemented:

- Exact operator-specific topology audits under a declared finite support-topology definition.
- Invariants: color-insensitive support mask, 4-connected support component count, and support hole count.
- Exhaustive checks over all binary 3x3 grids plus selected colored 3x3 probes in `outputs/exactness/topology_operator_audit.md`.
- Explicit finite counterexamples for operators that fail an invariant.

Not implemented:

- Broad topological invariant theorems over all grids and all operators.
- Algebraic-topology invariants beyond the declared finite support/component/hole summaries.
- Proofs outside the enumerated finite domains.

## ARC And AGI Scope

Implemented:

- ARC-style synthetic colored-grid diagnostics.
- Local ARC adapter and bounded diagnostic runner when ARC-AGI JSON files are present under `data/arc/`.
- Baseline and scientist-model ablations with saved metrics.

Not implemented or claimed:

- State-of-the-art ARC performance.
- Beating all ARC systems.
- A proof of a full path to AGI.
- Any empirical claim beyond the generated experiments.

Current ARC diagnostic boundary:

- `outputs/arc_diagnostic_eval_6task_3seed` is an external-validity diagnostic only.
- It reports output accuracy, pixel accuracy, runtime/budget fields, and qualitative failures.
- It does not compute ARC latent-rule recovery because local ARC files do not expose generating programs.

## Honest Reading

The formal layer is useful because it makes the mathematical metaphors testable in miniature. It should be read as exact bounded executable semantics where the finite system is declared, and as proxy-based inspiration everywhere else.

## H2 Falsification Scope

The active H2 is no longer a broad adversarial-truth claim. It is a conditional verification-by-falsification hypothesis: falsification is expected to help mainly when multiple train-fitting hypotheses diverge under perturbations, held-out cases, distractors, or compositional edge cases.

Implemented:

- Train-fit candidate counts as an empirical ambiguity proxy.
- Task metadata for designed ambiguity, distractor condition, and compositional condition.
- Logged verification budget and compute-match fields.
- Stratified paired contrasts for proposer-only versus proposer-falsifier comparisons.

Not implemented or claimed:

- A general truth predicate for reasoning.
- Evidence that falsification generally improves reasoning.
- Support for H2 outside the strata and budgets where repeated-seed contrasts show an effect.
