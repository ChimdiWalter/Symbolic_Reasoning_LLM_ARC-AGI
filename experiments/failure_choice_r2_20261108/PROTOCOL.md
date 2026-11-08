# Failure-guided choice test, revision 2: pre-registration

Author: Chimdi Walter Ndubuisi. Revision 2, written on 8 November 2026 before any of its held tasks exists, and
amended the same day after its pre-run review (`reviews/PRE_RUN_REVIEW.md`, PASS-WITH-NOTES), still before any held
task exists. The amendment is listed at the end of section 2.

**Question.** When CORA fails on a task, does the evidence in its failure record help it choose which change to make,
beyond simply having every change available? Revision 1 (experiments/failure_choice_20261108, scored once, outcome
"none") showed why it could not: typed-hole construction checks whether it applies at almost no cost, so the best
fixed order (construction first) already matched the oracle. Revision 2 adds a change that cannot cheaply check
whether it applies, so that choosing can matter, and asks the question again. The tasks are **controlled generated
tasks**: transformation tasks built from ARC training input grids by a generator that knows each task's cause. They
are not ARC puzzles, and the results are not ARC accuracy.

Terms used throughout:
- **CORA's base attempt**: S1's base program search (A2's bottom-up search over the arc-dsl grammar G0 at S1's base
  budget of 150,000 primitive executions). S1 is CORA's original capability-growth test; its code is reused
  unchanged.
- **Failure record**: what the failed base attempt leaves, plus a paid representation probe (section 4).
- **Intervention**: one change CORA can make after a failure. The bank has three: **deeper search**, **alternative
  object views** and **typed-hole construction** (section 4).
- **Calls**: primitive executions counted by A2's search itself, plus one call for every object extraction or
  bounding-box computation of the views and the probe, and for every application of a candidate structure outside a
  search. Every budget and cost is in calls, so every result is deterministic and independent of the machine.
- **Router**: a rule that orders the bank's interventions for one task.

## 1. Design

Every held task has one injected cause: a **missing operation** (fixed by typed-hole construction), **depth** (the
program exists in G0 beyond the base budget; fixed by deeper search) or a **wrong object view** (the transformation
acts on objects that arc-dsl extracts only with non-default flags; fixed by searching with alternative object views
added). For each task the base attempt, its failure record and each intervention are measured once, in calls. Eight
arms are replayed exactly at the same total budget per task: base only (A), base plus extra search (B), the static
full bank in a fixed order (C), a random order (D), the fixed router on another task's failure record (E), the fixed
evidence-based router (F), a learned router trained on source families (G) and the oracle router (H, an upper
bound). The primary contrast is F against C at the pre-declared binding budget, on exact correct query outputs,
paired by task with a family-clustered interval.

## 2. What changed from revision 1, and what the source set shows

**Added:** the wrong-object-view cause and the view intervention (sections 3 and 4), a paid representation probe in
the failure record, a third ordering choice for every router, and a cap K_V for the view search. **Unchanged:** the
worlds, the missing-operation and depth causes and their families, the measurement of base, search and
construction, the replay rule, the contract, the primary and the decision rule. **Not included:** insufficient
evidence (no arm abstains).

**What the source set shows, before the freeze** (`runs/dev/CONSTANTS_EVIDENCE.json`, `runs/dev/source/ANALYSIS.json`;
source families only). The view search behaves as intended: it fails on all 44 missing-operation tasks after
running to its cap, solves all 14 view tasks (200,000 to 2,300,000 calls), and finds 12 of the 27 depth programs at
about three times search's calls; deeper search within 4,000,000 calls solves no view task, and construction
rejects every view and depth task after about 900 calls. **The best fixed order is no longer oracle-equivalent:**
at the binding budget the best of the six orders (construction, search, view) solves 42 of 85 source tasks and the
oracle 52; at 0.25 and 0.5 times the binding budget 7 against 12 and 22 against 29; at 2 and 4 times, 67 and 67.
So a selection advantage is possible in principle, and on the source set it closes as the budget grows, the pattern
the coordinator predicted. On the source set the fixed router reaches the oracle (52 at the binding budget, 10
tasks more than the static bank and none fewer), but it was written on these tasks, so that figure is optimistic.

