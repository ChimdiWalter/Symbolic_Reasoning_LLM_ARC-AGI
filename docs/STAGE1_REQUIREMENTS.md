# Stage 1 Requirements: Object-Level Program Induction

Date: 2026-07-02.
Status: implementation requirements distilled from this project's own concept documents.
Sources: `WAY_FORWARD.md` (Stage 1 plan, Sections 2-4), `RESUME_CUMULATIVE.md` (cumulative-reasoning
chain and acceptance criteria), `CORTICAL_REASONING_PLAN.md` (Layers 1, 2, 6), `DECISIONS.md`
(D2, D3, D7, D13), `AGENTS.md` (experiment discipline, review checklist), `claim_traceability.md`
(trace-driven operator invention row), `limitations.md`, `results_summary.md`,
`outputs/breakthrough_gap_closure_report.md` ("What Not To Claim"),
`outputs/deep_unsolved_analysis/*.md`, `outputs/arc_taxonomy/*.md`, `FORMAL_SPEC.md` and
`PROCESS_LOG.md` (design intent), plus code reads of `geocat_arc/perception/{objects,matching,
relations,segmentation,change_detection}.py`, `geocat_arc/categorical_dsl/{program,types,
operators_basic,operators_object_logic}.py`, and `geocat_arc/reasoning/{rule_inducer,
reasoning_engine}.py`.

Baseline to beat (verified, `outputs/failure_landscape_2026_07_02.json`): union 123/1000
submission-valid (pipeline 102, GeoCat 72). Target population: 409 object-preserving unsolved
tasks (`outputs/object_level_opportunity_2026_07_02.json`) + 196 shrink tasks
(shrink_var 103, shrink_const_out 86, shrink_int_factor 7).

## 0. The user's directive (binding)

