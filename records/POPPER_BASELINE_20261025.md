# Popper baseline: inductive logic programming against CORA on recolour-or-delete puzzles (25 October 2026)

**Status.** This is a descriptive comparison. It is not a frozen study and nothing was pre-registered. The real puzzles
are exposed public training puzzles, so they count as development evidence only.

**Software.** Popper (Cropper and Morel, 2021; MIT licence), tag v4.4.0, with SWI-Prolog 10.0.0 and clingo 5.8.2. These
were installed in their own environment (`records/POPPER_BASELINE_ENVIRONMENT_20261025.md`).

**Code.** Encoder, runner, decoder and scorer: `baselines/popper/popper_baseline.py`.

## What was compared

Popper learns logic programs from background facts and from positive and negative examples. Here it learns the
predicate `new_color(Object, Colour)`, and only for puzzles where it can be stated exactly. These are puzzles whose
every example keeps its size and whose every change recolours or deletes a whole object.

**Objects.** CORA's own segmentation, view S1: cells of one colour that touch side by side.

**Facts about each object.** Each object gets the following facts:
- its colour, size, height and width;
- the native CORA flags: line, rectangle, has a hole;
- four more flags: single cell, touches the border, only object of its colour, largest, smallest;
- an explicit negation of every flag, because Popper's rules cannot negate on their own;
- the relations above, left of, adjacent and inside, with each other object of the same grid.

**Examples.**
- Every object whose colour changes is a positive example at its new colour.
- Every other colour of the puzzle is a negative example for that object.
- An object that keeps its colour is a negative example at every other colour.

**Prediction.** The learned program runs in SWI-Prolog on the test input's objects.
- An object with exactly one derived colour is painted that colour. Deletion is the background colour.
- Any other object is left as it is.
- Each puzzle gets one answer; the second attempt repeats the first.

**Limits.**
- 60 seconds of wall-clock time per puzzle.
- At most 2 Popper processes at once, at nice 10.

**Scoring.** The solving step never opened an expected output; only the separate scoring step read them.

**Two encodings.**
- *Primary:* the facts above.
- *Same-grid:* the primary facts plus `same_grid(A,B)`, meaning two different objects of one grid. This lets a rule
  name another object of the same picture, as in "recolour to the colour of the largest object". It was added
  **after** the primary scores were seen, so it is a post hoc sensitivity check.

**CORA columns.** These are read from CORA's recorded studies on the same puzzles:
- the real-puzzle check: `outputs/neural_cora_realarc_g2g3g4/score.json`;
- the version 2 study: `outputs/neural_cora_v2g2/synthetic_eval/score.json`;
- the version 3 study: `outputs/neural_cora_v2g3/synthetic_eval/score.json`.

"Solved" means an answer exactly right on every test input; CORA's figures allow its usual two attempts.

## How many puzzles can be encoded

| set | puzzles | encodable | why the rest cannot be encoded |
|---|---|---|---|
| real puzzles of the real-puzzle check | 34 | **5** | part of an object changes 18; background cells change 11 |
| generated puzzles, version 2 study | 200 | **80** (4 of 10 families) | output size differs 40; background cells change 45; part of an object changes 35 |
| generated puzzles, version 3 study | 296 | **196** (10 of 15 families) | background cells change 45; part of an object changes 55 |

Popper was run on all 5 encodable real puzzles. For the generated sets it was run on seeds 1 to 6 of every encodable
family: 24 puzzles from version 2 and 59 from version 3. One version 3 family has only 5 of those seeds.

Every real puzzle that any CORA version solved in the 34-puzzle check is one of these 5. That includes the original
CORA's 3 and the 3 each of versions 3 and 4.

## Results side by side

"Fits" means the program reproduces every example: Popper reported no missed positive and no covered negative.

| puzzles | n | Popper primary: fits / solved | Popper same-grid: fits / solved | CORA on the same puzzles (solved) |
|---|---|---|---|---|
| real, encodable | 5 | 4 / **1** | 3 / **1** | original **3**; v2 1; v3 **3**; v4 **3** |
| generated, version 2 sample | 24 | 22 / **9** | 23 / **18** | v1 8; v2 **15** |
| generated, version 3 sample | 59 | 59 / **25** | 57 / **26** | v2 32; v3 **54** |

No puzzle was solved by Popper and missed by CORA, except one version 2 family: `h_two_rule_features`, where Popper
solved 6 of 6 and versions 1 and 2 solved 2 of 6.

**Time per puzzle.**
- Popper's time is wall-clock. Popper is single-threaded, so its CPU time was about equal to its wall-clock time.
- CORA's times are CPU time from its own studies, which had their own candidate budgets.
- The budgets were not matched.

| puzzles | Popper median s (primary / same-grid) | runs that reached 60 s (primary / same-grid) | Popper CPU total s (primary / same-grid) | CORA median CPU s, same puzzles |
|---|---|---|---|---|
| real, encodable | 59.8 / 59.7 | 3 / 3 of 5 | 194 / 227 | original 23.9; v2 3.4; v3 8.6; v4 27.7 |
| version 2 sample | 32.8 / 0.8 | 10 / 10 of 24 | 792 / 650 | v1 2.6; v2 4.7 |
| version 3 sample | 0.7 / 0.9 | 11 / 11 of 59 | 1012 / 1004 | v2 4.5; v3 8.3 |

### Real puzzles

| puzzle | Popper primary | Popper same-grid | CORA original | v2 | v3 | v4 |
|---|---|---|---|---|---|---|
| ea32f347 | solved (smallest object to 2, largest to 1, the rest to 4) | solved | solved | solved | solved | solved |
| 9720b24f | fits, wrong on test (2 rules) | fits, wrong | solved | no | solved | solved |
| 6df30ad6 | fits, wrong on test (5 rules) | fits, wrong | solved | no | solved | solved |
| 85c4e7cd | fits, wrong on test (8 rules) | no fit in 60 s | no | no | no | no |
| e681b708 | no fit in 60 s | no fit in 60 s | no | no | no | no |

