# Failure-frontier audit, 2026-09-23

Measurement only. Nothing was proposed, constructed, installed, trained,
ablated or scored. No test output, HOLDOUT, E_transfer, Lockbox or Step-B
output was read. The live Step-B experiment was not touched.

Question asked: **does the current real TFG extractor produce useful
candidate-associated semantic failure evidence on actual authorized ARC
development failures?**

Answer: **no.** The candidate channel is a constant of the language, not a
function of the task.

## 1. Method

Task set fixed in advance by `records/FRONTIER_AUDIT_SELECTION_RULE.md`,
committed before any result was computed: the first 12 task ids in ascending
order of `data/arc/dev60_challenges.json`. The frozen v23 baseline records
0/120 on the protected evaluation set, so every dev task is a recorded
baseline failure and the ordering rule alone selects the 12.

Path run, unmodified: ordinary search, existing `TraceObserver`, existing
`tfg_extractor.build_tfg`. Budget 8.0 s per task, goal type Grid,
`max_frontier_terms` 12, blind-runtime `BASE_ENV`.

Harness: `scripts/audit_failure_frontier.py`. Raw records:
`outputs/frontier_audit/frontier_audit_records.json`.

## 2. Per-task TFG content

| task | demos | baseline fails | TFG nodes | frontier_term | frontier types | exec-nonexact | typed-unfitted | slot-fail records | value sigs | defined sigs | distinct frontier ASTs | max surface | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `13e47133` | 3 | yes | 24 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 5.103 |
| `142ca369` | 3 | yes | 24 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 4.559 |
| `16b78196` | 2 | yes | 22 | 12 | Grid | 0 | 2209 | 12 | 0 | 0 | 12 | 6 | 8.003 |
| `195c6913` | 3 | yes | 24 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 4.279 |
| `20270e3b` | 4 | yes | 23 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 0.688 |
| `20a9e565` | 3 | yes | 21 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 0.702 |
| `221dfab4` | 2 | yes | 21 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 6.201 |
| `247ef758` | 3 | yes | 24 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 3.587 |
| `269e22fb` | 5 | yes | 25 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 0.633 |
| `271d71e2` | 3 | yes | 24 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 1.521 |
| `28a6681f` | 3 | yes | 24 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 1.794 |
| `2b83f449` | 2 | yes | 21 | 12 | Grid | 0 | 2736 | 12 | 0 | 0 | 12 | 6 | 3.548 |

Aggregates over the 12 tasks:

| quantity | value |
|---|---|
| observer candidate events | 64,610 |
| frontier-eligible events | 32,305 |
| frontier_term nodes built | 144 |
| executed-but-non-exact candidates | 0 |
| value-signature nodes | 0 |
| defined value signatures | 0 |
| mismatch signatures | 0 |
| relation-change evidence | 0 |
| palette-change nodes (from demonstrations) | 36 |
| delta-signature nodes (from demonstrations) | 36 |
| shape-change nodes (from demonstrations) | 24 |
| distinct frontier result types | 1 (Grid, equal to the goal type) |
| distinct frontier operators | 1 (`PaintEach`) |

## 3. The decisive observation

The observer census is identical on 11 of the 12 tasks:

    {"typed": 2736, "slot_fit_failed": 2736}

The twelfth differs only because it hit the deadline, giving 2209/2209. Three
unrelated synthetic tasks (2x tiling, transpose, top-left crop) produce the
same census, and the same ordered list of frontier ASTs, as the real ARC
tasks.

Every candidate the search judges fails slot fitting. There are zero
`slot_fit_ok`, zero `executed_not_exact` and zero `exact` outcomes, on every
task. All 2,736 frontier-eligible candidates carry the single operator
`PaintEach`, which is the only primitive in the 11-primitive `BASE_ENV` whose
result type is Grid.

The only task-varying content in the entire graph is the demonstration
statistics: delta, palette and shape nodes computed directly from the
training pairs, not from any candidate.

This retrospectively explains the earlier failure-signal study without
rerunning it. That study compared no evidence, aggregate evidence,
candidate-associated evidence and shuffled candidate evidence, and found
shuffled controls performed about as well as real ones. They performed about
as well because they were the same thing: the candidate-associated evidence
does not vary across tasks, so shuffling it changes nothing. The real TFG is
an aggregate TFG plus a constant.

## 4. Where the information is lost

Counts at each stage, per task:

| stage | count |
|---|---|
| TraceObserver candidate events | 5,472 |
| of those, frontier-eligible outcomes | 2,736 |
| yielded by `frontier_candidates()` after dedup and the cap | 12 |
| `frontier_term` nodes in the finished graph | 12 |

