# Item-2 v1.5 conditional failure-conditioned selection: design decision

**STATUS: DRAFT, IN PROGRESS, NOT FROZEN.** Saved 2026-09-28 mid-block at the
user's request. No protocol or manifest hash exists yet. No selector has
been fitted on any data, and no v1.5 test group exists. An admission-rate
pilot is running on disjoint pilot seeds (see section 9).

## 1. Parent result, preserved

v1.4 (commit 134e36c, erratum-2 freeze 5ffa56f):
**CURRENT_TFG_IDENTIFYING_UNDER_TWINS**, determined by S7, confirmatory at 42
unique groups. S0 demonstrations 0.664; S2 0.574, S3 0.592, S4 0.571 and S7
0.565 identify the target; S5 and S6 do not; S7a passes only the
randomization test; S2 to S5 react far beyond same-input rerun noise.
The two limitations are load-bearing:
- nothing showed failure evidence adds information beyond demonstrations
  (S0 is stronger than every reasoning stage);
- the positive holds only under shared-input twins, while v1.3 found no
  identifiability on independent inputs.

## 2. Question

Given two legal candidates that differ in one key-feature position, does the
query's associated failure evidence improve selection of the correct
candidate beyond demonstration evidence alone, and does that increment
survive on unseen target pairs under independently rendered inputs?

## 3. Inventory and reuse (decided)

- `cora_arc2026/scorer_fit.py`: `LogLinearScorer` (per-terminal weight rows,
  logits `w_t . x`, x = [1, standardized evidence, 5 grammar-state inputs])
  and `Standardizer` (fit-set mean and SD, constant fields dropped). **Reused
  unchanged.** Its `Standardizer.fit` iterates the fixed v1.2 field list, so
  v1.5 adds `FieldStandardizer`, the same rule on an explicit field list.
- The selection is the scorer's own operation: compare the logits of the two
  legal key-feature tokens at the known differing grammar state (found by
  advancing `GrammarState` through the shared prefix). No new architecture.
- Fit: the pairwise conditional log-likelihood over the two candidates, with
  L2 λ = 0.01 identical in every condition. The objective is strictly convex,
  so the optimum is unique; Newton's method reaches it to 1e-12, replacing
  v1.2's early stopping, so no validation split and no stopping rule is needed.
- `constructive_proposer.py`, the grammar, K and the compiler: untouched.

## 4. Evidence views (decided)

- **D_RICH (primary demonstration baseline, 23 fields):** the six S0
  features plus mean, min and max aggregates of the TFG's per-demonstration
  nodes (delta, palette, shape), which the extractor computes from the
  demonstrations alone.
  - Audit of what the pipeline already produces from demonstrations:
    `features_v12` (the six S0 fields), the TFG demonstration nodes, and the
    v1.3 calibration features (the same six). D_RICH is their union.
  - **D_AGG (secondary):** the six S0 fields, as in v1.4.
- **F_S7 (primary failure view):** the 42-field descriptor.
- **Explanatory failure views:**
  - F_NOVSIG: S7 without its 11 value-signature fields, which are scored
    against the target's own outputs.
  - F_SEARCH (48 fields): counts from the emitted trajectory. S2 typed groups
    and their delta types; S3 selector-induced and no-selector counts, plus
    hashed buckets of selector-predicate operators; S4 fits and fitted delta
    types.
- **Capacity matching:** every condition uses the same input width and the
  same standardizer. Inactive blocks are zero after standardization, so their
  weights never move, and D+F_ASSOC cannot win through extra dimensions.
- **Descriptive only:** `other_candidate_fits` records whether the OTHER
  candidate also reproduces the episode's demonstrations under the fitter. It
  never enters a view. It measures how often plain verification would decide
  the pair.

## 5. Conditions

- Primary: D, D+F_ASSOC, D+F_SHUFFLED.
- Secondary: F_ASSOC only, D_AGG, D_AGG+F_ASSOC.
- Explanatory: D+F_NOVSIG and D+F_SEARCH, each with its shuffled
  counterpart.

## 6. Controls and laws (decided)

- **Matched shuffle:**
  - Greedy global matching on the standardized D_RICH view, using pool
    statistics only; distance ties are broken by index.
  - Pairs must come from different groups; group membership is the only
    metadata used, to forbid copying a same-pair F.
  - Matched pairs swap F. Any leftover joins a 3-cycle with the nearest pair
    from two other groups.
  - D is never moved. The shuffle is built separately within each evaluation
    pool.
- **Candidate order:** sorted by sha256 of the task's demonstrations and the
  token, never by which candidate is true. A tie gives no choice and 0.5
  credit, so the choice is order-invariant exactly.
- **Leak scan of the view:** only the four frozen numeric blocks; no string;
  no value equal to a digest prefix or a seed.

## 7. Data and splits (decided)

- **TRAIN:** the 42 included v1.4 twin groups (336 episodes), fixed.
- **Twin positive control:** grouped 7-fold cross-validation over those 42
  groups. Groups sharing a target digest stay in one fold.
- **TEST:** new independent-input groups. One FEATURE pair from the frozen
  grammar and v1.4 twin law, with 4 admitted episodes per target, each on its
  own seed (pair_seed + 10 t + k) and so its own inputs. The v1.3 admission
  law and the v1.4 observer are unchanged, and there is no
  demonstration-distance filter.
