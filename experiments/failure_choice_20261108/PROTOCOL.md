# Failure-guided choice test: pre-registration

Author: Chimdi Walter Ndubuisi. Revision 1, written on 8 November 2026 before any held task exists.

**Question.** When CORA fails on a task, does the evidence in its failure record help it choose which change to
make, beyond simply having every change available? A router that reads the failure record is compared with a static
bank that applies every change in a fixed, pre-declared order, at the same total budget per task. The tasks are
**controlled generated tasks**: transformation tasks built from ARC training input grids by a generator that knows
each task's cause of failure. They are not ARC puzzles, and the results are not ARC accuracy.

Terms used throughout:
- **CORA's base attempt**: S1's base program search, that is A2's bottom-up search over the arc-dsl grammar G0 at
  S1's base budget of 150,000 primitive executions. S1 is CORA's original capability-growth test; its code is
  reused unchanged.
- **Failure record**: what the failed base attempt leaves (section 4).
- **Intervention**: one change CORA can make after a failure. The bank has two: **deeper search** and **typed-hole
  construction** (section 4).
- **Calls**: primitive executions, counted by A2's search itself (and, for construction, one call per application
  of a candidate structure to a grid outside a search). Every budget and cost here is in calls, so every result is
  deterministic and independent of the machine.
- **Router**: a rule that orders the bank's interventions for one task.

## 1. Design

Every held task has one injected cause: a **missing operation** (an operation removed from the base grammar; the
fix is typed-hole construction) or **depth** (the program exists in the base grammar but beyond the base budget; the
fix is deeper search). For each task the base attempt, its failure record and each intervention are measured once,
in calls. Eight arms are then replayed exactly at the same total budget per task: base only (A), base plus extra
search (B), the static full bank in a fixed order (C), a random order (D), the fixed router on another task's
failure record (E), the fixed evidence-based router (F), a learned router trained on source families (G), and the
oracle router that knows the cause (H, an upper bound). The primary contrast is F against C at the pre-declared
binding budget, on exact correct query outputs, paired by task with a family-clustered interval.

## 2. What was scaled down, and what the source set already shows

**Two of the four causes are in this test.** Decided before any source outcome was seen, for time:
- **Wrong object view** (a transformation over objects extracted with other arc-dsl object flags) is not included.
  It needs a base grammar without the alternative views, which changes S1's grammar, the worlds' controller records
  and every filter built on them; that could not be built and checked honestly by the freeze.
- **Insufficient evidence** (where abstaining is correct) is not included; no arm abstains, and every wrong answer
  counts as wrong.
No control is cut: all eight arms are present.

**What the source set shows, before the freeze** (`runs/dev/source/ANALYSIS.json`; source families only). At the
binding budget the static full bank in the order construction then search solves exactly the tasks the oracle
solves (45 of 71), and so do the fixed and learned routers; a random order solves 33, the shuffled diagnosis 39,
extra search alone 33. At every budget of the curve the static bank equals the oracle on the source set. The reason
is in the bank: typed-hole construction rejects an inapplicable hole at almost no cost (its specification step
finds no structure of the 211 consistent with the hole and stops after about 900 calls, on all 27 source depth tasks
and on 14 of the 44 missing-operation tasks), so construction can go first for free, while search first costs a
missing-operation task the whole search cap. On the source set, failure evidence beats a random or shuffled order
(12 against 0 and 6 against 0 tasks) but cannot beat the best fixed order, which is already at the oracle's level.
The held families may behave differently (a held depth task with an outer crop may match a selection structure and
make construction expensive), which is what the held test can show. A test in which routing can matter needs an
intervention without a cheap applicability check, such as the object-view cause; that is proposed as a separate
revision and is not part of this test.

## 3. Tasks

**Worlds.** The three worlds of the construction test at scale (experiments/construction_at_scale_20261105), copied
byte for byte with their task files, removed sets and controller records into `runs/worlds/`. Each world's G0 is
A2's grammar minus that world's removed operations: W1 removes upscale, downscale, compress and trim; W2 removes
dmirror, cmirror, rot90 and rot270; W3 removes vupscale, hupscale and switch. A world's other tasks (its validation
and previously solved tasks) are the context construction's gates use, as in that study.

**Causes**, injected by the generator (the construction test's Builder, `cas/generate.py`, unchanged; real ARC
training INPUT grids only, their outputs never used; sha256 ordering by salt):
- **Missing operation** (cause "operation"): a task built on one removed operation X with the construction test's
  templates X(I), X(A(I)) and B(X(I)) and filters: G0 plus the reference for X fits the demonstrations and predicts
  the query at the base budget, and G0 alone finds no fit at the base budget.