**Two limits, disclosed before the held set exists.**
- **The test is narrow.** F differs from C only on tasks whose demonstrations all keep their size; there it runs
  the view search before deeper search. Every held view task keeps its size by construction, because the generator
  paints objects onto the input grid, so F's evidence is a size check that the generated view cause satisfies by
  construction. The primary therefore measures two things: whether held view tasks need between about 350,000 calls
  (what C has left after the base attempt, construction and a failed deeper search capped at K_S, 2,500,000 calls)
  and K_V (2,250,000 calls; both caps are set in section 5); and
  whether running the view search earlier costs anything on held missing-operation or depth tasks that keep their
  size and that construction misses (switch, and cmirror or rot270 on square grids; rarely a crop that removes
  nothing).
- **Two of the three held causes were seen before.** The held missing-operation and depth families are revision 1's
  held families, scored before this revision was designed: there the static bank solved 14 of 32 missing-operation
  tasks, all by construction (search after construction solved none), and 16 of 18 depth tasks. Only their sources
  are fresh. The view operations (outbox, corners, inbox) are new to every held test.

**Amendment after the pre-run review** (8 November 2026; no held task, claim or GO exists):
1. View tasks are generated first in each world, and their quota is 5 per held view operation per world instead of
   2, so that the expected number of held view tasks is at least 18 (section 3). The estimate uses source-side
   counts only and generates no held task (`runs/dev/VIEW_FILL_ESTIMATE.json`, `python -m fgc.develop viewfill`).
   The reason: all 10 discordant source tasks are view tasks, so the primary's power depends on the number of held
   view tasks (the reviewer's simulation: 0.996 with 18, 0.90 with 9, 0.55 with 7, 0.24 with 6, and practically 0
   with 5 or fewer, since 5 against 0 discordant tasks gives p = 0.0625).
2. The description of the source set is corrected: 4 of its 14 view tasks reuse input grids of revision 1's held
   set (section 3).
3. The reviewer's procedural conditions are part of the procedure: the GO's third line, new kernel and job names,
   the checks between stages, a commit before each stage, one seal and one scoring (section 10).
4. The two limits above are disclosed, and the descriptive outputs add every fixed order of the bank (section 7).

## 3. Tasks

**Worlds.** The three worlds of the construction test at scale, copied byte for byte with their task files, removed
sets and controller records into `runs/worlds/` (as in revision 1). Each world's G0 is A2's grammar minus that world's
removed operations: W1 removes upscale, downscale, compress and trim; W2 removes dmirror, cmirror, rot90 and rot270;
W3 removes vupscale, hupscale and switch. G0 itself is unchanged; it can extract objects with every flag set.

**Causes**, injected by the generator (the construction test's Builder, `cas/generate.py`, unchanged for sources and
filters; real ARC training INPUT grids only; sha256 ordering by salt; `fgc/generate.py`):
- **Missing operation**: a task built on one removed operation X with the templates X(I), X(A(I)) and B(X(I)) and the
  construction test's filters (G0 plus the reference for X fits and predicts at the base budget; G0 alone does not
  fit at the base budget).
- **Depth**: a program a(b(c(I))) of three different operations of the world's unary list such that G0 finds no fit
  at the base budget and a G0 search of at most 4,000,000 calls finds a first fit that is correct.
- **Wrong object view**: X applied to every object of the grid under one of four alternative object views and
  painted in one colour, `fill(I, c, mapply(X, objects(I, u, d, b)))` (`underfill` for X = backdrop), with (u, d, b)
  one of the views (True, False, False), (True, True, True), (False, True, True), (False, False, True) and c the
  smallest colour absent from every input grid. The program runs on every input and its outputs are valid; no
  demonstration output equals its input and the outputs are not all equal; the default view (True, False, True)
  gives a different output on at least two thirds of the inputs; G0 finds no fit at the base budget; the view search
  of at most 4,000,000 calls finds a correct first fit; and a G0 search of at most 4,000,000 calls finds no correct
  fit. These are whole-grid transformations of every object; no object is selected by attribute.

**Families and the split.**

| | source families (develop F, train G, set the constants) | held families (the test) |
|---|---|---|
| missing operation | W1 upscale, W1 downscale, W2 dmirror, W2 rot90, W3 vupscale | W1 compress, W1 trim, W2 cmirror, W2 rot270, W3 hupscale, W3 switch |
| depth | W1, W2, W3 with a reflection or rotation outermost | W1, W2, W3 with a crop outermost |
| wrong view | W1, W2, W3 with X = box, backdrop or delta | W1, W2, W3 with X = outbox, corners or inbox |

