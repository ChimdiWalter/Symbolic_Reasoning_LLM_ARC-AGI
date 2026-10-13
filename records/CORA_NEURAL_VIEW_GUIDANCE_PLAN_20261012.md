# CORA-NVG: failure-conditioned neural view guidance, plan v0 (2026-10-12)

**Status: PLAN, draft v0.** Not frozen; no guide has been run.

This is an independent parallel trial under the user's CORA-NVG addendum of
2026-10-12. It touches nothing of:
- the Kaggle native_v1 package;
- the frozen engine trees;
- the frozen 120-task pilot, ARC-1000 or protected evaluation data;
- Step B or VDCG.

All code lives in `cora_neural_view/` and all outputs in
`outputs/neural_view_v0/`.

## 1. Question

**When it applies.** The frozen native reasoner fails a task, and at least
one coherent representation (segmentation view) was cut by the fixed
four-view cap.

**H1.** A frozen pretrained neural model shown the reasoner's authentic
failure trace chooses which representation to test better than the same
model:
- with demonstrations only;
- with a shuffled trace;
- with the failure type only.

It must also beat simple symbolic choices, and do so without new false
acceptances.

**H0.** The trace adds nothing. Any advantage comes from:
- extra tokens or compute;
- familiarity with view descriptions;
- memorization;
- a changed candidate population;
- leakage.

**Roles.**
- **The model is an advisor.** It only decides which counterfactual view
  the unchanged engine tests first.
- **The engine executes.** Its coherence test, cap, ranking, program search
  and leave-one-out are untouched.
- **The evaluator is independent.** It alone holds the hidden outputs.

## 2. What the project has already tried (history audit, 2026-10-12)

Sources: `../Reasoning_Project/RUN_HISTORY.md` (RH) and this repository.

| # | attempt (date) | what it did | result | lesson |
|---|---|---|---|---|
| 1 | prototype (Dec 2025) | language-model hints, learned ranking policy, ViT | prototype only, no numbers | n/a |
| 2 | neural-guided upgrade (Apr 2026) | Grid-JEPA plus a neural ranker over DSL candidates, using execution fit on training pairs | synthetic top-1 0.833; ARC 0/6 | DSL coverage was the bottleneck (RH:43-142) |
| 3 | world model (May) | slot attention plus GNN, as solver and as reranker | 0/104 exact; reranker 61 to 47 (overrode correct answers) | (RH:1684-1773) |
| 4 | neural perception bridge (May 13) | JEPA heads reorder solvers; `suggest_views` proposes view orders | no isolated result; 0/4 promotions used neural routing | (RH:2120-2177, 2565) |
| 5 | DINOv2 probe (May 28) | ViT features for change, operator and selector | at chance (50%, 64.7%, 50%); 0/299 promoted | (RH:2577-2701) |
| 6 | neural advisory and FailureEncoder (Jun) | failure-state summary plus JEPA embedding predict the missing concept | 0/50 candidates; removing it kept all 40 solves | dormant (RH:3122-3203) |
| 7 | ranker retrain (Jul 9) | MLP vs Bayesian-linear for LOO survival | AUC 0.902 vs 0.907 | neural "earns NO wiring" (RH:4588) |
| 8 | TRM and DRM (Jul) | recursive nets as second-attempt solver | about 1/50; 0/120 passed the gate | memorized (RH:6259-6599) |
| 9 | GuideNet (Jul 25-27) | DreamCoder-style recognition model reorders the inducer's search | 0 gains, 3 losses at 1,000 tasks | "search not order-bound"; pushed winners down on budget-limited tasks (RH:6460-6602) |
| 10 | per-task MDL solver (Jul-Aug) | CompressARC-style | 3/40; gate exact but too few | (RH:6658-6837) |
| 11 | CORA-TTI GPN-v1 (Aug-Sep) | typed failure graph to production and type | reconstructs known operators only; real vs shuffled traces 8 vs 6 of 24 | "GPN training not justified" |
| 12 | failure-graph scorer (Sep 24) | log-linear and 1-hidden-layer | beat shuffled by 0.197 nats per token but lost to demonstration statistics; failure features hurt | `records/SCORER_DIAGNOSIS_20260924.md` |

