# CORA-FHR v1: failure-conditioned construction of a derived growth operator

**Preregistered protocol. Status: FROZEN (specification). Not implemented,
not run.**
- **Written:** 2026-10-14, under the user's Step 1 authorization ("protocol
  and grammar specification only; do not launch the prospective experiment
  or make another Kaggle submission").
- **Grammar:** `docs/CORA_FHR_GGROW_v1.md`.
- **Frozen numbers:** `records/cora_fhr_v1_frozen_parameters.json`.
- **Evidence behind the design:** `records/CORA_FAILURE_FUNNEL_20261014.md`.

## 1. Question and hypotheses

**Question.** Can CORA use evidence from its own failure to construct a
growth operator that frozen CORA cannot use, so that the same reasoner
commits independently correct predictions beyond:
- frozen CORA;
- matched additional search;
- failure-blind construction?

**Why this capability.** The funnel located the dominant real-task failure
(DEVELOPMENT, 60 tasks):
- **27 of 60 tasks** fit the demonstrations only with memorizing rules: in
  19 of 25 analysable ones, constant GROW cell patterns keyed to colour or
  exact shape.
- **Native's own relational re-search** returned no program (0 of 11).
- **Three times the budget** fixed none (0 of 14).
- **None of the 11 derived GROW modes native detects** ever matched: `detect_grow` fell back to
  the constant `pattern`.
- **The frozen 9-family construction grammar** covers 5 of the 27.

**Hypotheses** (G is the held-out growth family set of section 5):
- **H1, capability:** arm E certifies correct test outputs on G tasks where
  frozen CORA fails, with operators of class NEW_COMPOSITION.
- **H2, not search:** matched additional search (B) does not reproduce E's
  gains.
- **H3, the evidence matters:** E's gains exceed those of failure-blind
  construction (C) and of shuffled-evidence construction (D), which use the
  same grammar and compute.
- **H4, safety:** E adds no certified-wrong prediction and loses no natively
  correct one.

## 2. The trigger: detecting unstable memorized growth

**T_MEM** fires on a task when both conditions hold:
1. **Native fails.** The frozen native object layer (CPU-clock budgets, as
   in the funnel) does not certify the task.
2. **Growth was memorized.** During native's identity-frame induction on the
   demonstrations, `detect_grow` fell back to the constant `pattern` on at
   least one object in at least SUPPORT_DEMOS = 2 demonstrations, within one
   segmentation variant (`cora_reach/instances.py`).

Both conditions read only the demonstrations and native's own behaviour on
them. The test input is never read, and no answer is.

**Abstain** (commit nothing beyond frozen CORA's output) when:
- T_MEM does not fire;
- no G-grow operator explains every instance of a variant;
- native rejects every installed proposal (not train-perfect, or its own LOO
  fails);
- the adaptive LOO of section 3 fails on any fold.

Every abstention is recorded with its reason.

## 3. Construction, installation and fold-local verification (arm E)

1. **Evidence.** The memorized instances, grouped per segmentation variant:
   - the object's cells and colours;
   - the added cells and their single colour;
   - the input grid.
2. **Construct.** Enumerate G-grow in canonical order. Keep the operators
   whose added cells equal every instance's added cells exactly, after
   observational deduplication, at most MAX_PROPOSALS = 8.
3. **Classify** each kept operator against B (grammar section 4):
   AVAILABLE_REACH or NEW_COMPOSITION.
4. **Select and install.** The canonically first proposal is installed into
   the unchanged native engine through the bridge overlay. Native re-runs the
   whole task. Native's own acceptance gate (train-perfect plus LOO by
   re-induction) decides, and `uses()` records whether the accepted program
   uses the extension.
5. **Adaptive LOO** (`cora_reach.measure.loo_fold` semantics, unchanged).
   For each demonstration i:
   - drop it;
   - re-extract the instances from native on the remaining demonstrations;
   - re-construct, re-select and re-install;
   - re-run native from scratch.

   The fold passes when native accepts a program that uses the fold's own
   extension and reproduces demonstration i exactly. Nothing passes from the
   parent run into a fold: no proposals, no extension names, no budgets.
