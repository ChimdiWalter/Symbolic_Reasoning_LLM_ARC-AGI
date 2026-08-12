# Decisions

## D1 Minimal Dependencies

Use the available Python stack (`numpy`, `matplotlib`, `pytest`) and avoid network installs. This keeps the project reproducible in the current environment.

## D2 Synthetic Colored-Grid Formalism

Use small integer grids as the primary environment. Objects are non-background connected components. This is simple enough for deterministic ground truth and rich enough for object, relation, topology-inspired, and compositional transformations.

## D3 Honest Treatment of Mathematical Inspirations

Category-theoretic, game-semantic, topological, and algorithmic-information language is used only as conceptual motivation. Implemented approximations are:

- compositional programs over typed grid operators,
- adversarial candidate rejection through contradiction checks and oracle probes in synthetic hidden-rule worlds,
- repair through candidate-neighborhood search after controlled corruption,
- compression through MDL-like program length, sparsity, and intervention robustness proxies.

The project now also contains exact bounded checks inside explicitly declared finite systems:

- exact shortest-program search over the generated finite DSL candidate set under configured depth/color limits,
- exact integer code length under the declared DSL coding scheme,
- exact small-category law checks over enumerated finite grid domains and supplied morphisms,
- exact operator-specific support/component/hole invariant audits over enumerated finite domains.

These exact statements are bounded results, not exact Kolmogorov complexity, full categorical semantics of reasoning, or broad topological invariant theorems.

## D4 Baselines

The direct input-output baseline is implemented as a nearest-example pixel baseline, not a trained transformer, because the current environment should run without installing deep learning dependencies. The code labels it as a proxy baseline. Learned baselines can be added behind the same interface.

## D5 Falsifier Scope

The falsifier has passive checks that use only provided examples and optional interactive checks that query synthetic hidden-rule worlds. Metrics distinguish passive robustness from oracle-probe counterexample survival.

## D6 Resume Support

Experiment execution writes `run_state.json` after each model. Re-running with `--resume` skips completed model entries and regenerates reports from available results.

## D7 Behavioral Versus Syntactic Rule Recovery

The evaluation now separates exact latent-program signature recovery from held-out behavioral recovery. A syntactically different program may be equivalent or repairable on held-out examples, especially when composed operators commute. False-rule acceptance is therefore counted only when a selected wrong-signature program also fails held-out behavior. This keeps H2 from penalizing benign equivalent trajectories while preserving the stricter latent-rule recovery metric.

## D8 Formal Boundary Layer

The project includes a finite operational formalization layer in `src/reasoning_project/formal.py`. It checks exact bounded small-category identity, associativity, well-defined composition, and optional closure laws over explicit finite grid domains and supplied morphism sets. It also computes exact finite path/equivalence witnesses over supplied domains, exact bounded DSL shortest-program reports, exact DSL code lengths under the declared coding scheme, exact bounded operator-topology audits, and algorithmic-information-dynamics-inspired finite-difference profiles.

These are intentionally finite executable semantics, not full category theory, HoTT, exact unbounded AID, ARC supremacy, or an AGI proof.

## D9 Compute-Matched H2 Diagnostics

For H2 falsifier tests, compute-matched comparisons use a blind proposer-only control when enabled by config. The control spends the same logged candidate/falsifier/probe budget but discards probe outcomes for selection. This isolates the effect of using falsification evidence while keeping the result scoped to the synthetic hidden-rule diagnostic that generated it.

## D9b Revised H2 Scope

The active H2 is conditional rather than broad. The project now tests whether verification by falsification helps when multiple hypotheses fit demonstrations but diverge under perturbations, distractor settings, held-out cases, or compositional edge cases. Reports must stratify H2 by ambiguity, family, distractor condition, compositional condition, verification budget, and compute-match condition before describing any support.

## D10 ARC Adapter Boundary

ARC local evaluation is handled through a separate adapter path. ARC tasks are loaded with train/test examples and optional true test outputs from local solution files, but they do not expose known latent programs. ARC smoke runs therefore report output accuracy, runtime, and budget fields only. They do not compute latent-rule recovery and do not support ARC performance claims until a larger, pre-registered evaluation protocol is added.

## D11 ARC Diagnostic Interpretation

The bounded ARC diagnostic in `outputs/arc_diagnostic_eval_6task_3seed` is an external-validity check, not a benchmark claim. Exact ARC task accuracy was 0.000 for all tested models on the 6-task labeled evaluation subset. Pixel accuracy improved for transformation/scientist variants relative to the direct proxy, but this does not establish task solving. Future ARC expansion should first reduce runtime and improve qualitative failure handling before increasing task count.