Nothing is lost between the observer and the graph. The reduction from 2,736
to 12 is the intended `MAX_FRONTIER_TERMS` cap, and it is not the defect:
all 2,736 eligible candidates share one operator, so a larger cap would admit
more of the same.

The loss is upstream of the observer. Near-miss evidence is never created,
because no candidate ever executes.

**Classification: `NO_NEAR_MISSES_ACTUALLY_GENERATED`.**

**Root cause: `FULL_ENGINE_NOT_INSTRUMENTED`.** The instrumented search is
the blind runtime's 11-primitive synthetic language. It cannot fit a single
candidate against real ARC data, so it produces no near misses to record. The
engine that actually solves ARC carries no instrumentation at all: a search
for `TraceObserver` and `set_observer` across `harness/`, `geocat_arc/` and
`src/` returns nothing, and `cora_tti/tti_fallback.py`, the real-engine
task-local install path, contains no reference to the TFG. The component that
reasons and the component that is observed are two different programs.

Two narrower defects are real but secondary, and neither would change the
measured result on its own:

1. Top-level enumeration admits only goal-typed ASTs
   (`_asts_of_type(goal, ...)` filters on `type_equal(result_type(name),
   wanted)`), so a candidate that terminates at the wrong type never enters
   the trace. Frontier result type therefore always equals the goal type and
   a type gap can never be represented.
2. The observer is handed the unfitted skeleton `ast`, while the fitted
   program `complete` is discarded at the same site. `_mismatch_signature`
   then evaluates a program with raw slots, which raises, so a value
   signature would degrade to `{"defined": false}` even when an
   executed-not-exact candidate does occur.

## 5. Failure-channel classification

**`EMPTY_OR_UNUSABLE`**, against the thresholds fixed in advance.

Frontier nodes are emitted on every task, so the channel is not literally
empty. It is unusable for construction: it carries no value or mismatch
evidence, no type gap, no relation change, one operator, and the same content
for every task. Conditioning a constructive proposer on it is equivalent to
conditioning on a constant.

## 6. Constructive decoder and compiler status, verified in code

A. **Grammar-constrained constructive AST decoder: SPECIFIED_ONLY.** No
implemented component maps a TFG plus a typed interface to a new canonical
AST. The three proposal entry points all return existing catalogue names:
`mdl_fallback_proposer` sorts the catalogue and returns the top k names;
`gpn_proposer` extracts names and drops anything outside the catalogue;
`gpn.propose` ranks Extension sketches over known names and result types.
`gpn.py` implements a name head and a result-type head only, and its own
docstring defers argument types to a Stage-B sketch head that does not exist.

B. **ConstructiveExtensionCompiler: SPECIFIED_ONLY.** The identifier appears
in exactly one place in the repository, the protocol document
`docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL.md`. There are no Python hits.

Neither has been accidentally rebuilt. Both remain genuine unfinished pieces
of the existing architecture.

## 7. Fixture

`tests/test_frontier_loss_fixture.py`, 5 tests, all passing. Synthetic tasks
only, no ARC data. It pins the defect as a falsifiable equality: two tasks
differing in shape behaviour, palette and structure produce an identical
candidate census and an identical ordered list of frontier ASTs. A repair
must break that equality.

## 8. Exactly one next implementation action

**Emit the existing `TraceObserver` candidate protocol from the engine that
actually reasons over ARC, and build the TFG from that trace.**

This is a repair to the demonstrated loss point, not a new component. It
reuses `TraceObserver`, `FRONTIER_OUTCOMES` and `build_tfg` unchanged. Scope:

- add `candidate(ast, outcome)` emission at the real engine's per-candidate
  accept and reject sites, using the existing six outcome names;
- record the fitted program rather than the unfitted skeleton at the
  executed-not-exact site, so `_mismatch_signature` can evaluate it;
- add a thin extraction entry point that runs a full-engine solve with an
  observer installed and calls the existing `build_tfg`;
- re-run this same audit and require the fixture equality to break.

Do this only in the sprint workspace's allowlisted copy of the engine. The
research tree's GEOCAT engine stays untouched, per the standing prohibition
on modifying the real engine, and the live Step-B experiment is unaffected.

Not licensed yet: the Stage-B constructive AST proposer and the
ConstructiveExtensionCompiler. They stay unimplemented until the repaired
channel is measured and shown informative. Building a proposer on this
signal would be building it on a constant.
