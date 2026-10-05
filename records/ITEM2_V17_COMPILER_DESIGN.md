# Item-2 v1.7: generic ConstructiveExtensionCompiler, design record

Recorded 2026-10-05, after the v1.6 result (27078d1,
PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES, hybrid, LEVEL 1).
This stage is licensed by that result. It receives an already-selected
legal extension (the oracle pair stays); no proposer is built here.

## 1. Where a compiled production must live (findings, from the engine source)

- **The same reasoner is the real ARC engine** (`geocat_arc`, the
  workspace's allowlisted copy). Its CORA expression phase
  (`meta_induction.induce_computed_candidates`) sits inside the ordinary
  candidate procedure, so every re-induction fold of the unchanged
  acceptance gate runs it on the fold's own pairs.
- **The phase already has a concept route.**
  - `search_with_concepts` instantiates a schema's enumerable slots from the
    vocabulary and fits its induced slots through the slot-learner dispatch.
  - It renders through `meta_ast.evaluate`, so there is no special
    evaluator.
  - Its programs come out as `ComputedPatternProgram` carrying the concept
    name.
- **Finding 1, the route is dormant.** The inducer calls
  `induce_computed_candidates(train_pairs, deadline=...)` with no concepts,
  and there is no installation hook.
- **Finding 2, multi-block schemas cannot be fitted.** The engine's
  induced-slot learner reads one partition, predicate and feature from the
  whole program (`bound_values`, last occurrence wins). It needs exactly one
  Select. So it cannot fit the multi-block schemas the constructive grammar
  produces. The occurrence-scoped fitter (frozen, `cora_tti`) was built for
  exactly this and is what the constructive domain's reasoner uses.
- **Finding 3, the expression phase is starved.** It gets only the time the
  parent induction has left. Measured on a constructive task the engine
  cannot solve, the object search spends the whole 8 s budget and the phase
  is reached once with the deadline 0.04 s past, trying zero hypotheses. So
  on exactly the tasks where an extension is needed, the frozen reasoner
  never consults it.

## 2. K*: the frozen reasoner configuration for the constructive loop

The engine source is unchanged (its tree digest is the one the v1.5 and v1.6
manifests pinned). Every arm of every comparison runs under K*. A treatment
arm differs only by a non-empty overlay.

| rule | what it does | effect without an extension |
|---|---|---|
| K*-1 expression slice | the expression phase gets its declared slice (`ARC_META_BUDGET_S`, 8 s) per call, rather than the parent's leftover time | **changes behaviour** relative to the v23 seal: the plain single-block meta search now runs on every trigger-firing task. The v23 count (185/1,000) belongs to K, not K*; K*'s baseline is measured where it is needed. |
| K*-2 fitting law | the learner for `Map[FeatureValue,Colour]` delegates the one shape the engine produces (one block, one Select) to the engine's own learner, unchanged; every other shape goes to the frozen occurrence-scoped fitter | inert: the engine never produces another shape |
| K*-3 overlay | installed productions are appended to the phase's concept list | inert: an empty overlay leaves the call unchanged |

Environment: `ARC_META_INDUCTION=1`, `ARC_META_BUDGET_S=8`,
`PYTHONHASHSEED=0`, and no other `ARC_*`.

## 3. Feasibility (synthetic fixtures, seed range 810,000,000; nothing scored)

Prototype of K*-1 to K*-3 on fresh constructive tasks of two blocks (seven
demonstrations for training, one held out):

| fixture | K* alone | K* + compiled extension |
|---|---|---|
| seed 810000100 | not accepted (8.1 s) | accepted through the unchanged gate; winner `computed_pattern` carrying the extension; held-out exact (15.5 s) |
| seed 810004800 | not accepted | accepted; same attribution; held-out exact (15.6 s) |
| seed 800000000 (five training pairs) | not accepted | not accepted: three re-induction folds could not refit a table (a key witnessed by only two demonstrations). The unchanged gate working as designed. |

## 4. Decisions

- The compiler is a pure function from a closed input schema to a canonical
  production.
  - Installation is a context-scoped overlay into K*, and nothing persists.
  - Attribution is structural and label-checked.
  - The ablation is K* against K* + {e} under identical conditions, with a
    fresh engine directory for each arm.
  - The L leg is an outer adaptive leave-one-out, re-proposing and
    recompiling in each fold. The engine's own gate refits the same
    production per fold, which is weaker; the protocol keeps the two apart.
- K*-1 is disclosed as a reasoner-configuration change with baseline
  consequences, and every later stage measures its baseline under K*.
