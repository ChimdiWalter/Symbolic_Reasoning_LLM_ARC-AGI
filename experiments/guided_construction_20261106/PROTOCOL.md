# Guided-construction test: protocol

Written 6 Nov 2026 before any outcome of this test existed. At commit time this study had run nothing, and study B
(`experiments/natural_growth_b_20261105/`, the one-shot test on the same held halves) had opened no held output.
This study never reads study B's held outputs or results. Design source: section 2.7 of
`records/NOV6_TAILORED_RESEARCH_PROGRAM.md` (with its sections 2.10 and 2.11); where this file is more specific, this
file governs. Code lives in `gcon/`; the log is `PROGRESS.md`.

## 1. Question and claim

The frozen object-level step (`experiments/object_growth_20261105/`, freeze version 2, `FREEZE_V2.json` sha256
`f6218c3eaca22e808870e8542eba48b82e74f0563f37cdbedc05097b1cefbd9e`, with `CONTRACT_AMENDMENT_1.md`; package
`objgrow/`) searches views and object edits in a fixed hand-set order and stops a hole's search after 20,000
operations. **Question:** does a small model, trained only on the step's own successes and failed attempts on the
source halves, let the step find the same exact programs with fewer operations, so that at a fixed budget that binds
it answers more held tasks correctly?

**Claim tested:** efficiency at an equal number of operations, never new reach. The guide only changes the order in
which the step's existing searches are tried. Nothing is removed from the search, every candidate is still verified
exactly on every pair, and at 20,000 operations both orders give identical answers wherever the cap never binds.

## 2. Terms

- **Hole:** a set of input-to-target grid pairs built from a task's demonstrations (the demonstrations themselves, or
  the demonstrations composed with one invertible grid operation on the input or on the output side). The growth
  controller gives three holes per task, in its rank order.
- **View:** one of the step's 12 ways of cutting a grid into objects (one-colour or any-colour objects under 4- or
  8-connectivity, one object per colour, single cells; each with the background taken as the most common colour or
  fixed to colour 0). The hand-set view order is the frozen one: m4, m8, x8, x4, col, cell, m4z, m8z, x8z, x4z, colz,
  cellz.
- **Operation:** one application of a candidate object-level program to one grid (the counter `COUNTS["op"]` in
  `objgrow/edits.py`). The frozen step allows 20,000 per hole. The **budget** of an arm is this cap, per hole.
- **Block:** one independent piece of the step's search within one hole and one view. There are three kinds:
  - **single-rule block S(v, e):** for view v and one edit e of the view's common-edit list, the frozen loop over the
    covering predicates (single atoms, then conjunctions) that stops at the first predicate that is admissible and
    verifies exactly;
  - **two-rule block T(v):** the frozen search for two first-match rules; as in the frozen step it runs only when every
    single-rule block of v ran to its end and none verified;
  - **whole-output block W(v):** the frozen crop, token and count forms of view v.
  The frozen symmetry-completion forms are tried once per hole after all blocks, without a cap, as in the frozen step.
- **Hand-set order:** views in the frozen order; within a view, S(v, e) in the frozen edit order (the step's
  `edit_sort_key`, colour tables last), then T(v), then W(v). This is exactly the frozen step's sequence.
- **Exact program, success:** a candidate that maps every pair of the hole to its target exactly and is multi-pair
  (its edit is proposed by at least two pairs, or it is a whole-output form; `CONTRACT_AMENDMENT_1.md` section 1).
  Only such candidates can be retried, so a block **succeeds** when it yields one. A **failed attempt** is a block
  that yields none, with the operations it spent.
- **Unit:** a source task on which the controller decided to construct (425 units: 74 ConceptARC, 68 Mini-ARC, 283
  1D-ARC; 1,275 holes; records `objgrow` `runs/v2`).
