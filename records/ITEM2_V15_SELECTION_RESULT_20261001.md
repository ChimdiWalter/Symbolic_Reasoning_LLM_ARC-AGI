# Item-2 v1.5 conditional failure-conditioned selection: result

Recorded 2026-10-02 from the sealed reports of 2026-10-01. Nothing was
refitted, rescored or changed after the reports were written. Step B was not
read.

## Official v1.5 outcome

**FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION**, ladder rule 6, over **288**
unique independent-input test groups (the full powered size).

- Integrity passed before any statistic.
- The sealed evaluator ran twice; both reports are byte-identical.
- Every fit converged.
- There was no leak, no train-test overlap, no order dependence and no freeze
  problem.

The condition of rule 7 (B fails decisively and D selects above chance) also
holds. Rule 6 takes precedence, so the official class is the one above.

The claim ceiling stated in advance applies: negatives are conditional on this
selector and this training resource.

## Identities

| item | value |
|---|---|
| protocol sha256 | `e3209c1f0ce3ab9d7c925f546dd9a25111b0b22cb0b8300dfbe53b5fb2e1e42a` |
| manifest sha256 | `0cc4b900d22c11cce444051e7374af33d4e2261bb75547df9c9f6fe77054a89c` |
| freeze | 216f2c4 (erratum 1; first freeze 89ac728 superseded) |
| delivery addendum | 5a9077c, frozen before any score |
| addendum erratum 1 (launch path of the verification diagnostic) | ff751e3, before any score |
| official report sha256 | `01528ce7152d7d8bff7ec4a1529c21b51a8de2b81ecea1905c413d72d7621dae` (pass 1, pass 2 and main identical) |
| supplementary verification sha256 | `5aeb95f38de11676eef8726e9dd6bfeac7925cd20b577141fcaf690eddf4823b` |
| supplementary dependence sha256 | `352c75a8ed096c847d481e12758499d176d5e1149f4942fb2e0720621138fbac` |
| test-set hash list | `outputs/tti/v15_test_corpus_sha256.txt` (2,739 records plus run state and run end), sha256 `d0620fa4f8dd228b804ec279bba797daa8c95ec42cc55be9bd8ffa9d12fa6abc` |

## Generation

- **Launch:** 2026-09-28T20:15:01Z (first slot start 20:16:44Z); generator
  PID 2819761, chain 2819666, nice 19.
- **Reboot:** Athe rebooted on 2026-09-30 at about 14:05Z. It stopped the run
  at slot 2045, with 2,046 records and 221 groups.
  - The records were checked before resuming: all parse, cover slots 0 to
    2045 contiguously, pass the freeze check, and the engine state was clean.
  - It resumed at 23:41Z with the unchanged frozen script: chain 75512,
    generator 75518. It continued at slot 2046 and rebuilt the 221 groups.
- **End:** generator exit 0 at 2026-10-01T11:57:44Z, stop reason
  `target_groups` at slot 2738.
  - That is 229,260 s (63.7 h) from the first start, within the 432,000 s
    cap; about 9.6 h of the time was lost to the reboot.
- **Totals:**
  - 2,739 slots, 288 admissions, 288 groups;
  - 64,769 pair attempts and 617,406 replicate attempts;
  - slot time median 62.2 s.
- **Every record** has `freeze_ok` true, and the environment is only
  `ARC_META_BUDGET_S=8` and `PYTHONHASHSEED=0`.
- **Families (admitted / slots):** (0,0) 26/548, (0,0,0) 18/547, (0,1)
  88/548, (1,0) 79/548, (1,1) 77/548.
- **Rejections:**

  | code | count |
  |---|---|
  | TARGET_NOT_FITTABLE | 493,625 |
  | TARGET_EXECUTION_UNDEFINED | 81,734 |
  | PAIR_REPLICATES_SHORT | 60,954 |
  | OTHER_FROZEN_CODE | 21,860 |
  | BASELINE_SOLVED | 3,558 |
  | EXCLUDED_TARGET_DIGEST | 2,589 |
  | TARGET_ALREADY_IN_CORPUS | 783 |
  | NO_INFORMATIVE_TFG | 306 |
  | EXCLUDED_GROUP_DIGEST | 80 |
  | DUPLICATE_GROUP_DIGEST | 75 (skipped before any engine run; no duplicate was admitted) |

## Post-generation order

The detached runner `scripts/run_v15_post_generation.sh` ran the four steps
in the order set on 2026-09-28, between 12:02:38Z and 12:04:33Z on
2026-10-01:
1. integrity only: PASS;
2. three-valued verification diagnostic: exit 0;
3. sealed evaluation twice: byte-identical;
4. dependence sensitivity: exit 0.

## Gates (test, 288 groups)

| gate | rule | result |
|---|---|---|
| A | D+F_ASSOC above 0.5 | **pass**: 0.585, p 9.2e-13 |
| B | D+F_ASSOC beats D | **fails decisively**: mean increment -0.0056 (95% CI -0.026 to +0.014), p 0.72, one-sided upper bound 0.011 < 1/20 |
| C | D+F_ASSOC beats the matched shuffle | **fails decisively**: +0.0048 (95% CI -0.019 to +0.028), p 0.36, upper bound 0.025 < 1/20 |
| D | mean increment over D at least 1/20 | **fails** (-0.0056) |
| H | nonnegative on verification-ambiguous queries | passes: +0.0049 per query over 186 groups (1,024 queries), p 0.40 |
| E, F, G | leakage, order, overlap | pass |

D alone selects the correct candidate at 0.591 (p 6.9e-16 against chance).
Adding the failure evidence changes accuracy by -0.6 points (95% interval
-2.6 to +1.4), and the matched-shuffle control says the evidence the query actually
received is no better than a matched donor's.

