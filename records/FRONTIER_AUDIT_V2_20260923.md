# Failure-frontier audit v2, repaired full-engine channel, 2026-09-23

Measurement only. Nothing was proposed, constructed, installed, trained,
ablated or scored. No test output, HOLDOUT, E_transfer, Lockbox or Step-B
output was read. Step B was not touched and stayed alive throughout. All
work ran single-process at `nice -n 19` in the isolated workspace.

**Classification of the repaired channel: PARTIAL.**

The repair worked on every axis the old channel failed, except one, which is
now isolated to a single mechanical cause.

## 1. What changed

One observational change, in this workspace's allowlisted engine copy only:
the real ARC reasoning engine now emits the existing TraceObserver candidate
protocol at its own candidate transitions, and the existing `build_tfg`
consumes that trace unchanged. Mapping: `records/ENGINE_EVENT_MAPPING.md`.
Preregistered acceptance gate: `records/REPAIR_SPEC_FRONTIER_V2.md`.

## 2. Files changed

| file | change |
|---|---|
| `geocat_arc/object_reasoning/_trace_hook.py` | new, 70 lines. Inert sink plus candidate serializers. |
| `geocat_arc/object_reasoning/inducer.py` | 4 emission sites, all additive. One import. The existing train-perfect computation is byte-identical. |
| `cora_arc2026/engine_trace.py` | new. Thin extraction entry point plus the producer-side value-evidence probe. |
| `scripts/audit_failure_frontier_v2.py` | new. The same audit against the repaired channel. |
| `tests/test_engine_trace_repair.py` | new, 9 tests. |

Nothing in `Reasoning_Project` or `Reasoning_Project_tti` was modified. The
adapter asserts at import that the engine it loaded is the sprint copy.

## 3. Before and after

| quantity | old blind-runtime channel | repaired full-engine channel |
|---|---|---|
| observer candidate events | 64,610 | 494 |
| identical census across unrelated tasks | yes, `{typed: 2736, slot_fit_failed: 2736}` | no |
| distinct frontier operators | 1 | 12 |
| tasks with >= 2 frontier terms | 12 of 12, all identical | 9 of 12, all different |
| candidates reaching beyond typing | 0 | 62 slot-fit-ok, 36 executed-not-exact, 7 exact |
| defined candidate value evidence | 0 | 0 in the graph, 17 of 17 at the producer |

## 4. Per-task table, same 12 tasks, same 8 s budget, same cap

| task | demos | solved | TFG nodes | frontier_term | frontier ops | typed | slot_fit_ok | slot_fit_failed | exec-nonexact | exact | TFG value sigs | engine value evidence defined | distinct frontier ASTs | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `13e47133` | 3 | no | 18 | 5 | 2 | 12 | 0 | 12 | 0 | 0 | 0 | 0 | 5 | 1.091 |
| `142ca369` | 3 | no | 27 | 12 | 3 | 24 | 2 | 21 | 2 | 0 | 1 | 1 | 12 | 8.029 |
| `16b78196` | 2 | no | 27 | 12 | 5 | 53 | 28 | 23 | 9 | 7 | 5 | 5 | 12 | 9.463 |
| `195c6913` | 3 | no | 29 | 12 | 2 | 43 | 11 | 31 | 10 | 0 | 3 | 3 | 12 | 14.968 |
| `20270e3b` | 4 | no | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.048 |
| `20a9e565` | 3 | no | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.121 |
| `221dfab4` | 2 | no | 23 | 9 | 6 | 16 | 2 | 13 | 2 | 0 | 1 | 1 | 9 | 7.669 |
| `247ef758` | 3 | no | 17 | 3 | 3 | 4 | 1 | 2 | 1 | 0 | 1 | 1 | 3 | 1.164 |
| `269e22fb` | 5 | no | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.176 |
| `271d71e2` | 3 | no | 29 | 12 | 5 | 33 | 4 | 28 | 2 | 0 | 2 | 2 | 12 | 8.03 |
| `28a6681f` | 3 | no | 28 | 12 | 4 | 33 | 11 | 22 | 7 | 0 | 3 | 3 | 12 | 0.75 |
| `2b83f449` | 2 | no | 15 | 5 | 2 | 13 | 3 | 6 | 3 | 0 | 1 | 1 | 5 | 8.17 |

