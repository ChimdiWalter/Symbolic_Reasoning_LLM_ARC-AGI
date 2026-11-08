# Natural-task growth test: protocol (pre-registered; frozen before any held-half run)

Written on 5 Nov 2026 in phase 1. Phase 1 used the source halves only: the split, feasibility, adapter checks and
this protocol. No search has run on a held half, no held test output has been opened, and the ARC-AGI-2 evaluation
set has not been used. The sha256 of this file, the code, the configuration, the split and the phase 1 records are in
`FREEZE.json`. Phase 2 runs only after the coordinator writes `runs/GO_PHASE2` naming the protocol and freeze
digests (section 9). A change after the freeze is a dated amendment with a new freeze, made before any held outcome.

## 1. Question and claim limit

**Question.** On natural ARC-style tasks, does growth from the system's own failures add exact correct answers on
tasks the system could not solve before, beyond what the same CPU time spent on plain search adds?

**The growth machinery** (the construction test of the capability growth study,
`experiments/capability_growth_20261027/`, reused unchanged):
- the controller runs the base search; on a failure it derives typed holes (input and target grid pairs that a
  missing operation would have to map) from the demonstrations;
- a candidate operation is constructed from a pre-registered structure space (section 3.3) when it maps every hole
  input exactly to its target;
- the candidate is verified on the demonstrations (novelty gate, retry of the task with the operation added), then
  checked for regressions and validated on other failures;
- a validated operation is promoted into a persistent registry and reused on new tasks.

On the constructed tasks of that study it recovered 8 of 11 tasks, against 0 of 11 with shuffled holes and 5 of 11
for matched static search.

**Claim limit.**
- The structure space is the construction test's (211 whole-grid structures), frozen before these benchmarks were
  downloaded. A gain would show that failure-derived selection from this space helps natural tasks. A null result
  says nothing about other structure spaces.
- The held halves come from the same task families as the source halves. A gain is transfer within a family
  (1D-ARC type, ConceptARC concept, Mini-ARC pool), not across families.

## 2. Data, families and the split

**Benchmarks.** These are the public ARC-style benchmarks of the universality study. Provenance, commits, licences
and the sha256 of every file are in `experiments/universality_similar_problems_20261102/DATA_MANIFEST.json`. The
prepared files are in `/path/to/benchmark_data/prepared/`, read only and read with
`python -I`.

| benchmark | tasks | test outputs | families | source tasks (outputs) | held tasks (outputs) |
|---|---|---|---|---|---|
| ConceptARC | 160 | 480 | 16 concepts | 80 (240) | 80 (240) |
| Mini-ARC (5 x 5 grids) | 149 | 149 | one pool | 74 (74) | 75 (75) |
| 1D-ARC (one row, at most 30 cells) | 615 | 615 | 14 types | 306 (306) | 309 (309) |
| all | 924 | 1,244 | 31 | 460 (620) | 464 (624) |

- **What the system sees.** The searches see `real.json` only: demonstrations and test inputs.
- **Test outputs.** Only the scorer opens `solutions_scorer_only/solutions.json`.
- **Overlap.** No benchmark task shares an input and output pair with ARC-AGI-2 (the universality study's freshness
  rules).

**Family.** A family is a 1D-ARC task type or a ConceptARC concept: the folder the authors put the task in. Mini-ARC
has no groups and forms a single pool.

**Split** (`split/SPLIT.json`, sha256 `0bce7bc1f6372e3fd44f97da64ecb3a70d2c36fe5d11bb623a0f42aed0d67e0d`, committed
in d8e4b4bc before any search ran on any task).
- Within each family, tasks are ordered by sha256("natural-growth-20261105|split|" + benchmark + "|" + the task's
  original file path).
- The first floor(n/2) tasks form the **source half** and the rest the **held half**. The held half takes the extra
  task of an odd family.
- **Source half.** A failed search may trigger construction and promotion here.
- **Held half.** It is for reuse only, and its answers are the primary outcome.

## 3. The system

### 3.1 G0 and the search

- **G0.** A2's arc-dsl grammar: the productions, function leaves and constants of the arc-dsl solvers verified on 194
  tasks of the project's training split of the ARC-AGI-2 training set, with A2's integer costs
  (`cgrow.lang0.build_g0(())`). Nothing is removed: on natural tasks there is no
  deliberately missing operation, so the system is the grammar as it stands. Its digest, over the production heads,
  function leaves and costs, is `63215cce7d07fceba6bf6930cb20d02a438c1dc836683072d4153f1a23eaddaa`.
