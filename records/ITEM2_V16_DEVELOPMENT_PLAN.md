# Item-2 v1.6 bounded repair: development plan, fixed before any repair performance is measured

Recorded 2026-10-02, after the v1.5 result (eb5efa5).
- No candidate response has yet been computed on any episode.
- No repair model has been fitted.
- Data facts read so far: candidate-pair counts, demonstrations per episode,
  and the timing of one probe on one episode (base search 0.34 s, one
  candidate fit about 0.01 s). None of them relates a response to the truth.

This plan is the only basis for the development choices. Anything it does not
fix is fixed in the protocol after development, from the development record
and never from a test result.

## 1. Repair question (the one authorized repair)

On candidate pairs that plain demonstration verification cannot settle, can a
candidate-conditioned measurement of how each proposed extension changes the
reasoner's failure state identify the true extension better than the
demonstration summary alone?

Name: **F_CFR**, candidate-conditioned failure response.

## 2. The reasoner and its failure state

The reasoner is the constructive domain's frozen base search K:
- the 200 baseline single-block schemas (`baseline_single_block_schemas`);
- fitted with the occurrence-scoped fitter (`scoped_slot_fitting`, the
  fitter whose identity every v1.2 to v1.5 episode records).

The v1.5 admission law requires K to fail on every admitted episode (R4), so
"the failure" is K's failure on the episode's demonstrations.

Why this reasoner and not another:
- Each candidate is a multi-block schema of the same grammar, so K + {e} is
  defined without translation.
- The full object engine and the blind typed search cannot host a
  multi-block candidate without a compiler. Building that compiler is
  outside this repair.

## 3. CandidateFailureProbe

Inputs: one candidate schema e and the episode's demonstrations. Nothing else:
- no test input or output;
- no target identity;
- no label, digest or seed.

1. **Baseline state S0** is computed once per episode and shared by both
   candidates. It holds K's exact set and its constraint-consistent set on all
   N demonstrations, and K's exact set on each leave-one-out fold.
2. **Exposure.** The arm is K + {e}: K's results are reused unchanged, and e
   is the only added production, fitted by the same fitter.
   - Nothing is installed anywhere.
   - No module table, registry or cache is written.
   - The probe of one candidate holds no state that the probe of the other
     can read.
3. **Leave-one-out re-derivation of K + {e}.** For each demonstration i, e is
   refitted on the other N-1 demonstrations and rendered on input i. The
   immutable gate's discipline is followed: refit from scratch, with no
   fitted value carried from the full fit.
4. **Restoration.** The fitter's module dictionary and K's schema list are
   hashed before and after every probe, and must be identical. Probing A
   then B must give byte-identical responses to probing B then A.

## 4. Response fields (one vector per candidate; at most four active)

| field | definition |
|---|---|
| `loo_exact` | share of folds in which e, refitted on N-1 demonstrations, reproduces the held-out demonstration exactly |
| `loo_fit_fail` | share of folds in which e has no fit on N-1 demonstrations |
| `loo_cell_error` | mean over folds of the fraction of held-out output cells e gets wrong; a missing fit, undefined render or shape mismatch counts 1.0 |
| `table_entries` | total induced table entries of e's fit on all N demonstrations, divided by N |

What is not included, and why:
- **Frontier depth, type distance and type connectivity:** inactive. K is a
  flat single-block search, so there is no typed frontier to measure.
- **Candidate usage potential:** constant, since every grammar-valid
  candidate is type-compatible with K's goal.

The pair representation is the difference
`Delta = r(first) - r(second)` in the v1.5 presentation order (sha256 of the
demonstrations and the token, never the truth). The shared baseline state
cancels in Delta, so Delta compares post-exposure states. That is stated
plainly in every claim.

## 5. Population and routing

- A query is one episode with its candidate pair.
- **Plain verification:** does each candidate fit all N demonstrations? The
  true candidate always fits by admission.
- **Verification-ambiguous query:** both candidates fit.
- **Decided query:** exactly one fits. It is chosen deterministically, and
  that gain is never attributed to failure conditioning.
- **Metrics:**
  - primary: accuracy on ambiguous queries;
  - also reported: end-to-end accuracy (decided queries correct by
    verification, plus the selector on ambiguous ones).

## 6. Representations (the whole menu; no fourth)

- **R0:** the four Delta fields, scaled by their training-pool RMS (no
  centering, which keeps antisymmetry). Trained on all queries; evaluated on
  ambiguous ones.
