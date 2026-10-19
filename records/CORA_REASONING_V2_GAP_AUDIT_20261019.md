# CORA reasoning v2: Phase 0 gap audit (2026-10-19; DEVELOPMENT; read-only over recorded artifacts)

**Directive:** "CORA | Learning when a hypothesis is not enough" (2026-10-19), Phase 0.
**Scripts:** `cora_revision_v2/gap_audit.py` and `cora_fhr/oracle_expressibility.py`.

## 1. What the forensic counts do and do not establish

**Code logic, reproduced:**
- `_fits(pairs, view, cap)` enumerates all 37,750 single **unguarded** G-grow expressions (depth 1, depth 2,
  same-source union) in canonical order.
- It applies each expression uniformly to every object of one native segmentation view and requires the
  union of added **positions** to equal each pair's changed cells.
- The cap (default 3) limits only how many fits are *listed*; existence is decided exhaustively.
- The original colour step tested only the first fit per view. The 2026-10-19 audit
  (`oracle_colour_audit_standin58.json`) tests every fit.

| claim | status |
|---|---|
| 50 of 58: no single unguarded expression fits the positions in any of 7 views | established, **for that class only** |
| of the 8 position-expressible: 5 have no fit with one colour per object | established (exhaustive over single expressions) |
| 3 pass the necessary checks | established (one also needs a colour-choice rule) |
| "the tasks need fundamentally new semantics" or "56 of 58 are beyond the grammar" | **not established** |

**Untested:**
- guarded scene-level programs;
- compositions beyond depth 2;
- multiple operations;
- other representations;
- exact colour generation.

**The raw results are unchanged;** the wording was corrected in the ledger, README, paper and drafts.

## 2. Transformation types (`outputs/cora_revision_v2/gap_audit_20261019.json`)

**Observable, from training pairs only, all 240 stand-in tasks:**

| type | tasks |
|---|---|
| grid resize | 71 |
| additions only, single colour | **31 (13%)** |
| additions only, multi-colour | 40 |
| additions + deletions | 30 |
| additions + recolour | 22 |
| recolour only | 22 |
| additions + deletions + recolour | 11 |
| deletions + recolour | 10 |
| deletions only | 3 |

**Forensic, the 58 pool with the test answer:** 35 multi-colour additions, 22 single-colour additions, and
1 addition + recolour.

**Reading:**
- G-grow models single-colour cell additions only, which are 13% of these tasks.
- The pool was selected as growth-shaped, but most of it adds several colours.
- **The growth-only hypothesis class is the wrong class for most ARC transformations.** This finding is
  observable without answers.

## 3. Native CORA's executable vocabulary (inventory; v2 must reuse, not duplicate)

`geocat_arc/object_reasoning/`. The per-object actions are:

| family | actions |
|---|---|
| keep and copy | KEEP, COPY, COPY_PART, SYNTH_COPY |
| move and reshape | TRANSLATE, MOVE_TO, MOVE_UNTIL_ADJACENT, ROTATE, REFLECT, SCALE, CROP_TO, EXTRACT_PART |
| colour and remove | RECOLOR, DELETE, PAINT |
| combine and grow | CONNECT, COMPOSITE, GROW |

GROW has about 20 modes (ray, ray_deflect, halo, frame_minority, fill_interior, fill_holes,
symmetry_complete, mirror_edge, cross_center, cavity_leak, toward, perpendicular, periodic_self, pattern, …).
Native also has colour features (unique, majority, color_swap, histograms) and pixel rules
(neighbor_pattern, neighbor_count).

**Native's own loop already runs several diagnostic probes:**
- 7 segmentation views;
- forced-composition re-search (phase B);
- forced-relational re-search (phase C);
- re-induced leave-one-out;
- an uncertified partial in attempt 2.

## 4. Native candidate coverage on the 60 dev tasks (recorded funnel, frozen assets; evaluator-only where marked)

| stage | tasks |
|---|---|
| candidates generated | 56 |
| a candidate fits **every** training pair | 34 |
| a **correct** candidate exists in native's pool (evaluator-only) | **8** |
| certified correct | 6 |
| correct candidate rejected by native's leave-one-out | 2 |

**Reading:**
- On **22** tasks no hypothesis fits the training pairs (NO_CONSISTENT_HYPOTHESIS).
- On **26** tasks hypotheses fit but none is correct (memorization).
- Only 8 have a correct hypothesis at all.

So a better *selector* over native's pool can gain at most 2 of 60 here. Both of those candidates failed
native's re-induced fold test, so neither could pass a strict fold-local GO gate. **The binding constraint
is candidate coverage**: the correct hypothesis is absent from native's space within budget on ≥ 48 of 60
tasks. Selection and diagnosis are not the bottleneck.

## 5. Observable signals: symptom → competing causes → allowed probe → safe action → falsification

