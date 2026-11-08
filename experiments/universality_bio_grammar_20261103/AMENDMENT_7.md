# Amendment 7 to Protocol U5 (2 Nov 2026, before any evaluation parent is processed): two work-match repairs from the independent re-review

`PROTOCOL.md` and Amendments 1 to 6 are unchanged in substance. This file adds to them. Its hash and the new exact code
freeze are in `AMENDMENT_7_FREEZE.json` and `CODE_FREEZE.json`.

**State.** No evaluation image has been segmented, no evaluation reference has been decoded, and no arm has touched an
evaluation parent. The policy freeze had not started: it was held (both shared CPU slots kept free of it) until this
code was frozen, so `POLICY_FREEZE.json` is computed only under this amendment. The hold stays in place until the
coordinator writes `GO_EVALUATION`.

The independent re-review of Amendments 5 and 6 passed everything except the two defects below. This amendment applies
its minimal patch.

## 1. An underworked MATCHED_SEARCH can no longer pass the label or the transfer conjunction (`u5eval.py`)

- **Label.** CROSS_DOMAIN_USEFUL becomes INCOMPLETE_CONTROLS when either the failure-blind or shuffled controls are not
  work-matched, or MATCHED_SEARCH is underworked. Before, only the controls were checked.
- **Order.** The gate is applied to each dataset's label before the transfer block reads the per-target labels. Two
  targets with an underworked MATCHED_SEARCH therefore cannot give `LEARNED_TRANSFER`.
- **Failure-evidence diagnostic.**
  - WITHHELD_UNMATCHED_WORK when the controls are unmatched (unchanged).
  - WITHHELD_UNMATCHED_MATCHED_SEARCH when MATCHED_SEARCH is underworked (new).
  - SUPPORTED or NOT_SUPPORTED only when all work is matched.
- **Records.** The label before the work gates is recorded as `label_before_work_gates`. The protocol's label rule is
  unchanged. It moved into `claim_label` so the regressions run the same code as `evaluate`.

## 2. A budget stop inside a step ends the matched search as "budget reached" (`u5static.py`)

`_step_candidates` stops before an operator's program space when the CPU budget is spent, and returns the candidates
of the operators already scored.

- **Fix.** `fit_matched` now detects that stop right after the call, and the search ends at once as "budget reached".
  - The partial candidate list is counted (`programs_scored`, `partial_step_candidates_discarded`) but never applied.
  - The interrupted stage is not recorded as completed.
  - The result is the best program of the completed depth levels.
- **The defect.** Before, a stop at the last step of the final stage was labelled "schedule exhausted", and the partial
  beam could become the program. Reproduced on the Amendment 6 code with test (b)'s injection: two beam applications
  after the stop, and a two-step program taken from the partial beam.
- **Matched-work rule.** MATCHED_SEARCH is work-matched when either:
  - its CPU is at least half of CORA's calibration CPU; or
  - its whole schedule completed: every stage recorded, and no in-step stop.

  A record that says "schedule exhausted" but has an in-step stop or a missing stage is not matched.

## 3. Factor-of-two decisions use unrounded CPU

- **New exact records.** `fit_matched` returns `cpu_s_exact`, and the policy freeze records
  `CORA_calibration_cpu_s_unrounded`.
- **Inputs still rounded.** CORA's induction CPU and the controls' admission CPU come from the LIVECell induction
  record. Under the Amendment 6 code, which is byte-identical in every file that writes it, that record is written to
  one decimal. It is not re-run.
- **The rule.** Every factor-of-two decision uses an unrounded value where one is recorded. Otherwise it takes the
  worst case of the rounding interval: plus or minus 0.05 s for each one-decimal value, and plus or minus 0.155 s for
  CORA's calibration CPU (three one-decimal roundings and one two-decimal rounding).
- **Consequence.** Rounding near zero can make a comparator unmatched, never matched.

## 4. Neural-proposal arm

The independent lane's proposers V1 and V2 both failed their source gates (NO_GO). No neural proposal file will be
scored, and none exists under the data folder. The arm is reported as "not delivered: source NO_GO".

## 5. Files and tests

- **Changed:** `scripts/u5static.py`, `scripts/u5eval.py` and `tests/test_u5.py`. Every other frozen file is
  byte-identical.
- **The running induction is unaffected.** The LIVECell induction now running writes `INDUCTION.json` with code that is
  identical under the Amendment 6 and 7 freezes: `u5induce.py`, `u5run.py`, `u5policy.py`, `u5core.py`, `u5tax.py`,
  `u5probe.py` and `u5data.py` are unchanged, and `u5induce` imports neither `u5static` nor `u5eval`.
- **Tests:** 21. These are the 17 earlier ones and four regressions:
  - **(a)** All held contrasts positive and the controls work-matched, but MATCHED_SEARCH underworked. Expected: both
    targets INCOMPLETE_CONTROLS, `LEARNED_TRANSFER` false, and the evidence diagnostic withheld. With MATCHED_SEARCH
    matched, the same case passes. The test also checks that `evaluate` applies the gates before the transfer block.
  - **(b)** An in-step budget stop injected at the last step of the final stage. Expected: "budget reached", the
    partial beam not applied, its scored programs counted, the stage not completed, and unmatched when the work is
    short.
  - **(c)** Control: full schedule exhaustion stays matched whatever the CPU; forged exhaustion records do not.
  - **(d)** Rounding near zero cannot make a comparator matched; unrounded values decide when recorded.
