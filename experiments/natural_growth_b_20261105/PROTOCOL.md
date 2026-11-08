# Library-transfer test (study B): protocol (pre-registered; frozen before any held-half run)

Written on 5 and 6 Nov 2026 from the source halves only. No search has run on a held half, no held test output has
been opened, and the ARC-AGI-2 evaluation set has not been used. The sha256 of this file, the code, the
configuration, the split, the frozen libraries and the phase 1 records are in `FREEZE.json`, which also holds the
slot for the object-level growth code (section 5). Phase 2 runs only after the coordinator writes `runs/GO`
(section 9). A change after the freeze is a dated amendment with a new freeze, made before any held outcome.

## 1. Question and claim limit

**Question.** Does learning accumulate across natural ARC-style tasks? Two routes are tested on the same held tasks:
- **the library route:** operations promoted from the programs that the system found on the source half with extra
  budget (4x) are added to the grammar; do they raise base-budget coverage on the held half of the same benchmark,
  and is the rise reach (answers that the same CPU spent on plain search cannot buy) or only efficiency?
- **the object-level growth route:** operations constructed from the system's own failures on the source half by the
  object-level growth builder (`experiments/object_growth_20261105/`, built separately); do they add exact answers on
  the held half beyond matched static search?

**Claim limit.**
- The held halves come from the same task families as the source halves. A gain is transfer within a benchmark
  (and, descriptively, within a family), not to new domains.
- A library entry is a program the system itself found; the test asks whether re-using it as one operation pays,
  not whether the system can invent anything.
- Study A (`experiments/natural_growth_20261105/PHASE1_RESULT.md`) showed that the construction test's whole-grid
  structure space has no candidate for any natural failure. Arms 5 and 6 test the object-level route built to
  address that; their code is not this study's and is frozen separately (section 5).

## 2. Data, families and the split (study A's, reused)

The benchmarks, families and the source/held split are study A's, unchanged (`experiments/natural_growth_20261105/`,
protocol section 2; `split/SPLIT.json`, sha256 `0bce7bc1f6372e3fd44f97da64ecb3a70d2c36fe5d11bb623a0f42aed0d67e0d`,
committed in d8e4b4bc before any search ran on any task).

| benchmark | source tasks (outputs) | held tasks (outputs) | families |
|---|---|---|---|
| ConceptARC | 80 (240) | 80 (240) | 16 concepts, 5 held tasks each |
| Mini-ARC | 74 (74) | 75 (75) | one pool |
| 1D-ARC | 306 (306) | 309 (309) | 14 types, 4 to 26 held tasks each |
| all | 460 (620) | 464 (624) | 31 |

- The searches see demonstrations and test inputs only. Only the scorer opens test outputs, behind the GO gate
  for the held halves.
- **Source half:** every search with extra budget, every promotion and every construction happens here.
- **Held half:** reuse only; its answers are the outcome.

## 3. The system

- **G0 and the base search:** study A's (protocol section 3.1): A2's whole arc-dsl grammar (digest `63215cce…`),
  150,000 primitive executions, a CPU cap of 20 CPU-s that never binds in practice, two attempts (the first two
  fitting programs with distinct test predictions), abstention when nothing fits.
- **Extra budget (discovery):** on a base-search failure, the search at 4x (600,000 executions, 80 CPU-s): the
  first two steps of the growth controller, re-run here on every source task (`ngb/discover.py`, stage 1).
- **Added operations:** one production each, signature (Grid[, Integer]) -> Grid, cost 3, charge 1, as in the
  construction test.
- **Hash seed.** A2's enumeration order within a cost level depends on Python's hash seed (iteration over a set of
  type tags), so two equal-cost programs with the same outputs can swap places between processes. Which tasks fit,
  and the predictions, do not depend on it. Study B runs everything with PYTHONHASHSEED=0; stage 1 ran before this
  was found and is checked against study A's frozen controller records by which tasks fit at base and at 4x.

## 4. The library (arm 2) and the shuffled library (arm 3): built in phase 1, frozen

**Candidates,** per solution tree found in stage 1, in this order (`ngb/ops.py`):
1. the whole tree, as the unary operation grid -> tree[I := grid];
2. every proper subtree that contains the input leaf, applies at least one primitive and is grid-valued on the
   source task's own grids;
