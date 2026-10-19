# Visual-first review poster: layout and content (19 October 2026)

- **Files:** `poster_visual_final_review.tex`, `.pdf` and `.pptx` (editable).
- **Status:** REVIEW DRAFT for Toni, Chris and Pierce. Not for print until approved.
- **Unchanged:** the submitted poster `docs/summit_poster/poster.pdf`.
- **Size:** A0 portrait (84.1 × 118.9 cm). This is a review assumption: no organizer guide is on file.
- **Fonts:** body 30 pt; secondary 26 pt; diagrams 22–26 pt; text inside figures at least 20 pt at printed size.
- **Words:** about 405 of body prose, excluding the title, block titles, diagram labels and the footer.

## Reading order

**Title:** LEARNING WHAT TO CHANGE.
**Subtitle:** From Visual Reasoning to Scientific Hypothesis Revision.

**Banner (full width):**
- *Can a reasoner recognize when its explanation is inadequate, and determine what needs to change?*
- *Solving a problem is not the same as knowing why the solution works, or what to change when the available concepts
  and rules fall short. A question shaped in discussions with Toni Kazic.*
- *Aims, not yet all achieved:* find objects and relations → write executable hypotheses → notice inadequacy → choose a
  justified revision → test it independently → transfer the procedure.

### Column 1: why ARC is a useful test

1. **REAL grids, task 00dbd492.** Training example 1, training example 2, and the new input with a "?". Caption: *ARC
   tasks require inferring a transformation from a few examples and applying it to a new input.* Here, each frame's
   fill colour depends on its size.
2. **ILLUSTRATIVE panels: four reasons to revise.** The figure says on its face that it is not a CORA result.
   - **A Memorization:** a copied rule fits the example, then fails a new input.
   - **B Wrong objects:** one grid split two ways (2 or 3 objects).
   - **C Missing rule:** right objects, but "move, recolour" cannot draw a connecting line.
   - **D Not enough evidence:** two rules (size-2 bars red; top bars red) fit the example and disagree on a new input.

   Caption: these are different possible causes; telling them apart from the examples alone is the research problem.

### Column 2: CORA, what I built and tested

1. **One sentence:** *CORA is an executable ARC reasoning system used to investigate how models construct, test and
   revise hypotheses from sparse visual examples.*
2. **Pipeline (solid, implemented):** ARC examples → find objects and relations → construct executable rules → check the
   rules against the examples → predict a new grid.
3. **Fitting is not enough [DONE].** Big numbers: **6** answers accepted, all correct; **26** tasks where every rule
   that fit the examples failed the test. Dataset label: 60 exposed ARC-AGI-2 training tasks; CORA's object reasoner
   as submitted.
4. **A rule CORA built [DONE, NARROW].**
   - **Figure:** REAL grids, task ka95aa62f67d9; a training example with its target, and the new input with CORA's
     output (correct).
   - **Rule:** depending on an object's colour, extend a line toward one of two corners: **blue up-left, red
     down-right**.
   - **Caption:** automatically constructed conditional operation; rebuilt 3 of 3 times with one example held out.
   - **Caveat:** an exposed task chosen in development; a failure-blind constructor found the same rule, so diagnosis
     did not cause this gain.
5. **Did it generalize? [NEGATIVE].** Big number: **0 / 58** new verified solves from rule construction: separately
   selected, still exposed training tasks; every construction variant; no wrong answers; no advantage from the failure
   record.

### Column 3: learning what to revise, the next step

1. **The proposed loop.**
   - **Solid:** new problem → objects and parts → competing hypotheses → test against examples → *Is the explanation
     adequate?*
     - **Supported:** predict → independent evaluation.
     - **Inadequate or uncertain:** *diagnose why* (dashed), then one of three revisions:
       - wrong objects → revise objects (dashed);
       - missing rule → construct a rule (solid);
       - too little evidence → keep alternatives (solid).
     - A revision is followed by *test the revision: keep or roll back* (solid), then predict.
   - **Caption:** recognizing an inadequate explanation is partly built (CORA-v2); knowing which revision helps is not
     yet shown. CORA never sees the hidden answer.
2. **CORA-v2 [DEVELOPMENT].**
   - Compares alternative executable hypotheses and records why it is uncertain.
   - **Figure:** REAL task 00dbd492, the new input and v2's correct guess, labelled *CORRECT DEVELOPMENT PREDICTION —
     NOT CERTIFIED*. The size-32 (green) fill is supported by one example, so the check with that example hidden fails.
   - On 118 exposed development tasks: 4 correct and 1 wrong exploratory guesses; nothing certified.
3. **Inventing new operations [RUNNING].** Automatic rule-language extension, a separate CORA experiment: can a system
   build new reusable operations itself? 475 of 497 proposal units done (19 October); no verdict; not part of CORA-v2
   or any Kaggle entry.
4. **From ARC to science [FUTURE, NOT TESTED].**
   - Diagram: ARC grid reasoning (solid) → learning which part of a hypothesis to revise (dashed) → testing that
     revision process on scientific data (dashed).
   - Candidates: proteins, single-cell and omics data, plant phenotypes, and pathways suggested by maize lesion mimics
     checked with molecular or perturbation evidence.
   - What could transfer is the revision policy, not ARC operations.

### Bottom band (full width)

- **Bottom line:** *Building a rule is not the same as learning which revision improves an unseen prediction. That is
  what we are trying to test.*
- **Legend:** solid = implemented, tested; dashed = proposed, not yet validated; status tags [DONE] [NEGATIVE]
  [DEVELOPMENT] [RUNNING] [FUTURE, NOT TESTED].
- **Neural baseline box:** official public ARC-AGI-2 scores.
  - native CORA 0.00%;
  - CORA with rule construction 0.00%;
  - NVARC reproduction 27.64%, a third-party Qwen3-4B method, not CORA: a competitive baseline.

  CORA asks whether executable revision adds a separate capability.
- **Footer:**
  - related work: Popper, DreamCoder, LILO, Model Discovery Agent. The failure-to-revision idea is not new; the
    question is which component to revise, against matched controls;
  - pointer to the claim ledger;
  - AI-assistance disclosure;
  - authorship pending collaborator review.

## Not on the poster (in the explainer)

- the forensic 50/5/3 expressivity check and its restricted scope;
- the selection and two-stage engineering slices;
- the two-attempt replay;
- the cohort eligibility check;
- Phase 2a (running);
- Step B's protocol;
- the NVARC complementarity audit;
- full citations;
- reproduction commands.