- **Depth** (cause "search"): a program a(b(c(I))) of three different operations of the world's unary list (S1's
  eleven operations plus compress and trim, minus the removed ones) such that G0 finds no fit at the base budget and
  a G0 search of at most 4,000,000 calls finds a first fit that is correct.

**Families and the split.** A family is one removed operation of one world (missing operation), or one world and the
class of the depth program's outer operation a. Source and held families do not overlap:

| | source families (develop F, train G, set the constants) | held families (the test) |
|---|---|---|
| missing operation | W1 upscale, W1 downscale, W2 dmirror, W2 rot90, W3 vupscale | W1 compress, W1 trim, W2 cmirror, W2 rot270, W3 hupscale, W3 switch |
| depth | W1, W2, W3 with a reflection or rotation outermost | W1, W2, W3 with a crop outermost (a half, compress or trim) |

**Source set** (`runs/source/`, 71 tasks): the construction test's own motivating tasks of the five source families
(44; that study saw them and their outcomes) and fresh depth tasks, 9 per world (27).

**Held set** (`runs/test/`, built only after the GO): fresh missing-operation tasks of the six held families
(templates T1, T2, T3, T1, T2, T3: at most 36) and fresh depth tasks with a crop outermost (at most 6 per world:
18), salted with `fgc-test-` plus the first 16 hex digits of the sha256 of the GO file, so that no held task can
exist before the GO. An unfilled slot is recorded, never replaced. No held task uses a source of any task of the
world copies (any partition) or of the source set.

**Size caps.** The construction test's worlds used 176 of the 187 main-pool sources whose inputs are at most 12 x 12,
so new tasks allow inputs up to 16 x 16 (outputs at most 16 x 16 as before); the source missing-operation tasks keep
the construction test's caps. The held families were part of the construction test's worlds, so their general
behaviour under construction and static search was seen there; their held tasks are new.

## 4. Measurement (system side; `fgc/measure.py`)

Each task is measured once, from its demonstrations and query inputs only (never its label, cause or family):
1. **Base attempt**: S1's base search over G0 at 150,000 calls, with its closest-program record.
2. **Failure record**, from the failed base attempt only, at no call cost: S1's controller analyses without its
   deeper probe: the shape relation between inputs and outputs, the closest program's share of correct cells, the
   typed-hole sketches (identity ?(I); outer B(?(I)); inner ?(A(I))) with their scores, and grid sizes and colour
   counts. S1's controller also runs a deeper search before deciding; that probe is the search intervention itself,
   so it is not part of the failure record.
3. **Search intervention**: the G0 search from the start, one fit wanted, measured up to 20,000,000 calls; its calls
   at the first fit are recorded.
4. **Construction intervention**: S1's typed-hole construction (the construction test's S-hole arm) from this
   task's own sketches: specification enumeration over the 211 structures in S1's seed-0 order, S1's gates
   (novelty, retry at the base budget, regression on every base-solved task of the world, validation on the world's
   other unsolved tasks), at most three retries, and the label-blind commit (the promoted structure, else the first
   quarantined one). Its gates run with an empty cache for each task, so its count is its complete work.
Every CPU cap is set out of reach, so only call budgets bind. The measurements run in private Kaggle CPU kernels
(internet off, `fgc/kaggle_build.py`), three tasks at a time per kernel. Two kernels measured the same 24 source
tasks with identical base, record, search and construction results (`runs/prelim/`, `runs/source/`).

## 5. Arms, constants, routers and the contract

**Replay rule** (`fgc/contract.py`, `run_arm`). At a total budget B per task (calls), an arm spends the base
attempt's calls, then applies interventions in its order until one commits a prediction or the budget is spent.
Search gets min(K_S, remaining) calls (arm B: all the remaining calls) and commits its first fit if that came within
them; otherwise it spends them all (or less, if it exhausted its fragment first). Construction needs its complete
measured calls; with fewer remaining it is cut off and commits nothing. The first committed prediction ends the arm;
a wrong one is a wrong answer. A search needing more than the measured 20,000,000 calls counts as failing.

| arm | order |
|---|---|
| A base only | none |
| B base plus extra search | search, with every remaining call |
| C static full bank | construction, then search, for every task |
| D random order | per task, from sha256("random:" + task id) |
| E shuffled diagnosis | F's rules on the failure record of the next task in sha256("donor:" + task id) order |
| F fixed evidence-based router | the hand-written rules below |
| G learned router | the logistic regressions below, trained on the source set only |
| H oracle router (upper bound) | the generator's cause names the first intervention |