3. for each of these, every variant with one integer-constant leaf replaced by an integer parameter (values -2 to
   10, G0's integer constants).

A candidate seen on an earlier source task is not repeated; every source task that produced it is recorded.

**Gates,** per candidate in order, the growth study's code unchanged (`cgrow/selfext_core.py` through study A's
`CappedGates`):
1. **Novelty.** Rejected as a search shortcut when a G0 program found by the base search on the 12 probe grids within
   200,000 executions (cost level 9 complete) reproduces it at every defined parameter value. So a base-budget
   solution, whose cost is at most 10 and usually far less, is rejected; the library holds what is hard to express.
2. **Redundancy.** Rejected when its behaviour on the probe grids and its sources' inputs equals an already promoted
   operation's.
3. **Regression** on U, the benchmark's source tasks G0 solves at base: a lost fit or a changed first prediction
   means rolled back.

A candidate that passes is **promoted**. No validation on other tasks is required: an entry is admitted for being
hard to express, not for proven reuse (the in-sample reuse is reported, section 10).

**Library L(b),** per benchmark: the promoted operations in order (source family, source task, candidate order). The
combined regression check runs G0 plus the library on every task of U and removes the most recent entry while a fit
is lost or a first prediction changes. The library's construction cost is the discovery CPU over every source task
of the benchmark (finding the solutions cost the failed searches too) plus the gates' CPU (each distinct gate result
charged once) plus the combined check.

**Shuffled library S(b):** the first |L(b)| operations of the other two benchmarks' libraries, in
sha256("shuffle:" + b + "|" + operation id) order. When the other benchmarks hold fewer, S(b) is smaller and the
shortfall is reported.

Both are frozen in phase 1 (`feasibility/library/<benchmark>/library.json`, `feasibility/library/shuffled.json`);
phase 2 only reuses them.

## 5. Object-level growth (arms 5 and 6): the builder's frozen code, through a contract

