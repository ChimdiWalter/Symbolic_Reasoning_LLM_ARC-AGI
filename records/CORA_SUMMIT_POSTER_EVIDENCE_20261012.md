# CORA, ARC Prize Research Summit 2026-10-23: poster evidence index (2026-10-12)

Read-only, evidence-indexed preparation note (summit addendum, section F).
Every number on the poster must trace to a row of this file. Not used for
the poster: the pilot v2 bundle, the 488 untouched candidates, any test
output, any evaluator key map, Step B, VDCG (a separate project, never
imported here). Figures are drawn only from the sealed outputs below by
`scripts/summit_figures.py` into `docs/summit_poster/figures/`.

## 1. Evidence table (tier first; never exceed the tier)

| tier | statement allowed | numbers | source |
|---|---|---|---|
| SYNTHETIC, prospective, run once | A specified constructive loop passed its frozen synthetic end-to-end gate | complete B/P/U/L/T/A witnesses 27/30 (repaired engine K*') vs 12/30 (K*); adaptive LOO 27 vs 12; terminal verifier 28/28; claim LEVEL 2, synthetic domain only. Disclosed weakness: K*' accepted 5/5 seven-demonstration and 28/28 four-demonstration deliberately wrong installed extensions (the engine is not a discriminator) | `records/ITEM2_V19_PROSPECTIVE_RESULT_20261007.md` (sha256 83889f13...), commit 2885a04; manifest 528981dd..., rows aad86def... |
| SYNTHETIC, preserved negative | The tested failure-association selector did not beat demonstrations alone | D alone 0.591, D + failure association 0.585 (increment -0.006, 95% CI -0.026 to +0.014), 288 independent groups; conditional on that selector and training resource | `records/ITEM2_V15_SELECTION_RESULT_20261001.md` (96c32559...), commit eb5efa5 |
| REAL DEVELOPMENT (60 training-development tasks; no test output read) | Failure-conditioned construction produced executable repairs that reached the native engine; one was accepted and used with all demonstrations; none survived adaptive LOO | 54 native object-engine failures; 31 with usable failure evidence; 4 machine-generated proposals; 4 compiled; 4 installed (0/60 before, ce123e8); 1 accepted and used; adaptive LOO 0 of 14 folds; activations 0; READY = PASS by the pre-registered installation rule only | `records/REACH_V1_MEASURE_20261011.md` (f0bbd78c...), commit bb11f95; frozen c8d8e3a (manifest 2e567bce...); rows 821a6556... (60ddd04) |
| FORENSIC (development only, observation only; the subsets examined were chosen AFTER the failure was seen: causal debugging, not test evidence) | The LOO failures trace to a segmentation-variant admission mismatch in the native engine | 11 of 14 failed folds and all 3 full-data rejections; resources ruled out (WALL = CPU1 in 23 of 23 arms) | `records/LOO_V1_DIAGNOSIS_20261012.md` (f022f287...), commit c2b8cd4; probes `outputs/loo_v1/probe_kf892487f1049.json` (955542c), `probe_variants.json`, `probe_eligibility.json` (82251a4) |
| FORENSIC, addendum (same tier and caveat) | Count consistency is deletion-stable; the complete eligibility test is NOT monotone (CORRECTED by Clarification 01); on kf892487f1049 the defect is the 4-variant cap cutting the strictly coarser S6 that the engine's own fold-convergence rule relies on | losses of a coherent view: 0 of 72 synthetic and 0 of 50 FC-task comparisons, but 7 of 724 across all 60 development tasks (pooled coverage; consistency never broke); on kf892487f1049 only (0,2) and (1,3) add S1 to S5 | `records/LOO_V1_DIAGNOSIS_ADDENDUM_20261012.md`, commit a719383; `outputs/loo_v1/probe_exposure.json` (794ad70b..., 3ba75e5) |
| SYNTHETIC, negative controls (24 seeded tasks, 6 families; not ARC) | Forcing one segmentation variant first is not a safe generic repair | task level: 0 of 24 gained, 5 of 24 harmed (4 of the 7 natively correct; 1 rejected became a false acceptance); runs: 168, correlated within task, 6 harmful (PROMOTE: 2 correct to rejected, 1 rejected to false acceptance; ADMIT, the reach v2 class: 2 correct to rejected, 1 correct to false acceptance); native: 7 correct, 2 false acceptances, 15 rejected | `outputs/loo_v1/probe_negative.json` (2f100350..., 70d3ed9), probe 1f03a1c; figure `fig_negative_controls.png` (914049c) |
| PROPOSAL, NOT AUTHORIZED | One narrow correction is specified with predictions, frozen criteria and a kill rule | P2 (LOO-anchored completion): FORENSIC only, cannot be a certificate (its anchor saw the inner held-out demonstration). P3 (fold-local view dedup): tested once on 41 synthetic tasks and REJECTED (1 gain; 4 harmed: 2 regressions, 2 new false acceptances; 98c9bed) | addendum section 7; `records/LOO_V1_DIAGNOSIS_ADDENDUM_CLARIFICATION_01.md`, `records/LOO_V1_SEGMENTATION_EQUIVALENCE_20261012.md` (c2fa2ae) |
| STATIC census (60 development + 24 synthetic tasks; no induction) | Equal object counts do not imply equivalent views; the cap holds duplicate views | on (0,2) and (1,3) the 4 searched views are 2 distinct reasoner inputs; 571 of 1,849 development slots (31%) duplicate an earlier view; dedup would change 277 of 522 development subsets and 4 of 6 native successes | `outputs/loo_v1/probe_equivalence.json` (90c2a325..., 7d11993) |
| REPAIR BUILT, NOT MEASURED | A variant-carrying installation was implemented and tested on synthetic fixtures only | its 60-task recheck was stopped before any unit finished (0 rows): no result exists | 568af22 (code), 41c20a2 (stop) |
| FROZEN, NOT RUN | A prospective protocol and an untouched sample exist | pilot v2, N = 120 | c1906ee, manifest c93ec1db... |
| BASELINE | Historical certified training score | 185 / 1,000 (sealed v23 run + arbitration), unchanged | evaluator-pinned v23 records (sha256 763beefd..., 35e8f5c9...) |
| PROPOSAL, UNTESTED | A second-domain (biological perturbation) protocol is specified | none: no biological data or result | this file, section 6 |

The single true claim of v1.9, in one sentence: on synthetic tasks from its
frozen generator, the repaired engine with the frozen proposer produced 27 of
30 complete prospective witnesses against 12 of 30 for the earlier engine, a
LEVEL 2 claim limited to that synthetic domain and witness-support regime.

## 2. The 02/13 candidate-pool observation (kf892487f1049), with source pointers

- Full data (4 demonstrations): the native engine with the constructed
  bbox_fill extension accepts the one-rule program G (selector true; grow by
  the installed relation; colour of self) and uses it.
- Every outer fold (3 demonstrations) finds G (or, on the window_fill fold,
  the same one-rule program with window_fill) at the top level; the engine's
  own leave-one-out then re-induces from 2 demonstrations.
- On the pairs (0,1), (0,3), (1,2), (2,3) the engine searches S6 first and
  returns G, which reproduces the other two demonstrations. On (0,2) and
  (1,3) it searches S1, S2, S3, S5 only and returns a constant-class program
  (2 rules on (0,2), 4 on (1,3)) that is wrong on the held-out demonstration
  (21 to 33 cells). G is
  train-exact on every pair; exploring all candidates of the searched
  variants does not recover it; a ranking cause is refuted.
- The predicate: `geocat_arc/object_reasoning/segmentation.py:261`
  `_count_relation_consistent` (one pair is always consistent; across pairs
  a constant difference, a constant output count or a constant integer
  ratio), used by `evaluate_variant` (line 291; coherent = consistent and
  pixel coverage >= 0.80, line 47). In S1 to S5 the demonstrations have
  (input, output) object counts (2,1), (4,2), (2,1), (4,2): inconsistent on
  any subset that mixes the two types, consistent (constant difference) on
  (0,2) and on (1,3). In S6 the counts are (1,1), (2,2), (1,1), (2,2):
  consistent everywhere.
- The cap: `geocat_arc/object_reasoning/inducer.py:166`
  `MAX_SEG_VARIANTS_TRIED = 4`; `_induce_candidate` (line 2846) keeps the
  coherent variants in `SEGMENTATION_TRIAL_ORDER` (`types.py:52`: S1, S2, S3,
  S5, S4, S6, S7) and searches the first four. On (0,2) and (1,3) S6 is
  ELIGIBLE but ranked sixth, so it is never searched: "eligible but cut by
  the cap", not "ineligible".
- The engine's own leave-one-out (`inducer.py:2749` `loo_validate`)
  re-induces from every n-1 subset; inside an outer fold that is n-2.
- Figures: `docs/summit_poster/figures/fig_kf89_variant_admission.png`
  (derived from the probes and the diagnosis rows),
  `fig_kf89_training_demonstrations.png`.

## 3. Training demonstrations safe to visualize

- kf892487f1049: its 4 TRAINING demonstrations (input and output), from
  `records/pilot_v1/dev_bundle.json` (opaque key). The bundle holds no test
  output; its test input is not shown. The ARC task identifier behind the
  key is evaluator-side and is not disclosed.
- Optional, same mechanism: k5a49896251a2's 3 training demonstrations (S6
  eligible on every subset, cut by the cap on every single demonstration).
