# ARC-2026 delivery sprint: resume

Last updated 2026-09-24. Read this first.

## State

**Scorer-failure diagnosis COMPLETE.** Preregistered classification:
`CANDIDATE_SIGNAL_REDUNDANT_ON_V12`. Record:
`records/SCORER_DIAGNOSIS_20260924.md`. Report:
`outputs/tti/scorer_diagnosis.json`. Preregistration sha256 `6e95a7a8...`,
sealed before any outcome.

Capacity is NOT the cause: a bounded nonlinear model gives candidate features
a delta of -0.016, positive on 1 of 5 folds. Compression is NOT the cause:
all 180 episodes have distinct candidate vectors, zero collisions, and a
richer 42-field graph descriptor is WORSE than demonstration statistics under
both models, though that test is confounded by 42 features against 144
training episodes per fold.

Candidate features actively HURT. Permuting them to a demonstration-nearest
neighbour IMPROVES prediction.

Important qualifier on the label: demonstration statistics do NOT determine
the target either. They predict the first partition token at 0.383 against a
0.411 majority baseline. The accurate statement is that NO evidence group
recovers the target on this corpus. And the corpus does contain the cases the
frontier should disambiguate: 45 of 45 closest-quartile pairs have different
targets.

Standing: scorer verdict FAILURE_CONDITIONING_NOT_ESTABLISHED, v1.2 corpus
PASSED all 11 gates, proposer earns NEW_AST_GENERATION only.

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

Preregister v1.3 as a contrastive corpus, designed so failure evidence can in
principle identify the target. The evidence sets the requirement precisely:
the corpus needs episode groups whose demonstration statistics are close while
targets differ, AND whose failure frontiers differ systematically with the
target. v1.2 already satisfies the first half and fails the second. A v1.3
must also carry enough admitted episodes to support a wide descriptor without
the sample-size confound that clouded the raw-graph test here.

Do NOT implement v1.3 in the same block as its preregistration. Do NOT
regenerate v1.2, relax any gate, retrain the official scorer, or reinterpret
the frozen verdict. The ConstructiveExtensionCompiler stays BLOCKED.

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
