# Item-2 v1.5 conditional failure-conditioned selection: design decision

**STATUS: FROZEN, NOT RUN.** Authoritative text:
`docs/CORA_TTI_FAILURE_CONDITIONED_SELECTION_v1.5.md` (sha256
`dc02e1ae9e38076968491cec28d7e142c51228c54ae9ccee17039825efd9c88b`); manifest
`outputs/tti/failure_conditioned_selection_v15_manifest.json` (sha256
`16dc3ef778e9cbeed3e5c906607ccce21023fae4c82b88d0c0eff2d30e09e2b2`). No selector
has been fitted on any real data and no test group exists. The freeze commit
is in `RESUME.md`.

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

## 9. Admission pilot (complete) and caps

The pilot ran 34 slots and admitted 3 groups in 2,887 s.
- Per-slot admission: 0.088, exact 95 percent interval 0.019 to 0.237.
- Time: 84.7 s per slot, 960 s per admitted group.
- By family (admitted / slots): (0,0) 0/7, (1,0) 2/7, (0,1) 1/7, (1,1) 0/7,
  (0,0,0) 0/6.
- Novelty skips: 27 excluded targets and 1 excluded group.

Admission is well below v1.4's twin rate. The likely reason is that the
earlier corpora already used the most easily admitted targets. The pilot
measured admission and runtime only; the verification diagnostic was
deliberately not computed on pilot pairs.

Frozen caps: 288 unique groups, 9,000 slots or 120 h, whichever comes first.
Expected time is about 77 h at the point estimate, 29 h at the upper end of
the interval, and about 95 groups by the cap at the lower end. A positive
stands at 72 groups or more; a negative below 288 is MIXED_OR_INCONCLUSIVE.

## 10. Implementation (frozen)

- `cora_arc2026/v15_sel.py` (core)
- `scripts/generate_v15_pairs.py` (pilot and full)
- `scripts/evaluate_v15_selection.py` (sealed; `--integrity-only`)
- `scripts/v15_power.py` (proxy and power, reproduced exactly)
- `scripts/run_v15_generation.sh`, `scripts/run_v15_evaluation.sh`
- `tests/test_v15_selection_feasibility.py`, 43 tests. Beyond the unit
  tests, they include:
  - every control on synthetic fixtures;
  - a full synthetic end-to-end evaluator run, byte-identical twice;
  - the exact rebuild of the exclusion set;
  - the exact reproduction of the power values.

Reused and hashed unchanged: `scorer_fit.py`, `v14_loc.py`, `v13_gen.py`,
the engine trace, the extractor, the trace hook, the calibration and the
v1.4 training hash list.

Faults found during the block, all fixed before freeze:
- my first power simulation's convolution shifted by 2v (caught by a
  brute-force check);
- the shuffle's first distance computation would have needed about 1 GB
  (replaced by Gram distances);
- two fixture tests unpacked the conditions in the wrong order (a test bug;
  the module was right).

## 11. Next action, exactly one

One adversarial review of the frozen protocol and implementation, per
protocol section 17. Blocking findings are corrected by a recorded erratum
before any test group exists. Then: RUN THE FROZEN v1.5 CONDITIONAL
FAILURE-CONDITIONED SELECTION EXPERIMENT.
