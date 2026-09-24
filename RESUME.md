# ARC-2026 delivery sprint: resume

Last updated 2026-09-24. Read this first.

## State

**v1.3 contrastive corpus: Phase A calibration IN PROGRESS.** No group has
been generated, no calibration constant is frozen, no pilot has run, and the
audit has not run. Live state is in `logs/v13_generation_state.txt`, which is
authoritative over this summary.

Protocol sha256 `66aa1c56...389d8f1e`, manifest sha256 `9492f392...ab56de14`.
Implementation sealed before any outcome: core and generator at 0146e20, the
nonlearned G1 to G10 auditor at 4a6efd8.

Two corrections made during setup, both recorded. The Phase A implementation
slot ceiling was raised to 12000 at ca033a7, because per-attempt admission
measures about 5 percent and the original ceiling could not reach the frozen
200-episode target. And the chain watcher was replaced at e192636 because it
would have launched the pilot on the mere existence of the calibration file;
the frozen protocol requires that artifact to be COMMITTED first. The boundary
was never crossed: at the time the defect was found Phase A was still running,
no calibration file existed and zero pilot groups had been generated.

Standing evidence, unchanged: v1.2 corpus PASSED all 11 gates. v1.2 scorer
FAILURE_CONDITIONING_NOT_ESTABLISHED. Diagnosis
CANDIDATE_SIGNAL_REDUNDANT_ON_V12, with the qualifier that no evidence group
recovered the target. Proposer earns NEW_AST_GENERATION only.

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

## Next action, exactly one

Complete the frozen v1.3 experiment in order: finish Phase A to exactly 200
admitted episodes, verify them mechanically, write and hash the calibration
artifact, COMMIT it, then run exactly 40 pilot group slots, freeze and commit
q, then the full run of ceil(84/q) capped at 1200, then splits by ascending
group digest at 60/12/12, then the sealed auditor, then STOP with PASS or FAIL.

Nothing is trained in that chain. No group is ever filtered on any property of
its frontier. No threshold moves. The ConstructiveExtensionCompiler stays
BLOCKED even on a PASS, which licenses only a separately preregistered scorer
discrimination experiment.

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
