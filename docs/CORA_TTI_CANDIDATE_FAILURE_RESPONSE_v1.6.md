# CORA-TTI Item-2 v1.6: candidate-conditioned failure response (the one bounded repair)

Status: FROZEN 2026-10-02 (manifest `outputs/tti/candidate_failure_response_v16_manifest.json`).
Written after the v1.5 result (eb5efa5), the development block fixed by
`records/ITEM2_V16_DEVELOPMENT_PLAN.md` (3bcb8e7; amendment 1 788cfc3 before
any response was read; amendment 2 533c189 after the development evaluation
and before any prospective data), and the development record
`records/ITEM2_V16_DEVELOPMENT_RESULT.md`. Nothing here changes after the
freeze except by a recorded erratum made before any prospective outcome is
seen.

## 1. Question

On candidate pairs that demonstrations and plain verification cannot settle,
does a candidate-conditioned measurement of how each proposed extension
changes the reasoner's own failure state identify the true extension better
than the demonstration summary alone, prospectively, on independent-input
pairs disjoint from every earlier corpus?

v1.5 (FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION, 288 groups) asked what
the failure looks like. v1.6 asks what happens to it when a candidate is
exposed. This is the single repair authorized after v1.5. If it fails, the
failure-conditioned constructive rollout stops with its exact blocker; no
repair v2 follows.

## 2. Reasoner, failure state and probe

- **Reasoner K:** the constructive domain's frozen base search, the baseline
  single-block schemas fitted with the occurrence-scoped fitter
  (`cora_tti.scoped_slot_fitting`, identity recorded in every episode). The
  admission law requires K to fail on every admitted episode, so "the
  failure" is K's failure on the episode's demonstrations.
- **Why this reasoner:** every candidate is a multi-block schema of the same
  grammar, so K + {e} is defined without a compiler. The full object engine
  cannot host a multi-block candidate without the compiler that this repair
  must not build.
- **CandidateFailureProbe**, for one candidate e and the N demonstrations:
  1. the baseline state S0 (K's exact and constraint-consistent sets on all
     N demonstrations and on each N-1 fold) is computed once per episode and
     shared by both candidates;
  2. e is exposed as K + {e}: K's results are reused, e is the only added
     production, fitted by the same fitter; nothing is installed, no table
     or cache is written, and the two candidates' probes share no state;
  3. the smallest legal internal counterfactual: for each demonstration i,
     e is refitted from scratch on the other N-1 and rendered on input i;
     both candidates see the identical probes, and the comparison value is
     the demonstration-visible output i (these episodes hold no hidden
     output);
  4. a hash of the fitter's and the meta language's module state and of K's
     schema list is taken before and after every probe and must be equal;
     probing A then B must equal probing B then A byte for byte.
- **Response fields** per candidate: `loo_exact` (share of held-out
  demonstrations reproduced exactly), `loo_fit_fail` (share of
  re-derivations with no consistent fit), `loo_cell_error` (mean fraction of
  held-out cells wrong; a missing fit or undefined render counts 1),
  `table_entries` (induced table entries of the full fit, per
  demonstration). Pair representation: Delta = r(first) - r(second) in the
  v1.5 presentation order (hash of the demonstrations and the token, never
  the truth).
- **Inactive by domain:** type disconnection, frontier depth and typed
  continuations (K has no typed frontier); candidate usage potential
  (constant); failure-class transition (recorded and audited; a coarsening
  of the fields above).
- **Considered and not built:** metamorphic transformations of the
  demonstrations, because deciding which transformations preserve a
  candidate's semantics needs per-feature equivariance knowledge, which
  would put hand-written semantics into the probe.

## 3. Population and routing

- A query is one admitted episode with its candidate pair.
- Plain verification: does each candidate fit all N demonstrations? The true
  candidate always fits by admission.
- **Decided query:** exactly one fits; chosen deterministically; never
  credited to failure conditioning.
- **Verification-ambiguous query:** both fit. The primary population.
- Reported: accuracy on ambiguous queries (primary) and end-to-end accuracy
  (decided queries by verification, ambiguous ones by the arm).
- Development fact: 1,024 of 2,304 v1.5 queries (44.4 percent) in 186 of
  288 groups are ambiguous; the probe's own fit check reproduces the v1.5
  verification diagnostic exactly.

## 4. Arms

| arm | rule | fitted weights |
|---|---|---|
| **P0 PURE_CFR** (primary) | lexicographic over the response keys, in order with fixed directions: `loo_exact` higher, `loo_cell_error` lower, `loo_fit_fail` lower, `table_entries` lower; the first key that differs decides; otherwise no choice (half credit). Keys: all four (none was constant in development). | none |
| P0_then_D (second gated arm) | P0; a P0 tie falls to D; headline hybrid | D part only |
| **P1 HYBRID_CFR** (secondary) | the v1.5 conditional logit over [1, standardized D_RICH, grammar state] plus shared weights on the RMS-scaled raw Delta (representation R0, chosen by the frozen development law; R1 was also eligible, R2 was not); L2 0.01; Newton to 1e-12; convergence required | yes |
| **P2 PASSIVE_V15** (control) | D + F_S7 through the v1.5 scorer, fitted on the same training resource | yes |
| D | demonstrations alone | yes |
| F_S7 | passive failure alone | yes |
| R | response alone through the logit | yes |