- **Answer of an arm on a task:** as in `objgrow.arm.construction_answers(task, ops=())`: G0's base search (A2's
  arc-dsl grammar, 150,000 executions, 20 CPU-s, two attempts); on a failure with at least two demonstrations, the
  three holes, the constructor under the arm's order and budget, and the retry of the first at most 3 multi-pair
  candidates (holes in rank order, within a hole by agreement group then simplicity, repeats dropped); the first
  retry that fits gives the two attempts. A task is **fitted** when the base search or a retry finds a program
  consistent with every demonstration. Fitting uses demonstrations only.
- **Correct (pass at 2):** study A's scorer (`ngrow/score.py`): a test output is correct when either attempt equals
  it; a task's score is its number of correct test outputs (ConceptARC tasks have three, the others one).

## 3. Data, custody and exposure

- **Training and development:** source halves only (`experiments/natural_growth_20261105/split/SPLIT.json`, read
  only): the 425 units and their 1,275 holes from the controller's stored records, re-run by this study's code with
  per-block logging. No test output of any half enters features, labels, the budget rule or the stop rule.
- **Held data:** the 464 held tasks of the same split (309 1D-ARC, 80 ConceptARC, 75 Mini-ARC), and the 120 tasks of
  the ARC-AGI-2 public evaluation. The held run sees demonstrations and test inputs only. Test outputs are opened
  once, by this study's scorer, after the GO and under an exclusive marker.
- **Order of events:** this protocol is committed before study B's scorer opens any held output. Code, weights,
  configuration and the budget are frozen (`FREEZE.json`) and reviewed before the GO.
- **Reused read-only:** the frozen object-level step (`objgrow`), study A's data, scorer and statistics (`ngrow.data`,
  `ngrow.score`, `ngrow.analysis`), and study B's seed-independent G0 builder and donor rule (`ngb.ops.G0Builder`,
  `ngb.object_arm.donor_of`). Every search of this test, the reference included, uses that builder, and every process
  runs with PYTHONHASHSEED=0.
- **Exposure statement (in every table):** the held halves were held out from this study's development, but every
  task of the three benchmarks was run and scored once on 2 Nov by the submitted entries and once by the companion's
  constructor; held halves share families with source halves; the public evaluation is exposed (it was examined in
  development of earlier entries); no pretrained model is used, so there is no checkpoint contamination.

## 4. The test's constructor

`gcon/engine.py` re-implements only the frozen per-view loop of `objgrow/construct.py` (`hole_candidates` and
`paint_candidates`) as blocks, and calls the frozen helpers for everything else (pair analysis, predicates,
admissibility, colour tables, the whole-output and symmetry forms, operations). The cap checks sit where the frozen
code has them: an operation is applied only while the hole's counter is at most the budget.

**Executing an order under a budget.** All 12 views' pair analyses are computed first (the frozen step computes all
of them too, so no work is added; they apply no operation). Blocks then run in the order's sequence until the
counter exceeds the budget. A two-rule block is placed after the last single-rule block of its view and runs only
when all of them ran and none verified. Symmetry forms follow, uncapped, as in the frozen step.

**Canonical re-sort (the tie-break risk).** The frozen step keeps the first copy of each repeated candidate and then
sorts stably by (agreement group, simplicity), so a new order would change tie-breaks. Before that step, the test's
code sorts the found candidates by their place in the hand-set sequence (frozen view index, then the block's place in
the view, then the candidate's place within the block). The frozen grouping, sorting and cut at 8 candidates then
run unchanged. Hence, whenever no hole's cap binds, every order yields the same candidate list as the hand-set order.

**Fallback.** If the block engine cannot be made to pass the equivalence checks of section 8 by 14:30Z, the guide
reorders views only (through the frozen `hole_candidates` views argument, with the same re-sort and invariants).

**Development trace and simulation.** On the source halves every block of every hole is run once to its end or to
20,001 operations (no block can use more under any budget of this test), with its operations, success and found
candidates logged. Results of any order at any budget up to 20,000 are then computed from this trace without
re-running the search. The held run executes every arm directly. Simulation must equal direct execution: this is
checked on a sample of source holes for several orders and budgets (section 8). If the full trace would exceed the
development budget, blocks that the hand-set order does not reach within 20,000 operations are run to 5,001
operations; results above 5,000 operations are then partial and descriptive only (the rules use at most 5,000).

## 5. The guide and its comparators

**Features** (computed after pair analysis and before any verification; no test input, no test output, no benchmark
name):
- hole: number of pairs, mean input area, all pairs same shape, hole rank (0 to 2), hole has a grid operation;
- view: the view (12 indicators); changed objects, appeared cells, objects per pair, required objects (log counts);
  share of changed objects explained; share of appeared cells unexplained; full and partial correspondence; growth
  case (cells appear, nothing changes); number of common edits, covering predicates and covering conjunctions (log);
- block: kind (S, T, W); edit type (19 frozen edit names and the colour table); the edit's parameter size; share of
  pairs proposing the edit; the edit's place in the view's list; a bound on the block's operations (S: covering
  predicates and conjunctions times pairs; T: the frozen two-rule edit pairs times predicates; W: predicates times
  pairs); for W whether some object matches each target's shape and whether the targets are one-colour.

