# Why v2's 00dbd492 prediction is fold-fragile (engineering analysis, 2026-10-19)

**Scope.** 00dbd492 is an exposed ARC-AGI-2 training task: it is in standin58 and was examined in the forensic audit.
This is engineering on a development task, not evidence of generalization.

**Data used.** The reasoner side reads only the training pairs and test inputs. The test answer is used once, by the
evaluator, for the already-recorded correct/incorrect label (`outputs/cora_revision_v2/smoke_8_20261019.json`).

**Code.** `cora_revision_v2/scene_reasoner.py` (`_fold_detail`, `table_support`) and `cora_revision_v2/diagnosis.py`
(commit 4c4c30d).

## 1. Observations

- **Full version space:** 1,365 hypotheses, which give a single distinct test prediction, and it is correct.
  - They are 455 positional fits × 3 colour tables: size, height and width. On these square frames the three tables
    are interchangeable.
  - The simplest is `hull[self]` with TABLE:size = {16 → 8, 24 → 4, 32 → 3}: a hollow square's interior is filled with
    a colour set by its size.
- **Object sizes (frames; 1 is a centre dot):**

| | frame sizes |
|---|---|
| demo 0 | 32, 16 |
| demo 1 | 24 |
| demo 2 | 16, 24 |
| demo 3 | 16 |
| test | 16, 32, 24, 16 |

- **Leave-one-out, with the whole search rerun in each fold:**
  - **Fold 0 (demo 0 held out):** 1,365 hypotheses, every one undefined on demo 0. Outcome `UNPREDICTABLE`, cause
    `UNSEEN_TABLE_KEY`; missing keys: size 32 (h = w = 9).
  - **Folds 1–3:** a unique prediction, and it is correct.
- **Support of each table entry the test needs:** 16 → 3 demonstrations, 24 → 2, **32 → 1**.

## 2. Competing causes, the probe for each, and the result

| cause | bounded probe | result |
|---|---|---|
| genuine ambiguity | count distinct predictions in the full version space and in every fold | rejected: one distinct prediction wherever any is defined; no tie |
| incorrect representation | do positional fits exist in every fold, including fold 0? | rejected: geometry fits in every fold; only the colour lookup fails |
| verification or implementation defect | why is every fold-0 hypothesis undefined? | rejected: only demo 0 contains a size-32 frame, so the fold's table has no entry for it. This is the designed behaviour, and folds 1–3 succeed |
| inadequate feature induction (no rule that extrapolates) | is the colour a function of size the language could extrapolate (constant, ordinal, arithmetic)? | not supported: 8, 4, 3 for 16, 24, 32 follows no such pattern, and nothing in the demonstrations suggests one |
| **missing table entry (insufficient evidence)** | how many demonstrations support each entry the test needs? | **supported:** the size-32 entry rests on one demonstration, and the test needs it |

## 3. Diagnosis

- **What fails:** the fold fragility is **insufficient evidence**. The test needs a table entry that a single
  demonstration supports. Leave-one-out cannot verify such an entry: the fold that omits that demonstration has no such
  entry, so it abstains. It does not predict wrongly.
- **What does not fail:** this is not ambiguity, representation or a defect.
- **Verdict:** the prediction may well be right, and here it is, but these demonstrations cannot verify it.
  - Certification stays withheld. The verifier is unchanged.
  - The prediction is reported as **EXPLORATORY (uncertified)**.

## 4. Failure-blind comparison (same geometry and colour language)

- A failure-blind reasoner with the same version space and a simplicity order produces the **same** test prediction.
  It also fails the same fold, so it gets the same certification outcome and the same attempt.
- The diagnosis changes the explanation and the tier: EXPLORATORY rather than DISCOURAGED. It does not change the
  answer. **On this task the diagnosis adds no correct prediction.**

## 5. What changes, and what stays

- **Certification:** unchanged. A prediction is certified only if it is unique and rebuilt in every fold.
- **New: uncertified predictions are split into tiers by the type of fold failure:**
  - EXPLORATORY: single-demonstration support, or a tie the demonstrations cannot break;
  - DISCOURAGED: a fold rebuilt a different unique answer.
- Whether this tiering predicts correctness is measured in-sample in the engineering run (in progress). It must then
  be checked on a fresh cohort before any use.
- **Remaining uncertainty:**
  - The single demonstration could be coincidental.
  - Size, height and width tables are indistinguishable on these demonstrations. They agree on the test, so the choice
    is harmless here.