P0 uses only the demonstrations, the frozen K, exact execution, the
candidate's semantics, its leave-one-out re-derivation and the fitted
candidate's complexity. No model, fitted weight or development-trained
number enters it. The P0 order was fixed on 2026-10-02 before any response
was read; development could only drop a constant key.

## 5. Controls

- **Frontier replaced (matched donor response):** each query's whole Delta
  replaced by a donor's from a different group in the same pool with the
  same verification status; donors with the same candidate token pair are
  preferred (their Delta re-oriented to the recipient's candidate order by
  token identity), then the same structural family; nearest by
  pool-standardized D_RICH; greedy 2-cycles, a 3-cycle for any leftover,
  ties by index. Fidelity (same-pair share, same-family share, D_RICH
  correlation) is reported. Applied to P0 (P0_SHUFFLED) and to P1 (model
  fitted on shuffled training Delta, scored on shuffled test Delta).
- **Identity destroyed (swapped):** the two candidates' responses exchanged,
  Delta becomes -Delta. Under P0 this inverts every decision exactly; under
  P1 it tests that the response must be attached to the right candidate.
- **Structurally unseen pairs:** candidate token pairs held out of training
  by the frozen rule (sha256("v16-heldout|" + pair_key) first hex digit in
  0 to 4) or absent from the training resource.

## 6. Data

- **Development resource:** the v1.5 test corpus, 288 groups (its official
  result is spent; it is development data only). Its responses:
  `outputs/tti/v16_dev_responses.json`.
- **Training resource for P1, P2, D, F_S7, R:** development groups whose
  token pair is not held out: 167 groups (121 groups on 15 held-out pairs
  are excluded from training).
- **Prospective test corpus:** generated by `scripts/generate_v16_pairs.py`
  under the v1.5 admission law unchanged (one FEATURE pair per group from
  the frozen grammar, 4 admitted episodes per target on independent seeds,
  the same full-engine observation), seed base 500,000,000, slot stride
  10,000, attempt stride 100, 25 attempts per slot, families in the frozen
  order. Pairs are skipped before any engine run if the group or either
  target digest is in the exclusion set or already in the corpus.
- **Exclusion set:** `outputs/tti/v16_exclusion_digests.json`, sha256
  e936bc6fe364fba1d1c26ba5c2615744b60c6edfd552b59d4daf2f46c8c208ea: every
  v1.2, v1.3, v1.4, smoke and v1.5-pilot digest (the v1.5 exclusion set,
  477 targets, 72 groups) plus every target and group digest in the v1.5
  test corpus including its skip records (2,094 targets, 2,430 groups in
  total).
- **Test responses:** computed after generation by `scripts/v16_responses.py
  test`; a pure function of (candidate schema, demonstrations); the probe
  identity, the fitter identity and the state-restoration flag are recorded
  and checked.

## 7. Statistics

- **Unit:** half-credit units per query (2 right, 1 tie, 0 wrong); a group's
  value is the integer sum over its ambiguous queries of the unit
  difference between two arms. Groups with no ambiguous query drop out.
- **Inference:** exact one-sided sign-flip over group sums by integer
  convolution, alpha 0.01; the exact sign test and group-clustered 95
  percent intervals are reported.
- **delta_min:** 0.05 per ambiguous query, retained from v1.5. Development
  put the best arm's point estimate at 0.045 (interval 0.025 to 0.065), so
  the floor is not powered: a significant increment below it is classified
  CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR and licenses nothing. The floor was
  not lowered because no principled threshold other than the inherited one
  was found; this risk is accepted and recorded.
- **Decisive failure:** not significant at 0.01 AND one-sided 95 percent
  upper bound below delta_min.
- **Sample size:** target 280 ambiguous groups, floor 72, from
  `scripts/v16_power.py` (seed 20261002, 1,000 simulations, development
  group-size distribution, P0_then_D discordance with D 0.068): gate B power
  0.92 at the lower plausible effect 0.025 and 1.00 at 0.045 with 280
  ambiguous groups. Caps: 440 unique groups (about 284 ambiguous at the
  development share of 0.646), 6,000 slots, 432,000 s from the first start.
  A positive stands at 72 ambiguous groups or more; a negative below 280 is
  MIXED_OR_INCONCLUSIVE.
- **Dependence (supplementary):** `scripts/v16_supp_dependence.py`, tier 1
  donor-graph components, tier 2 fixed within-family blocks, at least 30
  units, whole-unit sign flips; never changes the official result.