## D12 Expanded H2 Interpretation

The expanded H2 suite adds four independently designed ambiguity probes beyond the non-commuting composition probe. The current positive H2 result should be read as conditional support in deliberately constructed ambiguity/composition strata only. It does not imply that falsification generally improves reasoning, and it should be stress-tested with more tasks per family and varied probe/distractor regimes.

## D13 Exact Bounded Semantics

Exactness is allowed only when the finite domain, DSL/operator set, coding scheme, search bound, equality notion, invariant definition, and check method are explicitly named. Current exact bounded artifacts are generated by:

- `scripts/check_exactness.py`
- `outputs/exactness/exactness_report.md`
- `outputs/exactness/topology_operator_audit.md`
- `EXACTNESS_AUDIT.md`
- `TOPOLOGY_OPERATOR_AUDIT.md`
- `exactness_traceability.md`

Anything outside those declared finite systems remains proxy-based or conceptual.

## D14 Paper-Breadth Evidence Boundary

The paper-breadth synthetic suite adds eight families beyond the original smoke set and extends H2 to seven ambiguity probes. The active paper-grade diagnostics are:

- `outputs/paper_breadth_3seed_sweep`
- `outputs/h2_paper_ambiguous_5seed_sweep`
- `outputs/paper_breadth_smoke/h4_bounded_compression`

Interpretation remains bounded:

- H1 is supported only on synthetic colored-grid structural-transfer strata.
- H2 is supported only on constructed high-ambiguity/compositional strata, and one H2 family shows no gain.
- H3 is a recovery-after-corruption diagnostic, not a task-accuracy claim.
- H4 has stronger bounded DSL-minimum evidence but remains proxy-based for causal compression.
- H5 is not broadly supported because exact task accuracy does not improve over partial stacks and ARC exact solve rate remains zero in the current diagnostic.

## D15 Action-Schema Mining Granularity (2026-07-05)

The 1000-scale promotion pass registered zero operators: 42 accepted object
programs yielded 35 distinct full (selector, action) fragment schemas with
occurrence histogram {1: 31, 2: 4} — clear action families (10x
crop_to/bbox_self, 6x recolor/induced_map) were separated ONLY by their
per-task selector predicate, which is exactly the part that legitimately
varies across tasks.

Decision: mine a SECOND, coarser granularity alongside the full schema — the
"action schema", where the whole selector predicate becomes one free
``predicate`` slot (memory._abstract_action_schema). At instantiation
(inducer._try_library_operator) the predicate hole is filled by re-running
the NORMAL zero-conflict selector induction (_induce_selector_for) for the
target group — no new enumeration machinery, same gates, same LOO
reinduction. This generalizes STAGE1_REQUIREMENTS.md Section 5.3 ("schemas =
expressions with free color/axis/scalar slots"; "parameters are always
re-induced per task") to the selector position. Identity actions
(parameterless keep) are never mined. Full schemas are still mined —
both granularities compete through the same Section 5.4 validation.

Rejected alternative: coarsening the full-schema key by abstracting feature
names inside selector predicates — that would unify semantically different
selection concepts (is_contained vs is_majority_shape) under one key and
make operator names lie about their provenance.

## D16 (2026-07-06): Phase-B forced composition after LOO rejection of a flat program

STAGE2_REQUIREMENTS 2.2 step 1 says the depth-1 search "if train-perfect:
done".  Taken literally that starves composition exactly where it is most
needed: tasks where the flat search finds an OVERFIT train-perfect program
(per-pair constants behind narrow selectors) that then fails the LOO gate —
the task dies at FailureStage.LOO even when a clean two-stage program
exists (verified on a synthetic wall+ball task: flat fit 1.0, LOO 0/3;
composed depth-2 passes 3/3 and the hidden test).

Decision: when the chosen train-perfect program is FLAT and fails LOO,
induce_program re-searches once with force_compose=True under the SAME
task deadline (budget discipline 2.2.3 intact).  In force mode the stage-1
candidate pool additionally contains one-rule-out ablations of the
rejected flat programs (dropping a rule exposes its group as residual for
a fresh stage-2 table where its parameters may be relationally
expressible).  The ENTIRE forced search re-runs per LOO fold
(_fold_inducer_forced), so LOO-by-reinduction remains the only blocking
gate and validates the exact procedure that produced the candidate.

Rejected alternatives: (a) always exploring composition even when a flat
program fits — wastes budget on the overwhelmingly common honest-flat
case; (b) treating the overfit program itself as stage 1 — its residual is
zero on train, so any stage 2 is an identity stage, which 2.2.2 forbids.
