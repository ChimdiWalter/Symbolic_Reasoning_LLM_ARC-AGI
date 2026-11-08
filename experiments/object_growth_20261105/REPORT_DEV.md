# Object-level construction step: development report

Status: final, 6 Nov 2026 00:30Z; wording amended 01:35Z by `CONTRACT_AMENDMENT_1.md` (numbers unchanged). Code
frozen in `FREEZE.json` (version 1); the amendment is pinned in `FREEZE_V2.json`. Development data only: the source halves of
ConceptARC, Mini-ARC and 1D-ARC (`experiments/natural_growth_20261105/split/SPLIT.json`) and a seeded sample of the
project's ARC training split. No held half, no held test output and no ARC-AGI-2 evaluation task was opened.
Code: `objgrow/` (digests in `FREEZE.json`); records: `runs/`; log: `PROGRESS.md`.

## 1. What was built

The natural-task growth test found that every one of the 425 natural failures of G0 (A2's full arc-dsl grammar
under the base search: 150,000 primitive executions, 20 CPU-s, two attempts) yields typed holes, but none of the
211 whole-grid structures maps any hole. This study adds a hole-directed, object-level structure space to the same
growth machinery; the controller's holes, A2's search and the construction test's gates are reused unchanged.

A **hole** is a set of input-to-target grid pairs (the demonstrations, or the demonstrations composed with one
invertible grid operation on the input or on the output side; three holes per failure). For each hole and each of
12 **views** (one-colour or any-colour objects under 4- or 8-connectivity, one object per colour, single cells;
each with the background taken as the most common colour or fixed to colour 0):

1. **Object correspondence.** Every input grid is segmented into objects. An input object is *changed* when one of
   its cells differs in the target; a target cell that differs and belongs to no input object is *appeared*. For
   every changed object the edits that reproduce its fate are bound from the pair (their parameters are read off
   the target); for an unchanged object next to appeared cells, the growth edits that write those cells. A hole has
   a *full* correspondence when every changed object is explained and every appeared cell is written.
2. **Per-object edits** (typed arc-dsl expressions over an object): delete; recolour to a constant, to an attribute
   (the colour of the adjacent, enclosing, enclosed, nearest, largest or smallest object; the size; the object
   count) or through a colour table keyed by an attribute; shift by a vector; move until blocked or to the border;
   gravitate to the nearest object; mirror, rotate or scale in place; rays in 12 directions to the border, until
   blocked or until next to another object; connect to the nearest object; fill enclosed cells; fill the bounding
   box; hollow; outline; shifted and mirrored copies.
3. **Selection predicates:** 24 boolean features (largest, smallest, single cell, has a hole, touches the border,
   unique size, shape or colour, most or least common colour, topmost and the other extremes, encloses, enclosed,
   fills its box, surrounded by one colour, odd size, ...), value atoms (colour, size, height, width, holes, size
   rank, size at least k), relations (adjacent to, encloses, enclosed by a colour), their negations, and
   conjunctions of two atoms.
4. **Compose and verify.** A candidate operation is one or two first-match rules (predicate, edit) painted over
   the input (moves run one object at a time, nearest to the target wall first), or a whole-output form (crop to
   the selected object, a token of its colour, a count strip, symmetry completion). A candidate is kept only when
   it maps every hole pair exactly. It is **multi-pair** when its edit is proposed independently by at least two
   pairs; whole-output forms are labelled multi-pair unconditionally. This is a proposal criterion: no candidate is
   rebuilt with a pair withheld (`CONTRACT_AMENDMENT_1.md`, section 1). Candidates are ordered by the number of
   verified candidates that agree with them on the test inputs, then by simplicity; at most 8 per hole; only
   multi-pair candidates reach the gates.
5. **Gates** (the existing protocol): **novelty** (a G0 program of cost at most 7, found by A2's search on 12 probe
   grids plus the unit's demonstration inputs, reproduces the candidate: rejected as a search shortcut); **retry**
   of the unit's task with the operation added as one production of cost 3 and charge 1 (at most 3 retries per
   unit); **regression** on the benchmark's G0-solved source tasks (rolled back when a fit is lost or when G0's old
   first prediction is in neither of the two new attempts, so a changed first attempt passes when the second
   equals it; amendment section 2); **validation** on at most 30 other unsolved source tasks of the benchmark (one new fit: promoted
   into the registry; none: quarantined, task-local). A unit stops at its first promoted operation. The grown
   grammar is G0 plus the registry after a combined regression check.