- Never: any test output, any pilot v2 task, any evaluator key map.

## 4. Not simply CEGIS or DreamCoder: a falsifiable difference

CEGIS-style loops already refine candidates from counterexamples, and
DreamCoder/LILO-style systems already grow reusable libraries. CORA's claimed
difference is narrower and testable: it diagnoses WHICH layer failed (search,
representation admission, executable capability, evidence) and changes only
that layer, under fixed verification. It would be FALSIFIED if, at matched
observations, library, verifier access and total compute, failure-typed
adaptation does not beat (a) fixed-language search with the same budget, (b)
CEGIS-style repair with the same extension rights, (c) demonstrations-only
and shuffled-failure construction, on blind held-out tasks. None of these
comparisons has been run on real tasks; the development data above show why
the diagnosis layer matters (a representation-admission defect masqueraded as
a failed repair).

## 5. Domain-portable interface (concept)

Invariant part (the control protocol): attempt with K; extract an auditable
failure trace; type the failure; choose search / representation / construct
/ abstain; validate independently with rules fixed in advance; use e
provisionally only if licensed; re-run the same reasoner; blind scoring and
removal controls; separate promotion. Domain-specific parts: observation
adapter, program semantics, priors, validators.

Left lane (implemented): ARC grids -> object/segmentation adapter -> controller
-> grid programs. Right lane (UNTESTED PROPOSAL, no results): measured
perturbation responses across cell states, donors and guides -> state adapter
-> the same controller -> a typed condition-dependent response rule, fitted
on training data only; checks would be leave-one-guide, leave-one-donor,
held-out combinations, calibration, confounder stress tests and an
independent evaluator; predictive validation only; causal biology needs
controlled interventions.