## 8. Gates (each arm; the primary arm is P0)

- A: above 1/2 on ambiguous queries, p < 0.01.
- B: beats D on ambiguous queries, p < 0.01.
- C: beats its matched donor-response control, p < 0.01.
- D: mean per-query increment over D >= delta_min.
- E: zero leakage (the response view holds only the four finite floats; the
  truth never enters a view; no digest, seed or label echoes).
- F: order-invariant choice for every query and arm (exact by construction
  for P0 and the logit; checked).
- G: digest disjointness (no target or group digest shared between the
  training resource and the test; none repeated within the test).
- H: nonnegative observed increment over D on ambiguous queries.
- T (transfer): on structurally unseen pairs (the 15 held-out token pairs
  or any pair absent from the training resource), at least 30 ambiguous
  groups, a positive increment over D, and above chance at p < 0.05.

## 9. Classification ladder (first rule wins)

Gated arms, in order: P0, P0_then_D, P1.
0. freeze, integrity, leakage, order, overlap or convergence failure:
   MIXED_OR_INCONCLUSIVE (AUDIT_BLOCKED);
1. ambiguous groups < floor: MIXED_OR_INCONCLUSIVE, no statistic computed;
2. P0 passes A, B, C, D, H, T: **PURE_CFR_SELECTION_GENERALIZES**;
3. P0_then_D passes A, B, C, D, H, T:
   **PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES** (hybrid headline);
4. P1 passes A, B, C, D, H, T: **HYBRID_CFR_SELECTION_GENERALIZES**;
5. the first gated arm passing A, B, C, D, H but not T: that arm's
   FAMILIAR_PAIRS_ONLY class (does not license the compiler);
6. the first gated arm passing A, B, C at alpha but not D:
   CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR (does not license the compiler; the
   floor is not lowered);
7. ambiguous groups < target: MIXED_OR_INCONCLUSIVE (underpowered negative);
8. every gated arm fails C decisively:
   CANDIDATE_RESPONSE_NOT_EPISODE_SPECIFIC;
9. every gated arm fails B decisively:
   CANDIDATE_INTERVENTION_NO_INCREMENT_OVER_DEMONSTRATIONS;
10. otherwise MIXED_OR_INCONCLUSIVE.

Only rules 2, 3 and 4 license the next block (the generic
ConstructiveExtensionCompiler and the end-to-end K + {e} loop). The headline
follows the arm: rule 2 is pure symbolic reasoning; rule 3 is a pure
intervention rule with a learned demonstration fallback, and is called
hybrid; rule 4 is hybrid failure-conditioned selection. Nothing licenses the
1,000-task run, DEV or HOLDOUT.

Reported, not gated: P0's coverage (share of ambiguous queries on which the
rule decides) and precision (its accuracy on those queries, against D and the
replaced-failure control on the same queries, with the exact above-chance
test); every arm's end-to-end accuracy; P0 and P1 against P2; the swapped
controls; per-family and seen/unseen breakdowns; failure-class transitions.

## 10. Claim ceiling

If P0 passes: a candidate-conditioned measurement of how proposed executable
extensions affect the reasoner's own failure state improves constructive
extension selection beyond demonstrations alone on prospectively generated,
disjoint tasks under the frozen protocol, with no fitted parameter in the
decision. If only P1 passes: the same for a hybrid selector. This is LEVEL 1
of the frozen ladder (LEVEL 0 failure representation carries target
information; 1 intervention predicts the better extension prospectively; 2 a
novel extension constructed and certified; 3 a real ARC task causally
rescued, B/P/U/L/T/A; 4 transfer or reuse; 5 accumulation at controlled
cost). No higher level is claimed from this result. Negatives are
conditional on this probe, this reasoner and this training resource.

## 11. Freeze, review and run order

1. Development evaluation on the v1.5 corpus (DEVELOPMENT ONLY), recorded
   in `outputs/tti/v16_dev_report.json` and `records/ITEM2_V16_DEVELOPMENT_RESULT.md`.
2. Power calculation, caps, this document completed, manifest written by
   `scripts/freeze_v16.py` (pins: protocol, implementation files, dependency
   trees, external files, runtime versions, exclusion set, training hash
   list and responses, development report, power record).
3. ONE adversarial review of the frozen block; defects fixed by recorded
   erratum, re-hash, re-freeze.
4. `scripts/run_v16_generation.sh` (detached, resumable, flock, per-slot
   freeze check, atomic records), then
   `scripts/run_v16_post_generation.sh CHAIN_PID`: test responses,
   integrity only, the sealed evaluator twice byte-compared, dependence.
5. The official verdict and the supplementary checks recorded separately.

Hard isolation: nothing is read from Step B, Reasoning_Project, VDCG,
E_transfer, the Lockbox or protected ARC answers; Reasoning_Project_tti is
used only through the previously authorized read-only dependencies.
