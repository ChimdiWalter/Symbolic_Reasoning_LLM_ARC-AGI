# Item-2 v1.6 bounded repair: development result (DEVELOPMENT ONLY)

Recorded 2026-10-02. Every number here comes from the v1.5 test corpus used
as development data (`outputs/tti/v16_dev_report.json`). None of it is a
scientific result, none of it is a prospective test, and none of it may be
cited as evidence for the repair. The prospective test is a new corpus.

## 1. What was computed

- `scripts/v16_responses.py dev`: the CandidateFailureProbe on all 2,304
  episodes of the 288 development groups (4 workers, about 42 minutes);
  state restored on every group; probe identity `e7d72f67...`, fitter
  identity `2cc45152...`.
- Verification agreement: the probe's own fit check reproduces v1.5's
  verification diagnostic exactly: 1,024 episodes where both candidates fit
  all demonstrations (ambiguous), 1,280 where only the true one fits.
- `scripts/v16_dev_evaluate.py`: CV-A (7 token-pair-component folds; every
  validation pair unseen in its training folds) and CV-B (7 group folds).

## 2. Population

- Ambiguous queries 1,024 of 2,304 (44.4 percent), in 186 of 288 groups.
- By family: (0,0) 77, (0,0,0) 46, (0,1) 271, (1,0) 304, (1,1) 326.
- Ambiguous queries per group: 1 (26 groups), 2 (18), 3 (15), 4 (17), 5 (6),
  6 (2), 7 (9), 8 (93).
- Distinct candidate token pairs: 43. Held-out pairs under the frozen hash
  rule: 15 pairs, 121 groups.

## 3. P0 PURE_CFR (rule fixed before any response was read)

| quantity | CV-A | CV-B |
|---|---|---|
| accuracy on ambiguous queries, D | 0.563 | 0.566 |
| P0 | 0.557 | 0.557 |
| P0 replaced failure (donor response) | 0.519 | 0.501 |
| P0 swapped identity | 0.443 | 0.443 |
| P0 against D | -0.006 (interval -0.043 to +0.030, p 0.64) | -0.009 (p 0.69) |
| P0 against replaced failure | +0.038 (0.023 to 0.053, p < 0.001) | +0.056 (p < 0.001) |

Why P0 does not beat D: it makes no choice on 83.7 percent of ambiguous
queries. `loo_exact` decides 102 queries and points at the truth in 87 (85.3
percent); `table_entries` decides 65 and is right in 55 (84.6 percent);
`loo_cell_error` and `loo_fit_fail` never decide, because they tie whenever
`loo_exact` ties. A tie scores one half, below D's 0.563.

No key is constant, so none is dropped. The order and the directions were
not changed. Family increments over D: (0,0,0) +0.196 (12 groups), (0,0)
+0.039, (1,1) +0.018, (0,1) -0.037, (1,0) -0.048; no family with at least
10 groups is below -0.05.

## 4. P0 then D (rule first, demonstrations on a tie)

| quantity | CV-A | CV-B |
|---|---|---|
| accuracy on ambiguous queries | 0.608 | 0.613 |
| against D | +0.045 (0.025 to 0.065, p < 0.001) | +0.047 (0.025 to 0.068, p < 0.001) |

Development discordance with D and with its replaced-failure control: see
`outputs/tti/v16_dev_report.json` (fields `P0_then_D_discordance_*`).

## 5. P1 HYBRID_CFR

| representation | CV-A against D | CV-A against replaced failure | CV-B against D | eligible |
|---|---|---|---|---|
| R0 raw Delta | +0.020 (p 0.12) | +0.011 (p 0.27) | +0.014 (p 0.21) | yes |
| R1 ambiguous-trained | +0.024 (p 0.09) | +0.014 (p 0.14) | +0.046 (p 0.004) | yes |
| R2 residualized | -0.004 | -0.011 | +0.019 | no (rules 5, 6, 7) |

Selection law: R0 and R1 are eligible with the same four active fields; the
tie goes to R0 by procedure order. **P1 representation: R0.**

P1 swapped identity (R0): 0.535 in CV-A, below D. Response alone (R): 0.513.

## 6. P2 PASSIVE_V15 and the passive channel

- P2 (D + F_S7, same training resource): 0.562 against D 0.563, increment
  -0.002. The v1.5 negative reproduces on this population.
- F_S7 alone: 0.504 (CV-A).

## 7. Seen against unseen (CV-B, validation queries)

| subset | groups | D | P0 | P1 | P2 | P0 against D | P1 against D |
|---|---|---|---|---|---|---|---|
| structural pair seen | 146 | 0.586 | 0.558 | 0.592 | 0.586 | -0.028 | +0.006 |
| structural pair unseen | 40 | 0.490 | 0.552 | 0.533 | 0.486 | +0.062 | +0.043 |
| token pair seen | 180 | 0.574 | 0.556 | 0.585 | 0.572 | -0.018 | +0.011 |
| token pair unseen | 6 | 0.280 | 0.600 | 0.400 | 0.320 | +0.320 | +0.120 |

On unseen pairs the learned D baseline drops toward or below chance while
the P0 rule, which has no fitted weight, does not. Six token-pair-unseen
groups is too few to say more than that.

## 8. Shuffle fidelity (validation pools)

- CV-A: same token pair 0.90, same family 0.35, D_RICH correlation 0.52,
  same verification status 1.0, same group 0.
- CV-B: same pair 0.51, same family 0.59, correlation 0.32.

The donor control therefore mostly compares a query's response with a
response to the same candidate pair on other demonstrations; P0's margin
over it is not a pair-level prior.

## 9. Decisions taken from this development record (plan amendment 2)

1. P0 stays the primary arm, unchanged; it is expected to fail gate B
   prospectively because it abstains. That expectation is recorded here.
2. P0_then_D is the second gated arm, ahead of P1; its headline is hybrid.
3. P1 representation R0.
4. The floor stays 0.05. A significant increment below it is named
   CFR_INCREMENT_SIGNIFICANT_BELOW_FLOOR and licenses nothing.
5. P0 coverage and precision are reported, not gated.
6. Sample size from `scripts/v16_power.py` at the lower plausible
   development effects (section 10).

## 10. Power and caps (`outputs/tti/v16_power.json`, `outputs/tti/v16_caps.json`)

- Development discordances on ambiguous queries: P0_then_D against D 0.068,
  against its replaced-failure control 0.078; P1 against D 0.230.
- Exact sign-flip power for gate B (P0_then_D against D), 1,000 simulations,
  seed 20261002, development group sizes: at 280 ambiguous groups 0.92 at
  effect 0.025 (the lower plausible effect) and 1.00 at 0.045; at 240
  groups 0.87 and 1.00.
- The 0.05 floor is not powered: joint pass of B and D at effect 0.045 is
  about 0.25, at 0.05 about 0.5. The floor is retained (plan amendment 2).
- Caps: 440 unique groups (about 284 ambiguous), floor 72 ambiguous groups,
  6,000 slots, 432,000 s from the first start; transfer gate at least 30
  unseen ambiguous groups.
