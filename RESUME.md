# ARC-2026 delivery sprint: resume

Last updated 2026-09-24. Read this first.

## State

**v1.2 corpus COMPLETE and PASSED its frozen gate.** 450 of 450 slots, 7,947
targets attempted, 215 admitted: 180 train, 32 validation, 3 structural
holdout. All eleven frozen criteria pass. Record:
`records/V12_CORPUS_AUDIT_20260924.md`. Report:
`outputs/tti/v12_corpus_audit.json`.

This is the first Item-2 corpus to admit anything. Version 1.1 admitted zero
of 1,500.

Key numbers: 215 distinct target digests from 215 episodes, duplicate rate
zero. Frontier terms 2 to 12, mean 7.87, interquartile range 7.0. Distinct
frontier operators 1 to 9. Only 382 rejections were baseline-solved, so the
structural separation holds without touching the baseline. Only 2 rejections
lacked informative evidence, so the repaired full-engine path delivers.

**Material limitation the gates did not cover:** the structural holdout arm
admitted 3 of 90 slots, all family (2,1); family (2,) admitted zero. That was
predicted in the protocol before generation, because single-block targets sit
inside the baseline's own enumeration. Three episodes cannot support a
structural-family held-out test.

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

Fit the existing Stage-B scorer on the v1.2 corpus. `EvidenceScorer.weights`
already exists, so fitting changes no interface. The fitted scorer must then
beat the five frozen controls, being associated real evidence, shuffled,
irrelevant, aggregate-only and none, on exact-at-five recovery.

Confront the holdout thinness when designing that test. Either run the
discrimination test on a held-out split of the training families and state
plainly that structural-family generalization was not measured, or
preregister a v1.3 that makes the holdout families reachable. That choice is
prospective and must not be made after seeing a score.

The ConstructiveExtensionCompiler stays separate and unbuilt until the
discrimination test passes. Data order in `records/DATA_USAGE_ORDER.md` is
unchanged: no 1000-task run, no protected holdout.

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