- **What it is.** Operations constructed from the system's own typed holes on the source-half failures by the
  object-level growth builder (`experiments/object_growth_20261105/`; code freeze announced by the coordinator, due by
  7 Nov 00:00Z). Arm 5 uses the registry built from each failure's own holes; arm 6 the registry built with shuffled
  holes (another family's failure), by the builder's own donor rule.
- **This study did not read that tree** and will not until the coordinator announces its freeze.
- **Contract** (`ngb/object_arm.py`; filled into `config/STUDY_CONFIG.json` by a dated amendment):
  - `make_ops(benchmark, variant)` with variant "own" or "shuffled" returns the registry as operation objects (an id,
    whether it takes an integer parameter, its parameter values, and a call grid[, k] -> grid or undefined), built
    from the source half only;
  - `construction_cpu_s(benchmark, variant)` returns every CPU-second the builder spent on the source half for that
    registry (its controller, construction and gates), which is charged to the arm.
- **Freeze slot.** `FREEZE.json` has `object_growth` with `code_sha256` null until the amendment fills it with the
  sha256 over every file of the builder's folder (and their individual digests). The gate refuses a held run while
  the slot is empty and the GO names arm 5 vs arm 4 as the primary.
- **Not available.** Until the amendment, arms 5 and 6 are G0 (their rows are copies of G0's, marked "not
  available"), and the pre-registered rule makes arm 2 vs arm 1 the primary (section 7).

## 6. Arms on the held halves (reuse only), outcomes

Every held task is searched once per arm at the base budget, except the static arms:

| arm | code label | search on each held task |
|---|---|---|
| 1 | G0 | G0 alone, base search |
| 2 | lib | G0 plus L(b), base search |
| 3 | shuf | G0 plus S(b), base search |
| 4a | static_lib | G0, no execution limit, CPU cap T(b, lib) per task |
| 4b | static_obj | G0, no execution limit, CPU cap T(b, obj) per task |
| 5 | obj | G0 plus the object-level registry (own holes), base search |
| 6 | obj_shuf | G0 plus the object-level registry (shuffled holes), base search |

- **Matched static allowance,** per benchmark b and growth arm: T(b, arm) = [the arm's whole source-half cost (the
  library: discovery over every source task, gates, combined check; object growth: the builder's reported cost),
  measured on Athe and scaled by the kernel's speed factor, plus the arm's base searches on the held half of b,
  measured on the kernel] / (held tasks of b). Growth pays for all its work. Static searches run in child processes
  limited to 12 GB of address space; a failed child gives no answer and is recorded. Arm 4b runs only when object
  growth is available.
- **Empty registry.** An arm whose registry is empty has exactly G0's grammar; its rows are copies of G0's, marked.
- **Correct.** A held test output is correct when either attempt equals the benchmark's test output exactly (pass@2).
  **Answered:** the arm found a fitting program. **Precision** = correct / answered. **Task outcome:** its number of
  correct test outputs (0 to 3 for ConceptARC, 0 or 1 otherwise).
- **Population.** All held tasks. The localisable stratum (study A's definition: G0 fails and its closest program
  gets at least one cell right, from the G0 arm's own record) is reported descriptively.

## 7. Analysis (`ngrow/analysis.py`, `ngb/report.py`)

**Paired comparison of arms A and B** over the same tasks, study A's procedure: per task d = (correct outputs under
A) - (under B); the exact McNemar (sign) test on the tasks with d > 0 against d < 0; the effect sum(d) with a
family-clustered bootstrap 95% interval (clusters: ConceptARC concepts and 1D-ARC types; Mini-ARC tasks are
single-task clusters; resampled with replacement within each benchmark, 10,000 draws, `random.Random(20261105)`).
**Decision:** "A beats B" if p < 0.05 and the interval lies above 0; "B beats A" if p < 0.05 and it lies below 0;
"tie" if the discordant counts are equal; otherwise "inconclusive".

**Primary, keyed to the builder's reported funnel (pre-registered rule).**
- If the object-level growth builder reports **at least one promoted operation by 6 Nov 2026 12:00Z**, the primary is
  **arm 5 vs arm 4b** (object-level growth against matched static search at the object allowance).
- Otherwise the primary is **arm 2 vs arm 1** (the library against G0 alone).
- The coordinator applies the rule and writes the choice as the GO's third line ("primary arm5_vs_arm4" or
  "primary arm2_vs_arm1"); the analysis reads it from the GO and has no discretion.

**Secondaries,** Holm-adjusted together:

| test | comparison |
|---|---|
| S0 | the other candidate primary (arm 2 vs arm 1, or arm 5 vs arm 4b) |
| S1 | reach or efficiency: arm 2 vs arm 4a |
| S2 | arm 2 vs arm 3 (the library against a shuffled library of the same size) |
| S3 | arm 5 vs arm 6 (own holes against shuffled holes) |
| S4 | precision: wrong answers per task (answered minus correct), arm 2 vs arm 4a |
| S5a, S5b, S5c | arm 2 vs arm 1 on ConceptARC, Mini-ARC and 1D-ARC separately |
| S6 | ARC-AGI-2 check: arm 2's union library vs matched static (section 8) |
| S7 | ARC-AGI-2 check: arm 5's union registry vs matched static (section 8) |

A test whose arms are both G0 (an empty or unavailable registry) is an exact tie and stays in the family.

**Reading reach against efficiency.** The library adds reach when arm 2 beats arm 4a (S1); when S1 is a tie or
inconclusive while arm 2 beats arm 1, the library bought only what the same CPU buys in plain search (efficiency).

**Descriptive, no decision weight:** every arm's correct, answered and precision with Wilson 95% intervals, by
benchmark and by family; arm 2 vs arm 1 by family; the static arms, arm 3, arm 5 and arm 6 against G0; arm 2 vs
arm 5; the localisable stratum; the construction funnels (candidates, shortcuts, redundancies, roll-backs,
promotions, library sizes, CPU).

## 8. Pre-registered secondary: one-shot check on the ARC-AGI-2 public evaluation set

- **Data:** study A's pinned `outputs/score_first/data/arc-agi_evaluation_challenges.json` (sha256
  `e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8`; 120 tasks, 172 test inputs); solutions
  `arc-agi_evaluation_solutions.json` (sha256 `84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1`),
  opened by the scorer only after every arm has finished. Not used in phase 1 beyond the counts.
- **Arms,** each once: G0; G0 plus the union of the three libraries (ConceptARC, Mini-ARC, 1D-ARC order, repeats
  dropped); G0 plus the union of the three object-level registries (own holes); matched static search at the pooled
  held-half allowance of the library arm, and of the object arm (the three benchmarks' totals summed over their 464
  held tasks). An empty union means the arm's grammar is G0.
- **Same caps, same analysis** (S6 and S7 in the Holm family).
- **Exposure.** This set was used in earlier development and gates of the project (the scored entries were developed
  and checked against it). It is not a fresh test; a gain is reported with that caveat, and a zero as a zero.