Aggregates: 494 candidate events, 194 frontier-eligible, 82 frontier terms,
231 typed, 62 slot-fit-ok, 158 slot-fit-failed, 36 executed-not-exact, 7
exact, 17 value-signature nodes of which 0 defined, 17 of 17 producer-side
signatures defined.

Three tasks emit nothing at all. On those the engine gives up before rule
induction, at segmentation or matching, so there is no candidate to observe.
That is a true property of the engine on those tasks, not a trace defect.

## 5. Acceptance against the preregistered gate

| item | result |
|---|---|
| 1. six outcome classes emitted | PARTIAL: five emitted truthfully; `typecheck_failed` has no real-engine counterpart and was reported rather than redefined |
| 2. trace varies across unrelated tasks | PASS, and structurally, not by counters |
| 3. candidates reach beyond typing | PASS, 62 slot-fit-ok and 36 executed-not-exact |
| 4. fitted executable program recorded, not the skeleton | PASS |
| 5. value and mismatch signatures defined for near misses | FAIL in the graph, PASS at the producer |
| 6. no test output or protected data in the trace | PASS, the challenge file holds no outputs |

Scientific acceptance, thresholds unchanged and applied as written:

- tasks with >= 2 candidate-associated frontier terms: **9 of 12**
- tasks with non-empty candidate-associated value or mismatch evidence in
  the graph: **0 of 12**
- the same evidence, computed by the engine's own executor: **8 of 12**

INFORMATIVE required >= 8 of 12 on both conditions jointly. The graph meets
the first and fails the second, so the preregistered classification is
**PARTIAL**. The more favourable producer-side reading would reach exactly
8 of 12, and it is recorded here, but the audit measures graph content, as
version 1 did, and the threshold is not reinterpreted after the fact.

## 6. The single systematically missing evidence class

**Executable value and mismatch evidence never reaches the graph.**

The cause is mechanical and exact. `tfg_extractor._mismatch_signature`
renders a candidate with `E.evaluate`, the blind-runtime evaluator. An object
program is not a blind-runtime AST, so evaluation raises, the exception is
caught, and the signature degrades to `{"defined": false}`. Seventeen
value-signature nodes are created and all seventeen are empty.

The evidence itself exists and is rich. Rendering the same candidates with
the engine's own executor gives, for example:

    {"defined": true, "shape_matches": true, "cells_wrong": 111,
     "fraction_wrong": 0.1233, "palette_extra": 0}

Seventeen of seventeen are defined that way. The producer is correct; the
consumer cannot execute what the producer now records.

This was not repairable inside this block's boundary. The fix belongs in
`cora_tti/tfg_extractor.py`, which lives in `Reasoning_Project_tti` and was
explicitly out of scope.

## 7. Deferred, as instructed

Top-level enumeration in the blind runtime still admits only goal-typed
candidates, so a type gap cannot be represented there. Unchanged in this
block, so that only one variable moved. The frontier result type in the
repaired channel is empty rather than Grid, because object programs carry no
blind-runtime type.

## 8. Claims earned and not earned

Earned:

- the real reasoning engine can be observed through the existing protocol
  without changing its search result;
- its failure traces are task-conditioned and structurally diverse;
- it does generate near misses: fitted candidates that execute and miss;
- those near misses carry defined, quantitative mismatch evidence when
  rendered by the correct executor.

Not earned:

- that the graph currently carries usable value evidence. It does not.
- that the failure channel is INFORMATIVE. It is PARTIAL.
- anything about construction, invention, language extension or ARC score.
  No proposer, compiler, extension, install or scoring was built or run.

## 9. Exactly one next action

**Give `build_tfg` an executor for the candidates it is handed.**

One optional parameter, defaulting to the present behaviour, threaded to
`_mismatch_signature` in place of the hardwired `E.evaluate`. The full-engine
adapter then passes the engine's own renderer. No new representation, no new
observer, no change to any outcome name, no change to the frontier
definition.

It requires a decision, because it touches `cora_tti/tfg_extractor.py` in
`Reasoning_Project_tti`, which this block was told not to modify. The two
options are to authorize that one edit, or to vendor the extractor into this
workspace. Re-running the same audit afterwards decides INFORMATIVE against
the unchanged threshold.

The constructive AST proposer and the ConstructiveExtensionCompiler remain
unbuilt and SPECIFIED_ONLY, in every branch.
