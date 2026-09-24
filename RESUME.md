# ARC-2026 delivery sprint: resume

Last updated 2026-09-24. Read this first.

## State

**v1.3 contrastive corpus protocol FROZEN.** Nothing generated.
Protocol `docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.3.md` sha256
`66aa1c561ac4fd2a619459f15919282776a5898ab3ae6f36ae6944a5389d8f1e`.
Manifest `outputs/tti/constructive_protocol_v1.3_manifest.json` sha256
`9492f392d13e95b033b3f6a77d6dd75d27cbb11b6d0ac7dad104901fab56de14`.
Decision record `records/ITEM2_V13_CONTRASTIVE_DESIGN_DECISION.md`.
Freeze commit d6c81e2. 19 static feasibility tests pass.

The earlier draft at commit db6f500 is SUPERSEDED and not authoritative.

Design in one line: groups of two targets differing in exactly one grammar
position, four replicates each, judged by a NONLEARNED within-group
nearest-neighbour test against an exact chance of 3/7.

Standing evidence, unchanged: v1.2 corpus PASSED all 11 gates, 215 admitted.
v1.2 scorer FAILURE_CONDITIONING_NOT_ESTABLISHED. Diagnosis
CANDIDATE_SIGNAL_REDUNDANT_ON_V12 with the qualifier that NO evidence group
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

Generate the scheduled v1.3 corpus and run its frozen audit. Order inside that
block: Phase A calibration of 200 episodes first, which fixes every
normalization constant and is published before selection begins; then the
40-slot pilot to measure the group admission rate q; then the full request of
ceil(84/q) group slots capped at 1200; then the nonlearned audit; then STOP and
record PASS or FAIL.

Expect a long detached run. v1.2 took 47 minutes for 450 episode slots, and
v1.3 targets 672 admitted episodes in 8-episode groups where every member must
be admitted, so plan for many hours and launch with setsid nohup and a state
record.

Do NOT fit any scorer in that block. Do NOT filter groups on their frontiers.
Do NOT adjust a threshold. On FAIL, preserve it. The
ConstructiveExtensionCompiler stays BLOCKED and is not licensed by any v1.3
outcome alone.

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
