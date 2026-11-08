# Amendment 8 to Protocol U5 (2 Nov 2026, before any evaluation parent is processed): a tolerant secondary arm, one technical correction, and a private target

`PROTOCOL.md` and Amendments 1 to 7 are unchanged in substance, and the primary arms, labels and transfer conjunction
are unchanged. This file adds to them. Its hash and the new exact code freeze are in `AMENDMENT_8_FREEZE.json` and
`CODE_FREEZE.json`.

**State.**
- No evaluation image has been segmented, no evaluation reference has been decoded, and no arm has touched an
  evaluation parent.
- The protocol's policy freeze is running under the Amendment 7 code.
- The hold stays in place until the coordinator writes `GO_EVALUATION`.

**What was observed first.** The protocol's LIVECell induction (calibration parents only) admitted no operator.
- It specified 10 operators; every one made 0 accepted edits on the validation parents.
- The failure-blind and shuffled controls admitted nothing either.
- The frozen CORA grammar is therefore empty. This amendment was written after that calibration result and before any
  evaluation outcome.

## 1. CORA_TOLERANT: a calibration-informed secondary arm

This arm asks whether the strictness of verify-or-abstain is what blocks biology. It is labelled "calibration-informed
secondary arm, added after the empty LIVECell grammar was observed, before any evaluation outcome". It never replaces
the primary CORA label.

- **Rule (`u5policy.verify_tolerant`).** A program passes if both hold:
  - it is the top program in at least two-thirds of the leave-one-parent-out folds;
  - it harms no demonstration parent.
- **Fixed, not tuned.** The tolerance (2/3) was fixed before the first run. No other value is tried, and nothing is
  tuned.
- **Fold tops.** These come from the protocol's fit: no harm on the fold's parents, positive pooled gain, at least one
  edit, and no conflicting selection. The conflict rule is therefore unchanged.
- **No ties, no restart.** At most one program can be the top of two-thirds of the folds, so there is no tie to break
  and no restart check. The accepted units are that program's executed selection.
- **Unchanged from the protocol:**
  - the exact certification of the decisive programs (the passing program and the fold tops);
  - accepted == applied == logged;
  - the failure records, the specification, the admission checks, the candidate ceilings and the control draws;
  - the work accounting.
  The controls' CPU is again lowered by reuse of the unit tables cached in the same process, and is reported as is.
- **Where it runs.**
  - The admission on LIVECell: `INDUCTION_TOLERANT.json`, with FAILURE_BLIND_TOLERANT ×5 and SHUFFLED_TOLERANT ×5. The
    protocol's `INDUCTION.json` is never rewritten.
  - The in-domain admission on NuInsSeg and MoNuSAC: CORA_TOLERANT_INDOMAIN.
  - Transfer of the tolerant LIVECell grammar to both targets: CORA_TOLERANT.
  - The private target (section 4).
- **Comparators.**
  - STRONG_NATIVE (= ABSTAIN_ALL), plus ALL_ON and MATCHED_SEARCH as fitted in the protocol's freeze. Their work match
    is checked against the tolerant arm's own calibration CPU.
  - The tolerant controls.
  - The same label rule and Amendment 7 work gates. The two-target conjunction is computed for this arm as a secondary
    result.
- **Files.** `POLICY_FREEZE_TOLERANT.json`, `DECISIONS_FROZEN_TOLERANT.json`, and `results/RESULTS_TOLERANT.json` with
  `SUMMARY_TOLERANT.md`.
- **Order.** The arm is decided and scored after the primary results are committed (`scripts/tolerant_chain.sh`).
- **Chronology.** The tolerant LIVECell induction started at 13:33:41Z on calibration parents, with its code files
  hashed at launch.
  - At 13:39:00Z it stopped at the defect in section 2, with nothing written.
  - It was re-run from the start at 13:42:09Z under the corrected code; the hashes are in
    `work/TOLERANT_INDUCTION_CODE.sha256` and equal this freeze.

