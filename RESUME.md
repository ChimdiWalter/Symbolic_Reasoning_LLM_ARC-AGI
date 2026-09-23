# ARC-2026 delivery sprint: resume

Last updated 2026-09-23. Read this first.

## State

Measurement block complete. Nothing is implemented pending review.

The failure-frontier audit answered the question that gated all constructive
work, and the answer is negative. Full report:
`records/FRONTIER_AUDIT_20260923.md`.

**Failure channel classification: EMPTY_OR_UNUSABLE.**
**First loss point: NO_NEAR_MISSES_ACTUALLY_GENERATED.**
**Root cause: FULL_ENGINE_NOT_INSTRUMENTED.**

Over 12 prospectively selected dev tasks the instrumented search produced
64,610 candidate events, 32,305 frontier-eligible, 144 frontier terms, and
zero executed-but-non-exact candidates, zero value signatures, zero mismatch
signatures. The observer census is the constant `{typed: 2736,
slot_fit_failed: 2736}` on 11 of 12 tasks, and three unrelated synthetic
tasks reproduce that same census and the same ordered frontier ASTs. The
candidate channel does not vary with the task.

This explains the old failure-signal study's null result without rerunning
it: shuffled controls matched real evidence because the real evidence was
already task-independent.

## Do not redo

- The failure-signal study (no evidence / aggregate / associated / shuffled).
  Already run; result recorded and now explained.
- The feature inventory. See `records/IMPLEMENTATION_MATRIX_CORRECTED_20260923.md`.

## Next action, exactly one

Emit the existing `TraceObserver` candidate protocol from the engine that
actually reasons over ARC, and build the TFG from that trace. Repair, not new
architecture: reuse `TraceObserver`, `FRONTIER_OUTCOMES`, `build_tfg`.
Scope and acceptance test are in section 8 of the audit report. Acceptance:
`tests/test_frontier_loss_fixture.py::test_candidate_trace_is_identical_for_unrelated_tasks`
must start failing.

Make the change only in this workspace's allowlisted engine copy. The
research tree's GEOCAT engine stays untouched.

Not licensed yet: the Stage-B constructive AST proposer, and the
ConstructiveExtensionCompiler. Both remain SPECIFIED_ONLY by verified code
search. Do not build either on the current signal.

## How to re-run the audit

    export PYTHONDONTWRITEBYTECODE=1 ARC_META_BUDGET_S=8
    .venv_arc2026/bin/python scripts/audit_failure_frontier.py
    .venv_arc2026/bin/python -m pytest tests/test_frontier_loss_fixture.py -q

`.venv_arc2026` is this sprint's own interpreter prefix. It reads packages
from the shared environment through a path file and can never install into
it, so the live experiment's environment stays unwritable from here.

## Boundaries held this block

No scoring, no test outputs, no HOLDOUT, no E_transfer, no Lockbox, no
Step-B output, no proposal, no install, no K modification, no GPN training,
no ablation. Step B untouched.