Non-neural work on the v23 views S1-S7:
- **A fixed corpus-prior order.** Per-task ordering was rejected for fold
  invariance (RH:5351-5359). The inducer's ROUND-4 note also says
  data-dependent ordering flips between folds and the winner diverges.
- **The sealed cheap-first probe (R21, `ARC_VARIANT_BUDGET=1`).** It
  promotes views only inside the kept four, after the cap.
- **PROMOTE (eligible views first).** 0 gains on 24 synthetic tasks, 2
  regressions, 1 false acceptance
  (`records/LOO_V1_DIAGNOSIS_ADDENDUM_20261012.md`). The same addendum found
  ranking is not the blocker on the real task (H_rank FALSE).
- **P3 (deduplication before the cap).** Rejected: 1 gain, 2 losses, 2 false
  acceptances.

**What NVG adds, the only reasons it is not a rerun:**
1. **It acts only on failures.** It is never consulted when the native
   search succeeds on a subset. GuideNet and P3 acted everywhere.
2. **It acts at admission, choosing which coherent view enters the capped
   search.** It does not reorder actions, programs or the kept four.
3. **It uses frozen pretrained open weights.** Nothing is trained on
   generated tasks (items 2-12 were trained).
4. **The decisive test is the ablation on one model:** authentic trace vs
   demonstrations only vs shuffled trace vs failure type only.
5. **The guide only allocates a fixed budget of counterfactual tests.** The
   engine's own acceptance decides.
6. **Guidance is computed per training subset from that subset alone,**
   covered by a mutation test. This addresses the fold-invariance objection
   directly and measures it.

**Prior expectation, stated before any result.** H0 is likely. Three
earlier uses of failure evidence never beat demonstration-only controls, and
both search reordering and view promotion caused harm. A negative result is
informative and will be reported as such.

## 3. Literature and novelty (full review: `records/CORA_NVG_LITERATURE_20261012.md`)

**Closest prior work.**
- **KAAR** (Lei et al., arXiv 2505.17482) tried abstractions in a fixed
  order and moved to the next one after a failure. Asking LLMs to choose
  abstractions from the raw grids was "unsatisfactory" (verified in the full
  text). **Arm C therefore repeats a published negative result.**
- **GPAR and ARGA** (AAAI 2024 and 2023): fixed simple-to-complex
  abstraction order; ARGA's Tabu list suspends failing abstractions.
- **ABPR** (2026): structured derivation traces beat plain execution
  feedback for frontier LLMs revising ARC-AGI-2 programs, with no shuffled
  control.
- **RLEF** (ICML 2025): mismatched feedback impairs repair, the template
  for arm E.
- **AlphaGeometry**: a proposer is called when deduction stalls.
- **CEGAR**: failure-driven abstraction refinement.

**Not novel:**
- a neural model guiding a symbolic synthesizer;
- a proposer whose output a verifier certifies;
- repair from execution feedback;
- traces beating plain feedback on ARC;
- multiple ARC views, or the view mattering;
- fixed-order or failure-triggered abstraction fallback;
- an LLM choosing abstractions from the task alone;
- shuffled-feedback controls;
- failure-driven abstraction refinement;
- predicting solver failure from traces;
- vision or JEPA priors for ARC (an ARC-JEPA v1 GitHub pre-release exists:
  1/172).

**What might be new (cautious).** An empirical test of whether the content
of an authentic, typed failure trace improves a frozen model's choice of
segmentation view for an unchanged symbolic engine. It must beat:
- demonstrations only (C, the KAAR negative);
- the failure type only (F);
- a shuffled trace (E);
- the fixed-order fallback (B1, the KAAR/GPAR/ARGA rule) and the
  training-statistic heuristics (B2, B3).

It must do so at matched compute, counting the advisor's cost. The
leave-one-out verifier stays unchanged, and losses and false acceptances
are reported. The second open element is counterfactual
failure-transition prediction gated by the engine's own test: no exact
precedent was found. **This is a possible finding, not an architecture,**
and it vanishes if D matches F, E or B.

