# Summit poster: content proposal for review (DRAFT, 2026-10-18; not a layout)

**For:** Toni, Chris and Pierce to review before any change to scope, credits or authorship.

**Rules for this draft:**
- The current single-author poster (`docs/summit_poster/`) stays unchanged until approval.
- Every number traces to `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md`.
- Evidence tiers: **DONE**, **NEGATIVE**, **PROPOSED**.

**Proposed title:** Learning What to Change: From Visual Reasoning to Scientific Hypothesis Revision

**Scope line:** completed ARC-AGI-2 development studies, a bounded executable-construction prototype, and
a proposed test of whether a revision procedure transfers to scientific prediction.

**Authorship:** to be confirmed from actual contributions. No co-author is added without approval. The
separate SAC student submission is not affected.

## Column 1. The question (Toni's)

- **Question:** can a system induce useful representations and executable rules from a few observations,
  find which part of its reasoning failed, choose a revision, and transfer that revision procedure to a
  domain with different semantics?
- **Ambiguity example** (one ARC task, already in our records): several programs fit every demonstration
  but disagree on the test. Fitting is not explaining.
- **Three different things can be wrong:**
  - the **representation** (which objects exist);
  - the **rule** (what happens to them);
  - the **evidence** (the demonstrations do not decide).
  Each needs a different revision, and the wrong one can damage what already worked.
- **Prior art, stated plainly:**
  - learning from failures: Popper (Cropper and Morel);
  - library learning: DreamCoder (Ellis et al.), LILO (Grand et al.);
  - model inadequacy and experiment design: Model Discovery Agent (Murphy).
  - Our question is narrower: choosing **which component** to revise, measured against matched controls.

## Column 2. What CORA has measured (DONE and NEGATIVE)

- **DONE: the real-task diagnosis.** CORA's object branch was run on 60 exposed ARC-AGI-2 training tasks,
  with the frozen assets as submitted.
  - Its check accepted 6 answers, all correct.
  - 26 tasks had only demonstration-fitting programs that were all wrong (memorization).
  - A correct candidate existed on 8 tasks.
  - With the check off, the first-ranked outputs were 8 correct and 25 wrong.
  - This concerns one branch, not a reliable solver.
- **DONE: one synthetic executable repair.** CORA constructed a missing **single-step** operator (a ring
  around the minority-colour cell) and installed it reversibly in the unchanged engine. It rebuilt the
  operator in 3 of 3 leave-one-out folds and predicted the held-out query correctly; removing the operator
  removed the gain.
  - **Figure:** the actual logged witness (existing `fig_fhr_witness_dev_D3_04.png`).
- **DONE: one real-task witness, narrow.** On one ARC-AGI-2 training task that frozen CORA and extra search
  both fail, CORA built a rule with an applicability guard: "colour-{1} objects shoot a ray north-west, others
  south-east". It rebuilt the rule in 3 of 3 folds and answered correctly.
  - The failure autopsy found this case.
  - A failure-blind constructor with the same evidence found the same rule.
  - The rule is not part of the Kaggle entry.
  - **Figure:** a replay frame from `docs/summit_demo_20261023/replay_real.py`.
- **NEGATIVE, shown with the same prominence:**
  - a failure-blind constructor with the same information matched it;
  - the mixed-coverage pilot failed its frozen stop rule;
  - on 60 real tasks the construction added no certificate (matched search added one);
  - of 62 eligible tasks in the Kaggle rehearsal, 20 left no failure evidence at all, 39 had evidence that no
    operator fitted, 2 hit a compute cap, and 1 proposal failed its folds.
  - a hand-designed controller that picks a revision type from the solver's trace missed the only task that
    extra search fixed (6 vs 7);
  - in a frozen 10-case guard pilot the failure record gave 2 correct answers against 1 (plus 1 abstention)
    for the blind arm; one discordant pair is not evidence.
- **Benchmark box (attribution exact):**
  - native CORA, official public score 0.00;
  - an independent reproduction of the published NVARC Qwen3-4B pipeline, 27.64 (not CORA);
  - the CORA-FHR research entry was submitted 18 October; its score is shown only when it returns, beside
    its local zero-commit rehearsal.

## Column 3. What comes next (PROPOSED)

- **A component-revision architecture.** Observable failure trace → a choice among search, representation
  revision, program revision with an applicability guard, or abstain → execution in the unchanged engine →
  fold-local independent check → commit or roll back. The proposer can never modify its checker.
- **The next falsifiable pilot.** Does authentic failure information choose better revisions than a strong
  failure-blind policy with the same object information, size and colour features, and the same compute?
  There is a fixed stop rule, and a negative result is reported as such.
- **The biological question (proposed; a synthetic mock-up only, labelled SYNTHETIC).** Can the same
  revision policy decide, for molecular measurements, whether to revise the representation, revise the
  model, or ask for an experiment? The contract with Pierce and Toni is in `BIO_PROBLEM_CONTRACT_DRAFT.md`.
  No biological result is claimed.

## Reader takeaway

Fitting observations, diagnosing failure, constructing a correction and transferring a reasoning procedure
are different achievements. CORA makes several of them executable and testable. The experiments so far show
where learning from failure has **not** yet been demonstrated.
