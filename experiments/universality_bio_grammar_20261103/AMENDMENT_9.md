# Amendment 9 to Protocol U5 (2 Nov 2026, before any evaluation parent is processed): the legacy CPU bound and an acceptance waterfall diagnostic

`PROTOCOL.md` and Amendments 1 to 8 are unchanged in substance. This file adds to them. Its hash and the new exact code
freeze are in `AMENDMENT_9_FREEZE.json` and `CODE_FREEZE.json`.

**State.** No evaluation image has been segmented, no evaluation reference has been decoded, and no arm has touched an
evaluation parent. The protocol's policy freeze is still running. Its decisions are unaffected; this amendment changes
only the evaluator's work-match bound and adds a diagnostic. The hold stays in place until the coordinator writes
`GO_EVALUATION`.

The independent reviews of Amendments 7 and 8 (sha256 `bafed7db...` and `9ad40981...`) passed everything except one
bound. This amendment applies their correction.

## 1. A conservative bound for every CPU record without exact CPU

CORA's calibration CPU on a target is A's induction CPU plus the target's final fit. Its components carry these roundings:

| component | rounding | worst case |
|---|---|---|
| probe CPU of each child, rounded before summation | 0.001 s each; at most 7 classes × 40 tasks = 280 children | 0.140 s |
| probe total | one decimal | 0.05 s |
| admission CPU | one decimal | 0.05 s |
| induction total | one decimal | 0.05 s |
| final fit | two decimals | 0.005 s |
| **all components** | | **at least 0.295 s** |

The 0.155 s slack of Amendment 7 omitted the first row.

- **The rule.** The legacy slack is now `LEGACY_SLACK_S = 0.30` s. It applies to every CORA calibration CPU built from
  records without exact CPU:
  - the protocol's LIVECell record;
  - the tolerant record, whose probe CPU is the same rounded sum;
  - every private-target entry.
  A one-decimal total available without its sum gets another 0.05 s.
- **One source.** `u5eval.cora_cpu_upper` is the only source of this bound, and the work record reports the basis it
  used.
- **The re-review's counterexample.** A recorded CORA CPU of 1.0 s and a budget-stopped MATCHED_SEARCH with an exact
  0.58 s:
  - with the old slack the search was matched (0.58 ≥ 1.155 / 2);
  - with the new slack it is unmatched (0.58 < 1.30 / 2).

## 2. Renamed fields

- **New names.** The policy freeze now writes:
  - `CORA_calibration_cpu_s_recorded_sum`, the sum of the components as recorded (rounded);
  - `CORA_calibration_cpu_s_conservative_upper`, that sum plus 0.30 s.
  The tolerant entries likewise write `CORA_TOLERANT_calibration_cpu_s_recorded_sum` and `..._conservative_upper`.
- **The old name.** `CORA_calibration_cpu_s_unrounded` is no longer written.
  - The protocol's running freeze, started under the Amendment 7 code, still writes it. The evaluator reads it as a
    recorded sum and adds the legacy slack.
  - The tolerant induction record's `cora_induction_cpu_s_unrounded` (written by the unchanged producer) is read the
    same way.

## 3. Regression tests

- **The counterexample.** It is tested with every record variant: the legacy name, the recorded sum, the conservative
  upper, and a one-decimal total alone. All are unmatched at 0.58 s.
- **The matching thresholds.** The sum variants match from 0.66 s (threshold 0.65 s); the one-decimal variant matches
  from 0.68 s (threshold 0.675 s).
- **Test (d) updated.** 0.62 s against a recorded sum of 1.0 s is now unmatched, and 0.70 s is matched.

## 4. An acceptance waterfall diagnostic (calibration only)

`scripts/u5waterfall.py` counts what survives each step of the protocol's acceptance rule for one operator. It works in
the exact admission context on A: the operators admitted before it (none on LIVECell), demonstrations on the induction
parents, and queries on the validation parents. The counts are, in order:

1. programs scored, conflicted, harmless, with positive pooled gain, admissible, and FIT;
2. the units selected by some FIT program and by every one (the near-top intersection);
3. the leave-one-parent-out tops: how many are distinct, how many fall outside FIT, and how many fail on their held-out
   parent;
4. the intersection with the fold tops;
5. the class agreement;
6. the units the executor's conflict rule removes from the top program;
7. verify's own status, the accepted units, and the edits applied through the executor's reconciliation.

These counts are made for the queries and for the demonstrations. It is run once, after this freeze, for `close` on
LIVECell, the one operator that reached EVIDENCE with no accepted edit. The output is `WATERFALL_livecell_close.json`.
No decision depends on it. A test checks that it reproduces verify's FIT size, status and accepted units on synthetic
scenes, and that its stages only narrow.

## 5. Producer code unchanged

- **Unchanged files.** `u5policy.py`, `u5run.py`, `u5induce.py`, `u5core.py`, `u5probe.py` and `u5tax.py` are
  byte-identical to Amendment 8. Those are also the hashes recorded when the tolerant induction was launched.
- **Not re-run.** The LIVECell induction is not re-run, as the reviewers advised.
- **Changed and new.** `scripts/u5eval.py` (the consumer) and `tests/test_u5.py` changed; `scripts/u5waterfall.py` is
  new.
- **Mock check.** On the mock evaluation, the arms, contrasts and labels of the primary scope are identical to
  Amendments 7 and 8. Only the MATCHED_SEARCH work record's upper bound changes, as intended.

**Tests:** 27 (the 25 earlier ones, test (d) updated, plus the counterexample and the waterfall).

**Limit stated by the review.** Work equality is operationalized as:
- for the controls: equal candidate counts plus CPU bounds;
- for MATCHED_SEARCH: the CPU-or-full-schedule rule.

This is the frozen criterion, not a proof of equal search difficulty. The report gives the actual work records.