**Design changes adopted from the review:**
1. B1 is named as the prior-art fixed-order failure fallback.
2. B3 is added: among views not yet searched (the searched views are
   treated as tabu, as in ARGA), rank by training-only coverage times
   consistency.
3. **JEPA gate (development split only).** Frozen embeddings must pick the
   reference-useful view better than chance and better than a component-
   count descriptor, or the J arms are dropped before the final run.
4. **Minimum power.** At least 30 warranted decisions in the final split.
   Otherwise the result is labelled UNDERPOWERED, and only counts are
   reported.

## 4. Athe resources (measured 2026-10-12/13)

| resource | measured | budget for NVG |
|---|---|---|
| CPU | 24 threads (i9-9920X, 12 cores); load 58-64, oversubscribed by Step B and other jobs | engine runs `nice 19`, at most 6 workers |
| RAM | 125 GiB, 96 GiB available | at most 16 GiB |
| GPU | 2x RTX 2080 Ti 11 GB. GPU 0 idle (55 MiB, 3%); GPU 1 in use by another process (2.9 GB) | GPU 0 only (`CUDA_VISIBLE_DEVICES=0`), at most 8 GB; GPU 1 never touched |
| disk | /home 275 GB free; /deltos 4.6 TB free (95% used); / 76 GB free | models at most 10 GB in `~/.cache/huggingface` (28 GB before) |
| software | `.venv_arc2026`: torch 2.11+cu128 (CUDA available), transformers 4.57, accelerate 1.13, timm 1.0.27; driver 580, CUDA 13.0 | fp16 (Turing has no bf16); nothing installed into another project's environment |

## 5. Models (frozen; no fine-tuning; no remote inference)

| model | role | revision | licence | size | status |
|---|---|---|---|---|---|
| Qwen/Qwen2.5-1.5B-Instruct | text guide (C-F) | 989aa7980e4c... | Apache-2.0 | 3.09 GB | downloading; hashes go to `outputs/neural_view_v0/models.json` |
| facebook/ijepa_vith14_1k | JEPA perceptual guide (J) | f157467ea509... | CC-BY-NC-4.0, research only | 2.52 GB | downloading |
| Qwen/Qwen3-0.6B | declared fallback (only if 1.5B cannot run) | c1899de289a0... | Apache-2.0 | 1.50 GB | not downloaded |
| HuggingFaceTB/SmolVLM2-2.2B-Instruct | optional vision-language guide | 482adb537c02... | Apache-2.0 | 8.99 GB | not downloaded: no documented text-encoding limitation yet |
| facebook/vjepa2-vitl-fpc64-256 | video JEPA | b3c1679b7c34... | MIT | 6.43 GB | not used: grids are static images, so I-JEPA is the matching JEPA |

**Contamination.**
- Qwen2.5's pretraining corpus is undisclosed web-scale data. Public ARC
  JSON is plausibly in it, so no claim rests on public ARC tasks.
- I-JEPA was pretrained on ImageNet-1k.
- The corpus here is private, freshly generated synthetic data. Its results
  are kept separate from any public-ARC result.

**I-JEPA's licence is non-commercial.** It may not enter any Kaggle
package; none is planned.

**Inference.**
- No sampling. Decisions are made by log-likelihood scoring over a closed
  option set, so the output is always well-formed.
- fp16, context at most 4,096 tokens.
- Prompts are fixed before any final-split run, and their sha256 goes in
  the freeze.

## 6. Mechanism and interface

**Trigger, identical for every guided arm.** It is checked at an induction
call on a training subset T (the full training set or a leave-one-out
subset). It fires when:
- the native attempt on T yields no train-exact program; and
- at least one coherent view of T was cut by the cap.

Otherwise the call is NO_CHANGE: the native path, untouched.

**Guide input, fold-local: only T and the task's unlabelled test inputs.**
- T's demonstration grids (inputs and outputs) and the unlabelled test
  inputs. Never the demonstration removed from T, its output, or any
  full-data result.
- The eligible views under anonymous labels (view_A, ...), freshly permuted
  for each decision. Each is described only by its properties:
  connectivity, single or multicolour, background-adaptive, colour layer,
  proximity grouping.