**Constants** (`config/ROUTERS.json`; formulas fixed before they were computed, `fgc/develop.py`; evidence in
`runs/dev/CONSTANTS_EVIDENCE.json`):
- **K_S** (search's cap inside the bank) = 2,500,000 calls: the 90th percentile of the search's calls at its correct
  first fit over the 27 source depth tasks (2,454,826), rounded up to 250,000.
- **T*** (the binding budget) = 3,500,000 calls: the 75th percentile of the oracle arm's spent calls over the 54
  source tasks it solves within 20,000,000 calls (3,293,679), rounded up to 250,000.
- **Static order** = construction, then search: the order with more correct source tasks at T* (45 against 25).
- **Budget curve**: 0.25, 0.5, 1, 2 and 4 times T*.

**F, the fixed evidence-based router** (hand-written from the source failure records; reported as fixed, never as
learned): construction first by default, because its typed-hole specification rejects an inapplicable hole at almost
no cost; search first only for the source depth signature: the base attempt's closest program already reproduces at
least 80% of the output cells, the output is at most 35% of the input's area, and the identity typed hole does not
explain the output (sketch score below 0.9). On the source set this flags 12 of the 27 depth tasks and none of the
44 missing-operation tasks.

**G, the learned router**: one L2-regularised logistic regression per intervention (L2 = 1, 3,000 gradient steps,
rate 0.1, standardised features), on the 18 failure features of `fgc/arms.py` (sketch scores, closest-cell share,
base enumeration level and bank size, demonstrations, area ratio, colour counts, shape relation), predicting that
the intervention alone commits a correct answer (search within K_S); trained once on the 71 source tasks (25 and 30
positives) and frozen in `config/ROUTERS.json`; it puts first the intervention with the higher predicted probability.

**The strong full-bank control, as a contract** (`fgc/contract.py`; the companion asked us to own it, its note
0588, item 2). Every arm runs through one function, `run_arm`, and nothing else:
1. **One bank.** The static full bank and every router arm get the identical executable bank, executed by one
   function on the current task's own measurement; every intervention was measured on that task's own
   demonstrations and query inputs, with the same grammar, search, 211 structures, parameter search and gates.
2. **One meter.** Every arm gets the same total budget, charged by one meter: the base attempt's calls, then each
   intervention's calls.
3. **Arms differ only in order**: an arm is an order function from a failure descriptor (the features of a failure
   record) and the task's opaque id to an ordering of the bank.
4. **Shuffled diagnosis changes only the descriptor**: arm E is F's order function on a donor task's descriptor;
   the donor's demonstrations, measurement and budget are never passed; donor demonstrations are never the control.
Source-only literal checks on invented tasks (`fgc/contract_checks.py`, `checks/CONTRACT_CHECKS.json`, all pass):
ten hand-computed replays; every arm executes on the current task's measurement object; the shared budget; equal
results for equal orders; E equals F on the donor's descriptor and F itself on the task's own; and literal source
checks that the sealing code executes every arm on the current task's measurement, uses the donor only as an index
into the descriptors, and executes no intervention outside the contract.

**What the contract cannot match, by design:** arm B gives search every remaining call and has no construction, arm
A runs no intervention, and arm H's order comes from the generator's cause (named controls and an upper bound); the
descriptor costs no calls, so F, G and E get their order for free while C and D need none (its CPU is recorded); the
bank itself uses the failure record, because construction is built from the current task's own typed holes in every
arm including C, so the test measures failure evidence for choosing the bank's order, not inside construction; and
no arm can interleave interventions or split one intervention's work.

## 6. Primary contrast

F against C at T* = 3,500,000 calls, on exact correct query outputs (at most two committed attempts; correct when
one equals every query output), task by task: exact two-sided McNemar test on the discordant tasks and a
family-clustered percentile bootstrap interval of the mean paired difference (families resampled with replacement,
10,000 draws, seed 7). **Success rule:** McNemar p < 0.05 and the interval's lower end above 0.

## 7. Secondary and descriptive outputs

- **Secondaries, Holm-adjusted together:** G against C, F against E, F against D, at T*, each with the primary's
  statistics and success rule.
- **Budget curve:** every arm's correct count and mean calls at each budget. The coordinator's pre-registered
  prediction is that the router's advantage appears at binding budgets and shrinks as the budget grows (F minus C
  at 4T* smaller than at T*); reported as holding or not, with the curve.
- **Efficiency:** the smallest budget multiple at which each arm reaches C's correct count at T*, and F's mean calls
  minus C's at T* with a family-clustered interval.
- **Descriptive:** every arm by cause and family; arms B and H; G's predicted probabilities; which intervention
  committed each answer.

