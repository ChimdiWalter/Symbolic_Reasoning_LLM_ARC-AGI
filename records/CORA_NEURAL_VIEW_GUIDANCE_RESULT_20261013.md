# CORA-NVG result: failure-conditioned neural view guidance (2026-10-13)

**Verdict: H1 REJECTED. The route is closed (NEURAL_GUIDANCE_ROUTE_REJECTED for
CORA-NVG).**

- With the frozen Qwen2.5-1.5B guide, the authentic failure trace made view
  choice worse than demonstrations alone. A shuffled trace had exactly the
  same effect.
- No neural guide beat the fixed-order failure fallback.
- The frozen I-JEPA guide fell below random on the final split, and trace
  conditioning changed none of its choices.
- No arm except random produced a false acceptance.

Protocol: `records/CORA_NEURAL_VIEW_GUIDANCE_PLAN_20261012.md` (plan v0 and
amendments 1-3). Freeze `outputs/neural_view_v0/freeze_v1.json` was
committed at 7f0b17e before the single final run. The run started
2026-10-13T15:13:25Z and ended at 15:24:21Z (GPU 0 on Athe). The rows are
`outputs/neural_view_v0/guide_rows_final.jsonl` and the evaluation
`outputs/neural_view_v0/stageA_final.json`.

**Tier:** synthetic, a private generator. This is not real ARC, not a
Kaggle result and not capability invention.

## 1. Final split

- **Tasks.** 210 tasks from 5 held-out families (f_layer_frame,
  f_layer_corner, f_diag_mirror, f_noise_shift, f_colour_cycle).
  f_cluster_frame yielded no decision, because the proximity view was never
  cut.
- **Native runs.** BASE and BASE_REPEAT agree on all 210.
- **Decisions.** 165 (both native runs REJECT, at least one cut view):
  **35 warranted, 0 misleading, 130 no help.** The power rule (at least 30
  warranted) is met.

## 2. Results (Stage A: the guide's chosen view scored by the engine's own promoted-view run)

| arm | information | gains of 35 warranted | harms (new false acceptances) | abstentions of 165 | top-1 useful (warranted) |
|---|---|---|---|---|---|
| B1 fixed-order failure fallback (KAAR/GPAR/ARGA-style) | cut list | **35** | 0 | 0 | 1.000 |
| B3 ARGA-style tabu, coverage x coherence | cut list plus statistics | **35** | 0 | 0 | 1.000 |
| B2 coarsest first | demonstrations | 10 | 0 | 0 | 0.286 |
| R random (mean of 5 seeds) | none | 12.6 | 0.8 | 0 | 0.360 |
| C Qwen, demonstrations | demonstrations | 19 | 0 | 0 | 0.543 |
| F Qwen, failure type only | plus type | 19 (choices identical to C) | 0 | 0 | 0.543 |
| **D Qwen, authentic trace** | plus trace | **1** | 0 | 69 | 0.543 |
| E Qwen, shuffled trace | plus another task's trace | 1 | 0 | 69 | 0.543 |
| C-CF counterfactual, demonstrations | demonstrations | 5 | 0 | 145 | 0.657 |
| D-CF counterfactual, authentic trace | plus trace | 0 | 0 | 163 | 0.657 |
| E-CF counterfactual, shuffled trace | plus another trace | 0 | 0 | 163 | 0.629 |
| J-C I-JEPA, demonstrations | demonstrations | 3 | 0 | 0 | 0.086 |
| J-D I-JEPA, failure pairs | plus trace | 3 (identical) | 0 | 0 | 0.086 |
| J-E I-JEPA, shuffled pairs | plus another trace | 3 (identical) | 0 | 0 | 0.086 |

**Paired exact McNemar tests on gains.**

| comparison | discordant decisions | p |
|---|---|---|
| D vs C | 0 vs 18 | < 0.0001 |
| D vs E | 1 vs 1 | 1.0 |
| D vs F | 0 vs 18 | < 0.0001 |
| D vs B1 | 0 vs 34 | < 0.0001 |
| D vs B2 | 0 vs 9 | 0.004 |
| D-CF vs C-CF | 0 vs 5 | 0.06 |
| J-C vs B1 | 0 vs 32 | < 0.0001 |
| J-C vs R0 | 1 vs 9 | 0.02 |
| B1 vs R0 | 24 vs 0 | < 0.0001 |
| J-D vs J-C | 0 vs 0 | |

**Label-permutation agreement.** D 0.861, C 0.588.

**Cost (165 decisions).**
- C: 38 s, 224K tokens.
- D: 40 s, 238K tokens.
- D-CF: 109 s, 626K tokens.
- J-C: 23 s.
- B1: none.

## 3. Pre-registered conclusions

1. **H1 (D beats C and E): rejected.** D is significantly worse than C and
   indistinguishable from E.
   - The trace's *presence* moved the model to abstain (69 of 165). Its
     *content* did not matter: E equals D.
   - The type-only line (F) changed nothing relative to C.
2. **No neural arm beats B1 or B3.** Every comparison against B1 favours B1.
3. **Counterfactual-transition prediction (section 13 of the addendum)
   shows no advantage.** It abstains almost always, and the authentic trace
   makes it abstain more.
4. **The JEPA gate passed on development data but did not replicate.**
   - On the final split, J-C is below random.
   - J-D equals J-C equals J-E. By amendment 2's interpretation rule, any
     JEPA signal was demonstrations-only, and here there was none.
5. **Safety.** No guide arm caused a false acceptance. Random did, 0.8 on
   average. The only FALSE_ACCEPT views were S7 in two diagonal tasks, and
   no guide chose them.

## 4. What the result does and does not show (limitations)

**The warranted evidence comes from one family.**
- All 35 warranted decisions are `f_diag_mirror`. There the useful view
  (S4, multicolour 8-connected) is the first coherent view the cap cuts, so
  the fixed-order fallback is optimal by construction.
- The colour-layer families (frame, corner) were no-help: promoting S6 does
  not make them expressible.
- The proximity family gave no decisions.
- So the final split tests view admission in essentially one representation
  regime. On development data, B1 lost to I-JEPA in a colour-layer family
  (S6 second in the cut order). That case did not recur in the final
  families.

**The negative direction for the language-model guide is robust within
this design.** The trace degraded choices, and the shuffled-trace control
reproduces the degradation exactly. The 1.5B model is small. A larger model
was explicitly not to be tried to rescue a failed hypothesis (stopping
rules, plan section 11).

**This agrees with the project's earlier findings.** Failure features never
beat demonstration-only controls (the failure-graph scorer of 2026-09-24,
the TTI shuffled study). Search reordering by a learned guide lost tasks
(GuideNet). KAAR reported LLM abstraction choice from raw grids as
unsatisfactory.

**Stage B (fold-local shadow end-to-end) was not run.** Stage A did not
support H1, as plan section 9 requires before Stage B.

## 5. Decision

- **The failure-conditioned neural view-guidance route is closed for
  CORA.** No JEPA or LLM view guide goes into any Kaggle package.
- **The fixed native trial order plus failure fallback (B1) remains the
  best tested admission rule on this corpus.** It is not deployed either:
  admission changes stay governed by the P3 and PROMOTE evidence on false
  acceptances.
- **Claim ceiling.** On a private synthetic corpus, a frozen 1.5B LLM and a
  frozen I-JEPA encoder did not improve representation admission over a
  fixed-order fallback. Authentic failure traces reduced LLM guidance
  quality, exactly as much as shuffled traces did.
- **What this leaves open.** Whether neural candidates, rather than neural
  rankings of CORA's views, can expose missing capabilities: directive
  section 12, a separate experiment.
