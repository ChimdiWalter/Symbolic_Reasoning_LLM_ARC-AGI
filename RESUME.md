# ARC-2026 delivery sprint: resume

Last updated 2026-09-23. Read this first.

## State

Observation repair DONE and measured. Nothing else implemented, pending
review.

**Repaired failure channel classification: PARTIAL.**
Report: `records/FRONTIER_AUDIT_V2_20260923.md`.
Event mapping: `records/ENGINE_EVENT_MAPPING.md`.
Preregistered gate: `records/REPAIR_SPEC_FRONTIER_V2.md`.

The real ARC engine now emits the existing TraceObserver protocol at its own
candidate transitions, and the existing `build_tfg` consumes it unchanged.
The trace is task-conditioned, 12 distinct frontier operators instead of 1,
62 candidates fitted, 36 executed and non-exact, 7 exact. Observation does
not change the search result.

One evidence class is still missing from the graph: value and mismatch
signatures are created but every one is `{"defined": false}`, because
`tfg_extractor._mismatch_signature` renders through the blind-runtime
evaluator, which cannot execute object programs. The same candidates give
defined evidence, 17 of 17, under the engine's own renderer.

Scored against the unchanged preregistered threshold: 9 of 12 tasks carry
>= 2 frontier terms, 0 of 12 carry defined value evidence in the graph, 8 of
12 would qualify on the producer-side reading. PARTIAL, not INFORMATIVE.

## Earlier state, superseded

The pre-repair measurement is `records/FRONTIER_AUDIT_20260923.md`:
EMPTY_OR_UNUSABLE, NO_NEAR_MISSES_ACTUALLY_GENERATED, root cause
FULL_ENGINE_NOT_INSTRUMENTED. Its fixture still passes and still correctly
describes the blind-runtime path, which was deliberately left unchanged.

## Do not redo

- The failure-signal study (no evidence / aggregate / associated / shuffled).
  Already run; result recorded and now explained.
- The feature inventory. See `records/IMPLEMENTATION_MATRIX_CORRECTED_20260923.md`.

## Next action, exactly one

Give `build_tfg` an executor for the candidates it is handed: one optional
parameter, defaulting to today's behaviour, threaded to `_mismatch_signature`
in place of the hardwired `E.evaluate`. The full-engine adapter then passes
the engine's own renderer.

It needs a decision first, because it touches `cora_tti/tfg_extractor.py` in
`Reasoning_Project_tti`, which the repair block was told not to modify.
Either authorize that one edit or vendor the extractor into this workspace.
Re-run the same 12-task audit afterwards and score it against the unchanged
threshold.

Not licensed: the Stage-B constructive AST proposer and the
ConstructiveExtensionCompiler. Both remain SPECIFIED_ONLY. Do not build
either until the channel measures INFORMATIVE.

Still deferred on purpose: the blind runtime's goal-typed-only enumeration,
so that only one variable moves at a time.

## How to re-run

    export PYTHONDONTWRITEBYTECODE=1 ARC_META_BUDGET_S=8
    .venv_arc2026/bin/python scripts/audit_failure_frontier_v2.py
    .venv_arc2026/bin/python -m pytest tests/ -q

Single process, `nice -n 19`, so it cannot compete with Step B's 20 workers.

`.venv_arc2026` is this sprint's own interpreter prefix. It reads packages
from the shared environment through a path file and can never install into
it, so the live experiment's environment stays unwritable from here.

## Boundaries held this block

No scoring, no test outputs, no HOLDOUT, no E_transfer, no Lockbox, no
Step-B output, no proposal, no install, no K modification, no GPN training,
no ablation. Step B untouched.