- **Phase 1 incident (5 Nov, 22:38Z to 22:44Z).** A defect in the first dry run let G0's base search run on the
  demonstrations and test inputs of 95 of the 120 evaluation tasks. No solution was opened, the output rows were
  deleted unread (only counted), and the defect was fixed before the re-run (`PROGRESS.md`). G0's base search is
  deterministic and its code frozen, so the arm it would have informed (arm 1 here) is unaffected; the record is
  kept for the reviewers.

## 9. Seeds, CPU-time caps, stop rules, GO and freeze

- **Seeds and randomness:** PYTHONHASHSEED=0; bootstrap `random.Random(20261105)`; the shuffled library and donor
  rules are hash orders. Nothing else is random.
- **CPU-time caps** are process CPU time, never wall-clock: base search 20 CPU-s and discovery 80 CPU-s (never
  binding in phase 1: every search stopped on its execution budget); novelty 10 CPU-s; matched static T(b, arm) as
  defined in section 6.
- **Speed factor:** study A's benchmark (`ngrow/bench.py`, a fixed 200,000-execution search with no fit, five
  repeats, Athe reference 1.432 CPU-s), clipped to [0.5, 2]; it scales the Athe-measured source-half costs inside the
  static allowances.
- **Stop rules:** per kernel, no stage starts once its children have used 30 CPU-h (the run is then INCOMPLETE and
  reported with every finished arm). A failed kernel is resumed from its durable records, never re-run with changed
  code. A missing arm is reported as missing, never imputed.
- **GO.** `runs/GO`, written once by the coordinator, has as its first three lines exactly
  "protocol_sha256 <sha256 of PROTOCOL.md>", "freeze_sha256 <sha256 of FREEZE.json>" and "primary arm5_vs_arm4" or
  "primary arm2_vs_arm1". `ngb/gate.py` checks these, every frozen file's digest and the object-growth slot before
  any held task, held test output or ARC-AGI-2 file is opened. The GO authorises one execution of the phase 2 kernels
  and of the scoring.