## 8. Decision rule (the first that holds, in this order)

1. **Selection advantage**: the primary succeeds.
2. **Static bank better**: McNemar p < 0.05 and the primary interval's upper end below 0.
3. **Efficiency**: F solves at least as many tasks as C does alone (only-F at least only-C) and F's mean calls are
   lower by a material amount: the family-clustered interval of the calls difference lies entirely below
   -175,000 calls (5% of T*).
4. **Capability**: the bank adds solved tasks over extra search at T*: C against B meets the success rule.
5. **Coverage**: C against B meets the success rule only at 4T*.
6. **None** of the above.
The result is reported with its label, as "controlled generated tasks", naming the fixed router (F, the primary)
and the learned router (G, a secondary) separately.

## 9. Expectation and power, from the source set

On the source set F and C agree on every task at every budget (no discordant task), so the primary has no power
there by construction (resampling the source families: 0 of 1,000 simulated held sets succeed). The source decision
is "coverage" (C against B at T*: 16 against 4 tasks, p 0.012, interval -1.4 to +35.7 points; at 4T*: 18 against 3,
p 0.0015, interval +1.4 to +42.9). Expectation for the held set, stated before it exists: no selection advantage
(F and C equal or nearly so), failure evidence better than a random order (source: F against D, 12 against 0) and
than a shuffled diagnosis (6 against 0), and a decision of capability or coverage. A selection advantage would need
held families on which construction spends calls and fails where search succeeds; F's depth signature may also
misroute held missing-operation tasks that crop (compress, trim), which would favour C.

## 10. Procedure after the GO (each step detached, with a status file and a line in PROGRESS.md)

1. **GO.** The coordinator writes `GO_FGC`: `protocol_sha256 <sha256 of PROTOCOL.md>` and
   `freeze_sha256 <sha256 of FREEZE.json>`.
2. **Held set.** `setsid nohup sh launch/run_job.sh gen_test python3 -m fgc.generate
   test`: the gate's generate stage checks the GO and every frozen digest, refuses if a claim or runs/test/ exists,
   writes runs/RUN_CLAIM.json (one use), derives the salt from the GO, and builds the held set (CPU slot, nice 19).
   The held manifest is committed before any measurement.
3. **Measurement.** `python3 -I fgc/kaggle_build.py TEST_k runs/test/TEST_SYSTEM.json 3 ...` for three kernels of
   about equal size, committed, pushed privately (internet off) with `launch/push_when_free.sh` and polled by
   `launch/poll_kaggle.sh`; each output archive's digest is checked against the digest its notebook printed
   (`fgc/fetch.py TEST_k test`). A kernel that fails is measured again from the same frozen package (the measurement
   is deterministic); that is the only recovery.
4. **Seal.** `python -m fgc.pipeline seal runs/test/measure runs/test` under the gate's seal stage: every arm's
   committed predictions at every budget, without labels; SEALED_PREDICTIONS.json and SEALED_SHA256 are committed
   before scoring.
5. **Score.** `python -m fgc.pipeline score runs/test runs/test/evaluator_only/TEST_EVAL.json runs/test/measure
   runs/test` under the gate's score stage: ANALYSIS.json with the decision.
6. **Report and post-score audit** by our reviewer.
Recovery of a failed build, pre-declared: generation is deterministic; if it fails after the claim, the
coordinator may once remove runs/RUN_CLAIM.json and any partial runs/test/, log that in PROGRESS.md with the reason,
and run step 2 again under the same GO (the same salt). A second failure ends the test.

**Cost.** Source set: generation about 15 minutes in one CPU slot; measurement 9,600 CPU-seconds on Kaggle for 71
tasks (search 8,500, construction 1,000, base 120), about 20 minutes per kernel. The held set (at most 54 tasks)
needs about the same: generation 15 to 30 minutes, three kernels of about 20 minutes, sealing and scoring under a
minute. Budgets are in calls, so the machine changes no result.

## 11. Files and freeze

Frozen (FREEZE.json, with sha256): this file; `fgc/*.py`; `config/STUDY_CONFIG.json`, `config/POOLS.json`,
`config/ROUTERS.json`; `launch/*.sh`; `checks/*.json`; the world copies (`runs/worlds/`); the source set and its
measurements (`runs/source/`); every dependency outside this folder that the code imports (the construction test's
`cas/env.py`, `cas/generate.py` and `cas/__init__.py`, S1's `cgrow`, A2, the harness, CAST, arc-dsl); and the ARC
training challenges file the generator reads. The gate (`fgc/gate.py`) re-checks every digest before each stage.
