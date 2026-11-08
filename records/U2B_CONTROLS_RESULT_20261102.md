# Result U2b: the controls U2 lacked (2 Nov 2026)

## Provenance

**Pre-registration and review:**
- **Protocol:** `experiments/universality_similar_problems_20261102/U2B_PROTOCOL.md` (sha256 `25260d2d…`, commit 7c7387e0).
- **Amendments:** two, each written after an independent pre-run review and before any new arm ran:
  - `U2B_AMENDMENT_1.md` (`1450bc82…`): the primary is renamed for the whole B3 policy, the B2 and same-module
    diagnostics are added, and a wording rule is set;
  - `U2B_AMENDMENT_2.md` (`5c457fe0…`): the wording gate must also see zero grid-identity mismatches.
- The re-review passed (coordination outbox 0152).

**The run:**
- Held until GO at 16:12:16Z.
- Six search passes and the analysis, finishing with EXIT 0 at 16:37:32Z.
- Results are in `results/U2B_RESULTS.json` and `U2B_SUMMARY.md` (commit 9d837fe0).

U2's frozen protocol and results are unchanged.

**Tasks:** the same 924 tasks and 1,244 test outputs as U2 (ConceptARC 480, Mini-ARC 149, 1D-ARC 615).

**Intervals:** 95% bootstrap, clustered by 1D-ARC type (14 clusters) and ConceptARC concept (16). Mini-ARC is resampled
by task, so it is unclustered. 10,000 resamples, stratified by benchmark.

**Compute, errors and underuse:**
- The new search arms used 1,459 CPU-s (0.41 CPU-h), CPU only.
- No child errors and no kills.
- The matched search spent 95% to 100% of its per-task budget on ConceptARC and 1D-ARC, and 72% to 87% on Mini-ARC,
  where it found fits early. Leave-one-out folds cost 0.46 CPU-s in all.

## Results, pooled over the three benchmarks (REAL)

- **Precision** is correct / answered.
- **Accuracy** is correct / all outputs.
- **pass@2** includes the copy fallback.

| arm | answered | correct | wrong | coverage [95% CI] | precision [95% CI] | accuracy | pass@2 [95% CI] |
|---|---|---|---|---|---|---|---|
| O+ v2 (frozen) | 382 | 358 | 24 | 0.307 [0.187, 0.427] | 0.937 [0.862, 0.979] | 0.288 | 0.299 [0.178, 0.423] |
| H-CAST, rule B3 (frozen) | 82 | 71 | 11 | 0.066 [0.021, 0.125] | 0.866 [0.812, 0.941] | 0.057 | 0.069 [0.030, 0.122] |
| O, cast_v1 (frozen) | 116 | 97 | 19 | 0.093 [0.040, 0.160] | 0.836 [0.761, 0.909] | 0.078 | 0.090 [0.044, 0.149] |
| FIT_ONLY (no leave-one-out) | 134 | 102 | 32 | 0.108 [0.049, 0.180] | 0.761 [0.667, 0.841] | 0.082 | 0.094 [0.046, 0.155] |
| B1 (top-2 leave-one-out) | 115 | 96 | 19 | 0.092 [0.040, 0.158] | 0.835 [0.748, 0.921] | 0.077 | 0.089 [0.044, 0.147] |
| B2 (genuine top-1 leave-one-out) | 92 | 78 | 14 | 0.074 [0.026, 0.135] | 0.848 [0.778, 0.930] | 0.063 | 0.075 [0.033, 0.129] |
| MATCHED_SEARCH (blind L0, matched CPU) | 18 | 18 | 0 | 0.014 [0.007, 0.023] | 1.000 | 0.014 | 0.027 [0.016, 0.038] |
| MATCHED_SEARCH_LOO | 18 | 18 | 0 | 0.014 | 1.000 | 0.014 | 0.027 |
| COPY | 0 | | | | | 0 | 0.012 [0.004, 0.022] |

**By benchmark**, REAL arm: precision with coverage in brackets.