6. **Budget.** Every segmentation, edit and operation application is counted; every gate result carries the
   process CPU of its first computation and is charged once per unit that used it, as in the existing code. In
   the search an object operation is charged one execution per input it runs on; its internal work is counted
   separately and shows in CPU, with no hard cap per call (amendment section 3).

The step is also packaged as an arm for the separate held-data study (`objgrow/arm.py`): reuse-only answers (G0
plus a registry, the base search) and construction answers (base search, then the holes, the constructor and the
retry of at most 3 multi-pair candidates), each with its process CPU.

## 2. Development funnel (source halves)

Records: `runs/v2/` (the final constructor; private Kaggle kernels, CPU only, internet off, four shards each; ConceptARC
1,772 s wall, Mini-ARC 142 s, 1D-ARC 3,350 s), scored on Athe (`runs/v2/FUNNEL.json`, `runs/v2/<bench>/reuse.json`).
`runs/v1/` holds the same pipeline with the constructor of 22:43Z (2, 0 and 21 operations promoted). A *unit* is a
source failure on which the growth controller decided to construct; it has three typed holes.

| stage | ConceptARC | Mini-ARC | 1D-ARC | all |
|---|---:|---:|---:|---:|
| construction units | 74 | 68 | 283 | 425 |
| holes with a full object correspondence (of 3 per unit) | 127 of 222 | 121 of 204 | 674 of 849 | 922 of 1,275 |
| units with a full object correspondence | 50 | 45 | 283 | 378 |
| units with an exactly verified candidate | 28 | 9 | 277 | 314 |
| units with a multi-pair candidate (gated) | 24 | 9 | 273 | 306 |
| candidates gated; rejected as search shortcuts | 136; 0 | 54; 0 | 835; 0 | 1,025; 0 |
| candidates retried; fitting the motivating task (units) | 65; 59 (23) | 24; 23 (9) | 445; 424 (266) | 534; 506 (298) |
| units promoted; quarantined candidates; rolled back | 2; 57; 0 | 0; 23; 0 | 179; 245; 0 | 181; 325; 0 |
| units recovered (a fitting candidate predicts every test output); through a promoted operation | 15; 1 | 6; 0 | 246; 172 | 267; 173 |
| registry (distinct promoted operations after the combined regression check) | 2 | 0 | 19 | 21 |
| construction CPU-s; gate CPU-s of distinct results | 159; 5,917 | 98; 1,064 | 536; 8,777 | 793; 15,758 |
| reuse: source tasks fit, G0 then grown grammar (of 80, 74, 306) | 1 then 4 | 6 then 6 | 0 then 217 | 7 then 227 |
| reuse: test outputs correct, G0 then grown grammar | 1 then 8 of 240 | 6 then 6 of 74 | 0 then 217 of 306 | 7 then 231 of 620 |
| reuse: newly correct tasks; of them outside the motivating and validating tasks; lost fits | 2; 0; 0 | 0; 0; 0 | 217; 35; 0 | 219; 35; 0 |

The regression set (the source tasks G0 solves at the base budget) has 1, 6 and 0 tasks, so the 1D-ARC regression
check is vacuous; no recorded regression decision depended on the second-attempt rule (amendment section 2).

By family. ConceptARC (units; recovered): SameDifferent 5; 3, TopBottom2D 4; 2 (both promotions: crop to the topmost
object, delete every object but the bottommost), CompleteShape 4; 2, ExtendToBoundary 5; 2, MoveToBoundary 5; 2,
AboveBelow 4; 1, Count 5; 1, FilledNotFilled 4; 1, HorizontalVertical 5; 1; none in Center, CleanUp, Copy,
ExtractObjects, InsideOutside (2 fit, both mispredict), Order and TopBottom3D. 1D-ARC (units; recovered; promoted
units): fill 24; 24; 24, hollow 24; 24; 8, move_1p 25; 22; 25, move_2p 25; 22; 19, move_2p_dp 25; 25; 25, move_3p
25; 21; 23, move_dp 25; 25; 25, scale_dp 25; 21; 14, recolor_cmp 18; 18; 10, recolor_cnt 20; 20; 1, recolor_oe 21;
13; 0, mirror 23; 9; 3, padded_fill 3; 2; 2. The 19 registry operations are moves by 1, 2 or 3 cells and moves until
blocked, connect to the nearest object, rays until blocked, hollow, recolour the largest object (five colours), a
shape-keyed colour table, and the surrounded-cell deletion.

