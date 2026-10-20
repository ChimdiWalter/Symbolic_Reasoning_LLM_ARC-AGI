# Neural-CORA v2: the ncv2-g1 relational AST and the reasoning loop (20 October 2026)

**ncv2-g1** is a versioned, additive, researcher-designed typed AST over CORA's **existing** native operations.
- It compiles one-to-one onto native ObjectProgram and ComposedProgram dicts.
- It is executed only by the unchanged native interpreter (`render_program`).
- It does not modify `cora_neural_v1/`, `geocat_arc/` or any frozen result. A test checks that the native code's
  aggregate sha256 equals the v1 freeze manifest.

**Code:** `cora_neural_v2/`

| file | role |
|---|---|
| `rast.py` | the AST, signatures, type checker, S-expressions and JSON |
| `bridge.py` | the compiler to native, and native execution |
| `inventory.py` | the native inventory, read from the registries, and the exposure check |
| `macros.py` | typed, hygienic Lisp-style macros |
| `constraints.py` | demonstration evidence and the sound prunes |
| `search.py` | the budgeted, pairing-aware search |

## 1. The language

**Two concrete forms of one tree:**
- an S-expression, e.g.
  `(program S1 (list (rule (exists adjacent (test color == 2)) (recolor (color 4)))) keep (same_as_input))`;
- JSON: `{"op": ..., "args": [...]}`.

There is no eval and no generated code. Programs are data that are typechecked, compiled and then executed natively.

| slot | ncv2-g1 ops (each a native construct) |
|---|---|
| SCENE / VIEW | `program` view S1–S7: same-colour 4/8-connectivity, multicolour 4/8, background-adaptive, colour layers, proximity. `seq` gives stages that re-segment the previous output (native ComposedProgram) |
| OBJECT / RELATION / GUARD | `test` over all 36 registered native features (colour, size, size_rank, bbox, shape signatures, holes, containment, alignment, uniqueness, …); `and`; `in_set`; `exists(relation, PRED)` over the native relations (adjacent, inside, contains, left_of, right_of, above, below, same_color, same_shape, same_shape_normalized, same_size, …) |
| BINDING | `rule_with((?t REF) …, PRED, ACTION)` binds reference variables, used as `(var ?t)`. REFs: `self`, `nearest(PRED)`, `nearest_of_color`, `container`, `contained`, `largest(PRED)`, `unique(PRED)`, `shape_twin`. They resolve relative to the transformed object, as native RefExprs do, so binding compiles by exact substitution |
| GEOMETRY | `translate`, `move_to`, `move_until_adjacent(_to)`, `reflect(_shift)`, `rotate(_shift)`, `scale`, `copy_targets` / `copy_offsets` / `copy_period` / `copy_rays`, `copy_part`, `extract_part`, `connect`, `fill_line`, `crop_to`. Relational vectors: `vector_to`, `gap_closing`, `align_to`, `step_toward`, `slide`, `to_border`, `mirror`, `reflect_across`, `scaled` |
| COLOUR / VALUE | `color`, `color_of(REF)`, `most_common_color` / `least_common_color`, `color_map`, `feature_map`, `feature_affine`; `paint(REF)` copies per-cell colours, so multicolour outputs are possible |
| CONTROL / COMPOSITION | first-match rules plus a default (keep / delete); `composite` (several deltas applied to one object, in order); `seq` (stages); renders `same_as_input`, `crop(REGION)`, `crop_by_action`, `constant_shape(H, W, COLOR)`, so size changes are possible |
| HOLES | `(hole TYPE)` typechecks as TYPE in a sketch but never compiles |

**Not exposed yet** (`cora_neural_v2/inventory.py` `NOT_EXPOSED`, with reasons):
- native GROW modes;
- SYNTH_COPY (a learned-verb asset);
- copy's per-index `k` mode;
- `matched_template`;
- the framed, overlay, reduction, generative, computed-pattern and erase-patch program classes.

**What g1 expresses that `ncv1-g0` cannot:**
- relational guards (`exists`), conjunctions and set membership;
- object references with binding;
- relational vectors (toward, align, gap-close, mirror, reflect across);
- copying in four modes;
- connect, move-until-adjacent, rotate, scale, part copy and extraction, paint;
- colour of a referenced object, and induced and feature colour maps;
- composite actions and multi-stage `seq`;
- crop and constant-shape renders, i.e. **size changes**;
- all 36 native features as guards.

dev60 has no size-change task, so the G2 ceiling check there does not exercise the size-changing renders.

`ncv1-g0` had 7 views, 31 selectors (colour, size and fixed booleans) and 92 actions (keep, delete, recolour,
translate, slide, fill_line, reflect), all shape-preserving.

## 2. Parity: AST → native, verified

**`tests/test_neural_cora_v2_ast.py` (46 tests).** It covers 32 programs: 31 single-stage programs and one two-stage
`seq`.
- For each one, the expected native program dict is **written by hand** from the native grammar.
- The bridge must emit exactly that dict. Only the `parameter_class` metadata is ignored; it never affects
  execution.
- The native interpreter must give identical outputs, shape and every cell, for both.
- The S-expression and JSON forms must round-trip.
- Every compiled op and parameter must exist in the native grammars and be read by the native apply function.
- Every positive case must change the grid. The changes ranged from 1 to 8 cells, plus 3 shape-changing crops, so
  the parity is not vacuous.