- **Base search.** A2's bottom-up enumeration (`cgrow/search.py`): 150,000 primitive executions, a CPU-time cap of
  20 CPU-s, cost levels up to 24, at most 400 function-valued closures.
- **Fit and attempts.** A program fits when it reproduces every demonstration output exactly. The two attempts are
  the first two fitting programs with distinct test predictions; with one fitting program, both attempts are its
  prediction.
- **Abstention.** A search that finds no fitting program gives no answer.
- **Phase 1 timing.** On every source task the base search stopped on its execution budget (or on two fits), never
  on the CPU cap, so it is deterministic. It took under 4 CPU-s: a mean of 1.4 on ConceptARC, 0.7 on Mini-ARC and 0.6
  on 1D-ARC.

### 3.2 The controller (`cgrow/controller.py`, unchanged)

When the base search fails, the controller:
1. runs the **deeper-search probe** at 4x the budget and the cap;
2. records the shape relation, the closest program (section 4) and the typed holes;
3. decides:
   - CONTINUE_PROGRAM_SEARCH if the probe fits;
   - INVENT_NEW_OPERATION if it does not and the task has at least two demonstrations;
   - REQUEST_ADDITIONAL_ADMISSIBLE_EVIDENCE if it has fewer than two.

### 3.3 Structure space and gates (`cgrow/schema.py`, `cgrow/selfext_core.py`, unchanged)

**Structure space.** SIGMA has 211 structures in four families, 44 of them with a parameter k in {2, 3, 4}:
- row and column selection by predicate;
- separable index maps, optionally transposed;
- k x k block reduction;
- colour replacement or exchange.

The seed-0 order (`random.Random("s1-order-0")`) is used by every method. An added structure is one production
(Grid[, Integer]) -> Grid with cost 3 and charge 1, and takes every parameter value through its integer argument.

**Gates**, in order, as in the construction test:
1. **Novelty.** The structure is rejected as a search shortcut when a G0 program found by the base search on 12 probe
   grids (200,000 executions, 10 CPU-s) reproduces it at every defined parameter value.
2. **Retry.** The unit's task is searched again with G0 plus the structure at the base budget, at most 3 retries per
   unit.
3. **Regression,** for a structure that fits its task. It is checked on U, the benchmark's source tasks that G0
   solves at the base budget. A lost fit or a changed first prediction means rolled back.
4. **Validation.** It is tried on the benchmark's other unsolved source tasks in sha256("pool:" + id) order, at most 30
   of them. One new fit means promoted; none means quarantined (task-local).

A unit stops at its first promoted structure.

## 4. Definitions used by the analysis (from the controller code)

- **Failure.** G0's base search finds no fitting program.
- **Partial fit.** This is the controller's closest program. During the base search, A2's enumerator (`bus.search`
  with `track_partial=True`) keeps, among the enumerated grid-valued programs that do not fit (the input grid itself
  included), those whose output on every demonstration has that demonstration's output shape. The closest program is
  the one with the most demonstration cells equal to the target; on ties it is the first enumerated (recorded as
  `closest` by `cgrow/controller.py` and as `partial_fit` by `ngrow/held.py`).
- **Localisable failure.** A failure whose closest program exists and gets at least one demonstration cell right.
  - Its residual (the cells it gets wrong) localises what is missing.
  - On the source halves this and the bare criterion "a closest program exists" give the same counts
    (section 10).
- **Typed holes.** These are the controller's sketches, each a set of (hole input, hole target) grid pairs of type
  Grid -> Grid:
  - identity ?(I): the demonstrations themselves;
  - outer B(?(I)) for each invertible G0 unary grid operation B: (input, B^-1(output));
  - inner ?(A(I)) for each invertible A: (A(input), output).

  They are ranked by how much of the target the hole input already explains; the identity plus the two best others
  are kept. Every failure with at least two demonstrations has at least the identity hole.
- **Constructible hole.** A hole for which some structure of SIGMA, at some parameter value, maps every hole input
  exactly to its target. Only a constructible hole yields a candidate.

## 5. Methods

**On the source half (construction).** A unit is a source task on which the controller decided INVENT_NEW_OPERATION.
Every unit starts from G0, and the methods differ only in where their candidates come from.