- Per-view training-only statistics on T: coherence, pixel coverage,
  consistency, objects per demonstration.
- The failure evidence, by condition.

**Guide output.** NO_CHANGE, or a ranking of the eligible views, of which
TRY_VIEW takes the top one. A trusted adapter maps labels back. Anything
else becomes NO_CHANGE. Explanations are never used as evidence.

**Action.**
- The top-ranked view is placed first in the strict tier.
- The cap stays at 4. Coherence, the relaxed tier and acceptance are
  unchanged.
- The induction on T is re-run inside the same deadline, so no extra
  budget.

**Counterfactual form (section 13 of the addendum).** The model is asked,
per view, which observable transition searching it would cause:
- a program fitting all of T's demonstrations;
- no change;
- a program that fits T but not new inputs.

Views are ranked by the scored probability of the first option. The
engine's search of the chosen view is the symbolic probe that tests the
prediction. Only an accepted engine result counts.

**Probe budget k.** k = 1 is the primary test; k = 2 is secondary. A
probe-all arm, P (every cut view in native order), is the identical probe
mechanism without ranking.

## 7. Conditions

The same Qwen weights and prompt skeleton serve C, D, E and F.

| arm | ranking source | information |
|---|---|---|
| A | native order (no change) | nothing |
| R | seeded random order of eligible views | nothing |
| B1 | fixed-order failure fallback: the first coherent view cut by the cap, in native order (KAAR/GPAR/ARGA-style; the PROMOTE rule) | trace (cut list) |
| B3 | ARGA-style tabu: searched views excluded; the rest ranked by training-only coverage times consistency | trace (searched list) plus demonstration statistics |
| B2 | object-change homogeneity: the fraction of a view's objects wholly changed or wholly unchanged across T's demonstrations | demonstrations only |
| C | LLM | demonstrations plus view properties and statistics |
| D | LLM | C plus the authentic native failure trace on T |
| E | LLM | C plus the failure trace of another decision with the same number of eligible views, labels mapped by position |
| F | LLM | C plus the failure type and status only (cora_diag) |
| J-C | I-JEPA | demonstrations only: alignment of each view's objects with the embedding change between input and output |
| J-D | I-JEPA | J-C weighted to the failure region (cells the native near-solve gets wrong on T's demonstrations) |
| J-E | I-JEPA | J-C weighted to another decision's failure region |
| P | every cut view in native order | probe-all ceiling: not compute-matched, reported separately |

**The authentic trace (D).**
- native failure stage;
- best training fit;
- the near-solve's view, fit and residual size;
- leave-one-out folds that failed or diverged;
- deadline events;
- which eligible views were searched and which were cut;
- the engine's own probe events.

## 8. Fresh synthetic corpus

- New generator `cora_neural_view/corpus.py`, seeds 7000 and up. None of
  the eight negative-probe and P3 families is reused.
- Each task: 3 training demonstrations, 2 held-out demonstrations generated
  by the same rule, and 2 unlabelled test inputs (the held-out inputs).
- Families are designed for different target views (colour layer,
  diagonal multicolour, proximity) and include:
  - views whose promotion is wrong;
  - failures no view repairs;
  - native-solvable controls.

**Strata, assigned by the evaluator from the reference.** Assignment is
automatic and guide-independent:
- warranted: some view's promotion is CORRECT;
- misleading: none CORRECT, some FALSE_ACCEPT;
- no help: all REJECT;
- native accepted: never a decision point.

**Splits are by family, with whole families held out.**
- Development families: building and debugging only.
- A selection set: only for the pre-declared parse and sanity rule (if
  over 20% of C-F decisions fail to score, switch to the declared fallback
  model).
- Final families: never inspected individually before the single frozen
  run. Only their stratum counts are shown.

## 9. Reference and metrics

**Reference, evaluator only.** For every decision task and every eligible
view V, the native engine with V promoted (applied uniformly) is run with
the full adaptive leave-one-out, 20 s budget. Outcome: CORRECT,
FALSE_ACCEPT or REJECT. The native BASE run is repeated twice to measure
run-to-run noise under host load.

**Stage A: representation guidance, observation only.** Per decision and
arm:
- gain: the chosen view's reference is CORRECT;
- harm: FALSE_ACCEPT;
- neutral: REJECT or NO_CHANGE.

Reported:
- gains, harms and net gain (gains minus harms);
- precision; recall over warranted decisions;
- correct abstention on no-help and misleading decisions;
- whether the useful view is reachable in the top four;
- label-permutation stability (D under two permutations);
- tokens, GPU and CPU time.

**Stage B: shadow end-to-end, fold-local.** Only if Stage A supports H1.
- The engine runs with a per-call overlay: guidance for each subset is
  looked up by the subset's content hash.
- Outcome as above, plus native-correct tasks lost, accepted programs
  rejected, program identity and runtime.
- Native results are never replaced.

**Primary comparisons (final split, paired over decisions).**
- D vs C, D vs E and D vs B2 on net gain (exact McNemar, two-sided,
  alpha 0.05).
- The harm count of every arm.

## 10. Leakage safeguards

- Guide inputs are built by one function from T and the unlabelled inputs.
  It has no parameter for held-out outputs.
- **Mutation test:** changing the removed demonstration's output, or a
  held-out output, leaves every guide input byte-identical for that subset,
  and so its guidance.
- View labels are anonymized and re-permuted per decision, so the model
  cannot ask for a view by name. Task ids never enter a prompt.
- Shuffled traces come only from other decisions in the same split.

## 11. Safety and stopping rules (Stage B deployment criteria)

**Deployment criteria.** All of these are required:
- zero new false acceptances;
- zero loss of native-correct tasks;
- no leakage (mutation tests pass);
- no change to the frozen engine's outputs where the trigger does not fire
  (identity overlay byte-identical);
- no extra symbolic budget (same deadline).

**Any failure rejects the mechanism for deployment.** The negative result
is kept; nothing is tuned on the final split; no model size or prompt is
added to rescue it.

**H1 is not supported if** D does not beat C and E on net gain, or does not
beat B2. The result is then reported as ordinary ranking, or as no
advantage.

**One final run only.** Exactly one frozen final-split run is authorized,
after the protocol, corpus, reference, prompts, code and model hashes are
committed.

## 12. Claim ceiling

At most: "a frozen neural guide used authentic failure traces to select
useful representations more reliably than task-only and trace-shuffled
controls under matched compute, without weakening symbolic verification" on
this private synthetic corpus, and only if every part holds.

It is not:
- a solve improvement on real ARC;
- semantic invention;
- durable learning;
- transfer.

## 13. Milestones

1. This plan.
2. Corpus generator and tests.
3. Reference (BASE x2 plus PROMOTE per view) on all candidates; strata
   counts.
4. Guides, mutation tests and an identity-overlay test.
5. Development run.
6. Freeze v1 (protocol, prompts, hashes).
7. One final run.
8. Result record.
9. Paper and poster only if the evidence is verified; otherwise a
   proposed-branch note.

## Amendment 1 (2026-10-13T01:40Z), before any guide outcome was seen

No guide has been scored against the reference. The reference run was still
in its native phase, and no promoted-view outcome existed.

1. **Decision.** BASE and BASE_REPEAT both REJECT, and the full training set
   has at least one view cut by the cap. Options are the cut views plus
   NO_CHANGE.
   - The guide decides admission only, as the mechanism defines.
   - When the two native runs disagree, the task is reported as unstable.
2. **B2 is redefined as "coarsest first":** the fewest objects over the
   training inputs, ties broken in native order.
   - Object-change homogeneity scores every per-piece view perfectly on
     recolouring rules, so it could not discriminate.
   - "Coarsest first" is the simplicity prior of ARC object solvers and is
     demonstrations only.
3. **Selection split dropped.** Closed-set likelihood scoring cannot produce
   a malformed answer, so the parse rule is moot. The development split
   serves debugging, the sanity rule and the JEPA gate.
4. **Arms added.**
   - C-CF, D-CF and E-CF: the counterfactual-transition form. Per view: a,
     a generalizing rule; b, nothing new; c, a rule that fits but fails on
     new inputs. Views are ranked by P(a), and the top view is tried only
     when a is its most likely answer.
   - D_perm1 and C_perm1: the same prompts under a second label
     permutation, measuring stability.
5. **J arms defined.** The score is the mean cosine between the I-JEPA
   embedding of a view's object partition of each training input and that of
   the output. Patches are cell-aligned, one 14-px patch per cell.
   - J-D restricts to the training pairs whose leave-one-out re-derivation
     failed in the authentic trace.
   - J-E uses another decision's failed-pair set.
   - J arms always try their top view.
6. **Reference semantics.**
   - Stage A scores a choice by the engine's own promoted-view run (uniform
     promotion, full adaptive leave-one-out, 20 s).
   - Stage B, fold-local guidance per subset through a lookup overlay, is
     built only if Stage A supports H1.
