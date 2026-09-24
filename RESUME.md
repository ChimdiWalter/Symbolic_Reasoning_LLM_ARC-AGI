# ARC-2026 delivery sprint: resume

Last updated 2026-09-24. Read this first.

## State

**Scorer fit COMPLETE. Verdict: FAILURE_CONDITIONING_NOT_ESTABLISHED.**
Record: `records/SCORER_FIT_RESULT_20260924.md`. Report:
`outputs/tti/scorer_fit_v1.json`. Preregistration v4 sha256 `14f0bdc7...`,
sealed before the fit.

Two preregistered gates. Associated evidence beats shuffled by 0.197 nats per
token, 23 of 32 paired: PASS. Associated beats aggregate-only: FAIL, because
aggregate-only is better by 0.013.

Reading: evidence identity matters a lot, but the candidate-associated
failure features add nothing over the demonstration statistics. The typed
failure frontier does not improve constructive selection on this corpus.

Exact-at-five is 0 in all five conditions. An adversarial review predicted
this before the run, measuring that a probe knowing the target's token
multiset recovers only 2 of 32 under this decoder, which is why the gate
metric was changed to target log-likelihood in advance.

Earlier milestones still standing: v1.2 corpus PASSED all 11 gates, 215
admitted. Frontier channel INFORMATIVE 8/12. Proposer emits legal new ASTs
absent from K.

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

Diagnose the frozen scorer failure WITHOUT changing the corpus or the
controls. The question the data poses: why do the candidate-associated
features fail to help when the demonstration statistics do? Candidate
explanations to separate are a property of the features themselves, the
log-linear model's capacity, and the possibility that these synthetic targets
are largely determined by demonstration-level structure.

Do NOT relax the gate, regenerate the corpus, drop a control, or swap the
metric. The ConstructiveExtensionCompiler stays BLOCKED: a failed
discrimination result does not license it.

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
