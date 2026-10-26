# Why CORA-only scores 0 of 120 on the public ARC-AGI-2 evaluation set, and what to build

**PROGRESS (25 Oct 2026): complete.** All sections come from `scripts/eval120_capability_gaps.py` (three passes:
`main`, `--extra`, `--groups`; output `outputs/eval120_capability_gaps/gaps.json`).

**Label: exposed public evaluation, development evidence.** These 120 puzzles are used here for diagnosis only.
They cannot serve as a confirmation cohort for any capability recommended below: every capability must be confirmed
on data not used to choose it (a fresh synthetic set and the hidden Kaggle test). Only general-purpose capabilities
are recommended; none is a transformation taken from an evaluation solution. The public evaluation set is public; nothing here is a
competition score. Expected outputs are read only by this analysis, never by a solver. Data: the competition archive
`arc-prize-2026-arc-agi-2` (solutions sha 84be4f4f, the same file the development runs were scored against). Runs: the
private Kaggle development runs of 21 to 22 October (run A: the submission configuration, original CORA then
version 3; run B: C1, version 3 with more search, and C2, version 4).

## 1. Output shapes

| relation (all pairs with a known output) | puzzles |
|---|---|
| same shape as the input | 81 |
| size change, no simple relation | 37 |
| constant output shape | 2 |
| exact crop, integer scaling or tiling | 0 |

49 puzzles have more than one test input; a puzzle counts only if every test output is right.

Versions 3 and 4 cannot construct anything for the 39 size-changing puzzles: version 3's scene analysis returns
nothing when a demonstration changes shape (`cora_neural_v2g3/scene.py`, lines 99 to 100), and version 4's inversion
and construction return no programs for such puzzles (`cora_neural_v2g4/invert.py`, `construct.py`). Only version 2's
native program classes and native object programs with the `crop` or `constant_shape` render modes
(`cora_neural_v2/rast.py`, lines 138 to 141) can produce another size. A third of the set is outside the newest
construction by design.

## 2. What CORA produced

- Run A: 101 puzzles have only fallback attempts (the test input copied); the original engine claimed a fit on 25
  puzzles and offered a partial answer on 12 (33 puzzles in all, every one same-shape); version 3 found no fitting
  program on any of the 113 puzzles it searched. Run B: version 3 with more search found none on 119; version 4 found
  one (97d7923e), and it was wrong.
- The original engine's 71 attempts: all have the right size; 38 have at least 90% of cells right, 33 between 50 and
  90%, none below 50%; **45 of the 71 are the test input returned unchanged** (on 15 puzzles every attempt is), and
  none copies a training output. High cell accuracy here is the input's own cells: in same-shape puzzles a median of
  10.4% of cells change. The fits are near-identity edits whose rule picks nothing, or the wrong things, on the test
  input: they reproduce the demonstrations without capturing the transformation.

## 3. What changes in the 81 same-shape puzzles (existing real-puzzle scripts, read-only)

| measure | puzzles |
|---|---|
| at least half of the changed cells on whole objects that are recoloured, moved or deleted (best view) | 33 |
| at least 90% of the changed cells on such whole objects | 16 |
| at least half of the changed cells are additions (background turned colour) | 15 |
| at least half on objects whose change matches nothing simple | 31 |
| at least half of the changed objects change only in part | 31 |
| an output object spans several input objects (grouping) | 55 |
| dominant kind of addition: copies of an object's pattern / rays / fills / other | 16 / 11 / 7 / 3 |
| a single kind of addition covers at least half of the changed cells: rays / copies / fills / other | 5 / 3 / 2 / 1 |

Median share of changed cells explained by whole-object changes in the best view: 0.19.

## 4. Simple whole-grid rules (oracle-style checks)

No puzzle's demonstrations are all reproduced by a global colour map, a rotation or reflection, integer scaling,
tiling by rotated or reflected copies, or a crop to one object chosen by size or box size (7 views, region or object
only); in no size-changing puzzle is every output even the box crop of some input object. The evaluation set is built
against such rules.

The original engine's attempts got a median of 0.0 of the cells that had to change right: its fits reproduce the
demonstrations without capturing the transformation.

## 5. Whole-object puzzles: selector gap, action gap or composition gap

On the 33 same-shape puzzles where at least half of the changed cells sit on whole objects, version 4's own machinery
was run read-only per change group (the objects with one fate), in the view that explains the most:

