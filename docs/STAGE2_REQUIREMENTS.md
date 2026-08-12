# Stage 2 Requirements: Depth-3 Typed Program Search with Ranked Candidates

Date: 2026-07-05.
Status: implementation requirements distilled from `WAY_FORWARD.md` Section 4 (Stage 2),
`docs/STAGE1_REQUIREMENTS.md` (binding constraints carried over verbatim), `DECISIONS.md`
(D3, D13, D15), and two fresh code surveys (2026-07-05) of
`geocat_arc/object_reasoning/{inducer,engine,types}.py` and
`geocat_arc/bayesian_program_search/*` (details below; line references verified).

Baseline to beat (verified): **151/1000** submission-valid under the 3-layer harness
(`outputs/unified_harness_v2/results.json`), induced_fraction 0.510, object layer 42 solves
(27 unique). Library: 2 validated operators (`outputs/object_reasoning_promotion_v3/library.json`,
D15 predicate-slot mining). Milestone B target: **>=200/1000**. Milestone C: **>=270/1000 with
mean accepted-program composition depth > 1.5**.

Target populations (from `outputs/failure_landscape_2026_07_02.json` measured categories,
minus tasks solved since):
- `object_new_shapes` (~214 at measurement): draw / extend / complete — reachable only by
  composition (select anchors -> generate strokes/completions relative to them).
- Residual same-shape and shrink failures where a single flat rule pass cannot express the
  transformation but two or three chained passes can (e.g. move-then-recolor, delete-then-fill,
  crop-then-tile).

## 0. The user's directive (binding — unchanged from Stage 1)

No new hand-coded task-specific solvers. Programs are CREATED by induction from each task's
train pairs over a fixed generic hypothesis space. LOO-by-reinduction is the only blocking
acceptance gate. Near-solves are training data and must be persisted. Submission mode only.
Report induced_fraction honestly. No task-ID branches anywhere.

Consequence for Stage 2 specifically: a composed program is accepted only if the ENTIRE
composed induction (all stages, including ranking) re-runs from N-1 pairs per LOO fold and
reproduces the held-out pair. Validating an already-found composition against the held-out
pair is NOT acceptance.

## 1. What exists today (verified 2026-07-05, do not re-derive)

Object-engine search (`geocat_arc/object_reasoning/inducer.py`):
- Outer loop over segmentation variants S1,S2,S3,S5,S4,S6,S7 (types.py:48-56;
  MAX_SEG_VARIANTS_TRIED=4), inner tier ladder in `_induce_on_table` (inducer.py:1730-1814):
  tier 1 (one rule per delta type, early-exit if all train-perfect), tier 1b (KEEP-absorption),
  tier 2a (parameter-signature subgroups), tier 2b (feature-value splits).
- Tiers 1b/2a/2b already COLLECT-ALL train-perfect programs and rank canonically
  (`rank_candidates`, inducer.py:1807) — Stage 1 round 3 removed first-match-wins WITHIN a
  tier. What remains first-match: correspondence alternatives (first train-perfect alternative
  breaks, inducer.py:2237) and library-operator hits per group (inducer.py:1579).
- Programs are FLAT: `ObjectProgram` = segmentation variant + ordered selector->action rules +
  default action + output_spec (types.py:506-604). Rules all read the ORIGINAL input's object
  table; `program_depth` = 3 + len(rules) is a step count, NOT composition. There is no
  program-to-program chaining anywhere (DeltaType.COMPOSITE is a fused single-object delta,
  not composition).
- LOO: `loo_validate` (inducer.py:2127-2155) re-runs the FULL search per fold via
  `_fold_inducer` with per-fold deadlines. Budget: cooperative `_check_deadline` raising
  `_BudgetExhausted`, caught so best-so-far survives (inducer.py:1803, 2248).
- `InductionConfig` (inducer.py:128-143): budget_s=60, max_selector_literals=2,
  max_expr_depth=2, max_rules=4, use_library, library, collect_all_in_tier.

Bayesian search guide (`geocat_arc/bayesian_program_search/`):
- REUSE AS-IS (zero coupling, pure numpy/scipy): `bayes_ranker.py` (BayesianLinearRanker —
  online Bayesian linear regression, `rank_candidates` by UCB), `acquisition.py` (ucb,
  expected_improvement, thompson_sample), `search_trace.py` (SearchTrace/SearchRecord JSONL).