## 6. The next decisive comparison and its failure policy

1. Development only: one representation-admission intervention, frozen with
   its negative fixtures, side-effect checks and matched accounting BEFORE
   code is edited; compared with the original on the same 60 tasks
   (program recovery, adaptive LOO, false acceptances, native regressions,
   CPU time). Labelled REPRESENTATION/SEARCH CORRECTION, not invention.
   The candidate is P2 (addendum section 7): inside the engine's own
   leave-one-out only, append the validated program's variant when the fold
   finds it coherent but the cap cuts it. NOT AUTHORIZED; its own predictions
   say the screen still fails (kf892487f1049 fold 1 is refuted by its
   held-out demonstration after the proposer picks window_fill).
2. Screen for a new pilot: at least one development task with invariant
   conditions 1 to 5 together. If it fails: record the blocker; the 488
   candidates and pilot v2 stay untouched.
3. Only then a new, versioned, prospectively frozen blind pilot (v3), on a new
   explicit authorization.

## 7. Negative controls (synthetic) for any admission intervention

`outputs/loo_v1/probe_negative.json` (70d3ed9, sha256 2f100350...): 24 seeded
synthetic tasks, 6 rule families, 3 training + 2 held-out demonstrations
each; the engine's own induction (train-exact + its own LOO, 20 s). The
engine as is: 7 correct, 2 false acceptances, 15 rejected (all at its own
LOO). Paired with each task's own native outcome:

| overlay | runs (tasks) | unchanged | harmful changes | gains |
|---|---|---|---|---|
| PROMOTE (an eligible variant searched first) | 131 (23) | 128 | 3: translate_down_0 S6 and translate_down_1 S7 correct to rejected; translate_down_2 S7 rejected to false acceptance | 0 |
| ADMIT (an ineligible variant searched first and admitted; the reach v2 class) | 37 (10) | 34 | 3: halo_0 S4 correct to false acceptance; multicolor_majority_3 S1 and S5 correct to rejected | 0 |

Mechanisms (engine code path): a coarser variant searched first prunes the
finer native ones through the parsimony skip; a forced view's program passes
the engine's gates but is wrong on held-out demonstrations; an incoherent
forced view uses 3.5 times the native time (consistent with budget
displacement). Poster statement allowed: "On 24 synthetic control tasks, forcing a
view first gained no task and harmed five; we therefore did not run the
variant-first repair." (The 168 runs are correlated comparisons, not 168
independent tasks.) Not
allowed: any claim that P2 is safe (it has not been run).

## 8. Likely skeptical questions, answered within the evidence

- Knoop: "Is this just a refinement harness?" It includes refinement; the
  extra layer is the typed decision of what to change. Its incremental value
  over matched refinement has not been shown on blind real tasks; that is the
  decisive experiment.
- Chollet: "Where is the intelligence rather than a hand-written skill set?"
  The growth grammar is a human-designed prior and is named as such. The
  proposal is to measure acquisition efficiency with that prior fixed and
  every cost counted (diagnosis, construction, verification, memory).
- "Did you solve a new ARC task?" No: 0 activations; the certified score is
  185/1,000, unchanged.
- "Is bbox_fill a new semantic capability?" Not established. Checked:
  not a renaming of a native growth mode, not a cache, and K alone does not
  reach it within the tested budgets. No complete bounded absence proof.
- "Does leave-one-out prove correctness?" No: it is an empirical stability
  test. Here it exposed a representation-admission defect.
- "Why not report the 120-task pilot?" It is frozen and has not been run;
  development predicts a no-witness outcome while the LOO blocker stands.
- "Why not just raise the cap or search every eligible variant?" Statically,
  letting the coarser completion reach every cut variant would change the
  search on 73 of 96 synthetic subsets, mostly through S7, the proximity
  view the engine keeps as a last resort; and forcing a variant first was
  harmful on 5 of 24 synthetic tasks (6 of 168 correlated runs) with no gains.
- "So the blocker was a bug in the engine, not a missing capability?" Yes:
  for kf892487f1049 the evidence says representation admission (a
  search-layer defect), which is exactly the kind of distinction the
  failure typing is meant to make. A fix would be labelled representation
  correction, not invention.
- "What about VDCG?" A separate project; none of its results are used here.

## 9. Corrections to the draft summit documents (2026-10-12)

1. "S6/S7 are not admitted / ineligible" -> S6 (and S7) are ELIGIBLE on
   (0,2) and (1,3) but cut by the 4-variant cap, because S1, S2, S3, S5
   become eligible there through a coincidental constant-difference count
   relation.
2. "The eligibility rule is under investigation" -> resolved at the predicate
   level (section 2); the remaining question is which generic intervention,
   if any, is safe (section 7).
3. A repair was built (568af22) but never measured: its recheck was stopped
   before any unit finished. No repair result exists.
4. "The fold winner on (0,2) and (1,3) has 4 rules" -> 2 rules on (0,2), 4 on
   (1,3); both constant class.
5. "Broader eligibility would fix it" -> forcing or admitting a variant was
   harmful on synthetic controls (section 7); the eligibility predicate itself
   keeps count consistency under deletion (complete-test monotonicity later corrected, see 11.6); P2 is forensic only (11.7).

## 10. Figure provenance (poster QC, 2026-10-12)

Every figure is drawn at its printed size, 24.1 cm wide (one block), with
text of at least 20 pt. Its inputs are pinned by sha256, and two rebuilds
are byte-identical (`docs/summit_poster/build.sh`). Full metadata is in
`docs/summit_poster/figures/PROVENANCE.json`.