| finding | puzzles |
|---|---|
| some change group has no exact selector (version 4's induction: comparisons, and-pairs, relational `exists`; natively confirmed) | 15 |
| every group has a selector, but some group has no action that passes the local check | 11 |
| every group has a rule that passes the local check | 9 |
| of those 9, no object changes in any other way | 3 |

On 8 of the 9 fully ruled puzzles, version 4's inversion composes no program that fits: the cells left over are part
changes or added cells that the part, region and ray kinds do not cover. On the ninth (97d7923e), 40 of 44 inversion
programs fit, version 4 found 98 fitting programs on Kaggle, and every attempt was wrong: the demonstrations do not
pin the rule down. More search does not help either: version 3 with 10,000 candidates and up to 300 s per puzzle
found no fit on any of the 119 puzzles it searched.

## 6. Ranked capabilities (general-purpose; L1 = an engineering extension of existing mechanisms; L2 = a new reasoning mechanism)

Most of what is missing is L1. Estimates are descriptive counts on this development set, not predicted gains.

| rank | capability | level | how it extends CORA's own mechanisms | puzzles it bears on (how counted) |
|---|---|---|---|---|
| 1 | a wider cover vocabulary for version 4: copies of an object's pattern at anchor objects; rays that stop, turn or recolour at obstacles; line segments between objects; fills of regions defined by relations | L1 | new rule shapes inside version 4's construction: members and don't-care objects from evidence, selectors induced and confirmed by native execution, programs as covers of the changed cells, after a whole-object inversion program | the 9 fully ruled puzzles, whose leftover cells are exactly what covers must explain; copy-dominant additions 16 (2 with copies at least 90% of the changed cells), ray-dominant 11 (5 at least 50%) |
| 2 | output-canvas induction for size-changing outputs | L1 | a typed stage that proposes the output frame (an object's or a panel's box, a constant shape, a scale) using native render modes, confirmed on the demonstrations' output shapes; versions 3 and 4 then construct on the canvas from execution differences | 39 puzzles now outside versions 3 and 4 by design (the simple crop, scale and tile forms explain none, so canvas plus construction is needed) |
| 3 | grouping: composite objects as a view | L1 | a view built from evidence (input objects whose union becomes one output object, by contact, containment or colour), on which the existing selectors and actions run unchanged | 55 of 81 same-shape puzzles have an output object spanning several input objects; an enabler, rarely sufficient alone |
| 4 | richer selector features: counts, odd-one-out by shape or colour, relations to the nearest object of a kind | L1 | new native features or relations, so selector semantics stay native and confirmation stays by execution | the 15 puzzles where some change group has no exact selector |
| 5 | richer action parameters: recolour by relation or count, move into contact, resize | L1 | new parameter families for version 3's construction and version 4's inversion, inferred from observed deltas | the 11 puzzles with selectors but no passing action |
| 6 | a non-vacuity check: reject a fit whose prediction leaves a test input unchanged when every demonstration changes its input | L1 | one more check in the existing selection | 45 of 71 original-engine attempts and 15 puzzles; improves precision and honesty, not coverage (no score gain expected) |

**Ablation for every capability** (mechanism level, matched compute): (a) version 4 as frozen; (b) version 4 plus the
capability; (c) version 4 with more search, its candidate budget raised until its native executions and CPU match
(b); (d) version 3 as a reference. Data: a fresh synthetic set with families that need the capability, families that
do not (false-fit control) and ambiguous traps; then the hidden Kaggle test, one submission per configuration. The
real public-training cohort used so far is exhausted (the published-order pool is used up), so a new real cohort
needs a new, pre-registered selection rule. A capability counts as an improvement only if (b) beats both (a) and
(c) by a pre-registered margin with bounded losses.

## 7. The L2 alternative: is this a revision decision?

Mapped onto the revision categories, the failures look like this:
- *representation inadequate* (no exact selector for some change group, 15 of 33; output objects formed from several
  input objects, 55 of 81; output canvas unrepresented, 39 of 120);
- *operations insufficient* (selectors but no action, 11; leftover part or added cells, 8 of the 9 fully ruled);
- *operation exists but was not generated*: no case found;
- *budget insufficient*: no evidence (more search found nothing);
- *weak support*: 45 of 71 original-engine attempts fit by changing nothing;
- *ambiguous demonstrations*: 97d7923e (98 fits, all wrong).

So the failures do call for a decision between revising the representation, extending the operations and searching
more, and the data say "search more" is almost never right. A learned or diagnostic policy could make that decision
from execution differences. It would only pay off if the representation and operation spaces it chooses between
contain the needed change, which is what the L1 capabilities supply. The L2 mechanism is therefore testable only after
L1, on synthetic tasks with planted causes, against failure-blind and shuffled-diagnosis controls at matched compute.

## 8. Recommendation

Build rank 1 first, the wider version 4 cover vocabulary. It is the cheapest: new rule shapes inside existing
machinery, with no new stage. It acts exactly where construction already gets closest: puzzles whose whole-object
rules all exist but whose leftover cells are uncovered. Then rank 2, output-canvas induction, the largest blind spot
(a third of the set). Both are general-purpose L1 capabilities, and both are measured by the ablation above, never on
these 120 puzzles.