- **R1:** R0, trained only on ambiguous queries.
- **R2:** residualized Delta, trained on all queries.
  - Each candidate's response field is predicted from the standardized
    D_RICH vector plus a one-hot candidate token, by ridge regression (penalty
    1.0).
  - The predictions are cross-fitted inside the training pool over 5
    token-pair-component folds.
  - Delta_resid = (r_first - r̂_first) - (r_second - r̂_second).

## 7. Model (the v1.5 family, one addition)

- **D part:** the v1.5 conditional logit, unchanged. Per-token weight rows
  over x = [1, standardized D_RICH (23 fields), grammar state (5)]; pairwise
  logit (w_a - w_b) · x.
- **Response part:** shared weights v on the representation's Delta
  (`+ v · Delta`). They are not token-specific, so they can apply to unseen
  pairs.
- **Fit:** L2 penalty 0.01 on all weights; Newton's method to a maximum step
  below 1e-12, at most 100 iterations; convergence required.
- **Tie rule:** a tie below 1e-12 gives half credit.
- **Order invariance:** exact by construction, and tested.
- **Conditions in development:**
  - D;
  - D + R;
  - D + R_shuffled;
  - R alone, for each representation.
- **Implementation check:** with zero response columns, the fitter must
  reproduce v1.5's `fit_pairs` weights to 1e-9 on the v1.5 training set.

## 8. Matched shuffle (complete response units)

- The recipient keeps its D; its whole Delta vector is replaced by a donor's.
- **Donor rules:**
  - the donor comes from a different group in the same pool, with the same
    verification status;
  - the donor preferably has the same candidate token pair, and its Delta is
    re-oriented to the recipient's candidate order by token identity;
  - otherwise the donor has the same structural family, with its Delta in its
    own presentation order;
  - among eligible donors, the nearest by standardized D_RICH;
  - greedy 2-cycles, a 3-cycle for any leftover, ties broken by index.
- **Reported:** fidelity, as the share with the same token pair, the share
  with the same family, and the own-against-donor D_RICH correlation.

The control asks whether THIS episode's response beats a response to the same
kind of pair on other demonstrations.

## 9. Development cross-validation (v1.5 test set used as development data only)

- **CV-A (primary, transfer):** folds are connected components of groups
  that share a candidate token pair (target digests are already unique),
  dealt round-robin over 7 folds in order of smallest group digest. Every
  validation pair is unseen in its training folds.
- **CV-B (secondary, familiar pairs):** 7 folds over groups dealt round-robin
  by group digest. Pairs are mostly seen.
- Shuffles are built within each training pool and each validation pool
  separately.
- **Group unit on ambiguous queries:** the sum of per-query differences in
  half-credit units over the group's ambiguous queries. Groups with no
  ambiguous query drop out of ambiguous metrics.
- **Development statistics** are descriptive. Their p values are reported for
  orientation only and never presented as a result.

## 10. Development selection law (fixed now)

A representation is **eligible** only if all hold:
1. the leakage scan is clean (the view holds only the frozen numeric fields;
   no value echoes a digest, seed or label);
2. every fit in every fold converges;
3. the choice is order-invariant on every query;
4. the CV-A folds are valid: no group in two folds, and no token pair in both
   a training and a validation pool;
5. in CV-A, on ambiguous queries, D + R beats D + R_shuffled (mean group
   difference > 0);
6. in CV-A, on ambiguous queries, the increment of D + R over D is > 0;
7. no collapse: in CV-A, no structural family with at least 10 ambiguous
   groups has an increment over D below -0.05.

Among eligible representations, the one with the fewest active fields is
chosen. Ties are broken in the order R0, R1, R2 (increasing procedure
complexity).

If no representation is eligible, the block records
DEVELOPMENT_NO_ELIGIBLE_REPRESENTATION, freezes no prospective test, and the
next action becomes a user decision.

## 11. Transfer design for the prospective test (fixed now)

The final selector is trained on the v1.5 groups minus a frozen set of
held-out token pairs. That set holds every token pair whose
`sha256("v16-heldout|" + pair_key)` has a first hex digit in 0 to 4, about
5/16 of pairs.
- Prospective groups whose pair is in that set, or absent from the v1.5 set
  entirely, are **structurally unseen**.
- The protocol freezes a minimum unseen count, and a transfer gate on that
  subset.

## 12. Audit categories (development)

Seen and unseen are reported for:
- candidate token pairs;
- structural pairs (anchor family + token pair);
- failure-class transitions (K's baseline class, the first candidate's
  leave-one-out class, the second's).