| symptom (observable at inference) | competing causes | discriminating probe (training pairs only) | safe action | falsified if |
|---|---|---|---|---|
| no candidate fits the training pairs | language gap; representation gap; budget | more budget, then other views, then composition; each is a bounded probe | abstain, or a researcher-declared extension under its own verification | a probe produces a training fit (the cause was budget, view or composition) |
| fits exist but use constant parameters copied from the demonstrations | memorization; underdetermined evidence | re-induced leave-one-out; the relational re-search | do not certify; diverse two attempts only if lawful | a relational fit appears and passes the folds |
| several fits disagree on the test | genuinely ambiguous evidence | compare the predictions of the version set | abstain, or use both attempts on the two best-supported distinct predictions | — |
| the fit changes or fails when a demonstration is withheld | fold fragility | re-induce per fold | do not certify | it is stable in every fold |
| a candidate exists but the engine rejects it | dispatch, routing or colour assignment | inspect the gate stage; never weaken it | record it; repair only in a new version | an engine-side fix makes it pass all checks |
| deadline or cap hit; native exception | budget; software defect | rerun the task at its declared budget once | report separately (BUDGET_LIMIT, SOFTWARE_ERROR) | — |

**Banned from the solver, because they need a hidden answer:**
- correctness of any candidate;
- forensic expressibility classes;
- funnel categories;
- the oracle colour audit.

**Do not conclude "missing grammar" from NO_PROPOSAL.** It is a fact about the evidence extractor, not about
the language.

## 6. Consequences for Phases 1 and 2 (decision)

- **A selection or diagnosis layer over native's existing candidates** has a measured ceiling of +2 of 60,
  and both gains are fold-fragile. As the smallest Phase-1 loop it is **predicted to fail the GO gate**, so
  building it first would spend the pilot on a known ceiling.
- **The directive's priority, action D (separate geometry from colour), targets the measured coverage
  gap:**
  - multi-colour additions are 40 of 240 stand-in tasks and 35 of the 58 pool;
  - native's GROW applies one colour per action.
  It is a researcher-designed language expansion, so it is labelled that way, not as grammar induction.
- **A GO-gate-valid test needs a fresh, predeclared, non-autopsy real cohort of growth-type tasks.** The
  permitted pools used so far (dev60 and the stand-in tasks) are exhausted for that class: every
  growth-shaped stand-in task is in the forensic pool or already native-certified. Choosing other ARC-AGI-2
  training tasks risks E_transfer or HOLDOUT membership, which I may not inspect. **The user must designate
  the cohort.**

## 7. Phase 1 built: v2 scene reasoner, with geometry and colour separated (researcher-designed language expansion)

**Module and tests.** `cora_revision_v2/scene_reasoner.py`; `tests/test_fhr.py::test_v2_scene_reasoner_geometry_colour_and_ambiguity`.
All 18 tests pass.

**What it does:**
- **Hypothesis:** (one of native's 7 views, one G-grow geometry, one of 9 colour policies). The policies are
  CONST, the object's majority or minority colour, ORIGIN (the colour of the source cell, tracked through
  every transform), NEAREST, and a learned table from size, colour set, h or w to colour.
- **Search:** it keeps the full **version space** of hypotheses reproducing every training output exactly as
  full grids.
- **Decisions:** it abstains when hypotheses disagree on the test, offering the two best-supported distinct
  predictions as attempts. It re-runs the whole search in every omitted-demonstration fold, and certifies
  only a unique, fold-robust prediction.
- **Inputs:** training pairs and test inputs only.

**Smoke test** (8 in-sample pool tasks, selected by the forensic analysis; ENGINEERING, not the GO test;
`outputs/cora_revision_v2/smoke_8_20261019.json`):

| task | diagnosis | unique test prediction (evaluator) | native |
|---|---|---|---|
| 00dbd492 | FOLD_FRAGILITY (1 of 4 folds: the held-out size is absent from the table) | **correct**: `hull[self]`, coloured by a size-to-colour table | fails (object branch, search, whole harness) → **new, uncertified** |
| 22eb0ac0 | FOLD_FRAGILITY (2 of 3 folds tie) | correct: `hull[edge:N]`, object colour | the whole harness already solves it |
| 3aa6fb7a | FOLD_FRAGILITY (2 demonstrations, so both folds tie) | correct: `reflect(H)[self]`, constant colour | the object branch already certifies it |
| 070dd51e, 17b80ad2, 29c11459, 2e65ae53, 3bd67248 | NO_CONSISTENT_HYPOTHESIS: COLOUR_POLICY_GAP | — | — |

0 wrong predictions offered.

**Reading:**
- Separating geometry from colour makes CORA's prediction correct on 3 of 8 in-sample cases, 1 of them new.
- Its strict fold-local check certifies **none**, because with one demonstration removed the evidence
  becomes ambiguous. The check is not relaxed.
- That leaves two open questions:
  - **science:** whether certified solves appear on a fresh cohort;
  - **competition:** whether uncertified unique predictions may lawfully fill attempt slots, as native's
    harness already does with its partials. That needs the user's authorization for any submission.

## 8. Phase 2 status: the cohort needs the user's designation

The GO gate needs a fresh, predeclared, non-autopsy cohort of real tasks. There is none left in the
permitted pools for this transformation class (section 6). The pilot is frozen-ready (arms A–F as in the
directive) but **not run**.