## 3. ARC training tasks (development reading)

`runs/arctrain/` (80 tasks of the project's S_train split in sha256 order; constructor of 22:43Z; 271 CPU-s): G0
fits 4; of the 76 failures, 29 have a full object correspondence, 4 a multi-pair candidate; all 4 fit on retry
and predict the test output exactly: 48d8fb45 (crop the object adjacent to colour 5, a task the design record names
as selecting by a feature the language lacked), 56ff96f3 (fill each colour's bounding box), d2abd087 (recolour by
size), ddf7fa4f (recolour the unique shape with the nearest other colour). About 5% of G0's failures on training
tasks are recovered by construction on the task itself; no reuse was measured there.

## 4. Honest expectation for the held halves and for the ARC-AGI-2 evaluation set

Two arms are possible with this code (`objgrow/arm.py`): **reuse only** (G0 plus the frozen registry, the base
search) and **task-local construction** (the base search, then the holes, the constructor and at most three
retries on the task itself).

- **Reuse only, held halves.** The expectation per family is the out-of-sample newly-correct rate on the source half
  (tasks that were neither the motivating nor the validating task of a promoted operation) times the held family
  size. 1D-ARC: hollow 24 of 24, move_2p 25 of 25, move_3p 25 of 25, scale_dp 26 of 26, mirror 2.3 of 23,
  recolor_cnt 1.1 of 20, recolor_cmp 0 of 20 (its promoted operations are colour-specific), padded_fill 0 of 4:
  103 of 309 held tasks measured; the four families fill, move_1p, move_2p_dp and move_dp (99 held tasks) have no
  out-of-sample source task because one operation fits every source task of the family, so their held gain is
  unmeasured and plausibly near complete. A reuse-only arm on 1D-ARC is therefore expected to add about 100 to 200
  correct tasks of 309, against 0 for G0 (and 23 at four times the budget). ConceptARC: 0 measured (the two
  TopBottom2D operations fit no other source task); about 0 to 2 of 80. Mini-ARC: 0 of 75 (empty registry). The
  matched static control receives the same CPU, which is large here (per held task about 77 CPU-s for ConceptARC,
  31 for 1D-ARC, 15 for Mini-ARC); deeper search already solves some 1D-ARC families, so the paired comparison on
  1D-ARC is open, and growth cannot win on Mini-ARC.
- **Task-local construction, held halves.** The source-half recovery rates are the best guide: 1D-ARC 246 of 283
  failures, ConceptARC 15 of 74, Mini-ARC 6 of 68; over-fitting exists (of the candidates that fit, 10 of 23 units
  on ConceptARC and 3 of 9 on Mini-ARC mispredicted the test), so about 20% of ConceptARC and 9% of Mini-ARC
  failures and most 1D-ARC failures are the expectation.
- **ARC-AGI-2 public evaluation set** (never opened here; previously used in development of the scored entries):
  about zero for reuse only, because the 21 registry operations are shaped by 1D rows and two ConceptARC concepts;
  0 to 3 of 120 tasks for task-local construction, given 5% of G0's failures on easier training tasks and the
  evaluation set's multi-rule tasks. A zero is to be reported as a zero.
- **Limits.** Candidates are single or two-rule object edits; tasks needing per-object parameters that vary by a
  rule not in the feature set (Center, Order, TopBottom3D, most of Mini-ARC) are not reached. The novelty gate at
  cost 7 rejected nothing (0 of 1,025), so every gated candidate was new to G0 at that cost. The held-data run is the
  separate pre-registered study; this code is frozen for it. An operation's output colours are not range-checked
  (an authored colour 11 is accepted; none was emitted), and the execution budget counts macro calls, not their
  internal work (`CONTRACT_AMENDMENT_1.md`, section 3).
