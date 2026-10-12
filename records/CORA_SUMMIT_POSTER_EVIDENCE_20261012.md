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
  (1,3) it searches S1, S2, S3, S5 only and returns a 4-rule constant-class
  program that is wrong on the held-out demonstration (21 to 33 cells). G is
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
2. Screen for a new pilot: at least one development task with invariant
   conditions 1 to 5 together. If it fails: record the blocker; the 488
   candidates and pilot v2 stay untouched.
3. Only then a new, versioned, prospectively frozen blind pilot (v3), on a new
   explicit authorization.

## 7. Negative controls (synthetic) for any admission intervention

Pending at the time of writing: `outputs/loo_v1/probe_negative.json`
(24 seeded synthetic tasks, 6 rule families; the engine with no overlay,
PROMOTE (an eligible variant first) and ADMIT (an ineligible variant first
and admitted); false acceptances, native regressions, gains).

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