## 2. Technical correction: the alias check of add_lowthresh edits (`u5induce.alias_share`)

- **The defect.** The alias check built the image without the low-threshold segmentation. It therefore failed on the
  first accepted add_lowthresh validation edit.
- **Why the protocol's runs were not affected.** Under the protocol's rule no add_lowthresh edit was accepted on
  LIVECell's validation parents, so `INDUCTION.json` never reached this path.
- **The fix.** The check now reads the same low-threshold labels that the policy used. No rule changes, and an added
  object still counts as neither a deletion nor an alias.
- **The running policy freeze.** It runs the protocol's in-domain admission under the Amendment 7 code.
  - If it reaches this path, it stops, and it is re-run from the start under this freeze.
  - Otherwise its output is identical under both codes, because the fix changes only the path that failed.

## 3. Evaluation code generalized, with primary behaviour unchanged

- **The refactor.** `u5eval.evaluate` now passes a scope configuration to `_evaluate`: the main arm, its controls, its
  induction record, its CPU source and its output files.
- **Evidence of no change.** A mock evaluation on calibration data gives a byte-identical `RESULTS.json` under the
  Amendment 7 and Amendment 8 code (sha256 `07cb386c...`).
- **Test (a).** It now inspects `_evaluate`, which holds the order of the work gates and the transfer block.
- **Private-side skips.** The replay and abstention statistics skip images decided on a side that a scope does not
  score. This is used only by the private target; every public decision covers exactly its scored images.

## 4. A private target from the author's own domain

The author authorized the use of their own lesion-phenotyping data, relayed verbatim by the coordinator.

- **What the private target is.** An extra transfer target for the same frozen LIVECell policies (CORA, its controls
  and CORA_TOLERANT), plus its in-domain arms.
- **Where it is specified.** A private addendum, kept outside git with the target's reader, segmentation script and
  chain. Their hashes are recorded in `AMENDMENT_8_FREEZE.json`, so the addendum is frozen without being published.
  - Both were frozen before any of its masks was read and before GO.
  - The addendum fixes the items, the parents, the split, the baseline, the thresholds and the reporting.
  - The split uses the protocol's rule, and the baseline is chosen by its source study's own validation metric,
    never by these references.
- **Generic hooks in git:**
  - `u5data.private_adapter` and `Reader`: a private target's evaluation and sensitivity references are guarded like
    evaluation references, and its evaluator opens only after its own decisions are frozen;
  - `u5eval.freeze_private`, `decide_private` and `evaluate_private`: outputs go only to mode-0700 folders inside the
    data folder, never under git.
- **Reporting.**
  - Results are aggregate only, labelled "private data; not publicly reproducible".
  - They never enter the protocol's labels, the two-target transfer conjunction or the public release.
- **Still excluded:** the protected third-party data, whose written terms prohibit this use; the private image cohort,
  which has no reference annotations; /tmp/reserved, Step B and VDCG.

## 5. Unchanged

- The primary arms, their labels, the transfer conjunction and the hold.
- The neural-proposal arm: "not delivered: source NO_GO".

## 6. Files and tests

- **Changed:**
  - `scripts/u5policy.py`: `verify_tolerant`;
  - `scripts/u5run.py`: `run_policy(rule=...)`;
  - `scripts/u5induce.py`: the rule parameter, the tolerant record, unrounded CPU, and the alias-check fix;
  - `scripts/u5eval.py`;
  - `scripts/u5data.py`: the private hook;
  - `tests/test_u5.py`.
- **New:** `scripts/tolerant_chain.sh`.
- **Tests:** 25 in all, the 21 earlier ones plus four new:
  - the exact two-thirds rule and the harm condition;
  - certification and reconciliation of the tolerant arm, which accepts three operators on synthetic scenes where the
    protocol's rule abstains on one (RESTART_UNSTABLE);
  - the tolerant record's isolation from `INDUCTION.json`;
  - the alias check of an add_lowthresh edit.