| arm | ConceptARC | Mini-ARC | 1D-ARC |
|---|---|---|---|
| FIT_ONLY | 0.673 (0.115) | 1.000 (0.087) | 0.788 (0.107) |
| B3 | 0.933 (0.031) | 1.000 (0.060) | 0.828 (0.094) |
| B2 | 0.900 (0.042) | 1.000 (0.074) | 0.803 (0.099) |
| MATCHED_SEARCH | 1.000 (0.013) | 1.000 (0.074) | 1.000 (0.002) |

**SHUFFLED** (another task's demonstrations): precision falls to 0.000 to 0.026 for every arm.
- Answers fall by about half only for B3 (82 to 39).
- They fall by a quarter to a third for B2 (92 to 68) and for blind search (18 to 12).
- FIT_ONLY still answers 126 times, and is right once.

## The primary contrast (pre-declared; Amendment 1)

**precision(B3) − precision(FIT_ONLY), REAL, pooled: +0.105 [+0.029, +0.234], one-sided p = 0.0017.
Decision: B3_POLICY_RAISES_PRECISION.**

This measures the whole selective B3 policy: module choice, genuine top-1 leave-one-out, agreement among fitting
programs, fold agreement and restart stability.

B3 never switched modules: all 82 of its answers came from the fit-only candidate's own module. So the same-module
diagnostic S12 equals the primary, and it is Holm-significant (+0.105, Holm p = 0.034).

## Leave-one-out on its own: wording not allowed

**The gate (Amendments 1 and 2) is FALSE.**
- B2, genuine top-1 leave-one-out without B3's other checks, points the same way:
  - S11 (B2 against FIT_ONLY): +0.087 [+0.006, +0.217];
  - S13 (B2 against FIT_ONLY, module held fixed): +0.087 [+0.006, +0.218].
- Neither is Holm-significant (both Holm p = 0.176).
- Grid identity held everywhere: 0 mismatches for B2 and for B3 on all three benchmarks.

So no causal claim is made about leave-one-out alone. The gain belongs to the B3 policy as a whole.

## Secondary contrasts (Holm over 13; REAL; pooled unless a benchmark is named)

| id | contrast | point [95% CI] | Holm p |
|---|---|---|---|
| S1 | precision: B1 − FIT_ONLY | +0.074 [0.010, 0.184] | 0.074 |
| S2 | precision: B3 − FIT_ONLY, ConceptARC | +0.261 [0.039, 0.455] | 0.176 |
| S3 | precision: B3 − FIT_ONLY, Mini-ARC | 0 (both 1.000) | 1.0 |
| S4 | precision: B3 − FIT_ONLY, 1D-ARC | +0.040 [0.000, 0.103] | 0.183 |
| S5 | coverage: B3 − FIT_ONLY | **−0.042 [−0.073, −0.015]** | **0.003** |
| S6 | precision: MATCHED_SEARCH_LOO − MATCHED_SEARCH | 0 | 1.0 |
| S7 | accuracy: FIT_ONLY − MATCHED_SEARCH (paired) | **+0.068 [0.022, 0.125]** | **0.003** |
| S8 | precision: B3 − MATCHED_SEARCH_LOO | −0.134 [−0.188, −0.059] | 0.176 |
| S9 | accuracy: O+ v2 − MATCHED_SEARCH (paired) | **+0.273 [0.152, 0.397]** | **0.003** |
| S10 | accuracy: H-CAST − MATCHED_SEARCH (paired) | +0.043 [0.006, 0.093] | 0.090 |
| S11 | precision: B2 − FIT_ONLY | +0.087 [0.006, 0.217] | 0.176 |
| S12 | precision: B3 − FIT_ONLY, same module | **+0.105 [0.029, 0.234]** | **0.034** |
| S13 | precision: B2 − FIT_ONLY, same module | +0.087 [0.006, 0.218] | 0.176 |

**Paired changes against the frozen entries** (pooled accuracy; pass@2 is almost identical):

| change | against O+ v2 | against H-CAST |
|---|---|---|
| FIT_ONLY | −0.206 [−0.333, −0.087] | +0.025 [+0.009, +0.045] |
| B2 | −0.225 | +0.006 [+0.001, +0.012] |
| MATCHED_SEARCH | −0.273 [−0.397, −0.152] | −0.043 [−0.093, −0.006] |

## Reading

**B3 trades coverage for precision.**
- Against accepting every fitting program, B3 removes 21 of the 32 wrong answers, and gives up 31 right ones.
- Its precision rises by 0.105, and its coverage falls significantly (S5).
- That matters in entry H, where a wrong CORA answer would displace C4's second attempt.
- On a plain two-attempt score, fit-only acceptance would solve slightly more (+0.025).

**CAST's search and modules do real work.**
- At the same per-task CPU, blind enumeration in CAST's own grammar answered 18 outputs, all trivially easy and all
  right.
- CAST's construction and pruned search reached 102 correct answers (S7). O+ v2, with R29, reached 358 (S9).
- On blind search, leave-one-out adds nothing (S6), because blind search answers only tasks that any check passes.

**Clustering widens the coverage intervals,** because success depends on the task type: O+ v2's 1D-ARC coverage
interval is [0.27, 0.73] clustered, against [0.46, 0.54] by Wilson. The precision intervals stay high.

**Context only, not an arm.** In the ConceptARC paper, the first-place ARC-Kaggle program averaged 0.5125 on the same
480 test inputs, with three guesses each (Moskvichev, Odouard and Mitchell 2023, Table 1). Our best on ConceptARC is
O+ v2's pass@2 of 0.117.

## Limits

- **The matched search** is blind enumeration in CAST's own grammar. It is not an external DSL solver, so "beats blind
  search" is relative to that comparator only.
- **Mini-ARC** intervals are unclustered.
- **Answers** are non-copy answers, as in U2.
- **Scope:** CORA components only; C4 and H's complete entry were not run. Most of O+ v2's lead comes from R29, which
  came from the independent lane.
- **What U2b does not show:** learned transfer, universal reasoning, or anything about the hidden ARC-AGI-2 test.

## Claim for the paper

> On three public ARC-style benchmarks unused in development, we added the controls our first universality test
> lacked, and reported uncertainty clustered by task type and concept. CORA's selective acceptance policy in the
> submitted neural entry (B3) raised precision over simply accepting the top program that fits every demonstration,
> by 0.105 (95% CI 0.029 to 0.234). It did so by abstaining more: coverage fell from 10.8% to 6.6%. Genuine top-1
> leave-one-out alone pointed the same way (+0.087) but was not significant after correction for multiple tests, so
> we do not attribute the gain to leave-one-out by itself. At the same CPU per task, blind enumeration in CAST's own
> grammar solved only 1.4% of outputs, against 8.2% for CAST's construction and pruned search and 28.8% for the
> CORA-only entry. CORA's search, more than its verification, is what solves problems here; its verification makes
> the answers it gives more trustworthy.

## Erratum (2 Nov, from the independent review, coordination outbox 0230)

**What is corrected:**
- The phrase "at the same CPU per task", in the Reading and in the Claim for the paper;
- secondary contrast S9.

They place O+ v2's 28.8% (358 correct answers) in a compute-matched comparison it was not part of.

**The budgets:**
- The blind search was matched to the CPU that the H-CAST component (`cast_selective_v2` at 15/30 s) actually used on
  each task.
- O+ v2 ran CAST v1 at 45 CPU-s (90 s wall), then R29 at 12 CPU-s (24 s wall).

**The correct statement:** under the H-CAST component's measured CPU budget, blind enumeration in CAST's own grammar
solved 1.4% of outputs, and CAST's construction and pruned search (FIT_ONLY) solved 8.2%. The O+ v2 entry, which also
runs R29 under a larger budget, solved 28.8%. That figure is descriptive, not compute-matched, and S9 is a descriptive
contrast for the same reason.

**What the rates measure:** each is correct answers on non-copy outputs divided by all outputs. None is a two-attempt
score.

The text above is left as reviewed; this section takes precedence where they differ.
