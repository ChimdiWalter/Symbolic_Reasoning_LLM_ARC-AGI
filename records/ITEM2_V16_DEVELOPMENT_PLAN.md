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

## 13. Amendment of 2026-10-02 (user's novelty and pure-reasoning addendum), fixed before any response was read

Recorded at 17:52 UTC while the development responses were still being
computed. No development evaluation had run.

### Arms

| arm | decision rule | fitted weights |
|---|---|---|
| **P0 PURE_CFR** (primary) | deterministic lexicographic rule over each candidate's response, below | none |
| P0_then_D | P0; a P0 tie falls to the D selector | D part only |
| **P1 HYBRID_CFR** (secondary) | D + response through the v1.5 scorer (sections 6 and 7); representation chosen by the selection law of section 10 | yes |
| **P2 PASSIVE_V15** (control) | D + F_S7, the v1.5 selector, fitted on the same training resource | yes |
| D | demonstrations alone | yes |
| F_S7 alone | passive failure alone | yes |

P0 uses only: the demonstrations, the frozen K, exact execution, the
candidate's semantics, its leave-one-out re-derivation, and the fitted
candidate's complexity. No model, no fitted weight, no development-trained
number enters it.

### P0 rule (order and directions fixed now, by mechanism)

Compare the two candidates key by key; the first key that differs decides;
if none differs, P0 makes no choice (half credit):
1. `loo_exact` higher: the candidate re-derived from N-1 demonstrations
   reproduces the held-out one more often (the immutable gate's own
   criterion);
2. `loo_cell_error` lower: smaller held-out residual;
3. `loo_fit_fail` lower: fewer re-derivations with no consistent fit;
4. `table_entries` lower: the simpler fitted candidate (the schema MDL is
   equal within a pair by construction, so complexity lives in the induced
   table).

Keys that the addendum lists but that are inactive in this domain, and why:
- type disconnection, frontier depth, typed continuations: K is a flat
  single-block search with no typed frontier;
- failure-class transition: recorded (`transition`) and audited, but it is
  a coarsening of keys 1 to 3, so it is not a separate key.

Development data may DROP a key only if it is constant on the development
set. Development never reorders keys, flips a direction, or adds a key.
If P0 does not separate the candidates on development data, that is a
development negative for P0 and is reported as such.

### Controls (complete response units)

- **frontier replaced:** the matched donor's response (section 8);
- **identity destroyed:** the two candidates' responses exchanged, so
  Delta becomes -Delta (under P0 this inverts every decision; under P1 it
  tests whether the response must be attached to the right candidate);
- **structurally unseen pairs:** the held-out pair subset (section 11).

### DiscriminativeFailureProbe in this domain

The smallest legal internal probe is the held-out demonstration: refit the
candidate on N-1 demonstrations and render the held-out input. Both
candidates see the identical probe, the comparison value is the
demonstration-visible held-out output, no hidden output exists in these
episodes, and state is restored exactly (checked by hash). That family of N
probes per episode is the probe; its summary is the response vector.

Considered and deferred: metamorphic transformations of the demonstrations.
Deciding which transformations preserve a candidate's semantics needs
per-feature equivariance knowledge, which would put hand-written semantics
into the probe. It is not built in this repair.

### Claim ladder (frozen terms)

LEVEL 0 failure representation contains target information (v1.4);
LEVEL 1 candidate-conditioned intervention predicts the better extension
prospectively (this repair's ceiling); LEVEL 2 a novel extension is
constructed and certified; LEVEL 3 a real ARC task is causally rescued
(B/P/U/L/T/A); LEVEL 4 an extension transfers or is reused; LEVEL 5
extensions accumulate at controlled cost. No level is claimed from evidence
of a lower one.

### Headline rule

If P0 passes the prospective gates, the headline is pure symbolic reasoning.
If only P1 passes, the headline is hybrid failure-conditioned selection, and
it says so. P1 never replaces P0 in the narrative after results are seen.

## 14. Amendment 2 of 2026-10-02, after the development evaluation (development data only)

Recorded at 18:40 UTC from `outputs/tti/v16_dev_report.json` (3d8408e).
These are development facts, never a result:
- P0 as fixed in section 13 decides on 16.3 percent of ambiguous queries
  (`loo_exact` decides 102, `table_entries` 65; the two error keys never
  decide because they tie whenever `loo_exact` ties) and is right on 85
  percent of those; on the rest it makes no choice. With half-credit ties
  it does not beat D (0.557 against 0.563).
- Its replaced-failure control falls to 0.52 (increment +0.038, p < 0.001),
  so the response is specific to the episode.
- P0 then D (the rule first, D on a P0 tie) reaches 0.608 against D 0.563
  (+0.045, interval 0.025 to 0.065, p < 0.001) in both cross-validations.
- P1 (R0 chosen by the law; R1 was also eligible) gives +0.020 (p 0.12) on
  pair-disjoint folds; P2 equals D.

Decisions, before the freeze and before any prospective data:
1. P0 stays the primary arm exactly as fixed; no key is dropped (none is
   constant), none is reordered or flipped. Development says it will most
   likely fail gate B prospectively because it abstains; that is recorded.
2. P0_then_D becomes the second gated arm, ahead of P1. Its headline is
   hybrid: a pure intervention rule with a learned demonstration fallback.
   It gets its own replaced-failure and swapped controls.
3. A significant increment below the floor gets its own class,
   CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR (A, B, C pass at alpha, D fails). It
   does not license the compiler. The floor stays 0.05; it is not lowered.
4. P0's coverage and precision (decided share, accuracy on decided queries,
   D on the same queries) are reported, not gated.
5. Ladder: 0 blocked; 1 floor; 2 P0 full pass; 3 P0_then_D full pass; 4 P1
   full pass; 5 the first arm with A to D and H but not T, named by arm; 6
   the first arm with A, B, C but not D: SIGNIFICANT_BELOW_FLOOR; 7 below
   the target: MIXED; 8 every gated arm fails C decisively; 9 every gated
   arm fails B decisively; 10 otherwise MIXED.