**Labels** (from the source trace only): success (0 or 1) and the block's operations, log(1 + operations).

**The guide:** a network with two hidden layers of 32 units (ReLU), features standardised on the training data, and
two outputs: the chance of success (logistic, cross-entropy loss) and log(1 + operations) (squared loss); the loss
is their sum. Plain NumPy, weights initialised from `numpy.random.default_rng(20261106)`, Adam with learning rate
0.003, mini-batches of 512 in a seeded order, 40 passes, weight decay 0.0001. No tuning: these settings are fixed
here.

**Order rule (every learned or counted arm):** blocks are sorted by score = p x exp(-c), the predicted chance of
success per predicted operation (c is the predicted log(1 + operations)), largest first; ties keep the hand-set
order. A two-rule block's score is capped at the lowest score of its view's single-rule blocks.

**Comparators (same blocks, same budget, same verification):**
- **logistic regression (the linear model):** the same two outputs with no hidden layer (logistic for success,
  linear for operations), same features, training and order rule;
- **frequency order:** a fixed table over (block kind, view, edit type) from the source trace, chance of success
  (successes + 1) / (trials + 2) and mean log(1 + operations); unseen keys take the pooled values; same order rule;
- **hand rule:** views ordered by full correspondence first, then the share of changed objects explained, then the
  hand-set view order; inside a view, the hand-set order;
- **donor guidance:** the guide's scores computed on the hole of the same rank of a donor task (study B's rule
  `donor_of`: the next task in sha256("obj-donor:" + id) order of another family; any other task on Mini-ARC) and
  applied to this hole's blocks by key (block kind, view, edit type; else the donor's best score for the kind and
  view; else last, in hand-set order). A donor without holes gives the hand-set order;
- **leave-one-benchmark-out guide:** the guide trained on the other two benchmarks' source records only, applied to
  the third benchmark.

**Training sets.** For the held run: the guide, the linear model and the frequency table use all 1,275 source holes;
the three leave-one-benchmark-out guides use the other benchmarks' holes. For development: **cross-fitting** with 5
folds by task hash within each benchmark (units sorted by sha256("guided-fold:" + id), fold = rank mod 5); each
fold's units are ordered by models trained on the other four folds.

## 6. Frozen rules on the source halves

**Budget rule.** Using the hand-set order, let F(b) be the number of the 425 source units fitted at budget b. The
**test budget** B is the largest b in {100, 200, 500, 1,000, 2,000, 5,000} with F(b) <= 0.75 x F(20,000). If no b
qualifies (even 100 keeps more than 75%), the budget does not bind and the test stops (reported as a development
negative). The four budgets of the held run are floor(B/4), B, 4B and 20,000.

**Stop rule (cross-fitted).** At B, a gain is a unit the cross-fitted guide fits and the hand-set order does not, a
loss the reverse. GO only if gains - losses >= 10 and gains >= 3 x losses, pooled over the three benchmarks.
Otherwise no held task is run for this test, and the development result is the test's reported negative.

Both are computed once, from the trace, in `DEV_REPORT.md`, together with the source budget curves of every arm.