- **Freeze.** `FREEZE.json` holds the sha256 of this protocol, the configuration, the split, every code file this
  study executes (its own, study A's reused modules, the growth code, A2 and arc-dsl), the benchmark files, the
  stage 1 and stage 2 records, the frozen libraries, the power record, and the object-growth slot.

## 10. Feasibility on the source halves (phase 1)

Records: `feasibility/discover_shard{0,1}.jsonl` (stage 1), `feasibility/library/<benchmark>/{discovery_summary,
candidates,library,insample}.json` and `feasibility/library/shuffled.json` (stage 2). Source test outputs were read
only for the in-sample estimates.

**Stage 1 (discovery, every source task; CPU measured on Athe under load).**

| source half | ConceptARC | Mini-ARC | 1D-ARC | all |
|---|---|---|---|---|
| tasks | 80 | 74 | 306 | 460 |
| fit at base; fit only at 4x | 1; 4 | 6; 0 | 0; 23 | 7; 27 |
| agreement with study A's frozen records (which tasks fit at base and at 4x) | exact | exact | exact | exact |
| discovery CPU (base plus 4x on every task) | 639 CPU-s | 297 CPU-s | 973 CPU-s | 1,909 CPU-s |

**Stage 2 (the library).**

| | ConceptARC | Mini-ARC | 1D-ARC |
|---|---|---|---|
| solutions; distinct programs | 5; 5 | 6; 5 | 23; 2 (22 of the 23 are 1d_flip tasks with one identical program) |
| candidates (whole, sub, abstraction) | 6 | 5 | 3 |
| rejected: search shortcut (cheap in G0); redundant; rolled back | 1; 0; 0 | 5; 0; 0 | 0; 0; 0 |
| promoted; library after the combined check | 5; 5 | 0; 0 | 3; 3 |
| library | `fill(I, ZERO, argmax(objects(I, T, T, T), size))`, its abstraction `fill(I, k, ...)`, `paint(I, mapply(dmirror, fgpartition(I)))`, `subgrid(first(objects(I, F, F, T)), I)`, `subgrid(argmax(fgpartition(I), ulcorner), I)` | empty (every base solution is cheap in G0) | `paint(I, vmirror(merge(fgpartition(I))))` (from 22 tasks), `fill(I, TWO, argmax(objects(I, T, T, F), size))`, its abstraction `fill(I, k, ...)` |
| shuffled library: wanted; available from the other benchmarks; shortfall | 5; 3; 2 | 0; 8; 0 | 3; 5; 0 |
| construction CPU (gates and combined check) | 41 CPU-s | 7 CPU-s | 25 CPU-s |
| library's whole source-half cost (discovery plus construction) | 680 CPU-s | 304 CPU-s | 998 CPU-s |

**In-sample estimates (source half, base budget).**

| | ConceptARC | Mini-ARC | 1D-ARC |
|---|---|---|---|
| leave-one-source-out: solved tasks re-solved by G0 plus the library built from the other solutions | 2 of 5 fit; 0 whole tasks, 3 of 15 outputs (TopBottom2D 2 of 3 through another family's operation; the base-solved Order task) | 6 of 6 (all base-solved; the library is empty) | 22 of 23 (every 1d_flip task; the 1d_recolor_cmp solution has no second source) |
| reach beyond 4x: source failures that G0 plus the library solves | 2 fit, 1 of 3 outputs each (ExtractObjects, FilledNotFilled) | 0 of 68 | 4 fit, 3 correct (1d_fill x 2 and 1d_recolor_cmp, all through `fill(I, k, largest object)` with k from the grid), 1 wrong |

What these numbers say:
- **The library route works mechanically on natural tasks:** solutions found with extra budget pass the gates, and
  the parametrised entry (`fill(I, k, largest object)`) solves 3 source failures that the 4x search could not.
- **Its gain is almost all one family:** the 1D-ARC flip operation, found on all 22 source 1d_flip tasks as one
  identical program, re-solves each of them at the base budget when learned from the others. The held half has 22
  1d_flip tasks.
- **Elsewhere the gain is small:** 3 whole tasks of reach on 1D-ARC (1% of its failures), partial outputs only on
  ConceptARC, nothing on Mini-ARC.
- **Matched static search gets the same programs:** the 4x search found them, and the static allowance (section 11)
  is above 4x the base CPU.

## 11. The honest expectation and power

From `power/POWER.json` (`ngb/power.py`): per family, the source-half counts of tasks on which the library beats
G0 (any correct output where G0 has none), beats matched static search (more correct outputs than the 4x search
found; a failure beyond 4x counts as 0 for static, which favours the library) and loses to it, scaled by held/source
tasks; then 300 simulations of the held table with Poisson draws of those counts, each analysed by the
pre-registered procedure (exact test and family-clustered bootstrap, 2,000 draws in the simulation).

**Expected held-half counts.**

| comparison | expected discordant held tasks | by family |
|---|---|---|
| arm 2 (library) beats arm 1 (G0) | about 28 | 1d_flip 22 (one identical program from 22 source tasks; 22 held tasks), 1d_fill 2, 1d_recolor_cmp 1, three ConceptARC concepts 1 each (partial outputs); Mini-ARC 0 (empty library) |
| arm 1 beats arm 2 | 0 | the library only adds productions; regression on U guards the base solutions |
| arm 2 beats arm 4a (matched static) | about 5 | the reach cases: 1d_fill 2, 1d_recolor_cmp 1, two ConceptARC tasks with one output each |
| arm 4a beats arm 2 | about 5 | the 4x solutions the leave-one-out library misses: 1d_recolor_cmp 1, four ConceptARC tasks (three whole, one by an output) |

**Simulated decisions** (frequency over 300 simulations):
- arm 2 vs arm 1: "arm 2 beats arm 1" in 79% of simulations, "inconclusive" in 21%. The exact test is far below 0.05 whenever the 22 flip tasks materialise; the clustered
  interval's lower end stays above 0 because small gains in five other families (about 6 tasks) rarely all vanish
  in a resample. If those small gains do not materialise on the held half and the gain is the one family alone, a
  resample without 1d_flip (probability (13/14)^14 = 0.355) has a difference of 0 and the decision is
  "inconclusive". Either reading is a single-family effect and will be reported as such, with the by-family table.
- arm 2 vs arm 4a: "inconclusive" in 85% of simulations, "tie" in 14%, a decision either way in about 1%. The 4x search already found every library program on the source half, and the matched
  allowance is about 7 times the base search's CPU (estimated T(b, lib): ConceptARC about 10 CPU-s, Mini-ARC about 5,
  1D-ARC about 4 per held task; base searches take 1.4, 0.7 and 0.6), so matched static search is expected to
  re-find the flip program on the held 1d_flip tasks. The expected verdict is **efficiency, not reach**: the few reach
  cases (parametrised recolouring) are balanced by the 4x solutions the library does not transfer.
- The arm 5 comparisons cannot be estimated here: the builder's funnel is not known to this study. The rule in
  section 7 keys the primary to it. If the builder promotes nothing, arms 5 and 6 are G0 and S3 is an exact tie.

**Honest expectation, stated before any held task is touched.**
1. The library arm will beat G0 on the held halves, almost entirely through the 22 1D-ARC flip tasks; the decision
   will be "arm 2 beats arm 1" or "inconclusive" depending on whether the few small gains outside that family
   appear, and in either case the honest reading is: learning accumulated in one homogeneous family.
2. Against matched static search the library will show no reach: a tie or an inconclusive difference of a few
   tasks either way. The same CPU spent on plain search buys the same answers.
3. Mini-ARC will show nothing (empty library); ConceptARC at most partial outputs.
4. The ARC-AGI-2 check: a zero or near-zero gain for the library union (its operations are benchmark-specific), to be
   reported as such.

**Thresholds.** The exact test needs at least 6 discordant tasks in one direction for p < 0.05.

## 12. Compute plan

- **Kernels** (private Kaggle, CPU only, internet off, 4 workers; built after the GO by `ngb/kaggle_build.py`): A runs
  ConceptARC and Mini-ARC, B runs 1D-ARC, C runs the ARC-AGI-2 check from A's and B's allowances. Each kernel's
  package holds demonstrations and test inputs only; the frozen libraries and, when configured, the builder's files
  travel inside it. Outputs are downloaded, their manifests verified, and scoring runs on Athe (`run.py report`).
- **CPU estimate** (Athe measurements; Kaggle's CPUs were about 1.1 times slower in the construction test's replay):
  held base searches, 5 arms x 464 tasks at about 1 CPU-s: about 0.7 CPU-h; matched static, two allowances of about
  4 to 10 CPU-s per task: about 1.3 CPU-h; ARC-AGI-2, 5 arms on 120 tasks: about 0.5 CPU-h. Total about
  3 CPU-h, under an hour of wall time per kernel; ceiling 30 CPU-h per kernel. No GPU.

## 13. Code, provenance and checks

- **Reused read-only:** study A's `ngrow/` (benchmark loading, the split, the full-G0 plug-in, the gates wrapper,
  the static child search, analysis, scoring rules, the speed benchmark), the growth study's `cgrow/` (search,
  gates), A2 and arc-dsl. No file outside this folder was changed.