## Twin control (42 training groups, pair-aware 7-fold cross-validation)

| | value |
|---|---|
| accuracy D | 0.586 |
| accuracy D+F_ASSOC | 0.574 (A passes, p 0.007) |
| accuracy D+F_SHUFFLED | 0.580 |
| accuracy D+F_TWINSWAP | 0.539 |
| B | fails decisively (-0.012) |
| C | fails decisively (-0.006) |
| against the twin swap | +0.036, p 0.17 |

Because the twin control does not pass A to D, TWIN_ONLY_SELECTION_SIGNAL does
not apply. Even under shared inputs, the selector gains nothing over D.

## Reported, not gated

**All conditions:**

| condition | accuracy | NLL |
|---|---|---|
| D (D_RICH) | 0.591 | 0.703 |
| D+F_ASSOC | 0.585 | 0.740 |
| D+F_SHUFFLED | 0.580 | 0.849 |
| D+F_NOVSIG | 0.593 | 0.723 |
| D+F_NOVSIG_SHUFFLED | 0.573 | 0.849 |
| D+F_SEARCH | 0.581 | 0.815 |
| D+F_SEARCH_SHUFFLED | 0.567 | 0.916 |
| D_AGG | 0.577 | 0.665 |
| D_AGG+F_ASSOC | 0.586 | 0.723 |
| F_ASSOC alone | 0.556 | 0.735 |

What the table shows:
- **Some target information.** F_ASSOC alone is above chance (0.556), but
  below D by 0.034 (95% CI -0.062 to -0.007).
- **Association in likelihood, no selection value.** The associated evidence
  has 0.109 nats lower NLL than the shuffled evidence. But adding it to D
  raises NLL by 0.037 nats, so the combined model is more confident without
  being more accurate.
- **No channel adds value over D.** The explanatory channels:

  | channel | against D | against its shuffle |
  |---|---|---|
  | F_NOVSIG (S7 without value signatures) | +0.002 | +0.0195, p 0.057 |
  | F_SEARCH (trajectory counts) | -0.010 | +0.014, p 0.12 |

- **Seen against unseen candidate pairs.** Pairs whose candidate tokens
  appear in the training groups gain +0.009 (p 0.27, 167 groups). Unseen
  pairs lose -0.026 (one-sided 95% upper bound -0.0008, 121 groups). The
  learned failure weights do not carry over to unseen pairs.
- **By family:** the increment over D lies between -0.056 ((0,0,0), 18
  groups) and +0.007 ((0,1), 88 groups); no family is significant.
- **Shuffle fidelity (test):**
  - mean field correlation between a query's own failure evidence and its
    matched donor's: 0.870 (minimum 0.786);
  - same-family share: 1.0.

  So the failure summary of a query is largely predictable from its
  demonstration summary. That is consistent with the review's major finding
  that F is computed from the demonstrations.
- **Verification diagnostic:**
  - on 1,280 of 2,304 queries (55.6%), the other candidate does not
    reproduce the demonstrations, so plain verification decides the pair;
  - on the 1,024 ambiguous queries, accuracy is D 0.538, D+F_ASSOC 0.543 and
    D+F_SHUFFLED 0.541.

## Supplementary checks (delivery addendum; never change the official result)

**(c) Three-valued verification recomputation:**
- verdict **UNQUALIFIED**: 2,304 episodes, FIT 1,024, NO_FIT 1,280,
  **0 ERROR, 0 mismatches** with the recorded booleans;
- NO_FIT codes: `slot_nonfunctional` 685, `slot_key_unobserved` 248,
  `final_execution_mismatch` 195, `scoped_fit_failed` 152;
- the verification statements above are therefore not limited by errors
  hidden in the record.

**(a) Dependence-aware gate C:** **NOT_SUPPORTED**, governing tier 2.
- **Tier 1** is unresolved. The family-first matched shuffle links every
  group of a family into one donor component, so there are only 5 units
  (88, 79, 77, 26, 18 groups), below the 30-unit minimum.
- **Tier 2** uses 143 fixed within-family blocks: sum +92 units, sign-flip
  p 0.047, not significant at 0.01.
  - Its donors are poorly matched: mean field correlation 0.06 against 0.87
    for the official shuffle.
  - So tier 2 compares a query's own evidence with an unmatched same-family
    donor's. A weak positive there is a looser control than the official
    matched one, not evidence against it.

## What this establishes

For this selector and this training resource:
- the current failure evidence (the S7 descriptor, and each explanatory
  channel) adds no selection value beyond the D_RICH demonstration summary,
  on unseen independent-input target pairs;
- the evidence the query actually received is no more useful than a matched
  donor's.

v1.4's positive result (the failure summary identifies the target under
shared-input twins) does not become an incremental selection gain.

The result does not show that failure carries no information. F alone is
above chance, and it is associated with the target in likelihood. It shows
that, as currently summarized and learned from 42 twin groups, that
information is redundant with what the demonstrations already provide.

## Consequences under the directive of 2026-09-28

- The generic ConstructiveExtensionCompiler is **not licensed** and stays
  blocked. So do the later stages: no-oracle proposal, closed loop, ARC
  pilot, 1,000 tasks, DEV and HOLDOUT.
- **One bounded repair is authorized**, keyed to this class: determine which
  failure channel, if any, is actually associated with the constructive
  decision, then run one clean prospective test on new data.
- If that test also fails, the result is preserved and the constructive
  rollout stops with its exact blocker. There is no further iteration.
- The v1.5 test set is now spent as a test set. It may serve only as
  development data for the repair design, never as the repair's test.