**Source set** (`runs/source/`): revision 1's source set (44 missing-operation and 27 depth tasks) and fresh
wrong-view tasks of the source view families (14: box 8, backdrop 5, delta 1; inputs at most 16 x 16), 85 tasks in
all. The view tasks use no source of any world copy or of revision 1's source set, but 4 of them (t6c9e5e1f,
t8f2f6420, tad7c9c94 and tc0796ca0) reuse input grids of revision 1's held tasks, because the source build left
revision 1's held set out of its exclusions. This revision's held set excludes those grids.

**Held set** (`runs/test/`, built only after this revision's GO): fresh tasks of every held family, generated in
each world in this order: wrong view (5 per held X per world: at most 45), missing operation (templates T1, T2, T3,
T1, T2, T3: at most 36) and depth (at most 8 per world: 24), salted with `fgc2-test-` plus the first 16 hex digits
of the sha256 of this revision's GO file. Unfilled slots are recorded, never replaced. No held task uses a source of
any world copy (any partition), of either revision's source set, or of revision 1's held set. Size caps: held tasks
allow inputs and outputs up to 20 x 20 (the pool's smaller sources are used up), for every cause alike; source tasks
have 12 x 12 or 16 x 16.

**Expected number of held view tasks** (`runs/dev/VIEW_FILL_ESTIMATE.json`; source-side counts only: no held task
is generated and no held operation is applied). In the source build every view slot scanned its world's whole
share, so a slot of operation X filled exactly when an unused eligible source passed X under the slot's view.
Eligible depends on the grids alone: at least three inputs, a colour absent from every input, every input within
the size cap. Fitted to the source build's 27 view slots (14 filled; 28 to 37 eligible sources per world), an
eligible source passes under a given view with probability 0.089 for box, 0.028 for backdrop and 0.0055 for delta;
a simulated source build with these rates gives 13.8 tasks on average (14 observed). The held shares hold 43, 50 and
37 eligible sources at the held cap (13, 18 and 12 of them at most 16 x 16). If the held operations behave like the
source operations, and ignoring that two operations may want the same source, 5 slots per held operation per world,
filled first, give 24.1 held view tasks on average (10th percentile 20). If sources larger than 16 x 16 pass at half
the rate, the average is 19.7; if they never pass, 12.4. The former quota of 2 gives 10.9 even with view tasks
first. The quota of 5 is the smallest whose average reaches 18 in the first two cases. The realised count is
recorded after the merge (section 10).

**The cause mix moves away from the source set's**: at most 45 view, 36 missing-operation and 24 depth tasks,
against 14, 44 and 27 there. At 24 view and 24 depth tasks, the source set's results by cause would put the order
construction, view, search about 2 tasks ahead of C's order (construction, search, view), with F, written on the
source set, ahead of both. C stays the static order pre-registered on the source set, and section 7 reports every
fixed order of the bank beside F.

## 4. Measurement (system side; `fgc/measure.py`, `fgc/views.py`)

Each task is measured once, from its demonstrations and query inputs only:
1. **Base attempt**: S1's base search over G0 at 150,000 calls, with its closest-program record.
2. **Failure record**: S1's controller analyses without its deeper probe (shape relation, closest program's share of
   correct cells, typed-hole sketches with scores, sizes, colours), at no call cost, and a **paid representation
   probe**: on every demonstration, the number of objects under the default and each alternative view, and, when input
   and output have the same size, the share of changed cells within one cell of the objects' bounding boxes under each
   view (objects spanning the whole grid left out); one call per extraction or bounding box (10 to about 300 calls per
   task). Routers that read a failure descriptor (E, F, G) pay these calls.
3. **Search intervention**: the G0 search from the start, one fit wanted, measured up to 20,000,000 calls.
4. **View intervention**: A2's search over G0 with the four alternative views of every grid added as representation
   leaves (A2's own mechanism, cost 1 each), one fit wanted, measured up to 4,000,000 calls. It has no cheap
   applicability check: when no program over the views fits, it runs to its cap.
5. **Construction intervention**: S1's typed-hole construction from the task's own sketches, as in revision 1.
Every CPU cap is out of reach; only call budgets bind. Measurements run in private Kaggle CPU kernels (internet off).

## 5. Arms, constants, routers and the contract

**Replay rule** (`fgc/contract.py`, `run_arm`). At a total budget B per task, an arm spends the base attempt's calls,
then (E, F, G) the probe's calls, then applies interventions in its order until one commits a prediction or the budget
is spent. Search gets min(K_S, remaining) calls (arm B: all the remaining calls) and the view search min(K_V,
remaining); each commits its first fit if that came within them, and otherwise spends them all (or less if its
fragment was exhausted first). Construction needs its complete measured calls; with fewer remaining it is cut off.
The first committed prediction ends the arm; a wrong one is a wrong answer.

| arm | order |
|---|---|
| A base only | none |
| B base plus extra search | search, with every remaining call |
| C static full bank | construction, then search, then view, for every task |
| D random order | a permutation of the bank per task, from sha256("random:" + task id + ":" + intervention) |
| E shuffled diagnosis | F's rules on the failure record of the next task in sha256("donor:" + task id) order |
| F fixed evidence-based router | the hand-written rules below |
| G learned router | the logistic regressions below, trained on the source set only |
| H oracle router (upper bound) | the generator's cause names the first intervention; the rest in the static order |

**Constants** (`config/ROUTERS.json`; formulas fixed before they were computed, `fgc/develop.py`):
- **K_S** (search's cap inside the bank) = 2,500,000 calls: the 90th percentile of search's calls at its correct
  first fit over the 27 source depth tasks, rounded up to 250,000.
- **K_V** (the view search's cap) = 2,250,000 calls: the same over the 14 source view tasks.
- **T*** (the binding budget) = 3,000,000 calls: the 75th percentile of the oracle arm's spent calls over the source
  tasks it solves within 20,000,000 calls, rounded up to 250,000.
- **Static order** = construction, then search, then view: the permutation with the most correct source tasks at T*
  (42; construction, view, search 35; the four orders that start with search or view 20 to 28).
- **Budget curve**: 0.25, 0.5, 1, 2 and 4 times T*.

**F, the fixed evidence-based router** (hand-written from the source failure records; reported as fixed, never as
learned): construction first, because its typed-hole specification rejects an inapplicable hole at almost no cost;
then, when every demonstration's output has its input's size (S1's shape relation "output size equals input size"),
the view search before deeper search, because a change that keeps the grid's size and that no whole-grid typed hole
explains is taken to act on objects; otherwise deeper search before the view search. Richer rules on the
representation probe (coverage of changed cells by object boxes, object-count gaps) were tried on the source set and
did no better, so the simplest rule is frozen. On the source set the size rule separates the causes exactly (every
view task keeps the size, no depth task does, 7 of 44 missing-operation tasks do); on held families it may not.

**G, the learned router**: one L2-regularised logistic regression per intervention (L2 = 1, 3,000 gradient steps,
rate 0.1, standardised features) on the 22 failure features of `fgc/arms.py` (the revision 1 features plus same
size, object-count gap, coverage gain and best coverage of the representation probe), predicting that the
intervention alone commits a correct answer (search within K_S, view within K_V); trained once on the 85 source
tasks (25, 20 and 30 positives) and frozen in `config/ROUTERS.json`; it orders the bank by decreasing predicted
probability, ties in the static order.

**The strong full-bank control, as a contract** (`fgc/contract.py`, unchanged in substance from revision 1): one bank
executed by one function on the current task's own measurement; one meter with the same total budget for every arm;
arms differ only in their order (and every arm that reads a failure descriptor pays the probe's calls alike); the
shuffled diagnosis changes only the descriptor, and donor demonstrations are never used. Source-only literal checks
on invented tasks (`fgc/contract_checks.py`, `checks/CONTRACT_CHECKS.json`, all pass): twelve hand-computed replays
with three interventions and the descriptor charge, the identity of the measurement every arm executes on, the
shared budget, equal results for equal orders, E equal to F on the donor's descriptor, and literal source checks
that the sealing code executes every arm on the current task's measurement, charges the descriptor to every arm that
reads one, and uses the donor only as an index into the descriptors. What it cannot match, by design: arm B searches
only, with every remaining call; arm A runs no intervention; arm H's order comes from the generator's cause; the
bank itself uses the failure record (construction is built from the task's own typed holes in every arm); and no
arm can interleave interventions.

## 6. Primary contrast

F against C at T*, on exact correct query outputs (at most two committed attempts), task by task: exact two-sided
McNemar test on the discordant tasks and a family-clustered percentile bootstrap interval of the mean paired
difference (families resampled with replacement, 10,000 draws, seed 7). **Success rule:** McNemar p < 0.05 and the
interval's lower end above 0.

## 7. Secondary and descriptive outputs

- **Secondaries, Holm-adjusted together:** G against C, F against E, F against D, at T*.
- **Budget curve:** every arm at 0.25, 0.5, 1, 2 and 4 times T*. The coordinator's pre-registered prediction: the
  router's advantage over the static bank appears at binding budgets and shrinks as the budget grows (F minus C at
  4T* smaller than at T*).
- **Efficiency:** the smallest budget multiple at which each arm reaches C's correct count at T*, and F's mean calls
  minus C's at T* with a family-clustered interval.
- **Descriptive:** every arm by cause and family; arms B and H; G's probabilities; which intervention committed each
  answer; the realised held count by cause, with the primary's power at the realised view count; and every fixed
  order of the bank (the six permutations) at T*, replayed with the frozen `contract.run_arm` from the committed
  measurements and shown beside F, so that a result can also be read against the best fixed order on the held mix
  (section 3). None of these enters the decision rule.

## 8. Decision rule (the first that holds, in this order)

1. **Selection advantage**: the primary succeeds.
2. **Static bank better**: McNemar p < 0.05 and the primary interval's upper end below 0.
3. **Efficiency**: F solves at least as many tasks as C alone (only-F at least only-C) and the family-clustered
   interval of F's mean calls minus C's lies entirely below -5% of T*.
4. **Capability**: C against B at T* meets the success rule.
5. **Coverage**: C against B meets the success rule only at 4T*.
6. **None** of the above.
The result is reported with its label, as "controlled generated tasks", naming the fixed router (F, the primary) and
the learned router (G, a secondary) separately.

## 9. Expectation and power, from the source set

On the source set (optimistic, since F was written there): F against C 10 against 0 discordant tasks, p 0.002,
interval +3.5 to +28.4 points, so the primary succeeds; G 49, H 52, E 38, D 31, B 27 of 85 at T*. Resampling the
source families into the former held plan's shape (six missing-operation families of six tasks, three depth families
of eight, nine view families of two), the primary succeeds in 996 of 1,000 simulated held sets; with fewer view
tasks, in 902 with 9, 552 with 7 and 244 with 6 (the reviewer's simulation). With the amended quota, each view
family sized by one simulated held build (section 3), it succeeds in 982 of 1,000; in 956 if sources larger than
16 x 16 pass at half the rate, and in 785 if they never pass. These are upper bounds: every missing-operation and
depth slot is taken as filled; held view tasks are taken to cost what source view tasks cost, although held inputs
may be 20 x 20 and the generator accepts view tasks of up to 4,000,000 calls, above K_V (every arm fails those, H
included); the held families differ (their view operations are outbox, corners and inbox; their depth programs
crop); and the size rule may misroute held missing-operation tasks that keep the size (switch, and cmirror or rot270
on square grids) to the view search after construction. Expectation for the held set, stated before it exists: a
selection advantage at the binding budget that shrinks to nothing by 2T*, F well above D and E, and G between C and F.

## 10. Procedure after the GO (every long step detached through scripts/run_detached.sh or a private kernel)

Every command runs from this folder. Each stage is committed (plain explicit-path commits, no trailers) before the
next one starts, each step's outcome is appended to PROGRESS.md, and the package, isolation and id checks are the
exact commands of `reviews/PRE_RUN_REVIEW.md` section 8.
1. **GO.** The coordinator writes `GO_FGC` here once, as three ASCII lines, each ending with one line feed and with
   one space between fields: `protocol_sha256 <sha256 of PROTOCOL.md>`, `freeze_sha256 <sha256 of FREEZE.json>` and
   `pre_run_review <the full commit of the reviewer's final pre-run review> <its verdict>`. The third line makes the
   salt unknowable before the review existed. A dry `python3 -I fgc/gate.py measure` must then fail only for want of
   a claim and a held manifest. The GO is committed before the claim and never edited, since its exact bytes set the
   salt.
2. **Claim, locally.** `python3 -I fgc/gate.py generate` checks the GO and every frozen digest, refuses if a claim or
   runs/test/ exists, writes runs/RUN_CLAIM.json (one use) and must print "ok generate". The claim is committed. The
   held set's salt is `fgc2-test-` plus the first 16 hex digits of the GO's sha256.
3. **Held set, on Kaggle, in a kernel named R2_TEST_GEN** (the local CPU slots are shared and often full):
   `python3 -I fgc/kaggle_build.py --generate-test R2_TEST_GEN W1 W2 W3` builds a private kernel that refuses unless
   the claim names this GO, carries the salt, and runs one generator per world on disjoint shares of the pool (sha256
   of the source id modulo 3). Before the push, the notebook must carry the salt and the package check against
   FREEZE.json must print "none"; the kernel folder is then committed and pushed with
   `launch/push_when_free.sh R2_TEST_GEN`. The archive is checked against its printed digest
   (`fgc/fetch.py R2_TEST_GEN gen`).
4. **Merge and the isolation check.** The three parts are placed in runs/test_parts/, and the merge runs as the
   detached job `fgc2_test_merge` (`python -m fgc.generate test_merge` through `launch/run_job.sh`; it refuses a task
   id or a source used twice). The isolation check must print 0 reused sources, 0 duplicates and no family outside
   the plan. The held count by cause is recorded, with the view count beside the power at that count from the
   reviewer's table (section 2). Then runs/test/, runs/test_parts/, the generation output and its fetch record are
   committed, before any measurement.
5. **Measurement, in kernels named R2_TEST_1 to R2_TEST_4**, never TEST_1, TEST_2 or TEST_3 (revision 1's held
   kernels). `python3 -I fgc/gate.py measure` must print "ok measure", which is recorded. Kernel k (1 to 4) gets its
   share of the held ids (`python3 -I fgc/kaggle_build.py R2_TEST_k runs/test/TEST_SYSTEM.json 3 ...`); its package
   check against FREEZE.json must print "none", and its folder is committed before its push with
   `launch/push_when_free.sh`. Outputs are polled and fetched with digest checks. A kernel that fails is measured
   again under a new name from the same frozen package (the same archive digest); that is the only recovery. Before
   the seal, the id check must print "missing 0 extra 0", and runs/test/measure/ and the fetch records are committed.
6. **Seal once, then score once**, through scripts/run_detached.sh as the jobs `fgc2_seal` and `fgc2_score` (never
   `fgc_seal` or `fgc_score`, which are revision 1's records), under the gate's seal and score stages.
   SEALED_PREDICTIONS.json and SEALED_SHA256 are committed before scoring, and ANALYSIS.json after it.
7. **Report** (RESULT.md: result, lesson, direction) and an independent post-score audit.
Recovery of a failed build: generation is deterministic; if it fails after the claim, the coordinator may once remove
runs/RUN_CLAIM.json and any partial runs/test/ or runs/test_parts/, log that, and repeat steps 2 to 4 under the same
GO (the same salt) and a new kernel name. A second failure ends the test. Before the freeze, the held generator's
code path was smoke-tested on the pilot pool only (one slot per family, a fake salt, one world; no main-pool source
touched, nothing kept: outputs/detached/fgc2_gen_smoke), and it ran to the end; after the amendment, the reordered
path was smoke-tested the same way (outputs/detached/fgc2_gen_smoke2).

**Cost.** Source set: generation on Kaggle (two kernels, about 70 minutes of wall time, one process per world);
measurement 17,300 CPU-seconds on Kaggle for 85 tasks (search 11,360, view 4,650, construction 1,100, base 160),
about 25 minutes over four kernels. The held set (at most 105 tasks) needs a generation kernel of up to about three
hours (15 view slots per world, each scanning its world's whole share), four measurement kernels of about 25 to 35
minutes, and under a minute to seal and score.

## 11. Files and freeze

Frozen (FREEZE.json, with sha256): this file; `fgc/*.py`; `config/*.json`; `launch/*.sh`; `checks/*.json`; the world
copies; the source set and its measurements (`runs/source/`); every dependency outside this folder that the code
imports (the construction test's `cas/env.py`, `cas/generate.py`, `cas/__init__.py`, S1's `cgrow`, A2, the harness,
CAST, arc-dsl); revision 1's held task labels file (its sources are excluded from this held set); and the ARC
training challenges file the generator reads. The gate re-checks every digest before each stage. The development
evidence in `runs/dev/` (the constants, the gap check and the expected view count) is committed and reproduces from
the frozen `fgc/develop.py`, but is not itself frozen.