- **Exclusion set** `outputs/tti/v15_exclusion_digests.json`, sha256
  `50349bcf4a0bcd78d7e134ab6cafe3833a01e58f30e2bd532c9a691e67f35219`: every
  target digest (471) and group digest (69) in the v1.2, v1.3 and v1.4
  corpora and the v1.4 smoke records. Test pairs with an excluded or
  already-used target or group are skipped before any engine run, and target
  digests are unique across test groups.
- **Seeds:**
  - test from 300,000,000 and pilot from 400,000,000;
  - grid seeds are seed times 97, disjoint from every earlier range.

## 8. Statistics (decided)

- **Primary loss:** 0-1 selection loss (ties 0.5). Accuracy is kept in units
  of 1/16 per group of 8 queries.
- **Primary inference:** one value per group, with exact one-sided sign-flip
  tests by integer convolution.
  - Gate A: D+F_ASSOC accuracy above 0.5.
  - Gate B: D+F_ASSOC beats D.
  - Gate C: D+F_ASSOC beats D+F_SHUFFLED.
  - Each at p < 0.01.
- **Minimum useful increment** δ_min = +0.05 accuracy (about 0.026 nats at a
  calibrated 0.60 to 0.65). Gate D: the mean increment over D is at least
  δ_min.
  - Justification: S7's standalone twin signal was +6.5 points and S3's was
    +9.2. An increment beyond demonstrations cannot exceed the standalone
    signal, and below about 5 points a 10-way ranking gains under half a
    position.
- **Power:**
  - The variance proxy comes from the completed v1.4 corpus: the S0 against
    S7 hit differences on the same queries (reproducing 0.6637 and 0.5655).
  - Discordance is 0.414, the group-mean SD is 0.2286 and the within-group
    correlation is about 0. The proxy is conservative for the nested
    comparison.
  - Exact sign-flip power, simulated with seed 20260928 over 1000 draws:
    256 groups 0.868, 272 groups 0.895, **288 groups 0.909**; 68 groups at
    +0.10: 0.883.
  - Frozen: **TEST_GROUPS = 288**, **FLOOR_GROUPS = 72**.
  - At exactly δ_min, the joint pass probability of B and D is about 0.5.
    That is disclosed.
  - Found and fixed while computing: my first simulation's convolution
    shifted by 2v instead of v and reported power near 0.1. It was checked
    against brute force before any number was used.
- **Ladder** (first rule wins):
  1. Integrity, order, leak or overlap failure: MIXED_OR_INCONCLUSIVE.
  2. Fewer than 72 groups: MIXED_OR_INCONCLUSIVE.
  3. A, B, C and D all pass: FAILURE_CONDITIONED_SELECTION_GENERALIZES.
  4. The twin control passes the same gates: TWIN_ONLY_SELECTION_SIGNAL.
  5. A negative below 288 groups: MIXED_OR_INCONCLUSIVE.
  6. C fails: FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION.
  7. B or D fails: DEMONSTRATIONS_SUFFICIENT_FOR_SELECTION
     (FAILURE_CONDITIONING_INCREMENT_NOT_ESTABLISHED).
  8. Otherwise: MIXED_OR_INCONCLUSIVE.

## 9. Admission-rate pilot, running

`scripts/generate_v15_pairs.py pilot --slots 60 --wall 2700`, launched
2026-09-28T15:12Z, PID 2448150, output `logs/v15_pilot/` and
`logs/v15_pilot_run.log`. It measures admission rate, runtime and rejection
profile only; no selector exists. Early lines: slot 0 not admitted (4
exclusion skips), slot 1 admitted in 126 s. The frozen slot and wall-clock
caps will be set from its result.

## 10. Written so far (unfrozen)

- `cora_arc2026/v15_sel.py`: generation side (exclusion set,
  independent-input episodes, slot and pair laws) and evaluation side (views,
  queries, order law, matched shuffle, FieldStandardizer, Newton pairwise fit
  on LogLinearScorer weights, scoring, exact tests, twin folds, leak scan,
  gates, ladder).
- `scripts/generate_v15_pairs.py`: pilot and full modes; resumable, writer
  lock, persistent wall clock, per-slot freeze re-verification.
- `outputs/tti/v15_exclusion_digests.json`.

## 11. Remaining, in order

1. Read the pilot; set the slot cap and wall-clock cap.
2. `scripts/evaluate_v15_selection.py`: freeze checks, training-resource hash
   check, test-corpus integrity, all conditions, the twin CV, the
   verification diagnostic, gates and the ladder; run twice, byte-identical.
3. `scripts/check_v15_integrity.py` plus the run scripts, with
   single-threaded BLAS.
4. `tests/test_v15_selection_feasibility.py`:
   - controls: planted signals, order invariance, the shuffle's properties,
     label permutation, intercept only, a duplicated candidate;
   - the leak scanner with injected leaks;
   - exclusion and seed disjointness;
   - the power reproduction;
   - ladder cases;
   - Newton against gradient ascent;
   - neutral blocks staying inert.
5. Protocol `docs/CORA_TTI_FAILURE_CONDITIONED_SELECTION_v1.5.md`, manifest,
   hashes, FREEZE commit; then one reviewer, per the project rule.

Next action after freeze: RUN THE FROZEN v1.5 CONDITIONAL FAILURE-CONDITIONED
SELECTION EXPERIMENT.