**Negative tests:**
- a native EvalError fails identically on both sides;
- wrong types, unknown features or relations, bad comparisons, unbound variables and wrong arity are rejected;
- holes refuse to compile;
- composite parts without parameters are rejected;
- the macros are typed and hygienic and compile to native ops;
- the native code hash is unchanged.

**`tests/test_neural_cora_v2_search.py` (13 tests).** The search recovers known programs (recolour, two-rule,
copy-offset, move-toward, pure crop, relational guard) on native-generated tasks with fresh seeds. It also tests:
- the firing filter;
- exact budget truncation;
- the score hook;
- the CPU cap;
- the exhaustive single-rule check, which finds a single-rule task's program and proves that a two-rule task has
  no single-rule explanation.

One parametrized case is skipped; the dedicated relational test covers it. The two suites together give 58 passed
and 1 skipped (the G2a record in `records/NEURAL_CORA_V2_G2_FREEZE_MANIFEST.json`).

**Part 2, added after the freeze in separate files (20 October):**
- `tests/test_neural_cora_v2_parity.py` (61 tests): 39 more programs covering every exposed native op, plus the
  execution semantics (first match, guard vs action, occlusion order, composite order, multicolour, dimensions,
  stages, rejected constructs).
- `scripts/neural_cora_v2_parity_bench.py`: 14,200 real-grid executions on dev60 demonstration inputs, with 0
  mismatches.
- The full inventory is `records/NEURAL_CORA_G2_NATIVE_COVERAGE_INVENTORY.md`.

## 3. The reasoning loop: implemented vs proposed

```
ARC demonstrations + unlabeled query
        |
        v
CORA belief state ------------------------------------------- [PARTIAL]
  views (exact-equivalence collapsed), candidate rules,
  version set of consistent programs, execution traces,
  diagnoses, budget
        |
        v
proposal order over whole rules ----------------------------- [IMPLEMENTED: symbolic G1-CH;
  (selector, bound action, parameters) scored jointly             learned joint guide PROPOSED]
        |
        v
typed relational AST with holes and bindings ---------------- [IMPLEMENTED]
        |
        v
sound prunes + firing filter + best-first search ------------ [IMPLEMENTED]
        |
        v
native CORA execution on the demonstrations ----------------- [IMPLEMENTED]
        |
        +--> consistent candidates and dissenting predictions  [IMPLEMENTED]
        +--> no fit, ambiguity, rejection; fold fragility      [no fit / ambiguity / rejection IMPLEMENTED;
                         |                                       fold fragility PROPOSED in v2 search]
                         v
              observable diagnosis state ------------------- [PARTIAL: labels only]
                         |
                         v
              revision policy: choose an action ------------ [PROPOSED]
              (view, guard, operation, colour, step,
               alternative, more search, abstain)
                         |
                         v
              revise, execute, keep or roll back ----------- [PROPOSED]
                         |
                         v
two attempts with provenance -------------------------------- [IMPLEMENTED]
        |
        v
BLIND independent evaluator --------------------------------- [IMPLEMENTED (v1 evaluate.py;
  (the only reader of query outputs)                             the dev60 evaluator stage)]
```

**Implemented arrows, each with a function, a test and a trace:**

| arrow | function | test | trace |
|---|---|---|---|
| AST typing | `rast.typecheck` | `test_typecheck_rejects` | — |
| compile | `bridge.compile_program` | `test_native_parity` | — |
| execute | `bridge.execute` → native `render_program` | the same | — |
| fit | `bridge.fit` | `test_search_*` | — |
| candidate rules | `search.selectors` / `actions` | `test_search_recovers_*` | — |
| view equivalence | `search.distinct_views` (exact: identical segmentation of every grid run) | `test_search_*` | — |
| firing filter | `search.fires` | `test_firing_filter_*` | — |
| order | `search.symbolic_scores` | `test_two_rule_order_*` | — |
| enumeration | `search.enumerate_programs` | `test_budget_truncation_is_exact` | — |
| two-attempt selection and record | `search.search` (optional CPU cap) | `test_cpu_cap_*` | `pred_at`, `state` |
| search miss vs language gap | `search.exhaustive_single_rule` | `test_exhaustive_*` | verdict, fraction checked |
| macros | `macros.expand` | `test_macro_*` | — |

**Proposed (not implemented):**
- the learned joint guide (`records/NEURAL_CORA_V2_QWEN_JOINT_PROGRAM_ADAPTER_DESIGN.md`);
- fold fragility inside the v2 search;
- the revision policy and executed revisions (G3);
- library learning (G4).

## 4. Revision baseline (next, after G2; specification)

**A transparent rule-based controller.** Given a failed or ambiguous search, it:
1. reads the observable state, e.g. no fit with demonstration 1 failing on recolour-only cells;
2. chooses one action, e.g. CHANGE_COLOUR_POLICY to induced `color_map`, REVISE_VIEW to a multicolour view, or
   INCREASE_SEARCH;
3. applies it as a concrete AST edit or search-space change;
4. reruns inference and records the changed candidate set and grids.

It is compared with failure-blind, try-all-repairs, shuffled-trace and matched-compute controls before any learned
policy is trained.