7. **Shuffled source (E arms).** The next decision in id order with the same
   number of options, never the task itself.
8. **Prompts and code.** The prompt text is produced by
   `cora_neural_view/guides.py` at commit 7cb8242. Its sha256 is pinned in
   freeze v1, before the final split is run.

## Amendment 2 (2026-10-13T13:35Z), before any guide saw the final split

**Development results.** These were used for debugging and the JEPA gate
only, and are not evidence. File: `outputs/neural_view_v0/stageA_dev.json`.
39 decisions: 13 warranted, 2 misleading, 24 no help.

| arm | gains | harms |
|---|---|---|
| B1 | 8 | 0 |
| B3 | 8 | 0 |
| B2 | 6 | 3 |
| random (mean) | 2.8 | 0.4 |
| C (Qwen) | 3 | 2 |
| D | 1 | 0 (7 abstentions) |
| E | 2 | 0 |
| F | 3 | 2 |
| C-CF | 3 | 0 (27 abstentions) |
| D-CF | 1 | 0 (36 abstentions) |
| J-C | 11 | 2 |
| J-D | 11 | 2 (choices identical to J-C) |
| J-E | 11 | 2 (choices identical to J-C) |

- **Label-permutation agreement:** D 0.69, C 0.59.
- **The JEPA gate passed.** J-C's top-1 useful rate on warranted decisions
  is 0.846, against 0.216 for random and 0.462 for B2. The J arms stay.