## 7. The held run (only after the coordinator's GO)

- **Tasks:** the 464 held tasks and the 120 ARC-AGI-2 evaluation tasks, demonstrations and test inputs only, on
  private Kaggle CPU kernels with internet off (4 workers per kernel; stop at 30 CPU-h per kernel; no GPU).
- **Reference:** for each task, `objgrow.arm.construction_answers(task, ops=(), g0b=<seed-independent builder>)`.
- **Arms on the 464 held tasks (13):** hand-set and guide at floor(B/4), B, 4B and 20,000; at B only, the linear
  model, the frequency order, the hand rule, donor guidance and the leave-one-benchmark-out guide.
- **Arms on ARC-AGI-2 (4):** hand-set and guide at B and at 20,000 (the guide trained on all source holes).
- **Shared work:** the base search and the holes, which no arm changes, are computed once per task (the base search
  by the reference call). A retry is a pure function of (candidate, task) and is computed once and shared by all
  arms, seeded with the reference's own retries; this also keeps arms consistent where a search stops on CPU time.
- **Records:** one row per task and arm with the answer, the stage, the candidates, the retries, the operations,
  segmentations, edit applications and process CPU per hole, and the freeze and GO digests. A task whose reference
  raises an error abstains in every arm; any other error row makes the run INVALID.

## 8. Checks (the run is INVALID if any fails)

Before the held run (development, Step 2):
- on all 1,275 source holes, the test's code in the hand-set order at 20,000 gives the frozen `hole_candidates`
  result (the same candidates in the same order with the same fields, and the same operation count), run live in
  the same process; the stored `runs/v2` hole records are compared as well and any difference is reported;
- on a seeded sample of at least 60 source holes, the hand-set order at budgets 100 to 5,000 equals the frozen
  function with its cap set to that budget, and simulation from the trace equals direct execution for the hand-set
  order, the cross-fitted guide and the hand rule at three budgets.
An unresolved mismatch stops the test.

After the held run and before any solution opens:
1. the hand-set order through the test's code at 20,000 equals `objgrow.arm.construction_answers(task, ops=())` on
   every task (fit, stage, attempts, program, retried candidates and their fits, the constructed operation);
2. the guided and hand-set orders are identical at 20,000 on every task with no capped hole (a hole whose counter
   passed 20,000);
3. every task has a row for every arm, every row carries the frozen digests and the GO's digest, and the kernels ran
   with internet off.

## 9. Analysis (scored once, after the GO, under an exclusive marker)

**Primary.** Correct held test outputs (pass at 2), guide against hand-set order at B, over all 464 held tasks.
Study A's procedure (`ngrow/analysis.py`, `compare`): per task d = (correct outputs, guide) - (correct outputs,
hand-set); exact two-sided sign test on the tasks with d not 0; the total difference with a family-clustered
bootstrap 95% interval (clusters: ConceptARC concepts and 1D-ARC types; Mini-ARC tasks are single-task clusters;
10,000 draws within benchmark, `random.Random(20261105)`). "Guide beats hand-set order" only if p < 0.05 and the
interval lies above 0; otherwise "inconclusive", "tie" (equal discordant counts) or "hand-set order beats guide".

**Secondaries (Holm over seven, same procedure, p-values Holm-adjusted):**
1. guide against donor guidance at B;
2. guide against the frequency order at B;
3. guide against the hand rule at B;
4. guide against the linear model at B (decides the "neural" wording);
5. guide against hand-set at 20,000 (predicted tie);
6. ARC-AGI-2 at 20,000, guide against hand-set (predicted identical; single-task clusters);
7. leave-one-benchmark-out guide against hand-set at B (transfer across benchmarks).

**Descriptive:** correct tasks and outputs of every arm by benchmark; operations, segmentations, edit applications
and CPU per arm; the held budget curves; the smallest hand-set budget of the four that matches the guide's correct
total at B (the "k times as many operations"); ARC-AGI-2 at B; why failed searches fail (no common edit, no
admissible predicate, verification failed). Every table carries the exposure statement.