| figure | printed size (cm) | tier and denominator | inputs |
|---|---|---|---|
| fig_synthetic_v19.png | 24.1 x 9.1 | SYNTHETIC, n = 30 tasks | v19 report 987ab9ea..., rows aad86def... |
| fig_funnel_reach_v1.png | 24.1 x 16.0 | REAL DEVELOPMENT, 60 tasks | measure_funnel 77fbac13... |
| fig_kf89_training_demonstrations.png | 24.1 x 13.6 | REAL DEVELOPMENT, 1 task, training demonstrations only | dev_bundle 6eb73236... |
| fig_kf89_variant_admission.png | 24.1 x 21.8 | FORENSIC, 1 task, 11 subsets | probe_eligibility 922151e2..., probe_kf89 9bdff08a..., diagnose_rows 31ddf9af... |
| fig_negative_controls.png | 24.1 x 28.2 | SYNTHETIC, 24 tasks, 168 correlated runs | probe_negative 2f100350... |

## 11. Further corrections (post-diagnosis addendum, 2026-10-12)

6. "Eligibility is monotone": corrected. Count consistency is
   deletion-stable; the complete test is not (7 of 724 development losses,
   all through coverage). See Clarification 01.
7. "P2 is the narrow repair": corrected. P2 is FORENSIC only, because its
   anchor was chosen with the inner held-out demonstration.
8. "168 harmful-change runs" as a sample size: corrected. These are
   correlated runs on 24 tasks; report task-level counts (0 gained, 5
   harmed).
9. Implemented vs proposed: the failure typing on the poster was forensic,
   done by hand. The general failure-type controller is proposed, not
   implemented.

## 12. P3 synthetic safety preflight (2026-10-12)

Record: `records/P3_SAFETY_PREFLIGHT_RESULT_20261012.md` (evidence 98c9bed;
frozen b594223). Verdict: P3_REJECTED.

| | result |
|---|---|
| tasks harmed | 4: 2 regressions, 2 new false acceptances |
| tasks gained | 1 |
| unexposed tasks | 7, byte-identical |
| unstable tasks | 0 |
| CPU | +15.5% |

Allowed poster statement: "Removing duplicate views, the fold-local repair,
was tested on 41 synthetic tasks: it gained 1 and harmed 4, so it was
rejected." Synthetic only.

## 13. Neural view guidance, a negative result (added 2026-10-13)

- **Poster** (block "The right view was cut, not missing"), the **abstract**
  (one sentence) and the **explainer** (Part 3) now state the CORA-NVG
  result.
- **Source.** `records/CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013.md`. Freeze
  `outputs/neural_view_v0/freeze_v1.json` at commit 7f0b17e; single final
  run 2026-10-13T15:13-15:24Z.
- **The numbers** (synthetic tier):
  - 165 decisions, 35 warranted;
  - fixed order 35 of 35;
  - frozen Qwen2.5-1.5B: 19 with demonstrations only, 1 with the authentic
    failure trace, 1 with a shuffled trace;
  - frozen I-JEPA 3; random 12.6.
- **Limitation, stated in the result record:** all 35 warranted decisions
  come from one family.
- **The explainer's diagnosis line was outdated** and is corrected: "No
  automatic failure diagnosis" now reads that a first version exists (13 of
  18 on recorded traces, `records/CORA_DIAG_V0_RESULT_20261012.md`) and is
  untested on new failures.
- **No new figure.** The poster's PNGs and `figures/PROVENANCE.json` are
  unchanged.

## 14. Official Kaggle result of the native solver (added 2026-10-13)

- The **poster** ("Not claimed" block) and the **abstract** (evidence line)
  now state: "Official Kaggle ARC-AGI-2 score of the native solver (October
  2026): 0.00".
- **Source.** `records/KAGGLE_NATIVE_V1_OFFICIAL_RESULT_20261013.md`:
  submission 57144804, notebook
  `chimdiwalter/cora-native-v23-arc-agi-2-october-baseline` version 1,
  dataset `chimdiwalter/arc-native-baseline-v1` version 1, tarball
  4b320ba2...; COMPLETE, public 0.00.