The system must be **truly reasoning**: it creates programs by **learning from each task's train
pairs**. There will be **no new hand-coded task-specific solvers**. Capability grows only through
(a) a fixed, generic, compositional hypothesis space, (b) induction that selects and parameterizes
hypotheses from examples, (c) an LOO generalization gate, and (d) accumulation: near-solves are
training data, and recurring learned fragments are promoted to reusable operators. This is the
operational definition of "true reasoning" already agreed in `WAY_FORWARD.md` Section 3 and the
central thesis of `RESUME_CUMULATIVE.md` ("Failures are not errors; failures are training data
for reasoning").

---

## 1. The cumulative-learning loop, mapped to object level

`RESUME_CUMULATIVE.md` defines the chain:

```
failed -> near-solved stored -> failure cluster formed -> operator invented ->
counterexamples survived -> task resumed -> task solved -> certificate emitted
```

Stage 1 instantiates every arrow at **object granularity**:

| Chain step | Object-level realization |
|---|---|
| attempt | Parse train pairs into objects (Section 2.1), match input/output objects per pair (Section 3.1), compute typed object deltas (Section 3.2), search selector->action rules (Section 3.3). |
| failed -> near-solved stored | If the best induced program explains a fraction f of objects/pixels with 0 contradictions on the explained part (thresholds in Section 5.1), store a **NearSolveRecord**: the partial program, the residual (unexplained objects and their deltas), and the feature table. Extends the existing `NearSolve` dataclass in `geocat_arc/reasoning/reasoning_engine.py` (task_id, strategy, apply_fn, train_accuracy, residual_pattern) with object-level fields. |
| failure cluster formed | Cluster NearSolveRecords by (delta-type histogram, residual pattern, failing selector family) — the object-level analogue of `near_solved_memory.py` failure clustering (Section 5.2). |
| operator invented | From a cluster, mine the recurring (selector-expression, action-expression) fragment and register it as a **named library operator** — a typed DSL sub-program with free parameters, not a metadata dict and not a hand-written solver (Section 5.3). This is the executable target `WAY_FORWARD.md` Stage 3 demands ("synthesize apply_fn as a DSL sub-program"); Stage 1 builds the storage and promotion path so accumulation is measurable from day one. |
| counterexamples survived | Every candidate program passes LOO-by-reinduction (Section 3.4); invented operators additionally pass the falsification-style checks in Section 5.4 before entering the library. Per the 2026-06-15 lesson (`results_summary.md`): falsification probes are advisory and must never veto a program that passes train-fit + LOO; the LOO gate is the blocking gate. |
| task resumed | When a new operator enters the library, re-run induction on all tasks whose NearSolveRecords are in the source cluster (and only through the normal induction path — no task-targeted shortcuts). |
| task solved | Program is train-perfect and LOO-perfect; emitted as a typed `categorical_dsl` program (Section 4). |
| certificate emitted | ProgramCertificate serialized per accepted program (Section 5.5), following the 17-field certificate design of `certificates.py` / `claim_traceability.md` but bounded to what Stage 1 actually measures. |

Requirement 1.1: the loop must run in this order for every task, with all state transitions logged
as events (reuse the event-type vocabulary of `events.py`: TASK_OBSERVED, HYPOTHESIS_PROPOSED,
HYPOTHESIS_ACCEPTED/REJECTED, NEAR_SOLVED_STORED, FAILURE_CLUSTER_CREATED, OPERATOR_PROPOSED,
INVENTION_VALIDATED/REJECTED, INVENTION_REGISTERED, TASK_RESUMED, TASK_PROMOTED_TO_SOLVED,
REASONING_CERTIFICATE_CREATED, FINAL_PREDICTION_EMITTED).

Requirement 1.2 (order-effect honesty): because library growth makes results order-dependent,
the harness must record task processing order, and the "cumulative" claim is only testable by the
Milestone D contrast in `WAY_FORWARD.md`: solve-rate on later tasks with library vs without.
Stage 1 must make that ablation runnable (a `--no-library` flag) even though the claim itself
belongs to Stage 3.

## 2. Hypothesis-space specification

The hypothesis space is fixed and generic. A concrete hypothesis = (segmentation variant,
selector expression, action, parameter expressions). Program creation means *binding these by
induction*, never by task lookup.

### 2.1 Object segmentation variants (the perception lattice)

All built on `geocat_arc/perception/segmentation.py::extract_connected_components` and
`objects.py::extract_objects`; the multicolor and view variants are the wiring gap named in
`WAY_FORWARD.md` Stage 1 item 1 and mirror the pipeline's `PerColorAdapter` / `MonochromeAdapter`
/ `MajorityBgAdapter` designs (results_summary "Adaptive Loop" section):

- S1: same-color 4-connected components (existing default).
- S2: same-color 8-connected components (existing `connectivity=8`).
- S3: multicolor 4-connected (any non-background cells connected regardless of color; object keeps
  a per-cell color map — requires extending `ARCObject` with an optional `cell_colors` dict).
- S4: multicolor 8-connected.
- S5: background-adaptive: background = most frequent color (not assumed 0), then S1-S4.
- S6: color-layer view: one object per color = all cells of that color (for scattered same-color
  patterns).

Requirement 2.1.1: segmentation choice is per-task and learned: the inducer tries variants in a
fixed order (S1, S2, S3, S5, S4, S6) and keeps the first variant whose object matching is
*coherent* across all train pairs (defined: >= 80% of non-background pixels covered by matched or
action-explained objects, consistent object-count relation between input and output across pairs).
Ties broken by fewer objects (parsimony, per D3/MDL intent). The chosen variant is recorded in
the program (it is the `Segment` step's bound argument) — never chosen by task ID.

### 2.2 Object features

Intrinsic (from `ARCObject` in `perception/objects.py`, extended where noted):

- color (or multiset of colors for S3/S4), size, bbox (r0,c0,r1,c1), bbox_height, bbox_width,
  centroid, shape_signature, normalized shape_signature (rotation/reflection canonical form — new),
  hole count / has_hole, is_rectangle, is_line, touches_border (new, trivial from bbox vs grid),
  aspect ratio, density (size / bbox area).
- Rank features computed over the object set of the grid: size_rank (largest=0), size_rank_reversed,
  is_unique_size, is_unique_color, is_unique_shape, is_majority_shape, color_frequency_rank,
  count_of_same_shape, count_of_same_color. (These mirror the ~59 boolean properties proven useful
  in `reasoning_engine.py`'s pipeline cousin; here they are typed feature functions, not ad hoc.)

Relational (from `perception/relations.py`, all 10 existing checks plus derived quantities):

- left_of / right_of / above / below / contains / inside (inverse of contains) / adjacent /
  same_color / same_shape / same_size / overlaps — as boolean relations to a second object.
- Derived quantitative relations (new, required for parameter expressions): vector-to(o2) =
  (o2.centroid - o1.centroid) rounded, gap-to(o2) along row/col, nearest-object(predicate),
  nearest-object-of-color(c), alignment (same row band / same column band), containment depth.

Requirement 2.2.1: every feature and relation is a named, typed, pure function registered in a
FEATURE_REGISTRY / RELATION_REGISTRY (name -> fn, arg types, return type). Induction may only use
registered functions; this keeps the hypothesis space enumerable and the programs serializable.

### 2.3 Action vocabulary (generic primitives only)

Per `WAY_FORWARD.md` Stage 1 item 2 delta types, each action is a generic, parameterized object
transform. Executable semantics already largely exist in `categorical_dsl/operators_basic.py`
(`TranslateAll`, `RecolorAll`, `ReflectAll`, `RotateAll`, `Copy`, `Render`) and
`operators_object_logic.py` (`CopyToPosition`, `CopyRelativeToAnchor`, `ConditionalRecolor`);
missing ones must be added as new Morphisms in the same style:

- `keep` (identity on object)
- `delete` (drop object)
- `translate(dr, dc)`
- `recolor(c)`
- `copy(k, placement_expr)` — k copies at positions given by a parameter expression
- `move_to(r0, c0)` / `move_until_adjacent(target_expr, direction_expr)` (gravity-style motion is
  move_until_adjacent with border/object target)
- `scale(factor)` (integer up/down on the object mask)
- `reflect(axis)` , `rotate(angle)` (about object bbox center or a learned anchor)
- `crop_to(region_expr)` — grid-level action for shrink tasks: output = subgrid (Section 3.6)

Hard rule: no action may embed task-specific constants at definition time. Constants enter only
as induced parameters, and only when a relational/feature expression (Section 2.4) does not
explain the data at equal or better LOO score (constants are the last resort in the parameter
lattice, because `rule_inducer.py`'s `_generalization_score` precedent: position/constant-dependent
hypotheses are penalized).

### 2.4 Parameter-expression language (what makes it program CREATION)

Action parameters are **expressions over features and relations**, not bare numbers. The expression
grammar (depth <= 2 in Stage 1):

```
ColorExpr  := const(c) | color_of(REF) | most_common_color | least_common_color
            | color_map[color_of(self)]            # induced global map, like GeoCat color rules
REF        := self | nearest_object(PRED) | nearest_object_of_color(c) | container(self)
            | contained(self) | largest(PRED) | unique(PRED) | matched_template
VecExpr    := const(dr,dc) | vector_to(REF) | vector_to_border(direction)
            | gap_closing_vector(REF, axis)        # move until adjacent
            | (k * unit(direction)) with k := feature(self) | const
RegionExpr := bbox(REF) | grid_quadrant(q) | separator_cell(i,j) | bbox(self)
ScalarExpr := const(k) | size(self) | count(PRED) | hole_count(self)
PRED       := feature predicate conjunctions of depth <= 2 over Section 2.2 features
```

Examples of the required expressivity (both from `WAY_FORWARD.md` Section 2): "move each object
to touch the nearest wall" = `translate(gap_closing_vector(border, learned_axis))` for selector
`all`; "recolor the largest object with the color of the object it contains" =
`recolor(color_of(contained(self)))` for selector `is_largest`.

Requirement 2.4.1: the inducer must prefer, in order: relational expression > feature expression >
induced map > constant, with ties broken by LOO margin then expression size (MDL preference, D3).
A program whose every parameter is a constant is still legal but must be flagged
`parameter_class: constant` in its certificate — these are the least "created" programs and the
induced-fraction metric (Section 6) tracks them separately.

## 3. Induction procedure

The proven pattern being lifted (explicitly, per `WAY_FORWARD.md` Stage 1 item 3) is
`geocat_arc/reasoning/rule_inducer.py`: zero-conflict mapping induction (`induce_rule`, which
rejects on the first `context_key -> two different outputs` conflict), fuzzy fallback
(`InducedRule._fuzzy_lookup`, nearest known key within Hamming distance len/3), majority-vote
partial rules (`induce_partial_rule` returning accuracy), generalization scoring
(`_generalization_score`: penalize position-dependent extractors and high key/total ratios), and
**LOO-by-reinduction** (`reasoning_engine.py::_loo_reinduce_rule`: re-induce from N-1 pairs, test
exact equality on the held-out pair; accept iff every fold passes). At object level the
"cell context" becomes the object feature vector and the "output color" becomes the typed delta.

### 3.1 Per-pair object matching

Use `perception/matching.py::match_objects` (greedy on `overall_similarity` = 0.3 shape +
0.2 color + 0.2 size + 0.3 location, threshold 0.1) as the base correspondence. Required
extensions (all generic):

- Unmatched input objects => candidate `delete`. Unmatched output objects => candidate `copy`/new
  (Stage 1 handles copies of existing shapes; genuinely new shapes are out of scope — class
  `object_new_shapes` is deferred to Stage 2 composition per `WAY_FORWARD.md`).
- One-to-many matches (same input shape appearing k times in output) => `copy(k, ...)`.
- Matching must also be attempted under translation-invariant shape identity (shape_signature
  equality ignoring position/color) so that moved and recolored objects still match; use the
  similarity components already in `matching.py` (`shape_similarity`, `color_similarity`,
  `size_similarity`, `location_similarity`) re-weighted per hypothesis: motion hypotheses
  down-weight location, recolor hypotheses down-weight color.
- Ambiguity rule: if two matchings tie, generate both and let downstream zero-conflict induction
  disambiguate (a wrong matching produces selector conflicts and dies).

### 3.2 Typed deltas

For every matched pair (o_in, o_out) compute the minimal delta in the fixed vocabulary:
`keep | translate(dr,dc) | recolor(c->c') | reflect(axis)+translate | rotate(angle)+translate |
scale(f) | composite(translate+recolor)`. Unmatched: `delete` / `copy`. Use
`perception/change_detection.py::detect_changes` for the grid-level cross-check (pixel diff totals
must reconcile with the object delta account; unreconciled pixels beyond tolerance mark the pair
as not object-preserving under this segmentation, triggering the next segmentation variant).

### 3.3 Selector -> action rule search

For each delta type present, induce which objects receive it:

1. Build the feature table: rows = all input objects across all train pairs, columns = Section 2.2
   features, label = the object's delta (type + raw parameters).
2. **Selector induction (zero-conflict):** enumerate predicates (single feature test, then
   conjunctions of 2, mirroring the conjunction search precedent in the pipeline's
   StructuralReasoner) and keep predicates that select exactly the labeled objects in *every*
   train pair with zero conflicts — the object-level `induce_rule`.
3. **Parameter induction:** for the selected objects, fit each parameter expression family from
   Section 2.4 and keep expressions consistent across all pairs (zero-conflict on parameters:
   e.g. `vector_to(nearest_object_of_color(2))` must reproduce every observed (dr,dc)).
4. **Fuzzy fallback (bounded):** if no zero-conflict selector exists, use majority-vote selectors
   (the `induce_partial_rule` analogue) *only* to build NearSolveRecords — a fuzzy rule is never
   accepted as a solution; it feeds memory (Section 5). At apply time on unseen objects whose
   feature vector was never observed, nearest-known-feature-vector fallback (the `_fuzzy_lookup`
   analogue) is permitted inside an accepted program only when it also survives the LOO gate.
5. **Generalization scoring:** rank competing rule sets by (LOO margin, fewer selector literals,
   higher-preference parameter class per 2.4.1, fewer rules). Reject selector sets that are
   pure extensional lookups (selector enumerates one object per pair by position — the analogue
   of POSITION_DEPENDENT extractors, which `rule_inducer.py` scores -1.0).

The full task program is the rule set {(selector_i, action_i)} + default action for unselected
objects (`keep` or `delete`, induced the same way) + `Render`.

### 3.4 LOO-by-reinduction gate (mandatory, blocking)

Exactly the `_loo_reinduce_rule` pattern: for each held-out train pair, rerun the *entire*
induction (segmentation choice, matching, selector and parameter induction) on the remaining
pairs, apply the resulting program to the held-out input, require exact grid equality. Accept
iff all folds pass and full-train fit is exact. For tasks with 2 train pairs, LOO degenerates to
1 fold each way and both must pass; single-pair tasks additionally require the program's
parameter class to be non-constant (relational/feature) to be accepted. This gate produced 85%
generalization on cell rules and 96% on structural inference (`WAY_FORWARD.md` Section 1) and is
the only accepted evidence of generalization in Stage 1.

### 3.5 Budget and ordering

Per-task time budget compatible with the unified harness (`evaluate_arc_unified` timeout
parameters); enumerate hypotheses cheapest-first (S1 segmentation, single-feature selectors,
translate/recolor deltas) and stop at the first LOO-perfect program of minimal expression size
(collect-all within the same cost tier, then rank — do not first-match across tiers, per the
Stage 2 direction and the documented +5 collect-all vs first-hit result).

### 3.6 Shrink tasks (object selection)

Same machinery, program shape `Segment -> Select(learned predicate) -> Crop/Render`
(`WAY_FORWARD.md` Stage 1 item 5): induce a predicate over Section 2.2 features that picks the
object (or separator cell / region) whose bbox crop equals the output in every train pair; the
predicate goes through the same zero-conflict + LOO gate. Output-constant tasks
(shrink_const_out) additionally allow `RegionExpr`/`ColorExpr`-valued outputs (e.g. k x k grid of
color_of(largest(PRED))).

## 4. Program representation

Requirement 4.1: every accepted solution is a `geocat_arc/categorical_dsl/program.py::Program` —
an ordered list of `ProgramStep(morphism, bound_args)` that type-checks under
`type_checker.check_composition` over `types.ArcType` (GRID, OBJECT, OBJECT_SET, COLOR, VECTOR,
AXIS, ANGLE, REGION, PREDICATE, GRID_PATCH). Canonical shape:

```
Segment(variant) -> [ (Select|Filter)(selector_expr) -> Action(param_exprs) ]* -> Render(h,w,bg)
```

Requirement 4.2: selector and parameter expressions are first-class serializable objects
(registry names + arguments), so `Program.to_dict()` yields a complete, human-inspectable JSON
program: no opaque closures in the artifact (closures may exist at runtime, but the JSON must be
sufficient to reconstruct them via the registries). Every solve writes
`outputs/<run>/programs/<task_id>.json`.

Requirement 4.3: new Morphisms needed for Section 2.3 actions are added to `categorical_dsl`
(one class per generic action, with `input_types`/`output_types` declared) — this is the wiring
of the "fully built, never wired" DSL noted in `WAY_FORWARD.md` Section 1.

Requirement 4.4: `Program.apply` (or an object-level executor extending it) is the *only*
execution path for accepted programs; the prediction submitted for the test input is
`program.apply(test_input)`. Solution provenance (`Solution.apply_fn` in the GeoCat interface)
must wrap the Program, preserving the existing `ReasoningEngine.solve` contract
(`result.solution.is_exact`, `result.solution.apply_fn`).

## 5. Near-solve memory and operator invention

### 5.1 NearSolveRecord schema

Store (JSON, append-only, one file per run + cumulative index) when best program has
train_fit >= 0.5 (object-level: fraction of objects whose delta is explained) but is not accepted:

```
{
  task_id, timestamp, segmentation_variant,
  program_partial: <serialized partial Program>,
  train_fit_pixels, train_fit_objects,
  explained_rules: [ {selector_expr, action, param_exprs, n_objects_explained} ],
  residual: {
    unexplained_deltas: [ {delta_type, count, example_features} ],
    conflict_report: {selector_conflicts, parameter_conflicts},
    loo_failures: [pair_idx]
  },
  delta_histogram: {translate: n, recolor: n, delete: n, copy: n, ...},
  failure_stage: segmentation|matching|selector|parameter|loo
}
```

This extends `NearSolve(task_id, strategy, apply_fn, train_accuracy, residual_pattern)` already in
`reasoning_engine.py` and replaces the pipeline's unused near_solved_memory with one that is on
the solve path (fixing the `WAY_FORWARD.md` Section 1 finding that memory contributed zero).

### 5.2 Failure clustering

Cluster NearSolveRecords by (failure_stage, delta_histogram signature, residual delta types).
A cluster with >= 3 tasks and a shared unexplained pattern is an invention candidate — the
object-level realization of `operator_invention.py`'s "mine near-solved failure clusters".

### 5.3 Operator promotion (library learning)

When the same (selector_expr schema, action, param_expr schema) fragment — schemas = expressions
with free color/axis/scalar slots — appears in >= 3 *accepted* programs, or an invention candidate
cluster yields a fragment that retro-solves >= 2 of its member tasks through the normal induction
path, promote it to a named library operator:

```
{ name: auto-generated (e.g. op_move_until_adjacent_by_color),
  fragment: <typed sub-program with free parameters>,
  provenance: [task_ids], created_at, loo_record, falsification_record }
```

Library operators are tried early (before raw enumeration) on future tasks, but their parameters
are always re-induced per task and they pass the same LOO gate. They are exactly "typed program
fragments, not memorized lookup tables" (`WAY_FORWARD.md` Stage 3). The DreamCoder-style miner
precedent (`library_learning.py`, previously 0 fragments because programs were depth-1) becomes
meaningful here because object programs have >= 3 steps by construction.

### 5.4 Counterexample survival for invented operators

Before registration, an invented operator must survive: (a) re-validation on all provenance
tasks via full re-induction; (b) applicability probes on 10 random already-solved tasks with the
requirement of zero regressions (regression = a previously accepted program is displaced by a
new program that fails LOO); (c) color-relabeling invariance where the fragment claims color
genericity (the surviving useful probe family from `active_falsifier.py`). Falsification failures
block *library registration* only — never an individual task solution that passed train+LOO
(2026-06-15 lesson).

### 5.5 ProgramCertificate

Every accepted program serializes a certificate
(`outputs/<run>/certificates/<task_id>.json`):

```
{ task_id, program (full JSON), segmentation_variant,
  train_fit: 1.0, loo_score: 1.0, loo_folds: n,
  parameter_class: relational|feature|induced_map|constant (worst over params),
  selector_literals: n, program_depth, expression_size,
  library_operators_used: [names], invented_from_cluster: id|null,
  hypotheses_enumerated, induction_time_s, harness_commit, run_id }
```

The certificate is a record of evidence (bounded claims only, per D13/D3) — not a proof object.

## 6. Hard constraints

1. **No task-ID conditionals.** No code path may branch on task ID or hash. Enforced by grep
   audit in CI (`grep -rn "task_id ==" ` and equivalents must hit only logging/serialization) and
   by a shuffle test: renaming task IDs must not change any prediction.
2. **No per-task hand-coded transforms.** No new solver whose applicability is engineered around a
   specific known task's structure (the failure mode `WAY_FORWARD.md` Section 1 documents:
   102 solves from ~30 hand-coded primitives). New executable code is admitted only as: generic
   Morphisms (Section 2.3), registry feature/relation functions (Section 2.2), or expression
   grammar productions (Section 2.4) — each must be justified by >= 2 distinct dev tasks and
   remain fully parameter-free of task constants.
3. **Submission mode only.** Test outputs are never read during solving; the harness is
   `evaluate_arc_unified(..., submission_mode=True)` in
   `src/reasoning_project/unified_reasoning_system.py` (Stage 0 single honest harness). Oracle
   numbers, if ever computed, carry the "test-leakage" label (`WAY_FORWARD.md` Section 5). Do not
   reuse `scripts/run_cortical_v6_eval.py` (hardcoded old cluster paths); write a new runner with
   project-local paths.
4. **LOO gate mandatory** (Section 3.4). No program is accepted on train fit alone. Milestone B
   requires >= 80% LOO generalization maintained.
5. **Zero regressions.** The 123-task baseline set must remain solved in every run; regressions
   fail the run.
6. **Induced-fraction metric** (new, reported in every summary):

   ```
   induced_fraction = (# accepted programs whose worst parameter_class is
                       relational | feature | induced_map, and whose selector was
                       induced from the feature table)
                      / (# accepted programs from the Stage-1 object inducer)
   ```

   Companion breakdown: parameter_class histogram, mean selector literals, mean program depth,
   % of solves using >= 1 library operator, % of solves reached via task-resumption after an
   invention event. Target: induced_fraction >= 0.9 on new Stage-1 solves (constant-only programs
   are legal but must stay < 10%). This is the quantitative answer to "is it creating programs or
   looking up solvers".
7. **Reporting discipline** (AGENTS.md): every run logs exact commands and artifact paths in
   `RUN_HISTORY.md`; long runs backgrounded with logs under `logs/`; claims stay bounded
   (breakthrough report "What Not To Claim" applies verbatim).

## 7. Acceptance tests

### 7.1 Development set (from `outputs/object_level_opportunity_2026_07_02.json`)

All 14 verified unsolved in `failure_landscape_2026_07_02.json` and screened for tractability
with the existing perception stack (object counts per pair shown from
`extract_objects`/`match_objects` screening on 2026-07-02):

Class `object_motion_or_copy` (8):

| Task | Train pairs | Max objects/pair | Why chosen |
|---|---|---|---|
| `05f2a901` | 3 | 2 | move object until adjacent to fixed target — pure `gap_closing_vector` |
| `dc433765` | 7 | 2 | single-step motion toward target; 7 pairs = strongest LOO signal in the class |
| `1caeab9d` | 3 | 3 | motion defined relative to a reference object (relational selector) |
| `a1570a43` | 4 | 5 | reposition shape relative to corner markers (`vector_to(REF)`) |
| `ae3edfdc` | 3 | 10 | multi-object gravitation to center objects — selector + shared relational vector |
| `5521c0d9` | 3 | 3 | translate-by-feature (`k * unit(direction)`, k = object height) |
| `2c737e39` | 3 | 9 | copy/move pattern relative to marker object |
| `e76a88a6` | 2 | 5 | copy template shape onto marker positions (copy + recolor combination) |
| `88a10436` | 3 | 5 | move multicolor object to marker — requires S3 multicolor segmentation |

(first 8 are the committed motion set; `88a10436` is the designated S3-segmentation probe —
9 motion tasks total is acceptable, dev set stays within 10-15 with the recolor set below at
the cost of one optional task.)

Class `object_recolor_or_delete` (5):

| Task | Train pairs | Max objects/pair | Why chosen |
|---|---|---|---|
| `0a2355a6` | 4 | 4 | recolor by intrinsic feature (hole count) — canonical feature->color rule |
| `6ea4a07e` | 6 | 3 | recolor with induced color map; 6 pairs = strong LOO |
| `1acc24af` | 4 | 5 | recolor/keep by relational property |
| `b2862040` | 4 | 7 | recolor by topological/connectivity property |
| `2204b7a8` | 3 | 8 | documented historical near-solve (color transfer reached validation, failed partial nearest_kept — `results_summary.md` 2026-05-28); the designated near-solve-memory regression test |

### 7.2 Shrink set (from `failure_landscape_2026_07_02.json` shrink categories)

| Task | Category | Screen result | Program shape expected |
|---|---|---|---|
| `4852f2fa` | shrink_var | output == one object's bbox crop (verified) | Segment -> Select(pred) -> Crop |
| `358ba94e` | shrink_const_out | output == one object's bbox crop (verified) | Segment -> Select(pred) -> Crop |
| `2dc579da` | shrink_var | 2 objects, select-region task | Select(minority/unique pred) -> Crop |
| `25e02866` | shrink_var | 4 objects -> 4x4 output | Select(learned pred) -> Crop |
| `445eab21` | shrink_const_out | 2 objects -> 2x2 constant-size output | Select(largest) -> ColorExpr output |

### 7.3 Pass criteria

- A1: >= 10 of the 19 dev tasks solved end-to-end (submission mode, LOO-gated, program JSON +
  certificate emitted for each).
- A2: induced_fraction = 1.0 on dev-set solves (every dev solve must have a non-constant selector;
  parameter_class constant allowed for at most axis/direction slots).
- A3: `2204b7a8` produces a NearSolveRecord if unsolved (memory path exercised); at least one
  failure cluster forms over the dev run.
- A4: zero regressions on the 123 baseline; zero task-ID conditionals (grep + shuffle audit pass).
- A5: LOO-by-reinduction is exercised on every acceptance (assert loo_folds == n_train_pairs in
  every certificate).
- A6: full-1000 run after dev acceptance: >= 160 total solves is the Stage-1 progress bar toward
  Milestone B (>= 200, `WAY_FORWARD.md` Section 6), with per-category gains reported against
  `failure_landscape_2026_07_02.json`.