- **Every LLM decision scored,** so the sanity rule is met.
- **No prompt, code or model change was made after these results.**

**Blinded sample-size extension.**
- The final split had 14 warranted decisions (67 decisions, 84 tasks). The
  pre-declared minimum is 30.
- Using only that prevalence (no guide has run on the final split), each
  final family gets seeds 7114-7134: 21 more tasks per family, 126 in
  total.
- The 84 existing final tasks are byte-identical, as checked.
- Corpus v0 is now 258 tasks, sha256 41004ce9...; the reference is
  extended by its resumable runner.
- If the final split still has fewer than 30 warranted decisions, the
  result is labelled UNDERPOWERED. No further extension.

**Secondary comparisons added** (declared before the final run):
- J-C vs B1, J-C vs random, B1 vs random;
- the harm count of every arm. The zero-new-false-acceptance criterion
  applies to every arm, the J arms included.

**Interpretation rule, fixed now.** If J-C beats B1 while J-D does not beat
J-C and J-E, the result is reported as ordinary demonstrations-only neural
representation ranking, not as failure-conditioned guidance.

## Amendment 3 (2026-10-13T15:00Z): freeze v1, before the single final run

- **Final split, counts only.**
  - 210 tasks. The two native runs agree on every task: 209 REJECT/REJECT,
    1 FALSE_ACCEPT/FALSE_ACCEPT.
  - **165 decisions: 35 warranted, 0 misleading, 130 no help.** Two cut
    views are FALSE_ACCEPT within decisions, so harms are possible.
  - **The minimum-power rule (at least 30 warranted) is met.**
- **Freeze.** `outputs/neural_view_v0/freeze_v1.json`, committed with this
  amendment, pins:
  - the code, the plan and the corpus;
  - the model revisions and weight hashes;
  - the LLM template, the counterfactual question and the sample prompts;
  - the final-split reference rows.

  `freeze check` reports no differences, and the 7 NVG tests pass.
- **What runs next.** `run_guides --split final` once, then
  `evaluate --split final`. No change after the result.
