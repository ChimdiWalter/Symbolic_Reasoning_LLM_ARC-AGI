# ARC-2026 delivery sprint: resume

Last updated 2026-09-23. Read this first.

## State

Observation repair DONE and measured. Nothing else implemented, pending
review.

**Repaired failure channel classification: INFORMATIVE.**
Report: `records/FRONTIER_AUDIT_V2_20260923.md`.
Event mapping: `records/ENGINE_EVENT_MAPPING.md`.
Preregistered gate: `records/REPAIR_SPEC_FRONTIER_V2.md`.

The real ARC engine now emits the existing TraceObserver protocol at its own
candidate transitions, and the existing `build_tfg` consumes it unchanged.
The trace is task-conditioned, 12 distinct frontier operators instead of 1,
62 candidates fitted, 36 executed and non-exact, 7 exact. Observation does
not change the search result.

The candidate-executor compatibility repair then carried the evidence into
the graph: 18 defined value signatures where there were 0. Scored against the
unchanged preregistered threshold, 9 of 12 tasks carry >= 2 frontier terms
and 8 of 12 carry defined candidate-associated evidence, so 8 of 12 meet both
conditions. The threshold was at least 8 of 12, so the channel is
INFORMATIVE. Three independent runs gave the identical verdict.

Cautions: it sits exactly at the threshold, the qualifying eight are the same
eight the producer probe found, and 3 of 12 tasks emit no candidates at all.

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

Implement the already-specified grammar-constrained constructive AST
proposer: typed failure graph plus typed interface to a NEW canonical AST
absent from the catalogue. Not name selection. This is now licensed, because
the channel measured INFORMATIVE against the preregistered threshold.

The ConstructiveExtensionCompiler stays a separate responsibility and remains
SPECIFIED_ONLY until the proposer exists. Do not merge the two.

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
