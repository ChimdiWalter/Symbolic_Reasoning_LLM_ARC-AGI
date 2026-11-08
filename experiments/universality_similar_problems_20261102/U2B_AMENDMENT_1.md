# U2b Amendment 1 (2 Nov 2026, before any new arm is run or scored)

**Why this amendment exists.** It responds to the independent pre-run review:
- the review is `<companion study folder>/u2b_blind_review_20261102/INDEPENDENT_REVIEW_V1.md`, sha256
  `1ad383871d99be49…`;
- `U2B_PROTOCOL.md` (sha256 `25260d2d…`) is unchanged;
- this file takes precedence where the two differ.

Its own freeze hash is in `U2B_AMENDMENT_1_FREEZE.json`.

**State when written.** No new arm had run, and no FIT_ONLY, B1, B2, B3 or matched-search answer had been scored. The
chain was held by `HOLD_U2B`, which the coordinator created at 14:09Z.

## 1. The primary contrast, renamed

- **The statistic is unchanged:** precision(H-CAST, B3) − precision(FIT_ONLY), on REAL, pooled over the three
  benchmarks.
- **The decision is now named B3_POLICY_RAISES_PRECISION** if its 95% lower bound is above 0. Otherwise it is
  NOT_SHOWN.
- **What it measures is the whole selective B3 policy:**
  - module choice (B3 may accept a later module than FIT_ONLY's);
  - genuine top-1 leave-one-out;
  - agreement among fitting programs across modules;
  - fold agreement;
  - restart stability.
- **It does not measure leave-one-out alone.** The protocol's question about "CORA's leave-one-out acceptance" is read
  as a question about B3's selective acceptance policy.

## 2. Three new secondary contrasts (Holm over the enlarged family: S1 to S13)

**The new contrasts.** All are pooled, on REAL.

| id | contrast | what it isolates |
|---|---|---|
| S11 | precision(B2) − precision(FIT_ONLY) | B2 is genuine top-1 leave-one-out, without B3's other checks |
| S12 | the same-module diagnostic for B3 | B3's acceptance filter, with the module held fixed |
| S13 | the same-module diagnostic for B2 | leave-one-out acceptance, with the module held fixed |

**The same-module diagnostic, defined.** It uses the saved `candidate_module` and `accepted_module` fields.

For a policy P (B3 or B2), the same-module subset is every test output where:
- FIT_ONLY gives a non-copy answer; and
- P did not accept a grid from a module other than `candidate_module`.

The diagnostic is precision(P) − precision(FIT_ONLY) on that subset.

**Why it is defined this way.**
- On this subset, P's answers are exactly the fit-only candidates that P accepted from the same module. Its
  abstentions on the same candidates are kept.
- So the contrast measures P's filter with module choice held fixed.
- Restricting further, to outputs where P accepted from the same module, would make the two arms return identical
  grids. The difference would then be zero by construction.

**Grid identity is checked.** On the subset, the number of accepted grids that differ from the candidate grid is
reported; it should be 0.

## 3. Wording about leave-one-out

- **Wording specific to leave-one-out** (for example, "leave-one-out raises precision") is allowed only if all of
  these hold:
  - S11 is Holm-significant and positive, with its lower bound above 0;
  - S13 is Holm-significant and positive, with its lower bound above 0;
  - the identity check finds no mismatch.
- **Otherwise,** results are described as the selection effect of the B3 policy (or of B2), with no causal claim about
  leave-one-out.

The analysis records this rule as `loo_specific_wording_allowed`.

## 4. Reporting additions (from the review)

The report adds:
- child errors and timeouts for the new arms;
- CPU underuse: the main-search CPU against its budget, and the tasks that stopped at their first fitting program;
- coverage;
- a clear distinction between precision among answered outputs and overall accuracy.

**Scope of the matched search.** It searches CAST's own grammar. A positive result is relative to that comparator
only, not to program synthesis systems in general.

## 5. Unchanged

Everything else is unchanged: the tasks, arms, budgets, bootstrap, hold rule and outputs.

## Implementation

- `scripts/u2b_analysis.py` adds the same-module restricted arms, the identity counts, S11 to S13, the renamed
  decision, the wording flag, and the error and underuse counts.
- `tests/test_u2b.py`: 5 tests pass. The end-to-end synthetic test now checks 13 secondaries, the renamed decision and
  the identity counts.
- The code is re-frozen in `U2B_CODE_FREEZE.sha256`. The other frozen files are unchanged.
