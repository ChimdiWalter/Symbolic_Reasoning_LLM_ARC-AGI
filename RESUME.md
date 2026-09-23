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

## Proposer built, and half its claim is earned

`cora_arc2026/constructive_proposer.py` implements
`propose_ast(tfg, interface, k)`. 14 of 14 frozen controls pass. On five
prospectively fixed real failures it emits 25 legal complete ASTs, all absent
from K, in about 0.03 s per task.

EARNED: new-AST generation from a real typed failure graph.
NOT EARNED: failure conditioning on real data. All five tasks share the same
rank-one candidate and four of five produce an identical list, although their
evidence differs substantially. The unfitted evidence prior saturates.
Nothing was tuned after seeing this. Full record:
`records/PROPOSER_BLOCK_20260923.md`.

## Next action, exactly one

Fit the scorer weights on the existing constructive dataset, per the frozen
model specification in the manifest: TFG encoder, interface embedding,
grammar-constrained decoder, non-LLM, hidden at most 256, stopping at 2000
epochs or a 200-epoch plateau in validation exact@5. The scorer already
exposes a `weights` mapping, so fitting changes no interface. Afterwards
re-run the same controls and the same smoke test and require the rank-one
candidate to vary where the evidence varies.

The ConstructiveExtensionCompiler stays a separate responsibility and remains
SPECIFIED_ONLY. Do not merge the two. Data-consumption order is fixed in
`records/DATA_USAGE_ORDER.md`: no 1000-task run until the end-to-end path
works, and no HOLDOUT until everything is frozen.

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
