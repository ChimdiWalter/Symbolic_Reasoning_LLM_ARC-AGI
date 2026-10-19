# CORA reasoning v2, Phase 2: real-task experiment protocol (DESIGN FROZEN 2026-10-19; NOT AUTHORIZED; NOT RUN)

**Execution requires all of:**
1. The cohort cleared by the membership-only check in `records/CORA_REASONING_V2_COHORT_AUDIT_20261019.md` section 5.
2. The user's explicit authorization of that check and of this run.
3. The code commit recorded below as frozen.

Any change to the arms, endpoints or thresholds after authorization makes a new protocol version.

## Questions

- **Phase 2a:** does the hypothesis reasoner (v2) add correct predictions, certified or exploratory, on a cohort that
  played no part in developing it? Does it do so without wrong certificates?
- **Phase 2b:** does selecting a revision from the authentic diagnosis beat a failure-blind and a shuffled-diagnosis
  selection with the same revision menu and verifier?
  - It needs the revision executor (menu below), built and frozen on the engineering cohort first.
  - It is not run before the summit.

## Cohort

- The first 40 **clear** candidates, in the published order, from the 100 additions-only candidates.
- **Clear** means outside Step B's Lockbox, Promotion and E_transfer, and outside every arc2026 exclusion.
- Fallbacks if fewer are clear: down to 25, then extended in the same order (cohort audit section 5).
- These are reused public training tasks. Results are a **development evaluation**, not a blind prospective test.

## Arms (all blind: training pairs and test inputs only, under opaque keys)

| arm | phase | what runs |
|---|---|---|
| A | 2a | frozen native v23 object branch with the frozen library (cdacd018) and learned verbs (b1f07ba5); budget as in `cora_fhr/measure.py` (90 s) |
| B | 2a | native with matched extra search: budget × f_B, where f_B = (native mean CPU + v2 mean CPU) / native mean CPU, from the engineering run, capped at 3, and fixed before the run |
| V | 2a | v2 reason + diagnose + decide (`cora_revision_v2`), 600 s CPU per task |
| D | 2b | V, then the one revision its own diagnosis selects |
| C | 2b | V, then every revision in the menu in a fixed order (strong failure-blind) |
| Cm | 2b | as C, stopped when D's CPU for that task is spent (failure-blind at matched compute) |
| E | 2b | V, then the revision selected by another task's diagnosis (a fixed derangement in published order) |
| F | after all rows | **forensic, evaluator-only:** which revision or class could fit the pairs plus the true test output. An upper bound, never fed back |

**Revision menu (2b).** EXTEND_COLOUR_FEATURES, GUARDED_GEOMETRY, WIDEN_SEARCH (cap × 2) and TYPED_SCENE_TRANSFORM.
Each:
- is executed in the unchanged hypothesis machinery;
- is accepted only by the unchanged verifier: unique, rebuilt in every fold, no tie;
- is otherwise rolled back.

## Endpoints

Certified and exploratory results are reported separately and never pooled.

- **Primary (2a):**
  - **new certified-correct tasks:** V certified and correct, where neither A nor B certifies a correct answer;
  - **certified-wrong:** V certified but wrong.
- **Secondary (2a):**
  - **exploratory either-attempt correct:** the precision of the EXPLORATORY tier and of the DISCOURAGED tier,
    separately;
  - the diagnosis-label distribution.
- **Primary (2b):**
  - certified-correct, D vs E and D vs Cm: one-sided exact sign tests on discordant tasks, Holm-adjusted α = 0.05;
  - harm: certified-wrong, and lost answers (correct in V, missing in the revised arm).

## GO / NO-GO

**Phase 2a GO requires all of:**
1. Complete row coverage in A, B and V.
2. Blind-bundle hashes verified.
3. Zero certified-wrong in V.
4. At least 2 cohort tasks where V has a correct attempt, certified or exploratory, that A and B lack.

Consequences:
- **GO:** proceed to the Phase 2b build and freeze. The GO is **not** evidence about the diagnosis.
- **NO-GO:** reported as such. A certified-wrong answer is a safety failure and stops v2's integration.

**Phase 2b, judged separately:**
- **CAUSAL GO:** D > E and D > Cm, both significant after Holm, with zero certified-wrong and zero lost answers.
- **Otherwise:** "diagnosis-driven revision selection not shown to help".

## Limits and stop rules

- At most 2 workers at nice 10, with CPU-time caps per task and arm.
- At most 6 h wall clock in total. If coverage is incomplete at the cap, the run is reported with its coverage and
  counts as a NO-GO on coverage.
- No retuning on cohort outcomes. No rerun after scoring.
- The evaluator reads answers only after every arm's rows are committed.
- No Kaggle submission.
- No access to Step B outputs other than the authorized membership bit.
- No protected split (HOLDOUT, the sealed C4 final, the frozen 120 pilot, the ARC-1000 experiment).

## Frozen code (to be recorded at authorization)

- **Commit:** _____ (must equal the commit of the last engineering regression run; tests passing).
- **Phase 2a uses existing code only:** `cora_fhr/measure.py` arms A and B, with a cohort corpus added after
  authorization; `cora_revision_v2/run_v2.py` for V.