| method | code label | candidates come from |
|---|---|---|
| growth from the system's own holes | S-hole | the unit's own typed holes, in the controller's rank order; per hole, the structures in seed order that map every hole input to its target |
| shuffled holes | S-shuffled | the typed holes of a donor failure from another family (the rule below) |
| demonstrations only | S-demo | the identity hole only (no decomposition) |
| blind enumeration | S-enum | no holes: every structure in seed order is added to G0 and the unit's task retried, until the unit has been charged 60 CPU-s |

- **Blind enumeration's charge.** Each gate result is charged to every unit that uses it, at the CPU of its first
  computation (the construction test's rule). Cached novelty searches therefore count against every unit, and a unit
  reaches its 60 CPU-s after 12 to 19 non-shortcut structures (phase 1).
- **Donor rule.** The benchmark's units are ordered by sha256("donor:" + id), and a unit's donor is the next unit in
  that cyclic order from another family. Mini-ARC is one pool, so its donor is simply the next unit.
- **Registry,** for each method and benchmark. It holds the promoted structures in unit order, without repeats. The
  grown grammar is G0 plus the registry.
- **Combined regression check.** The grown grammar is run on every task of U. While a fit is lost or a first
  prediction changes, the most recently added structure is removed and the check repeats.

**On the held half (reuse only, no construction).** Every held task is searched once by each arm:

| arm | search on each held task |
|---|---|
| G0 alone | G0, base search |
| growth from holes | G0 + the S-hole registry, base search |
| shuffled holes | G0 + the S-shuffled registry, base search |
| demonstrations only | G0 + the S-demo registry, base search |
| blind enumeration | G0 + the S-enum registry, base search |
| matched static search | G0, no execution limit, CPU-time cap T_static(b) per task |

- **Empty registry.** An arm whose registry is empty has exactly G0's grammar. Its answers are G0's, and it is
  charged G0's CPU.
- **Matched static allowance.** Growth pays for all its work, per benchmark b:

  T_static(b) = [controller CPU on every source task of b (base searches and deeper-search probes) + the growth
  method's construction CPU (each distinct gate result charged once, at the CPU of its first computation) + its
  combined regression check + its base searches on the held half of b] / (held tasks of b).

- **Static memory limit.** Each static search runs in a child process limited to 12 GB of address space. A child that
  fails gives no answer, and the failure is recorded.

## 6. Outcomes and populations

- **Correct.** A held test output is correct for an arm when either of its two attempts equals the benchmark's test
  output exactly (pass@2).
- **Answered.** A test output is answered when the arm found a fitting program.
- **Precision** = correct / answered.
- **Task outcome.** The task outcome is its number of correct test outputs: 0 to 3 for ConceptARC, 0 or 1 otherwise.
- **Primary population.** Held tasks whose G0 failure localises (section 4). Membership is computed from the G0 arm's
  own base-search record on each held task (system side), before any held test output is opened.
- **Secondary population.** All held tasks.
- **Stratum size.** The size of the localisable stratum per benchmark is itself reported. The source-half counts are
  in section 10.

## 7. Analysis (`ngrow/analysis.py`, `ngrow/report.py`)

**Paired comparison of arms A and B over the same tasks.**
- Per task, d = (correct outputs under A) - (correct outputs under B).
- **Exact McNemar (sign) test.** n_A counts the tasks with d > 0 and n_B those with d < 0. The test is the two-sided
  exact binomial on n_A of n_A + n_B at 1/2. When every task has one output this is the exact McNemar test.
- **Effect.** The total difference in correct outputs, sum(d).
- **Family-clustered bootstrap 95% interval of sum(d).**
  - Clusters are the families (ConceptARC concepts, 1D-ARC types); Mini-ARC tasks, which have no family, are
    single-task clusters.
  - Clusters are resampled with replacement within each benchmark: 10,000 draws, `random.Random(20261105)`,
    percentile interval.
- **Decision.**
  - "A beats B": p < 0.05 and the interval lies above 0.
  - "B beats A": p < 0.05 and the interval lies below 0.
  - "tie": n_A = n_B.
  - Otherwise "inconclusive".

**Primary.** Growth from holes against matched static search, on the primary population of the three held halves
pooled.

**Secondary,** with p-values Holm-adjusted together over these eight:

| test | comparison |
|---|---|
| S1 | growth from holes vs matched static search, all held tasks (the secondary population) |
| S2 | growth from holes vs shuffled holes, primary population |
| S3 | growth from holes vs blind enumeration, primary population |
| S4 | precision: wrong answers (answered minus correct) per task, growth vs matched static search, all held tasks (a difference in either direction is reported with its sign) |
| S5a, S5b, S5c | growth vs matched static search on ConceptARC, Mini-ARC and 1D-ARC separately, primary population |
| S6 | the ARC-AGI-2 one-shot check (section 8), growth vs matched static search |

**Descriptive, with no decision weight:**
- every arm's correct, answered and precision (with Wilson 95% intervals) on both populations, by benchmark and by
  family;
- growth vs G0 alone; matched static vs G0 alone; blind enumeration vs G0 alone; growth vs demonstrations only;
- the construction funnel per method: units, candidates, novelty rejections, retries, fits, correct motivating
  predictions, promotions, roll-backs, quarantines and registries;
- CPU per unit and per arm.

## 8. Pre-registered secondary: one-shot check on the ARC-AGI-2 public evaluation set

- **Data.** `outputs/score_first/data/arc-agi_evaluation_challenges.json` (sha256
  `e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8`; 120 tasks, 172 test inputs). Its solutions are
  `outputs/score_first/data/arc-agi_evaluation_solutions.json` (sha256
  `84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1`), opened by the scorer only after every arm has
  finished.
- **Not in phase 1.** Phase 1 neither runs these tasks nor uses them for feasibility (only the task and test-input
  counts were read).
- **Arms,** each applied once to the 120 tasks:
  - **G0 alone,** base search;
  - **growth,** G0 plus the union of the three benchmarks' frozen growth-from-holes registries: ConceptARC, then
    Mini-ARC, then 1D-ARC, each in its own order, repeats dropped. An empty union means growth's grammar is G0;
  - **matched static search,** G0 at the pooled held-half allowance: the three benchmarks' growth totals summed,
    divided by their 464 held tasks.
- **Same caps.** These are the same CPU-time caps and the same analysis as above (S6 in the Holm family).
- **Exposure.** This set was used in earlier development and gates of the project (the scored entries were developed
  and checked against it). It is not a fresh test, and a gain on it would be reported with that caveat.
- **A zero is reported as a zero.**

## 9. Seeds, CPU-time caps, stop rules, GO and freeze

**Seeds and randomness.**
- Structure order: seed 0 for every method.
- Bootstrap: `random.Random(20261105)`.
- PYTHONHASHSEED=0.
- Nothing else is random.

**CPU-time caps** are process CPU time (`time.process_time`), never wall-clock:
- base search 20 CPU-s;
- deeper-search probe 80 CPU-s;
- novelty search 10 CPU-s;
- blind enumeration 60 charged CPU-s per unit;
- matched static T_static(b) as measured on the machine that runs it.

The search caps keep their frozen values. Every phase 1 search stopped on its fixed execution budget, so they stop
nothing in practice, and a cap-bound stop is recorded if one occurs. Blind enumeration's 60 CPU-s per unit is the one
CPU-defined stop that binds. It is multiplied by the kernel's speed factor, so that it covers the same structures as
on Athe: the median CPU time of a fixed 200,000-execution search (`ngrow/bench.py`, five repeats) divided by its Athe
reference, clipped to [0.5, 2].

**Stop rules.**
- Per unit: 3 retries for the hole methods; 60 charged CPU-s for blind enumeration.
- Per kernel: no stage starts once the kernel's children have used 30 CPU-h. The run is then INCOMPLETE and reported
  as such, with every finished arm.
- **A failed kernel.** It is resumed from its durable records (finished tasks and units are skipped), never re-run
  with changed code.
- **A missing arm.** An arm missing for some held tasks is reported as missing; it is never imputed.

**GO.**
- `runs/GO_PHASE2`, written once by the coordinator, has as its first two lines exactly
  "protocol_sha256 <sha256 of PROTOCOL.md>" and "freeze_sha256 <sha256 of FREEZE.json>".
- `ngrow/gate.py` checks it, and every frozen file's digest, before any held task, held test output or ARC-AGI-2 file
  is opened (held runs, the static allowance, the ARC-AGI-2 arms, scoring).
- The GO authorises one execution of the phase 2 kernels and of the scoring.

**Freeze.** `FREEZE.json` holds the sha256 of:
- this protocol, the configuration (`config/STUDY_CONFIG.json`) and the split;
- every code file this study executes, its own and the reused ones;
- the benchmark files;
- the phase 1 records.

## 10. Feasibility (phase 1, source halves only)

Records: `feasibility/controller_source_shard{0,1}.jsonl` (controller), `feasibility/grow/<benchmark>/` (methods),
`feasibility/FEASIBILITY.json` (summary, `ngrow/feasibility.py`). The evaluator scored source test outputs only.

| source half | ConceptARC | Mini-ARC | 1D-ARC | all |
|---|---|---|---|---|
| tasks (test outputs) | 80 (240) | 74 (74) | 306 (306) | 460 (620) |
| G0 base search: tasks fit; correct outputs (answered) | 1; 1 (3) | 6; 6 (6) | 0; 0 (0) | 7; 7 (9) |
| G0 at 4x (base, then the deeper-search probe): tasks fit; correct outputs (answered) | 5; 11 (15) | 6; 6 (6) | 23; 23 (23) | 34; 40 (44) |
| base-search failures | 79 | 68 | 306 | 453 |
| localisable failures (partial fit with at least one cell right) | 62 | 68 | 306 | 436 (96%) |
| controller decisions: deeper search, construct, more evidence | 4, 74, 1 | 0, 68, 0 | 23, 283, 0 | 27, 425, 1 |
| typed holes per construction unit | 3 | 3 | 3 | 3 |
| construction units with a constructible hole | 0 of 74 | 0 of 68 | 0 of 283 | **0 of 425** |
| near misses (a structure matches at least half of some hole's pairs exactly) | 6 | 1 | 5 | 12 |
| growth from holes, shuffled holes, demonstrations only: candidates; promotions | 0; 0 | 0; 0 | 0; 0 | 0; 0 |
| novelty gate under the full G0 (first structures in seed order): checked; rejected as G0 shortcuts | 35; 16 | 33; 16 | 33; 16 | |
| blind enumeration sample (first 2 units of each family): units; structures retried; fits; promotions | 32; 471; 0; 0 | 2; 34; 0; 0 | 26; 442; 0; 0 | 60; 947; 0; 0 |
| CPU per unit, blind enumeration: charged by rule; actual (median) | 62.6; 21.7 CPU-s | 61.5; 36.8 CPU-s (2 units) | 61.6; 10.1 CPU-s | |
| CPU per task, controller (median; mean) | 6.35; 6.74 CPU-s | 3.52; 3.34 CPU-s | 2.61; 2.60 CPU-s | total 1,583 CPU-s (0.44 CPU-h) |

What these numbers say:
- **Localisation is not the bottleneck here.**
  - 96% of the base-search failures localise by the controller's own criterion: the bare criterion and the one-cell
    criterion give the same counts.
  - The reason is that the input grid itself is a right-shaped program whenever the output has the input's size,
    and so are many cheap edits of it.
  - So the premise that natural failures do not localise does not hold for this controller.
- **Constructibility is the bottleneck.**
  - Every construction unit has typed holes, but no hole of any of the 425 natural failures is mapped exactly by any
    of the 211 structures.
  - The structure space describes whole-grid index maps, selections, block reductions and colour maps. The natural
    holes are object-level transformations (moving or recolouring a segment, filling between pixels, extracting an
    object).
  - The same candidate step finds candidates for 14 of the 19 construction units of the construction test's own world
    (checked on its frozen records).
- **G0 itself.** At the base budget G0 answers almost nothing on these benchmarks. Deeper search adds answers on
  1D-ARC (23 tasks at 4x) and ConceptARC (4 tasks).
- **Timing.** Every base search and probe stopped on its execution budget, never on a CPU cap, so the controller's
  records are deterministic. Phase 2 reruns them from the frozen code, and its controller decisions must equal phase
  1's (a plumbing check, reported).

## 11. Power and the honest expectation

From `power/POWER.json` (`ngrow/power.py`). Expected held quantities are the source-half counts scaled by held/source
tasks per benchmark.

**1. Growth adds nothing to G0 here.**
- In phase 1 no method that uses holes promoted any structure, and the blind-enumeration sample promoted none either.
- Phase 2 reruns the controller and the methods from the frozen code. The searches stop on fixed execution budgets,
  and the candidate step is a pure function of the controller's records, so the same empty registries are expected.
- Growth's grammar on the held half is then exactly G0's, and so are its answers.

**2. The primary comparison cannot favour growth.**
- On the primary population G0 fails every task by definition, so growth answers none of them correctly. The count
  of tasks only growth answers is 0 with certainty, and P(growth beats matched static search) = 0.
- Matched static search answers what deeper search adds there.
- **Estimated allowance.** T_static is about 8.2 CPU-s per held task on ConceptARC, 4.0 on Mini-ARC and 3.1 on
  1D-ARC, about 5.6 times the base search's CPU; pooled, 4.15 CPU-s (empty registries, phase 1 CPU).
- **Source analogue.** At only 4x the base budget, deeper search already solved 25 of the 436 localisable
  source failures correctly (ConceptARC 2, Mini-ARC 0, 1D-ARC 23).
- **Expected primary population** on the held halves: about 440 tasks (ConceptARC 62, Mini-ARC 69, 1D-ARC 309).
- **Expected static-only primary tasks** on the held halves: about 25 (ConceptARC 2, Mini-ARC 0, 1D-ARC 23).
- **Thresholds.** The exact test needs at least 6 discordant tasks in one direction for p < 0.05. P(matched static
  search beats growth) = 1.00 (Poisson simulation).

**3. Scale of the gap.**
- For growth to win with 80% power against about 25 static-only tasks, growth would need about 50 primary held tasks
  that static search misses.
- Even 20 such tasks would give a power of 0.002.
- Phase 1 shows a candidate supply of zero.

**4. The secondaries follow.**

| test | expected outcome |
|---|---|
| S1 (all held tasks) and S5 (per benchmark) | mirror the primary |
| S2 (shuffled holes) | an exact tie, because all registries are empty |
| S3 (blind enumeration) | an exact tie, unless blind enumeration on all 425 units promotes a structure (none in the 60-unit sample) |
| S4 (wrong answers) | counts static search's extra wrong answers |
| S6 (ARC-AGI-2) | growth equals G0 by construction, so a zero gain is certain |

**5. Honest expectation: a clear negative.**
- On these natural benchmarks, failure-grounded growth with this structure space adds no correct answer, because no
  natural failure yields a constructible hole.
- Matched static search is expected to beat it on the primary population.
- This is stated before any held task is touched.

## 12. Compute plan

**Phase 2 kernels.** They are private Kaggle kernels, CPU only, internet off, 4 worker processes each. They are
built after the GO by `ngrow/kaggle_build.py` and pushed with the Kaggle command-line tool under the project account.

| kernel | runs | needs |
|---|---|---|
| A | ConceptARC and Mini-ARC: every stage of `ngrow/phase2.py` | the GO |
| B | 1D-ARC: every stage | the GO |
| C | the ARC-AGI-2 check | the registries and static allowances of A and B, packed into C's archive by the build |

No package carries a test output. The outputs are downloaded, their OUTPUT_MANIFEST.json is verified, and scoring
runs on Athe (`run.py report`, one CPU slot, minutes).

**Estimated CPU,** from the phase 1 measurements on Athe (in the replay of the construction test, Kaggle's CPUs were
about 1.1 times slower than Athe's):

| stage | estimate |
|---|---|
| controller on the 460 source tasks | 1,583 CPU-s |
| hole-based methods | about 0 (no candidates) |
| blind enumeration on all 425 units | charged 60 CPU-s per unit by rule, actually about 10 (1D-ARC) to 22 (ConceptARC) CPU-s per unit once novelty results are shared: about 1.5 CPU-h |
| held half: G0 | 464 base searches, about 400 CPU-s |
| held half: the four grown arms | copies of G0 while their registries are empty |
| held half: matched static | about 1,920 CPU-s plus about 3 CPU-s of grammar building per child process |
| ARC-AGI-2: G0 | about 120 x 3 CPU-s |
| ARC-AGI-2: matched static | 120 x the pooled allowance |

- **Total.** About 4 CPU-h, about 1 hour of wall time per kernel.
- **Ceiling.** 30 CPU-h per kernel.
- **GPU.** None.

## 13. Adapter changes (the smallest that work; no existing file is changed)

No file of the growth study, of A2 or of any other experiment is changed. The study imports
`cgrow.controller`, `cgrow.search`, `cgrow.schema`, `cgrow.lang0`, `cgrow.probes` and `cgrow.selfext_core` read-only
and adds these adapters in `ngrow/`:

1. **Natural tasks** (`data.py`). Tasks come from the benchmark files: the system view is the demonstrations and test
   inputs. They replace the growth study's constructed task files and split-guarded loader.
2. **G0 with nothing removed** (`plugin.py`). The construction test removed four operations; here G0 is A2's whole
   grammar.
3. **Plug-in** (`plugin.py`). It implements the shared core's plug-in interface for the natural G0.
   - The production function of a structure is identical to the construction test's.
   - The novelty probe grids are recomputed from `cgrow.probes` with the same seed, rather than imported from
     `cgrow.episode`, which loads the sandbox for model-written code. Their equality is checked.
4. **Validation cap.** At most 30 pool tasks are tried per promotion (`grow.py`). The construction test's pool had 23
   tasks; natural pools have up to 283, and each try is a base search.
5. **Per-method charge.** Each distinct gate result a method used is charged once, at the CPU of its first
   computation. This is in addition to the shared core's per-unit charge, and makes the static allowance independent
   of the order in which methods share the gate cache.
6. **Persistent registry over many units, per benchmark.** The construction test promoted at most one structure per
   unit and never combined them. Here the promoted structures of a method accumulate in unit order, and the combined
   regression check (section 5) guards the grown grammar.
7. **Per-benchmark sets.** The regression set U and the validation pool are taken from the source half of the same
   benchmark.
8. **Donor rule for shuffled holes.** The construction test took the same-slot motivating task of the next family.
   Here the rule is a hash-ordered cycle over the benchmark's units, which works for any number of units per family
   and for Mini-ARC's single pool.
9. **Scoring** (`score.py`). Success is an exact match to the benchmark's test output, per test output, pass@2, with
   several outputs per task where the benchmark has them; a search without a fit abstains. There is no reference
   operation, so the construction test's agreement-with-the-removed-operation scores do not apply.
10. **Controller records stored as JSON** (`controller_run.py`): tuples become lists, and the closest program is shown
    as text. The controller's list of competing hypotheses is dropped from the stored record; no method uses it.
11. **CPU-time comparability** (`bench.py`). A speed factor, measured on each kernel against the Athe reference of
    1.432 CPU-s, multiplies blind enumeration's 60 CPU-s threshold. The threshold is set through the shared core's
    module constant at run time; the search caps keep their frozen values (section 9).
12. **The held-half arms** (`held.py`, `arc2.py`) and the matched static search with its allowance computed from
    growth's total; the GO gate (`gate.py`); a write guard that refuses any write outside this folder (`env.py`).

**Checks (phase 1, passed).**
- **Equivalence** (`checks/EQUIVALENCE.json`). On the construction test's own world (its G0, controller records and
  tasks), this study's gates and plug-in rerun its three hole-based methods. They reproduce all 99 of 99 recorded units
  (the promoted structure, the retries and the recovery), and the recomputed probe grids are equal.
- **Dry run** (`checks/dry_run/`). Every phase 2 code path (the held arms, matched static search in child processes,
  the ARC-AGI-2 arms and the report) ran on two source tasks per benchmark standing in for the held halves, with exit
  code 0. Its numbers mean nothing.

## 14. Boundaries

- **Athe.** At most two CPU processes, through `scripts/with_cpu_slot.sh` at nice 19.
- **Kaggle.** Phase 2 runs on private Kaggle kernels, CPU only, internet off. Their packages carry demonstrations and
  test inputs only; scoring happens on Athe.
- **Off limits.** Never Step B, VDCG, other projects' job folders, GPU 1, or anything public.
- **Sibling work.** The construction test at scale (`experiments/construction_at_scale_20261105/`) is separate work
  and was not edited.
- **The independent team.** Its outcomes on these benchmarks were not read.

## 15. Outputs and reporting

- **Phase 2 outputs.** `runs/phase2/<kernel>/`, with STAGES.json, OUTPUT_MANIFEST.json and every arm's per-task
  records. The scorer writes RESULTS.json and REPORT.md.
- **Record.** It states every number, including empty registries, missing arms and the stratum sizes, with a claim
  for the paper written whichever way the result falls.
