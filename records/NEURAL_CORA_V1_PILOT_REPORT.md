# Neural-CORA v1 pilot report: a learned Qwen-feature guide for CORA's executable search (20 October 2026)

**Decision: G1 (LEARNING GO) = NO-GO.**

Classification: `LEARNED_OVER_PLAIN_SEARCH_ONLY`, under the protocol frozen at commit 081c1d3 before any training
(`records/NEURAL_CORA_V1_PILOT_PROTOCOL.md`).
- **What learned:** the trained guide changes CORA's search. It beats plain simplest-first search, an untrained guide
  and a shuffled-label guide by large margins.
- **What did not hold:**
  - It does **not** beat the strong symbolic control C+H.
  - It does **not** beat the same heads trained on 103 hand-crafted features (L1h). L1h is **significantly better**.
- **Conclusion:** there is no Qwen-specific benefit and no advantage over strong symbolic search. The tested version is
  closed. Nothing was tuned after the answers were read.

**Sources:**
- evaluation: `outputs/neural_cora_v1/evaluator/pilot_v1_eval.json` (sha256 `6cb9f097…`);
- task-level table: `task_level.jsonl` (`f6574d28…`);
- rows: `rows/eval_heldout.jsonl` (`944ec3b2…`) and `rows/eval_iid.jsonl` (`45b845b9…`).

## 1. What ran

**The single CORA-owned algorithm:**
- typed language `ncv1-g0`;
- the native interpreter;
- the best-first enumerator;
- the fixed two-attempt rule.

The guide only orders the search. It never emits a grid or sees an answer.

**Timeline (UTC):**

| stage | when |
|---|---|
| prep | 22:24 → 23:08 on 19 Oct (freeze, generate, audit, targets, features) |
| training | 23:08:43 |
| arm runs | 23:09:25 → 01:07 on 20 Oct, 2 workers at nice 10 |
| evaluation | 01:07 |

The total wall time was 2 h 43 min, inside the 6 h cap.

**Compute:**
- Qwen3-4B features: 1,276 s on GPU 0 (0.30 s per task), peak 7.51 GB.
- Head training: 14 s (L1), 8 s (L1h), 12 s (L0s).
- Typed search: about 0.6 ms of CPU per candidate.
- The context arm C0 overran its declared 5 s CPU budget. Its mean was 15.5 s per held-out task, because native checks
  deadlines between phases. It is context only.

**Isolation:**
- The evaluation files given to the solver hold demonstrations and test inputs only.
- `evaluate.py` alone read the answers.
- The rows are complete: 420 and 220 tasks, with no duplicates.

## 2. Training happened (real gradient updates)

| guide | features | trainable parameters | optimizer steps | best validation loss (epoch) | weights moved (L2) | initial → final weight sha256 | checkpoint |
|---|---|---|---|---|---|---|---|
| L1 | frozen Qwen3-4B (12,800) | 13,701,766 | 1,560 | 0.540 (6) | 31.0 | `974dc51c…` → `2aa5af84…` | `248d704d…` |
| L1h | 103 hand features | 700,038 | 1,560 | **0.461** (28) | 33.8 | `deffbf52…` → `b12f8c1c…` | `c713ef7a…` |
| L0s | Qwen, shuffled targets | 13,701,766 | 1,560 | 2.233 (2) | 20.5 | `974dc51c…` → `051b4140…` | `4df864a4…` |
| L0 | none (untrained) | 13,701,766 | 0 | — | — | `974dc51c…` | `c969b5ce…` |

**Total:** 4,680 real optimizer steps. Log: `models/training_log.json` (`b5fbb26d…`).

## 3. The primary result: held-out compositions, the primary set (n = 395)

Exact pass@2, with Wilson 95% intervals:

| arm | budget | pass@2 | rate [95% CI] | candidate coverage | wrong 1st attempt | abstained |
|---|---|---|---|---|---|---|
| C0 (native inducer) | 5 s CPU (overran) | 65 | 0.165 [0.131, 0.204] | 65 | 5 | 325 |
| C+ (simplest-first) | 1000 | 104 | 0.263 [0.222, 0.309] | 104 | 0 | 291 |
| **C+H** (strong symbolic) | 1000 | **358** | **0.906 [0.874, 0.931]** | 358 | 3 | 36 |
| L0 (untrained) | 500 | 30 | 0.076 [0.054, 0.106] | 30 | 0 | 365 |
| L0s (shuffled labels) | 500 | 51 | 0.129 [0.100, 0.166] | 51 | 0 | 344 |
| **L1h** (hand features) | 500 | **235** | **0.595 [0.546, 0.642]** | 235 | 1 | 159 |
| **L1** (Qwen features) | 500 | **198** | **0.501 [0.452, 0.550]** | 198 | 4 | 193 |

**The preregistered tests** (exact McNemar, two-sided; "a only / b only"):

| comparison | a only | b only | net | p | holds? |
|---|---|---|---|---|---|
| L1@500 vs C+@1000 | 100 | 6 | +94 | < 1e-6 | yes |
| L1@500 vs **C+H@1000** | 23 | 183 | **−160** | < 1e-6 | **no** |
| L1@500 vs **L1h@500** | 41 | 78 | **−37** | 0.00089 | **no** |
| L1@500 vs L0@500 | 170 | 2 | +168 | < 1e-6 | yes |
| L1@500 vs L0s@500 | 150 | 3 | +147 | < 1e-6 | yes |

**The other two conditions:**
- Harm: holds. L1's wrong first attempts were 4, against C+H's 3 + 5% of 395.
- Breadth: **fails**. L1's net gain over C+H@1000 is positive in only 1 of 7 families.