- **This study's code** (`ngb/`): candidate extraction and operation objects (`ops.py`), stage 1 discovery
  (`discover.py`, from the duplicate session, kept), the library stage (`library.py`), the held arms and allowances
  (`held.py`), the ARC-AGI-2 arms (`arc2.py`), the object-growth contract (`object_arm.py`), the gate (`gate.py`), the
  scorer (`score.py`), the analysis and report (`report.py`), the phase 2 driver (`phase2.py`), the power
  (`power.py`), the freeze (`freeze.py`), the kernel build (`kaggle_build.py`) and a dry run (`dry_run.py`).
- **Checks:** stage 1 agrees exactly with study A's frozen controller records on which tasks fit at base
  and at 4x (`feasibility/library/<benchmark>/discovery_summary.json`); the combined regression check passed for
  every library at full size; the dry run of every phase 2 code path (the seven held arms with matched static search
  in child processes, the five ARC-AGI-2 arms on two source tasks standing in, the report with the GO's primary line
  stubbed) ran end to end with exit code 0 on two source tasks per benchmark (`checks/dry_run/`; its numbers mean
  nothing); the gate refuses held runs, held test outputs and the ARC-AGI-2 solutions without a GO.

## 14. Boundaries

At most two CPU processes on Athe through `scripts/with_cpu_slot.sh` at nice 19; phase 2 on private Kaggle kernels;
never Step B, VDCG, other projects' job folders, GPU 1 or anything public; the builder's tree not read until its freeze is announced;
the construction test at scale not edited; the independent team's outcomes on these benchmarks not read.

## 15. Outputs and reporting

Phase 2 outputs go to `runs/phase2/<kernel>/` (STAGES.json with the GO's digest and the applied primary,
OUTPUT_MANIFEST.json, every arm's per-task records); the scorer writes RESULTS.json and REPORT.md. The record states
every number, including empty or unavailable registries, missing arms and the funnels, with a claim for the paper
written whichever way the result falls.
