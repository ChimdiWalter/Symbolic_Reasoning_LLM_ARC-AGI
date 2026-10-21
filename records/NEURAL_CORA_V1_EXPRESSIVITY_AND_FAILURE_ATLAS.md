# Neural-CORA v1 expressivity and failure atlas (20 October 2026)

**The question.** Is the binding constraint the *order* of search (which neural ranking could fix), or the *language*
(which no ranking can fix)?

**The answer:**
- On CORA's synthetic held-out families it is the **order**: the language covers 394 of 395 tasks.
- On real ARC development tasks it is the **language**: the v1 typed language fits **1 of 60**.

## 1. What `ncv1-g0` can express, by construction

| transformation type | v1 status |
|---|---|
| deletion | yes: delete, or keep-only with the default delete |
| recolouring | yes: one target colour per selected object |
| moving | yes: translate (48 vectors) and slide (4 directions) |
| addition | partial: fill_line only (rays and lines through objects). No copy, extension or pattern fill |
| copying | **no.** Native has `copy`, but the v1 IR does not expose it |
| part-wise transformations | **no.** Objects are atomic; native's `extract_part` is not exposed |
| object-context guards | partial: colour, size, size rank, touches border, is a line, is a rectangle, has a hole, unique colour or size. **No relational guards** (adjacent to, inside, aligned with); native's `relation_exists` is not exposed |
| multicolour outputs per object | **no** |
| ordering and composition | at most 2 first-match rules, plus a default |
| dimensional changes | **no:** every output keeps the input's shape (no crop, scale or tile) |
| relationships between objects | **no** (no correspondence or connect) |

The native interpreter can execute much more (copy, scale, rotate, move_until_adjacent, crop_to, connect, grow,
extract_part). The **v1 IR deliberately exposes a small subset**, for a clean first learning test.

## 2. Synthetic held-out families: the language is not the bottleneck

Candidate coverage at the largest budget run, primary set (`records/NEURAL_CORA_V1_PILOT_REPORT.md`):

| family | n | C+H@3000 covers | L1@3000 covers |
|---|---|---|---|
| delete the largest | 44 | 44 | 43 |
| delete-then-translate | 60 | 60 | 40 |
| line by size | 51 | 51 | 51 |
| line, default delete | 60 | 60 | 47 |
| recolour-then-line | 60 | 60 | 25 |
| slide by colour | 60 | 59 | 60 |
| slide-then-recolour | 60 | 60 | 26 |
| **all** | 395 | **394** | 292 |

**Failure classes on this data** (the directive's six):
1. **The candidate exists and the search missed it.** This is dominant for the learned guides: L1@3000 found no fitting
   program on 102 tasks that C+H solves. Better ordering helps here. C+H already orders well.
2. **Expressible, but proposal, selection or verification fails.** This is rare: ≤ 5 wrong first attempts per arm.
3. **Inadequate representation.** Not observed. The generator's objects never touch, so all views agree.
4. **Not expressible.** At most 1 task (C+H@3000 missed 1).
5. **Underdetermined.** AMBIGUOUS_PREDICTIONS: 27 tasks under C+H@3000, 33 under L1@3000.
6. **Software or resource failure.** None: TIMEOUT_OR_ERROR was 0 in every arm.

## 3. Real ARC development tasks: the language is the bottleneck

`scripts/neural_cora_v1_atlas.py`, output `outputs/neural_cora_v1/atlas/dev60_atlas.json`.

**The cohort (dev60):**
- 60 public ARC-AGI-2 *training* tasks, already exposed in development (claim ledger rows 1–5 and 11);
- selected earlier by a fixed hash order and a same-shape scope: at least 3 demonstrations, every demonstration keeps
  its shape and changes at least one cell;
- 0 of the 60 change size;
- grid sides from 3 to 30.

**How it was measured:**
- The solve stage read demonstrations only.
- It ran C+H, the strongest v1 order, for 3000 candidates.
- The score stage alone read the training solutions.

This is an **expressivity measurement on exposed tasks, not a score**.

| measure | dev60 |
|---|---|
| some program fits every demonstration | **1 of 60** |
| the correct output is among the consistent predictions | 1 of 60 |
| pass@2 | 1 of 60 |
| fits but is wrong | 0 |

**By observed change kind** (from the demonstrations; a task can have several kinds):

| kind | tasks | fits |
|---|---|---|
| adds cells | 38 | 0 |
| object count changes | 48 | 0 |
| removes cells | 14 | 0 |
| recolours cells | 30 | 1 |

**Context on the same 60 tasks** (native CORA's richer languages, claim ledger):
- the native object branch accepted 6 correct answers (L2);
- the whole native harness got 12 of 60 over two attempts (L4).

So `ncv1-g0` is far narrower than native CORA, and both are far below what a competitive solver needs.

**Caveats:**
- "No fit within 3000 C+H-ordered candidates" is **not proof** that the bounded language cannot express a task.
  Two-rule programs alone number in the tens of millions.
- The kinds are coarse statistics. They do not separate a missing operation from a missing representation (part or
  relation).

## 4. What follows

1. **A better neural ranker over `ncv1-g0` cannot approach 27.64%.** At most 1 of these 60 exposed same-shape tasks has
   any fitting program in the language.
2. **The dominant missing capabilities on real tasks:**
   - adding cells beyond rays (copy, extend, fill a region or pattern): 38/60;
   - changing the object count: 48/60;
   - and, by construction, relational guards, part-wise rules and size changes.
3. **The highest-value next experiment** is therefore the expressivity gate G2, not more search tuning (section 5).

## 5. Proposed next experiment (not run; needs the author's approval)

**`ncv1-g1`.** Expose native CORA's **existing**, already-implemented primitives in the typed IR:
- `copy` with vectors;
- `move_until_adjacent`;
- `connect`;
- `grow`;
- `crop_to` and `extract_part`;
- the `relation_exists` relational guards.

This is a **researcher-designed language extension of existing primitives, not automatic invention**. It changes
neither native nor any frozen language.

**The protocol to freeze:**
1. Measure compile coverage and correct-output coverage on dev60. It is exposed, so this is expressivity only.
2. Then measure them on a **fresh, predeclared eligible cohort**, chosen before testing by the existing cohort audit
   rule and kept away from every protected split.
3. G2 requires coverage of independently held-out transformation families, without task-specific operators.
4. Only if G2 passes would a learned guide be retrained over `ncv1-g1`. It would have pairing-aware heads, because
   section 7(d) of the pilot report shows that factorized bags cannot express selector–action pairing.
