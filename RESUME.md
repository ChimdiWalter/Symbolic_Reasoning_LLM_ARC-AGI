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

## The scorer fit is BLOCKED

Attempted and stopped. Full record: `records/SCORER_FIT_BLOCKED_20260923.md`.

There is no corpus of informative-failure-graph to target-AST pairs, and none
can be produced under the frozen v1.1 admission law.

1. The v1.1 pilot generated all 60 slots on 2026-09-04 and admitted ZERO of
   1,500 attempted targets. Its own recorded root cause is structural: R4 and
   R5 are mutually exclusive, because the sole registered slot learner and the
   fixed base search enumerate the same 200-triple product. Of 266 family-(2,)
   targets passing R5, 262 were base-search-solved. A second recorded blocker
   kills families with no Select stage, which includes two frozen train
   families.
2. The only verified admitted episodes, the 13 in the corrected v2 census,
   each contain ZERO frontier_term nodes. They came from the proxy runtime,
   which is the exact defect repaired earlier. They are also protocol v2 with
   no recorded protocol hash, and 13 is far too few. The reconstruction
   directories were audited and downgraded earlier and are not evidence.

Real ARC failures now give informative graphs but carry no target AST, and no
hidden answer may be read to supply one.

## Next action, exactly one, and it needs your decision

Propose and freeze a v1.2 amendment regenerating the constructive corpus
through the repaired full-engine observation path. It must fix, before
generation: how R4 and R5 become jointly satisfiable; that episode graphs come
from the deployed reasoner so the frontier is non-empty by construction, with
the twelve-entry feature allowlist extended to the repaired channel's
evidence; and whether Select-free families leave the train list or the
induction path that refuses them changes.

Those are protocol changes and scientific choices. I have not made any of
them.

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
