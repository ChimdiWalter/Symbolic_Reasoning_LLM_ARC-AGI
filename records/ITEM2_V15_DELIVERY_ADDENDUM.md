# Item-2 v1.5 delivery-readiness addendum

Frozen 2026-09-28, while the frozen v1.5 test corpus was being generated and
before any v1.5 score existed. Supplementary throughout: the official v1.5
experiment (freeze 216f2c4, protocol sha256 `e3209c1f...`, manifest sha256
`0cc4b900...`) is unchanged, and its result is reported separately from
everything here. No file in the frozen manifest or its dependency trees was
touched. The new code lives in `scripts/` and `tests/`, which are not hashed
trees. Hashes of this record and its scripts are in
`outputs/tti/v15_delivery_addendum.json`.

## (a) Gate C and dependence between test groups

The official matched shuffle gives each test query the failure evidence of a
query in another test group, so the per-group differences behind gate C are
connected. The official gate C result stands. Its p-value is **not**
described as an exact independent-group causal confirmation.

Frozen sensitivity procedure (`scripts/v15_supp_dependence.py`):

- **Donor connections.** Two test groups are linked when any query of one
  receives failure evidence from a query of the other.
- **Effective independent units.**
  - Tier 1: connected components of that graph under the official shuffle.
  - Tier 2: fixed blocks of test groups, formed within each family by
    group-digest order as consecutive pairs, with an odd remainder joining
    the family's last block. Donors are matched by the frozen rule inside
    each block only, and the official D+F_SHUFFLED model is scored with
    them. A family with a single group has no valid donor; it is left out of
    tier 2, and the count is reported.
- **Allowed resampling transformation.** A sign flip of a whole unit's
  summed D+F_ASSOC minus D+F_SHUFFLED difference. Groups inside a unit are
  never flipped separately.
- **Null assumption, stated as an assumption.** Within a unit, a query's own
  failure evidence and its donor's are exchangeable given everything the
  fixed models see, so each unit's paired difference is symmetric about
  zero.
  - The matched shuffle approximates this, but donor demonstrations differ
    from the recipient's, so it does not guarantee it.
  - No simulation is offered as proof.
- **Resolution rule.**
  - Tier 1 governs if it has at least 30 units; otherwise tier 2 governs.
    Both tiers are always reported.
  - The verdict is SUPPORTED (sum above zero and exact p < 0.01),
    NOT_SUPPORTED, or UNRESOLVED (fewer than 30 units).
  - The rule is fixed here and will not be changed after seeing which tier
    gives which answer.
- **In every case**, a strong failure-conditioning mechanism claim requires
  the later independent-task causal controls. This analysis alone cannot
  establish the mechanism.

## (b) Gate H

Gate H stays as frozen. It means **a nonnegative observed difference** of
D+F_ASSOC over D, summed over the verification-ambiguous queries of at least
30 groups. It is not demonstrated improvement and not formal
noninferiority, and a pass will not be described as proof of benefit where
verification cannot decide. Actual usefulness must come from the later
executable witness and the held-out behavioural tests.

## (c) Verification errors

The frozen code (`cora_arc2026/v15_sel.py`, `make_independent_episode`, lines
175 to 179) records `other_candidate_fits` as `fit is not None` and maps any
fitter exception to False. False therefore mixes "does not fit" with "the
check failed". This is not changed mid-run.

The occurrence-scoped fitter has no deadline and no randomness, so its
outcome can be recomputed exactly afterwards.
`scripts/v15_supp_verification.py` recomputes, for every admitted test
episode:
- FIT;
- NO_FIT, with the fitter's failure code;
- ERROR, with the exception type.

It compares this with the recorded boolean and reads no score.
Verification-based conclusions (gate H and the verification diagnostic) are
reported as **LIMITED** if any ERROR occurs or any recomputation disagrees
with the record. Later integration uses the three outcomes FIT,
NO_FIT_WITHIN_DECLARED_PROCEDURE and ERROR/UNKNOWN.

## (d) Claim and capacity

Any increment is beyond the particular D_RICH summary and this frozen
selector. It is not information beyond all demonstrations, because the
reasoner computes the failure evidence from the same demonstrations.

Equal allocated input width does not mean equal effective capacity. In D the
failure weights are forced to zero, so D has fewer free parameters than
D+F. Equal width is not used as proof that representation or capacity
cannot matter. The associated-against-shuffled comparison, which has the
same width and the same values, and the later compute-matched controls carry
that question.

## Stale sections of the design record

`records/ITEM2_V15_SELECTION_DESIGN_DECISION.md` sections 3 to 8 describe
the first freeze (89ac728). The authoritative protocol and erratum 1 govern
wherever they differ:

| item | first freeze (stale) | governs now |
|---|---|---|
| exclusion set | 471 targets and 69 groups | 477 and 72 |
| twin folds | by shared target digest only | also by shared token pair |
| shuffle | global | same family first |
| ladder | no decisive-failure rule, no gate H | decisive-failure negatives and gate H |
| claim | "beyond demonstrations" | "beyond the D_RICH demonstration summary" |

## Resource note

Before launch, a nice-19 probe process got 0.935 of a CPU core at a host
load of about 66. The v1.4 training episodes ran at a CPU/wall ratio of
0.975. Every engine run records its CPU and wall time, and the result will
report their distribution.

## Order after generation

1. `scripts/evaluate_v15_selection.py --integrity-only`, read.
2. `scripts/v15_supp_verification.py`, which reads no score.
3. `scripts/run_v15_evaluation.sh`, the official result, reproduced.
4. `scripts/v15_supp_dependence.py`.
5. Report official and supplementary verdicts separately.