**Predictions (copied from the predictions file; scored once):**
- guided-1. Guided and hand-set orders give the same answers on the ARC-AGI-2 public evaluation (0 to 3 of 120
  each). Scored at B and at 20,000: holds if at each budget the two orders' attempts are identical on all 120 tasks
  and each has 0 to 3 correct tasks.
- guided-2. Any gain at the selected budget lies on 1D-ARC; ConceptARC and Mini-ARC change by at most 3 tasks each.
  Scored at B: holds if ConceptARC and Mini-ARC each have at most 3 tasks whose correct count differs between the
  orders.
- guided-3. At the full 20,000-operation budget the two orders differ on at most 4 held tasks. Scored on the
  attempts: holds if at most 4 held tasks have different attempts.

**Outcome paragraphs** (from the program, filled only from audited numbers):
- Positive: "We trained a small network (two hidden layers of 32 units) on the object-level step's own records from
  the source halves, {N1} searches that produced an exact program and {N2} that failed. It changes only the order in
  which views and edits are tried; nothing is removed, and every answer is still checked exactly. In one
  pre-registered run on the 464 held tasks, at {B} operations per search (fixed on the source halves as the budget
  at which the hand-set order keeps three quarters of its answers), the guided step answered {Ng} tasks correctly
  and the hand-set order {Nf} ({G} gained, {L} lost; exact sign test p = {p}; family-clustered interval {lo} to
  {hi}). Guidance from another task gave {Nd}, a fixed frequency order {Nq}, a hand rule on the same features {Nh}
  and a linear model {Nl}. The hand-set order needed about {k} times as many operations to match. At 20,000
  operations both orders gave the same answers wherever the cap never bound, and on the ARC-AGI-2 public evaluation
  both answered {A} of 120. Learning bought efficiency, not reach." ("Network" becomes "learned guidance" unless
  secondary 4 shows the network beats the linear model.)
- Null: "At {B} operations the guided step answered {Ng} of 464 held tasks against {Nf} for the hand-set order
  (p = {p}). In {y}% of failed searches no single edit explained every changed object, or no selection rule picked
  out the changed objects; no ordering can find a program the language does not contain."
- Stopped on the source halves: "On the source halves, cross-fitted guidance gained only {g} tasks at {B}
  operations, below the pre-registered threshold of 10, so the held tasks were never opened for this test."
- Not run: "We designed, but did not run, a learned search order for the object-level step."

## 10. Milestones, cut-offs and compute (UTC)

| Step | When | What |
|---|---|---|
| 1 | 6 Nov 12:00 | this protocol committed |
| 2 | 14:30 | equivalence checks on all 1,275 source holes; an unresolved mismatch stops the test |
| 3 | 16:30 | source budget curves, the test budget and the stop-rule verdict in `DEV_REPORT.md`; a NO-GO ends the test |
| 4 | 19:00 | `FREEZE.json` (code, weights, configuration, budget), Kaggle packages, smoke test, gate refusal check; stop and report the digests |
| 5 | 22:00 | two exact-byte reviews PASS (one fix round) |
| 6 | 7 Nov 00:00 | the coordinator's GO (hard stop 06:00); the kernels are pushed once |
| 7 | 7 Nov 04:00 | outputs fetched; checks of section 8 |
| 8 | 7 Nov 08:00 | scored once; audit by 10:00 |

Any slip of more than two hours is reported at once and ends the test as "designed; development result only". No GO
by 7 Nov 06:00 means "designed, not run". Development: at most 2 CPU-h on Athe, at most 2 processes, each through
`scripts/with_cpu_slot.sh` (nice 19); CPU-time budgets only. Held run: private Kaggle CPU kernels only, after the GO.
Nothing public; no competition submission.

## 11. Wording

"Learned guidance" unless the network beats the linear model (secondary 4). "Fewer operations for the same exact
answers", never "new reach". A NO-GO or an inconclusive primary is reported as such. Any change to this protocol is a
dated amendment made before the outcome it could affect, and is re-frozen.