- NEEDS ADAPTERS: `program_features.py` (duck-types `.operator_names`/`.steps`; an
  ObjectProgram silently featurizes to zeros — must add an ObjectProgram/ComposedProgram
  branch and delta-type name sets), `real_objective.py` (`evaluate_program` expects
  `program.apply(grid)`; wrap `actions.render_program`).
- REPLACE: `search_loop.py` control flow is right (featurize -> rank by acquisition ->
  evaluate -> update posterior -> track best) but is bound to `categorical_dsl.RuleSchema`;
  write `bayesian_search_v2(candidates, score_fn, feature_fn, ...)` with injected sources.
- DEAD WEIGHT: `candidate_generator.py` (hardcoded old-DSL template enumeration) — bypassed
  entirely; Stage-2 candidates come from the object inducer.

## 2. Hypothesis space extension: typed composition

### 2.1 ComposedProgram (new, in object_reasoning/types.py)

`ComposedProgram` = ordered list of 1..3 `ObjectProgram` stages. Semantics: stage k+1 receives
stage k's rendered output grid as its input (full re-segmentation, fresh feature table, fresh
correspondence against the FINAL target). Depth 1 == today's flat program (backward
compatible; a depth-1 ComposedProgram serializes/behaves identically to its single stage for
all Stage-1 artifacts).

Requirements:
- 2.1.1 JSON round-trip via to_dict/from_dict with `program_class` tag; a fresh process must
  deserialize and re-render exactly (extends the Stage-1 serialization audit to compositions).
- 2.1.2 `composition_depth` (number of stages) is a first-class recorded metric, distinct from
  the step-count `program_depth`. Milestone C's "mean depth > 1.5" refers to composition_depth.
- 2.1.3 Certificates record per-stage provenance (which residual induced each stage, which
  library operators were used per stage).

### 2.2 Stage induction is residual-driven (the near-solve machinery becomes generative)

Intermediate grids are not observable from train data. Stage-2 induction therefore works on
residuals, exactly the data the near-solve store already captures:

1. Run the Stage-1 (depth-1) search. If train-perfect: done (depth 1).
2. Otherwise take the top-K partial programs (by explained-fraction, already computed for
   NearSolveRecords) as stage-1 candidates. For each: render its output per train pair ->
   new pair set (rendered, target) -> recursively induce the next stage on those pairs with
   the remaining depth and remaining budget.
3. A composition is train-perfect iff the final rendered grid equals the target on every pair.

Requirements:
- 2.2.1 Partial-program candidates come ONLY from the generic near-solve thresholds (Stage 1
  Section 5.1) — no per-task tuning of K or thresholds. K is a global config field
  (default 4, `max_stage_candidates`).
- 2.2.2 Depth cap 3 (config `max_composition_depth`, default 3). Identity stages are never
  admitted (a stage must strictly reduce residual on at least one pair — monotone progress
  requirement; prevents search blowup and trivial padding).
- 2.2.3 Budget partitioning: the per-task budget is shared across the composition tree
  cooperatively (same `_check_deadline` mechanism); no stage gets a private wall-clock that
  could multiply total cost. Global default budget stays 60 s for dev evals; the harness
  keeps its 90 s cooperative / 105 s hard cap.
- 2.2.4 Every failed composition attempt that meets near-solve thresholds is itself persisted
  as a NearSolveRecord (with stage-1 fragment recorded) — compositions feed the cumulative
  loop like everything else.

## 3. Ranking replaces first-match-wins (the ranker's first real job)

### 3.1 Candidate scoring

All train-perfect candidates (flat and composed, across correspondence alternatives — the
remaining first-match sites listed in Section 1 are removed) enter one pool scored by:

  score = train_fit (=1.0 for train-perfect; fractional for partial during search guidance)
        + w_loo * LOO_margin (fraction of folds passed, from the blocking gate — never a
          substitute for it)
        + w_len * length_penalty (MDL proxy per D3: expression_size + rules + stages)

Deterministic tie-break by the existing canonical program key so fold-invariance is preserved
(round-3 fold-deterministic ranking requirement carries over: the ranker must produce the
same order given the same candidate set regardless of fold, or LOO-by-reinduction breaks).

- 3.1.1 The FINAL accepted program among gate-passing candidates is chosen by this
  deterministic score, not by discovery order.
