# U2b Amendment 2 (2 Nov 2026, before any new arm is run or scored)

**Why this amendment exists.** It responds to the re-review of Amendment 1. The re-review files are read-only, in
`<companion study folder>/u2b_blind_review_20261102/`:

| file | sha256 |
|---|---|
| `AMENDMENT_1_INDEPENDENT_REVIEW_V1.md` | `58bbcb79…` |
| `AMENDMENT_1_ADVERSARIAL_PROOF.md` | `69db3905…` |
| `amendment1_wording_gate_probe.py` | `b98bdc34…` |

**What it leaves unchanged:**
- `U2B_PROTOCOL.md` (`25260d2d…`) and `U2B_AMENDMENT_1.md` (`1450bc82…`);
- the comparison design;
- the frozen U2 predictions.

**State when written.** No new arm had run, and nothing had been scored. `HOLD_U2B` was still in place.

## 1. The gap that was found

Amendment 1 §3 allows wording specific to leave-one-out only if S11 and S13 are Holm-significant and positive, **and
the identity check finds no mismatch**. The code set `loo_specific_wording_allowed` from the S11 and S13 statistics
alone. It never read the identity counts. The reviewers' probe showed the gate returning True with one B2 mismatch.

## 2. The correction

`loo_specific_wording_allowed` is now True only if all of the following hold:
- S11 and S13 are both Holm-significant, with a positive point estimate and a 95% lower bound above 0;
- `B2_grid_differs_from_candidate` is 0 on every REAL benchmark (ConceptARC, Mini-ARC, 1D-ARC);
- `B3_grid_differs_from_candidate` is 0 on every REAL benchmark. Amendment 1's wording ("no grid-identity mismatch")
  covers both policies.

**Fail-safe:** a missing count, or a missing REAL benchmark, counts as a mismatch.

**Form of the code:** the gate is one expression that uses only `bool`, `all`, `s11`, `s13` and `res`, outside any
nested scope. It can therefore be evaluated on its own, exactly as the reviewers' probe does.

## 3. The adversarial tests (in `tests/test_u2b.py`)

Each test evaluates the frozen gate expression the way the probe does:
- one B2 mismatch, with significant and positive S11 and S13, gives **False**;
- zero mismatches, with the same statistics, gives **True**;
- one B3 mismatch gives **False**;
- a missing REAL benchmark gives **False**;
- a non-significant S11, or an S13 interval reaching below 0, gives **False**.

All 7 tests in the file pass. Run against the corrected code, the reviewers' probe prints
`{"b2_grid_mismatches": 1, "loo_specific_wording_allowed": false}` and stops at its own assertion, "The frozen gate now
rejects the mismatch".

## 4. Unchanged

- The arms, the contrasts (S1 to S13, with Holm over 13), the bootstrap, the budgets and the hold rule are unchanged.
- The code is re-frozen in `U2B_CODE_FREEZE.sha256`. Only `scripts/u2b_analysis.py` (the gate expression and one
  summary line) and `tests/test_u2b.py` changed.