6. **Commit.** E commits the test prediction only if steps 4 and 5 both
   succeed. Otherwise it commits frozen CORA's output. The prediction is
   written before the evaluator runs.

## 4. Arms

All arms use the same tasks, the same native reasoner with CPU-clock budgets
(90 s cooperative, 7 frames × 45 s, a 450 s cap), and the same verification.

| arm | what changes |
|---|---|
| **A frozen** | nothing (the funnel's native run) |
| **B matched search** | native budgets × f_B, where f_B is fixed after the development run as E's median CPU over A's on development G tasks (written into the parameter file before the freeze) |
| **C failure-blind** | instances from the demonstrations alone (grammar section 5); then steps 2–6 identically, including fold-local re-proposal from demonstrations only |
| **D shuffled** | arm E's instances from the donor task; then steps 2–6 identically |
| **E authentic** | sections 2–3 |

**Removal ablation, for every counted gain:**
- the same task without the extension is arm A, which fails by the trigger;
- the accepted program must use the extension;
- the K-alone run at matched compute (B) must not certify the same answer
  (reach's separation condition (iii)).

## 5. Prospective corpus C4 v1 (SYNTHETIC)

The generator is written and committed before any run. Each task has
3 demonstrations and 1 test, on 10–14 × 10–14 grids.

**Ground truth.** It is a G-grow expression for the growth families, or a
stated rule for the controls. The constructor never sees it.

**Rejection rule for growth (G) samples, applied at generation.** A sample
is rejected if:
- any B_native mode explains its growth (native's `detect_grow` returns a
  mode other than `pattern` on the true objects); or
- any B_reach setting reproduces its added cells on all three
  demonstrations.

So no G task is solvable by selection from B.

| category | role | development (seeds 11000+) | final (seeds 11500+) |
|---|---|---|---|
| **G** growth, needs a NEW_COMPOSITION | H1–H3 | 3 families × 5 | **4 held-out families × 10** |
| **N0** native-available growth (halo, fill_interior, silhouette ray) | no change expected; losses | 3 | 10 |
| **S** reach-available growth (bbox_ring, connect, dilate) | selection, reported separately | 3 | 10 |
| **X** wrong action (recolor-by-size, translate) | the trigger should not fire; harm | 3 | 10 |
| **U** underdetermined: two non-equivalent G-grow operators agree on the demonstrations, differ on the test | abstention and false acceptance | 3 | 10 |

**Held-out mechanisms.** The final G families use G-grow compositions whose
(source, transform-pair) combinations appear in no development family. The
family table, with expressions, is written into the parameter file and the
generator before the freeze.

- **Development families** (debugging only):
  - D1 `ray(d, obstacle) ∘ edge(d)`;
  - D2 `shift(size_gap(d)) ∘ reflect(edge d)` applied to `self`;
  - D3 `union(ring(8), hull)` of `part_minority`.
- **Final families** (held out):
  - F1 `ray(diag d, obstacle) ∘ corners`;
  - F2 `ring(4) ∘ ray(d, border) ∘ part_minority`, written in depth-2 form
    as `ring(4)(ray(d, border)(part_minority))`;
  - F3 `repeat(size(d)) ∘ reflect(V)` of `self`;
  - F4 `union(ray(d1, border), ray(d2, border))` of `centre`, with d1 ≠ d2.

**Alternate family.** If B-rejection discards more than half of a final
family's samples at generation, that family is replaced by the
preregistered alternate F5 `shift(size(d))(ring(8)(self))`. The
replacement is recorded; no other substitution is allowed.

**Attribution.** Each family varies the number of objects (1–3), and some
have distractor objects that do not grow. So attributing added cells to
objects is non-trivial for the failure-blind control in some samples and
trivial in others. Each category is reported per family.

**Real-ARC secondary (DEVELOPMENT, no threshold).** Arms E and C on the 29
dev60 tasks with fits (27 FIT_BUT_ALL_WRONG, 2 REJECTED_BUT_CORRECT). It
reports certified-correct answers, false acceptances and novelty classes. It
is never a generalization claim. The grammar's design was informed by these
tasks' structure, which is disclosed here.

## 6. Success criteria, on the final split only

| id | criterion |
|---|---|
| **P1** gain | E certifies a correct output on ≥ 8 of the 40 final G tasks where A fails, in ≥ 2 of the 4 final families, each through a NEW_COMPOSITION operator |
| **P2** not search | at most 2 of E's counted gains are also certified correct by B |
| **P3** evidence | E's counted gains exceed C's by ≥ 3 |
| **P4** shuffle | E's counted gains exceed D's by ≥ 6 |
| **P5** safety | across all 80 final tasks, E adds 0 certified-wrong outputs over A and loses 0 of A's certified-correct outputs |
| **P6** necessity | every counted gain uses the extension, and A (no extension) does not certify it |
| **P7** adaptive LOO | every counted gain passes every fold, with fold-rebuilt extensions |

**Decision label, chosen by the first rule that applies:**

| label | rule |
|---|---|
| UNSAFE | P5 fails |
| NO_GAIN | E has fewer than 3 counted gains |
| SELECTION_ONLY | E's gains come only through AVAILABLE_REACH operators |
| SEARCH_SUFFICIENT | P2 fails |
| COMPOSITIONAL_GROWTH_WITHOUT_EVIDENCE_EFFECT | P1, P2 and P4–P7 hold, P3 fails |
| **CAPABILITY_GROWTH_DEMONSTRATED** | P1–P7 all hold |
| MORE_EVIDENCE_REQUIRED | otherwise |

**Supporting statistics, not decisive.** Exact McNemar tests (two-sided,
α = 0.05) of E against B, C and D on the 40 G tasks. The comparisons are
correlated and are reported as such.

**A single capability-growth witness,** for the summit demonstration, is
any one final task meeting P6, P7 and correctness, with A failing, B failing
and the operator NEW_COMPOSITION. One witness shows feasibility only.

## 7. Integrity requirements

- **The solver, constructor and diagnostic see:**
  - the training demonstrations;
  - native's own behaviour on them;
  - the test inputs, for rendering the committed prediction only.
- **Only the evaluator reads answers.** No oracle-derived program and no
  funnel oracle row is used by any arm.
- **Fold-locality:** every LOO fold rebuilds instances, proposals and the
  extension from its own demonstrations. A test asserts this.
- **Native v23 is frozen.** `geocat_arc` is not edited; every overlay is
  restored with an identity check. `cora_reach`'s frozen grammar is not
  mutated.
- **No protected data:** no evaluation solutions, HOLDOUT, ARC-1000 or
  pilot-v2 tasks. dev60 is development only. Step B, VDCG and E_transfer are
  untouched.
- **Freeze before the final run.** A manifest records sha256 of:
  - `cora_fhr/*`, `cora_reach/*` and `cora_funnel/run.py`;
  - the `geocat_arc` tree;
  - the generator and the generated final corpus;
  - the parameter file, including f_B.

  Any freeze problem means no run. Every attempted task and outcome is
  kept.
- **Claim ceiling:** compositional growth (L2). No new primitive is claimed.

## 8. Implementation plan

| step | deliverable |
|---|---|
| 1 | `cora_fhr/ggrow.py`: the evaluator and enumerator, with canonical order, deduplication and the extension form |
| 2 | `cora_fhr/baseline.py`: the B_native check (native `detect_grow`) and the B_reach check (210 settings); novelty classes |
| 3 | `cora_fhr/construct.py`: arms E, C and D proposal (instances, the G-grow search and the limits), reusing `cora_reach.instances` and the demo-only rule |
| 4 | `cora_fhr/bridge.py`: an adapted copy of `cora_reach/bridge.py` for G-grow extensions, with the identity-checked restore |
| 5 | `cora_fhr/measure.py`: the per-task policy for arms A–E, adaptive LOO, the removal and K-alone checks, and CPU-clock budgets (the funnel's `run.py` clock) |
| 6 | `cora_fhr/corpus_c4.py`: development and final splits, with B-rejection sampling |
| 7 | `cora_fhr/evaluate.py`: evaluator-only answers, P1–P7, the label |
| 8 | tests: determinism; no cell literals; restore identity; fold-locality; blindness; novelty classifier on known cases; generator rejection |
| 9 | the development run: C4 development split and the dev60 secondary; fix f_B; freeze |
| 10 | the final run: arms A–E on the 80 final tasks (detached, 4 workers); evaluation; record |

**Timeline:**
- Oct 15: steps 1–4.
- Oct 16: steps 5–8, and the intervention decision confirmed.
- Oct 17: step 9 and the freeze.
- Oct 18–19: step 10.
- Oct 20: analysis.
- Oct 21: summit freeze.

**Compute.** An E task costs about 1 + N extraction and induction runs. In
CPU time this is about 0.5–1 h per triggered task, and roughly 40–60 CPU-h
for the final run on 4 workers. That fits Oct 18–19 at the existing 4-worker
footprint.

## Amendment 1 (2026-10-14)

**Context.** Written during implementation, before any prospective
evaluation. The final split has never been generated, and no arm has run on
any final-family task. The original frozen files keep their hashes in the
ledger: protocol 26b08fff, grammar b0f9ad83, parameters 9578eda1.

1. **Fair object access for C (the user's Step 2 requirement).** Arm C no
   longer uses `cora_reach`'s 8-connected components. It segments every
   demonstration input with native's own `segment()` in each of the seven
   views, the same object representations native uses for E. Added cells
   (background in the input, non-background in the output, no input cell
   changed) go to the nearest object by Chebyshev distance; a tie discards
   that view for that demonstration. C reads no trace of the reasoner's
   failure.

   The difference left between C and E is the failure trace itself: which
   objects and view native memorized, and native's own correspondence of
   added cells to objects. C is now a stronger control.
2. **Tie abstention, in arms C, D and E, at the top level and in every
   fold.** Take the fitting expressions of the selected expression's
   complexity class (d1, d2 or union). If any of them adds different cells
   from the selected one to an object of an unlabelled input, the
   construction abstains. That input is the test input at the top level, and
   the held-out demonstration's input in a fold, segmented by native in the
   selected view.

   **Scope (refined during the first development check).** The check runs
   after native accepts the installed program, and considers only the
   objects the committed prediction grows. An object is grown when the
   prediction changes a cell of the selected operator's footprint.

   **Why the refinement.** Checking every object of the input flagged
   spurious ties on distractors the program never grows. It still reads
   inputs and CORA's own prediction only.

   **Reason.** Category U is unresolvable from the demonstrations by design.
   Under the frozen rule, the canonical-first operator would be committed by
   construction, failing P5 because of the protocol rather than the
   reasoner. The check reads inputs only.
3. **Common commit rule.** C and D, like E (section 3, step 6), commit an
   extension-certified output only where A has no certified output. No
   construction arm can displace a native certificate. Harms stay measurable
   as extension-certified wrong outputs.
4. **F3 replaced by F5 (the preregistered rule).**
   - **Calibration:** generation on calibration seeds 19000+, which are never
     final tasks; no arm was run on them.
   - **F3 rejection:** 86% of F3 samples (mirror, then tile) were rejected as
     baseline-explainable by `cora_reach` copy settings. That is above the
     50% rule.
   - **The rest:** F1 9%, F2 0%, F4 13%, F5 0%.
   - **Final split:** F1, F2, F4, F5.
5. **Engine assets.** Every arm's engine directory is prepared with the
   sealed v23 frozen library and learned verbs
   (`cora_pilot.native.prepare_object_dir`), as reach v1 did.
   - **Funnel disclosure:** the failure funnel's runs used fresh directories
     without these assets.
   - **Effect:** harness and funnel agreed 60 of 60 on object-layer
     certification on dev60, so its conclusions are unaffected.
6. **Label order (clarification).** SELECTION_ONLY is tested within the
   "fewer than 3 counted gains" branch: at least 3 extension-certified
   correct gains through an AVAILABLE operator. In the original order it was
   unreachable.
7. **Novelty class AVAILABLE_NATIVE added.** A native growth mode explains
   every instance. This is reachable only for C's instances; E's instances
   are `pattern` fallbacks by definition.
8. **f_B.** Provisionally 3.0 for development. The frozen value is the median
   over development G tasks of E's CPU divided by A's CPU, written into the
   parameter file before the freeze.

The parameter file is updated to match: final families F1, F2, F4, F5, the
tie rule, and f_B provisional.
9. **Identifiability of growth samples (generator side).** A G sample is
   rejected as `not_identifiable` unless one condition holds. In the simplest
   complexity class that fits the true training instances, every fitting
   expression must predict the truth's added cells on every true test
   object.

   **Found by:** the first development check. An obstacle-stopping ray
   whose demonstrations never hit an obstacle is indistinguishable from a
   border ray. Such a task is a U control, not a G task.

   **Scope:** the rule uses the ground truth, so it lives only in the
   generator. It applies identically to development and final families,
   fixed before the freeze. Category U remains deliberately unidentifiable.
10. **Generator v2: distractors are per task (development evidence,
    2026-10-14).**

    **The fault.** In development split v1 (sha 4af56bb2), a non-growing
    distractor appeared in only some demonstrations. Native's own LOO then
    failed in every family, N0 included (A certified 0 of 27). A fold
    without a distractor learns "every object grows", so the selector cannot
    be rebuilt from such subsets. That is a corpus artifact, not a property
    of growth.

    **The fix.** Generator v2 decides distractor presence once per task:
    every demonstration has one, or none does.

    **Check.** On development split v2 (sha d5bab8e4), A certifies all 3 N0
    tasks, all correct.

    **Scope.** The final split uses generator v2 and remains sealed.

## Amendment 2: PROPOSED (2026-10-14). Not in force; it needs the user's decision before the freeze

**Evidence.** Development only (dev split v2; `records/CORA_FHR_DEV_RESULTS_20261014.md`). No final-split
task has been generated or run.

**A. Fold verification: single-level outer adaptive LOO.**
- **Procedure:**
  1. Native's full acceptance gate stays on the top-level program.
  2. In fold i, demonstration i is removed before any extraction, diagnosis or construction.
  3. The operator is rebuilt from the remaining demonstrations.
  4. A program is fitted from those demonstrations alone (native's train-perfect program, `OBJECT_GATE_OFF`
     inside the fold only).
  5. The program is executed on the omitted input and must agree exactly with its output.
  6. No parent-fold program, operator, proposal, hint or label is reused.
  7. Fold programs are labelled fold-fit, never certified.
  8. The rule applies to every construction arm.
- **Implementation:** `CORA_FHR_FOLD_GATE=ungated`, with its invariant tested in `tests/test_fhr.py`.
- **Evidence:** in v1, folds failed on the nested gate; that was the corpus artifact. In v2, the nested gate
  never failed a fold. The refold what-if result is in `outputs/cora_fhr/eval_v2_refold.out`.

**B. The fold-level tie check is removed; the top-level tie check is kept.**
- **Evidence:** in v2 this was the only remaining fold blocker (9 tie abstentions).
- **Effect without it:** E 4, C 3 and D 1 NEW_COMPOSITION correct certifications, and 0 wrong in any arm.
- **Protection kept:** the top-level check still protects underdetermined (U) tasks.

**C. Shuffled control D.**
- Donors come from a different family: a fixed cyclic derangement over families.
- D's evidence shrinks per fold like E's: in fold i, the donor's evidence is re-extracted without the donor's
  demonstration i.
- **Evidence:** dev_D3_00's same-family donor gave D a certificate.

**D. Control C' becomes the primary H3 comparison.** It has the same native correspondences and extraction
compute as E, without the failure filter. P3 is restated as: E's counted gains exceed C''s.

**E. H3 needs mixed-coverage families.** C4's G-rejection makes every native growth correspondence a
memorization, so E equals C' by construction (10 of 10 D1 and D3 tasks).

A test of H3 needs families where native explains part of the growth and memorizes the rest, with the
memorized part needing a new composition. The failure trace then localizes what is missing.

**Without E, H3 is untestable, and a final run can test H1 (capability growth over A and B) only.**

**Matched search, measured.** B at f_B = 1.33 certified 0 of 15 development G tasks (0.99 CPU-h).