- 3.1.2 The BayesianLinearRanker guides SEARCH ORDER (which stage-1 partial to expand next,
  which segmentation/alternative to try next) via UCB over program features; its training
  signal is the realized score of evaluated candidates within the task (online, per-task
  posterior; no cross-task state inside a fold — determinism requirement).
- 3.1.3 Cross-task warm-start (posterior initialized from the accepted-program corpus) is an
  EXPERIMENT behind a flag (`--ranker-warm-start`), evaluated by the Milestone D contrast
  method, OFF by default (order-effect honesty, Stage 1 Requirement 1.2).

### 3.2 Feature adapter

`program_features.extract_features` gets an ObjectProgram/ComposedProgram branch: dimensions
for composition_depth, rules count, expression_size, selector literal count, delta-type
one-hots (KEEP/DELETE/TRANSLATE/RECOLOR/COPY/...), segmentation variant, library-operator
count, parameter-class one-hots. Feature names centrally registered; vector dim fixed and
versioned (the ranker requires fixed dim).

### 3.3 Ablation flags (Requirement, mirrors --no-library)

`--no-ranker` (fall back to canonical-order search) and `--depth-1` (Stage-1 behavior) must
both be runnable from `scripts/run_object_dev_eval.py`, so the Stage-2 claim ("ranking +
composition added X solves") is measurable, not asserted.

## 4. Acceptance gates (unchanged in kind, extended in scope)

- 4.1 LOO-by-reinduction over the WHOLE Stage-2 search: per fold, re-run segmentation trial,
  tier ladder, residual-driven composition, and ranking from N-1 pairs. Single-pair tasks:
  same constant-parameter rejection rule as Stage 1.
- 4.2 Falsification probes stay advisory (2026-06-15 lesson); LOO remains the only blocking
  gate. Composed programs additionally re-render exactly from JSON in a fresh process
  (Section 2.1.1) before acceptance.
- 4.3 Zero-regression bar: dev-19, sample-30, and the 60-task smoke must retain every
  previously solved task (compare via scripts/compare_eval_rounds.py, exit 0 required)
  before any full run.

## 5. Library interaction

- 5.1 Library operators participate inside every stage's group induction exactly as today
  (inducer.py:1573-1581); nothing new needed for depth-1.
- 5.2 After the first Stage-2 full run, re-run promotion (`scripts/run_library_promotion.py`)
  over the enlarged accepted-program corpus: D15 predicts more schemas cross the >=3 gate as
  program count grows; per-stage fragments of ComposedPrograms are mined as separate
  fragments (a stage is an ObjectProgram — existing mining applies unchanged).
- 5.3 Loop-closure metric to report each round: number of accepted programs whose
  `library_operators_used` is non-empty (first instance: b2862040 via op_recolor_by_slot,
  2026-07-05).

## 6. Evaluation protocol

1. Unit tests for every new type/function (suite currently 310 green; keep green).
2. Dev evals at default 60 s: dev-19 and sample-30 vs round-3/libgain baselines (zero
   regressions; new-solve counts reported per ablation cell: {depth-1, depth-3} x
   {ranker, no-ranker}).
3. Composition dev set: select ~20 unsolved `object_new_shapes` + multi-step-looking tasks
   from the failure landscape BY CATEGORY QUERY (not hand-picked IDs; record the query) as
   the Stage-2 dev probe.
4. 60-task 3-layer smoke, then FULL 1000-task run into `outputs/unified_harness_v4/` (new
   dir). Report: solved, induced_fraction, mean composition_depth, per-origin counts,
   library-usage count, honest gaps (train+LOO-pass-test-wrong list).
5. Paper-ready analyses (queued from Stage 1, unblocked by this run's data): LOO-gate
   calibration (acceptance precision vs hidden test) and frozen-system transfer on the ARC
   evaluation split.

## 7. Non-goals for Stage 2

- No neural ranker training (Stage 3; the linear posterior is enough for the first real job).
- No new segmentation variants or feature/relation registry growth unless a measured
  composition failure demands one (then it enters through the normal generic path).
- No cross-task memory inside the solve path beyond the validated library (order-effect
  honesty; Milestone D contrast stays a Stage-3 claim).
- No touching `outputs/unified_harness_v2/` artifacts (frozen baseline).