### Generated puzzles, solved of 6 per family

Version 2 study (CORA columns: version 1, version 2):

| family | Popper primary | Popper same-grid | CORA v1 | CORA v2 |
|---|---|---|---|---|
| h_rect_relational_recolour | 0 | 6 | 0 | 6 |
| h_two_rule_features | 6 | 6 | 2 | 2 |
| h_least_common_recolour | 1 | 1 | 0 | 1 |
| h_pixel_color_swap | 2 | 5 | 6 | 6 |

Version 3 study (CORA columns: version 2, version 3):

| family | Popper primary | Popper same-grid | CORA v2 | CORA v3 |
|---|---|---|---|---|
| comp_unique_delete_nonrect_recolour | 5 | 5 | 0 | 5 |
| comp_three_rules | 3 | 5 | 0 | 6 |
| comp_largest_delete_line_recolour | 5 | 5 | 0 | 6 |
| bind_largest_colour | 0 | 2 | 6 | 6 |
| trap_ring_most_common | 0 | 1 | 0 | 2 |
| trap_border_relational (5 puzzles) | 0 | 0 | 5 | 5 |
| amb_line_or_rect | 5 | 1 | 6 | 6 |
| amb_hole_or_size8 | 1 | 1 | 3 | 6 |
| ctrl_border_recolour | 6 | 6 | 6 | 6 |
| ctrl_unique_size_delete | 0 | 0 | 6 | 6 |

## What the comparison shows

1. **Real puzzles.** In the one class Popper can state, CORA solved 3 of 5 (the original, version 3 and version 4).
   Popper solved 1 of 5, ea32f347, with a three-rule program that is correct.
   - On two of the other real puzzles, Popper's programs fit the examples but were wrong on the test. On the remaining
     two, Popper found no fitting program in 60 seconds.
   - Its programs that fit but were wrong were lists of special cases: 2 to 8 rules over sizes, heights and relations.
2. **Popper fails in two situations.**
   - *Its facts cannot express the rule.* Examples are "the object of unique size" and "the most or least common
     colour". These are aggregate features that CORA has and this encoding does not. Popper then runs to the time
     limit, or fits the examples with special cases that do not carry to the test.
   - *The simplest reading is wrong.* The trap and ambiguous families were built so that the simplest reading of the
     examples is wrong. Popper returns the smallest program that fits, which is often exactly that reading.
3. **When the rule can be stated, Popper finds it fast.**
   - It found the two-rule `h_two_rule_features` rule in about a second (6 of 6, against 2 of 6 for CORA versions 1
     and 2).
   - With same_grid it found every relational rectangle rule (6 of 6, as version 2 did).
   - On the version 2 sample it then solved 18 of 24, against version 2's 15.
   - Version 3, which builds rules from execution differences, stays well ahead on its own puzzles: 54 of 59 against 26.
4. **The encoding matters as much as the learner.**
   - One added relation, same_grid, doubled Popper's version 2 score from 9 to 18.
   - On version 3 it changed the score by one puzzle in total. It gained 2 each on bind_largest_colour and
     comp_three_rules and 1 on trap_ring_most_common. It lost 4 on amb_line_or_rect, where richer facts gave more
     readings that fit the examples.
   - A Popper score here describes Popper together with one encoding.

## Caveats

- **The encoding choices favour some rules.**
  - The facts are CORA's own segmentation (view S1 only) and CORA's native object flags. I added numbers and negated
    flags, and, after seeing the results, same_grid.
  - There are no aggregate features (colour frequency, unique size, size rank), no arithmetic, and no objects from
    other views.
  - A puzzle whose objects are whole only under another view is counted as not encodable.
  - Different facts would change both the encodable count and the solved count.
- **Popper is not designed for grids.** It is a general system for learning logic programs. A grid-specific encoding,
  more facts or a different bias might do better. This is one reasonable encoding, not Popper's best possible result.
- **The generated puzzles favour CORA.**
  - They are written in CORA's own rule language over CORA's features.
  - The trap and ambiguous families were designed against the simplest reading. That design targets CORA's evidence
    selection, and it also catches Popper's preference for the smallest program.
- **One answer against two.** Popper gives one answer per puzzle; CORA gives two. On the ambiguous families, two
  attempts can cover both readings.
- **Budgets are not matched.**
  - Popper had 60 seconds of wall-clock time on a loaded machine: load about 28 on 24 cores, at nice 10.
  - CORA's results come from its own studies, with candidate budgets and CPU caps.
  - Popper needs no candidate budget, but it is stopped by time.
- **Small samples.** There are 5 real puzzles, and 24 and 59 generated puzzles (seeds 1 to 6). Real puzzles are
  development evidence only. No statistical claim is made.
- **Order of the work.** The same-grid variant was chosen after the primary scores were seen. The primary encoding was
  fixed before any score was seen, though not pre-registered.

## Files and how to rerun

- Code: `baselines/popper/popper_baseline.py`; progress: `baselines/popper/PROGRESS.md`.
- Score summary, with Popper's program for every puzzle: `baselines/popper/score_20261025.json`.
- Untracked outputs in `outputs/popper_baseline/`:
  - `rows_<set>[_samegrid].jsonl`, with predictions;
  - `tasks/`, Popper's input files for each puzzle;
  - `score.json`;
  - the run logs.
- Rerun (about 35 minutes for each encoding):
  - `nice -n 10 python baselines/popper/popper_baseline.py run real|synv2|synv3 [--same-grid]`
  - then `python baselines/popper/popper_baseline.py score`