- **Label:** OFFICIAL KAGGLE, NATIVE BASELINE. It is not evidence about the
  invention loop, which is not in the package.

## 15. Failure funnel and competition status (added 2026-10-14)

Poster blocks "Where CORA fails on real tasks", "Repairs tested before use",
"Competition status, 14 October" and "Next: construct the missing operation";
abstract paragraph 3; explainer panels 5–8. The full record is
`records/CORA_FAILURE_FUNNEL_20261014.md`.

| number on the poster | source | commit |
|---|---|---|
| the 60-task category bars (6 / 0 / 2 / 27 / 22 / 3) | `outputs/funnel_v0/eval_dev60_native.json`, sha256 3fb8c0e3…f595 (pinned in `scripts/summit_figures.py`); figure `fig_failure_funnel_dev60.png` | 9c58af8 |
| with LOO 6 right / 0 wrong; LOO off 8 right / 26 wrong | the same file: `S6_correct`, `incorrect_accepted`, `gate_off_correct`, `gate_off_wrong` | 9c58af8 |
| 21 of 25 constant-parameter; 59 of 74 failed folds rebuild a different program | `rows_dev60_native_rep.jsonl` (structure recorded), the funnel record's "Structural contrast" section | 9c58af8 |
| relational re-search 0 of 11 | the same rows: native phase C, identity-frame searches | 9c58af8 |
| ×3 budget fixes 0 of 14 | `eval_dev60_budget3.json` vs `eval_dev60_native.json` | 9c58af8 |
| oracle 26 of 27, same view in 24 | `oracle_dev60.json`, sha256 90f59ad7…c1f6dc, and the rows (ORACLE, evaluator-side) | 37881f9 |
| view admission explains 7 of 76 failed folds | `eval_dev60_native.json` summary, `failed_folds.full_view_not_admitted` | 81ecf25 |
| growth families cover 5 of the 27 | `outputs/reach_v1/grammar_coverage.json` joined with the funnel categories | 9c58af8 |
| whole harness 12 of 60; 18 of 29 claims wrong | `outputs/funnel_v0/eval_dev60_harness.json`, sha256 2d9d5dd0…7e78 | 5086a18 |
| arbitration 14 of 60; 36–39 of 60 on C2-dev; 0 lost | `arbitration_shadow_dev60.json`, `arbitration_shadow_c2dev.json` | 93a7d10 (dev60); this commit (C2-dev) |
| neural stand-in: 240 tasks decoded, 259 of 259 genuine, 0 fallbacks, 4.3 h | `outputs/kaggle_deploy/neural_v1_full_run1/coverage_audit.json`; `records/KAGGLE_NEURAL_V1_LOG_20261013.md` section 10 | 8e1976a |
| official public score 27.64 (NEURAL_TTT_BASELINE, not CORA) | the same log, section 11.2 (57160429); `outputs/kaggle_deploy/neural_v1_official_score.json` | this commit |
| Qwen2.5-1.5B 19 of 35, I-JEPA 3 of 35 | section 13 above | — |

The "PROPOSED" block describes an experiment that has not been run. Its
numbers (9 families, 5 of 27) are coverage measurements, not results.

## 16. CORA-FHR development witness (added 2026-10-14)

Poster block: "Constructing the missing operation"; abstract paragraph 4.

| number | source |
|---|---|
| figure `fig_fhr_witness_dev_D3_04.png` | pinned in `scripts/summit_figures.py`: `outputs/cora_fhr/c4_dev_v2.json` and `docs/summit_demo_20261023/data/witness.json` |
| 37,750 operators | `cora_fhr/ggrow.py`, `tests/test_fhr.py` |
| native 7/300, best existing 8/300 | `outputs/cora_fhr/witness_dev_D3_04.json`, `perturbation_novelty` |
| 3/3 folds, correct, ablation | the same file, and `rows_c4_dev_v2.jsonl` |
| 0 wrong, 0 lost over 27 tasks | `eval_c4_dev_v2.json` |
| matched search 0 of 15 | `eval_c4_dev_v2_B.json` |
| failure-blind match; E = C' by design | `rows_c4_dev_v2.jsonl` (arm C), `c2_audit_c4_dev_v2.json` |