## 4. By family (primary set, pass@2)

| family | n | C0 | C+@1000 | C+H@1000 | C+H@3000 | L0@500 | L0s@500 | L1h@500 | L1@500 | L1@3000 |
|---|---|---|---|---|---|---|---|---|---|---|
| delete the largest | 44 | 17 | 44 | 44 | 44 | 21 | 44 | 43 | 42 | 43 |
| delete-then-translate | 60 | 0 | 0 | 60 | 60 | 0 | 0 | 57 | 26 | 40 |
| line by size | 51 | 0 | 0 | 51 | 51 | 4 | 2 | 11 | **31** | 51 |
| line, default delete | 60 | 0 | 0 | 43 | 60 | 4 | 0 | 40 | 33 | 47 |
| recolour-then-line | 60 | 0 | 0 | 60 | 60 | 0 | 0 | 3 | **1** | 25 |
| slide by colour | 60 | 40 | 60 | 53 | 59 | 1 | 5 | 54 | **56** | 60 |
| slide-then-recolour | 60 | 8 | 0 | 47 | 59 | 0 | 0 | 27 | **9** | 26 |

L1 beats C+H only on slide-by-colour (+3), and beats L1h only on line-by-size (+20). It fails most on the **new
two-rule compositions**: recolour-then-line 1/60, slide-then-recolour 9/60, delete-then-translate 26/60.

## 5. Budget curves (primary set, pass@2)

| arm | @100 | @300 | @500 | @1000 | @3000 |
|---|---|---|---|---|---|
| C+ | 0 | 104 | 104 | 104 | — |
| C+H | 152 | 265 | 306 | 358 | 393 |
| L1h | 155 | 207 | 235 | 261 | — |
| L1 | 124 | 174 | 198 | 236 | 292 |

**Equal-candidate comparisons:**
- L1@500 vs C+H@500: 40 vs 148.
- L1@3000 vs C+H@3000: 1 vs 102.

The gap does not close with more budget. At 3000 candidates, C+H covers **394 of 395** held-out tasks. So the language
*can* express almost every held-out task, and the binding constraint is the **order**, not expressivity.

## 6. Secondary results

**In-distribution (eval_iid, n = 220, training families) shows the same pattern:**

| arm | pass@2 |
|---|---|
| L1@500 | 183 |
| L1h@500 | 211 |
| C+H@1000 | 212 |
| C+@1000 | 160 |
| L0@500 | 21 |
| L0s@500 | 79 |

- L1 vs L1h: 3 vs 31, p = 1e-6.
- L1 is weak even on in-distribution two-rule families: line-then-recolour 9/20, translate-then-delete 5/20,
  recolour-then-delete 11/20. L1h scores 18, 16 and 17.

**Template-aliased held-out tasks (n = 25, excluded from the primary set):** C+H 25, L1 21, L1h 20, C+@1000 19.

**Harms relative to C+H@1000:** L1@500 lost 183 tasks C+H solves and gained 23. Wrong first attempts stay rare in every
arm (≤ 5 of 395). The arms mostly abstain rather than err.

**Observable diagnoses at each arm's full budget** (primary set):

| arm | UNVERIFIED_QUERY | AMBIGUOUS_PREDICTIONS | NO_FIT_OBSERVED |
|---|---|---|---|
| C+H@3000 | 367 | 27 | 1 |
| L1@3000 | 260 | 33 | 102 |
| L1h@1000 | 245 | 18 | 132 |

## 7. Why G1 failed (the protocol's section 7 analysis)

**(a) The Qwen features are less informative than hand features for this decision. This is the main cause.**
- L1h beats L1 on both held-out and in-distribution tasks, and reaches a lower validation loss (0.461 vs 0.540).
- The frozen NVARC checkpoint was trained to *emit grids*. Mean-pooled hidden states over about 795 tokens compress
  the demonstrations' change structure less usefully than explicit delta features.

**(b) Training power.** The 13.7 M-parameter L1 head reached its best validation loss at epoch 6 and then overfit.
3,300 training tasks are few for 12,800-dimensional inputs. This contributes to the result but does not explain it:
L1h, on the same data, does better.

**(c) Label aliasing is not the cause.** There are 1.50 valid selectors and 1.68 valid actions per task, and the
primary metric is exact output correctness, which no alias can game.

**(d) The prior's factorization is a structural cause.**
- The heads predict independent bags of selectors and actions. They cannot express *which selector pairs with which
  action*.
- The held-out families are exactly new pairings. C+H's delta analysis sees several kinds of change and puts two-rule
  programs first, which is the compositional step the learned priors did not generalize.

**(e) The language has the solutions.** C+H@3000 covers 394/395. Expressivity is **not** the bottleneck on this
synthetic data. The dev60 atlas shows it is on real ARC.

**C+H also has a home advantage.**
- It was designed by the same researcher as the generator.
- It was refined after one held-out-family smoke test (seeds 5000–5002, logged in the protocol).

It is a deliberately strong control. Beating it was the bar for a Qwen-specific claim.

## 8. What this does and does not show

**It shows:**
- **Real learning inside CORA's executable search.** Trained heads changed the program order enough to solve 168 more
  held-out tasks than the same heads untrained, and 147 more than when trained on shuffled labels. This was with
  CORA's interpreter and checker deciding every answer.

**It does not show:**
- any Qwen-specific contribution;
- any advantage over strong symbolic search;
- diagnosis, revision, learning from failure, or semantic invention (none was tested);
- anything about real ARC.

**Per the protocol, this tested version is closed.**
- No retuning on these evaluation tasks.
- No larger model or budget to manufacture a positive result.
