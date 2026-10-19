# Reasoning v2: the first two slices of a typed scene transformation (engineering, 2026-10-19)

**Tier: REAL DEVELOPMENT on exposed tasks, plus synthetic unit tests.** Researcher-designed language expansion, not
grammar induction. Nothing here is certified, and nothing is part of any Kaggle entry.

## Why these slices

The base engineering run (`eval_{standin58,dev60}_eng.json`) gave the diagnosis distribution, from training pairs
only:

| corpus | additive, no single expression fits | needs a typed transformation (several actions, or recolour/delete only) |
|---|---|---|
| 58 pool | 49 (46 → abstain, 3 → guarded geometry) | 0 (the pool is growth-shaped by selection) |
| 60 dev | 26 (23 → abstain, 3 → guarded geometry) | 32 (25 several actions + 7 recolour/delete only) |

A typed scene transformation separates object selection, spatial transformation, colour assignment and grid
composition. Two slices were built, one limitation at a time.

## Slice 1: selection (`cora_revision_v2/selection.py`, commit 3e5f1d4)

- **What it adds:** a feature guard chooses which objects a geometry acts on. Unselected objects add nothing, the
  null else.
  - Guards are feature tests (feature == value, or in a value set) on native's views and features: size, colours,
    height, width, number of colours.
  - The guard is required to be true on every object whose additions lie inside the change, and false on every object
    whose additions would overreach.
- **New probe:** for an additive GEOMETRY_GAP, the per-demonstration probe now asks whether some single expression
  fits each demonstration alone on any **subset** of its objects. This separates "selection is missing" from "the
  geometry or the representation is outside the class".
- **Unit test (synthetic):** only colour-1 objects grow. The selection family recovers the rule and predicts the test.
  - In the same test, a base-family hypothesis also fits the demonstrations and predicts differently.
  - **The union of families can create disagreement.** A revision applied everywhere can therefore cost a unique
    answer. This is the reason to apply it where the diagnosis asks, which is Phase 2b's D-versus-C comparison.
- **Engineering run:** `outputs/cora_revision_v2/eng_sel_run.sh` adds grow + select on every task, i.e. the blind arm.
  It is RUNNING; results go in section 4.

## Slice 2: two-stage transformation (`cora_revision_v2/tst.py`)

- **Stage 1, in place:**
  - Each object is KEPT, DELETED or RECOLOURED as a whole, by one of:
    - a table from one feature, or from a pair of features (cf. native's two-literal selectors);
    - an ordered decision list of up to 2 (feature == value → action) rules plus a **default** action.
  - With a decision list, a value no rule names takes the default, so an unseen colour does not block a prediction.
    This is the same limitation the 00dbd492 fold exposed: a table cannot extrapolate to an unseen key.
- **Stage 2, spatial:** v2's growth hypotheses, fitted to the stage-1 result. On a demonstration that result is fixed
  by its output, so stage 2 is fitted once.
- **Unit test (synthetic):** "colour 3 → delete; largest → recolour 1; otherwise keep", with a test colour never seen
  in training. The decision lists predict it correctly; the tables abstain.
- **Engineering probe** on the 32 dev60 tasks the diagnosis routed to this family (blind predictions, then scoring):
  - stage 1 explains the in-place changes on 10;
  - on all 10, the remaining additions fit no single growth expression;
  - 1 task has complete hypotheses but none is defined on its test input;
  - **0 predictions, 0 correct.**
  - On the other 22 tasks, objects change only in part, which whole-object actions cannot express.

## Findings

1. Neither slice adds a certified answer. Selection adds 2 in-sample exploratory answers, one of them second-attempt only and none new to the merged two-attempt count; the two-stage slice adds 0.
2. The binding limitation remains expressivity:
   - partial-object changes;
   - additions that no single growth expression reproduces.
   The diagnosis now names which one applies, from the demonstrations.
3. The union effect (finding of slice 1) is a concrete, testable reason why diagnosis-driven revision could matter:
   applying a richer family where it is not needed adds alternatives that can turn a unique answer into a tie.

## 4. Selection run results (grow + select on every task: the blind arm; in-sample, exposed)

- **Run:** `eng_sel_run.sh` (commit 3e5f1d4).
  - rc 0 for both corpora, coverage 58/58 and 60/60;
  - no error or CPU-limit rows, no answer fields in any row, and each evaluation written after its final row.
- **Hashes:** rows fd4656ac and b3e243a7; eval 4957a301 and c44ef4b2; two-attempt replay c04368bf.
- **Cost:** mean CPU per task doubled (pool 19.9 → 39.8 s; dev 11.9 → 27.0 s). Maximum 178 s.

| | base (grow) | grow + select everywhere |
|---|---|---|
| certified | 0 | 0 |
| pool: exploratory correct / wrong | 3 / 1 | 4 / 0 |
| dev: exploratory correct / wrong | 1 / 0 | 2 / 0 |
| abstained (no attempt) | 54 + 59 | 54 + 58 |
| lost (correct before, not after) | — | 0 |

**Changed tasks:**
- **2546ccf6:** the wrong exploratory answer became correct, but only as the second attempt. The two leading
  predictions have equal support, so complexity breaks the tie. This gain is fragile.
- **kcc459b523a80 (dev):** none → exploratory correct, first attempt. The hypothesis is a selection one: objects of
  colour 2 get an 8-neighbour ring in a constant colour. Native's harness already solves this task.
- **22eb0ac0:** the **union effect** on a real task. A unique prediction (FOLD_FRAGILITY) became a disagreement
  (MANY_CONSISTENT_DISAGREE: 552 vs 4 supporting hypotheses). The answer is still correct first.
- **Two-attempt replay:** unchanged (pool 7 → 8 or 9, dev 12 → 12, 0 lost).

Selection adds in-sample candidate answers and doubles cost. It has not produced a certified answer, and has not added
a merged two-attempt gain. These are exposed tasks, so this is not evidence of generalization.
