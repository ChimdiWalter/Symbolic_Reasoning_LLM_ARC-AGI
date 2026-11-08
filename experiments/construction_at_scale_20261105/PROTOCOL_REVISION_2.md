# Construction test at scale: pre-registration (revision 2)

Study folder: `experiments/construction_at_scale_20261105/`. Author: Chimdi Walter Ndubuisi.

Revision 1 was frozen on 5 Nov 2026. Revision 2, frozen on 6 Nov 2026, answers the two exact-byte reviews of
revision 1: the project's own (`reviews/INDEPENDENT_PRE_RUN_REVIEW.md`, commit 7ae0cb1c, verdict HOLD, findings 1
to 12) and the companion study's (its notes 0457 and 0458, five blockers). The changes are listed in section 14. Revision 1 is kept byte for byte as
`PROTOCOL_REVISION_1.md` (sha256 b3759bfca67aecc6db51b6c6a8a280be9bc7ce828c01e336772acc3e319af7c6) with its
freeze record `FREEZE_REVISION_1.json` (sha256 260ee7533e5ce50ca754dc1f72481bcdbe9a8bba700b159b58b3fff2540cf3b8).
Both revisions were frozen before any main task was generated and before any method ran on any task of this
study. The sha256 of this file, of the code, of the configuration and of the seeds is recorded in `FREEZE.json`.
Phase 2 (generate, run, score) starts only after two independent exact-byte reviews and a one-use GO file written
by the coordinator (section 11).

**Exposure label.** Every task of this study is constructed from real ARC training input grids, with outputs made
by an arc-dsl reference operation. The study is mechanism evidence about how CORA grows its language from its own
failures. It is not ARC accuracy, and it reads none of the 120 public evaluation tasks.

## 1. Background and question

**The construction test (called S1 in the project's records).** It is recorded in
`experiments/capability_growth_20261027/protocols/TEST_S1_PROTOCOL.md` and corrected to task level in
`kaggle_entries/grammar_growth_research/package/records/NOV1_S1_TASK_LEVEL_CORRECTION.md`.
- **The language.** G0, the starting language, is A2's arc-dsl grammar (A2 is the project's bottom-up program
  search over arc-dsl, with costs estimated from 194 verified training solvers) minus a removed set of operations.
- **The schema language.** It is a fixed, pre-registered space of 211 operator structures (`cgrow/schema.py`). It
  has four kinds:
  - SEL, keep rows and columns by a predicate;
  - MAP, copy cells through a separable index map;
  - BLOCK, reduce k x k blocks;
  - COLOUR, replace or exchange two colours.
- **The result.** S1 removed four operations (compress, downscale, trim, upscale), giving one family of tasks
  each. Of its 11 motivating tasks:
  - CORA's own typed holes recovered 8;
  - matched static search recovered 5;
  - exact McNemar p = 0.375.

  The result was underpowered.

**Question.** Over 11 families and more than five times as many motivating tasks, does growth from CORA's own typed
holes recover missing operations more often than matched static search?

**Claim limit (unchanged from S1).** Every removed operation of this study equals a structure of the schema
language (section 3). The study therefore tests whether failure-derived specifications **select the right member of
a known, pre-registered space**, not open invention.

## 2. Definitions

- **Removed operation.** An arc-dsl primitive taken out of the grammar, as a production and as a function value,
  exactly as S1 removed its four. Removed operations and their references are known only to the evaluator.
- **World.** One starting language G0 = A2 grammar minus that world's removed set, with its own tasks. The study
  has three worlds (section 3); every method in a world sees only that world's G0 and system tasks.
- **Family.** The tasks built from one removed operation X. There are 11 families (section 3).
- **Templates (S1's).**
  - T1 is X(I[, p]);
  - T2 is X(A(I)[, p]);
  - T3 is B(X(I[, p])).

  Here I is the input grid, p is X's parameter, and A and B are unary grid operations of the world's G0.
- **Partitions (S1's).** For each family:
  - motivating tasks (M);
  - system validation tasks (V);
  - excluded tasks (E), which are evaluator-only and never seen by any method.

  For each world:
  - search-level decoys (D);
  - previously solved tasks (U), which form the regression set.
- **Motivating task.** An M task on which CORA's controller decides to construct a new operation
  (INVENT_NEW_OPERATION). The controller sends the task elsewhere when the 4x deeper search finds a fit.
- **Committed outputs.** Every method commits at most two outputs per query before scoring, by one label-blind
  rule (section 5). Matched static search commits the two predictions of its search. A growth unit commits the two
  predictions of the retry of the structure it keeps.
- **Recovered.** A unit is recovered when one of its committed outputs equals the query's output.
- **Oracle reach (descriptive only).** A growth unit reaches the task when any retried candidate's prediction is
  correct, over up to three retries with two predictions each; on excluded tasks, when any promoted structure
  tried alone solves the task. This is S1's endpoint and revision 1's primary; it is kept under this name so that
  S1 and this study can be compared on the same endpoint, but it has no matched control and carries no test.
- **Failure.** A recorded method failure counts as not recovered and is never replaced: a matched search that
  timed out, ran out of memory or whose child process failed; a growth unit that commits nothing.
- **Not applicable.** A unit that cannot exist by construction (an S-shuffled unit whose task has no donor family
  with a motivating task) is recorded as such, excluded from that method's contrasts only, and counted.
- **Recovery criteria.**
  - majority criterion: a method recovers a task in at least 2 of its 3 seeds;
  - all-3 criterion: in all 3 seeds.
- **Methods (S1's names).** The specification methods first:
  - **S-hole.** CORA's own typed holes, from its failure analysis.
  - **S-demo.** The demonstrations only, that is, the identity hole.
  - **S-shuffled.** The typed holes of another task: the same-slot motivating task of the next family in the same
    world.

  Then the two search methods:
  - **S-enum.** Blind enumeration of the schema language.
  - **C7m.** Matched static search with G0 alone.

  No neural method runs in this study.

## 3. Removed operations, worlds and families

Feasibility was checked by `cas/feasibility.py`, which is evaluator-only; outputs are in `feasibility/`. An
operation X is admitted only if both checks hold:
1. **Membership.** Some schema structure equals X's arc-dsl reference on 80 probe grids (seeds 515 and 99) at every
   parameter value used.
2. **Novelty.** S1's own gate (`s1.Gates.novelty`, reimplemented line for line) does not flag that structure as a
   duplicate under the world's G0. The gate searches the 12 probe-grid pairs with A2's search at 200,000
   executions and a 10 CPU-s cap; in every check it completed cost level 9 (S1's protocol text says "about cost
   7"), so no G0 program of cost 7 or less reproduces any admitted operation.

**Boundary with the companion study** (agreed in its inbox note 0135 and widened later the same day, both relayed
by the coordinator on 5 Nov 2026, before this protocol and family list were frozen):
- **Horizontal reflection is never removed, and no family is built on it.** Conventions differ on which axis
  "horizontal" names, so both arc-dsl mirrors across an axis stay in every G0: hmirror, which flips top to bottom,
  and vmirror, which flips left to right. With them stays rot180 = hmirror(vmirror(I)).
- **No family selects an object by an attribute.** That covers the seven semantics named in the note (maximum
  area, maximum width, multipart maximum area, diagonal maximum area, maximum holes, minimum centre distance and
  maximum nearest distance). It also covers any selection of the object with the maximum or minimum of an
  attribute, followed by cropping. Every family below is a whole-grid transformation, and so is every composite
  operation A or B of the templates.
- **The companion study's outcomes are not read,** including its results on the external benchmarks (ConceptARC,
  Mini-ARC, 1D-ARC). Its 128 authored tasks are not used: every task comes from this study's own generator over ARC
  training input grids.
- **The sibling natural-task growth test** (`experiments/natural_growth_20261105/`) uses the same machinery. This
  study never edits that folder.

| world | removed set (all removed together) | G0 size | families and parameter values | equal schema structures |
|---|---|---|---|---|
| W1, S1's world | compress, downscale, trim, upscale | 136 productions (S1's G0) | compress; downscale k = 2, 3; trim; upscale k = 2, 3 | SEL:multi:multi; SEL:mod:mod, MAP:sample:sample:0, BLOCK:first; SEL:inner:inner, MAP:core:core:0; MAP:spread:spread:0 |
| W2, quarter-turn and diagonal-reflection world | dmirror, cmirror, rot90, rot270 (the symmetries of the square outside {identity, hmirror, vmirror, rot180}) | 136 | the four, no parameter | MAP:same:same:1, MAP:flip:flip:1, MAP:same:flip:1, MAP:flip:same:1 |
| W3, stretch and colour-exchange world | hupscale, vupscale, switch | 137 | hupscale k = 2, 3; vupscale k = 3; switch(a, b) with a and b the source's two most frequent colours | MAP:same:spread:0; MAP:spread:same:0; COLOUR:a:b:1 (all 45 colour pairs checked) |

**The 11 frozen families.**
- W1: compress, downscale, trim, upscale;
- W2: dmirror (main-diagonal reflection), cmirror (anti-diagonal reflection), rot90 (quarter turn clockwise),
  rot270 (quarter turn anticlockwise);
- W3: hupscale (each column repeated k times), vupscale (each row repeated 3 times), switch (two colours
  exchanged).

All 11 operations pass both checks, at every parameter value used. Further facts and decisions:
- **vupscale.** It is admitted at k = 3 only. At k = 2 the G0 program merge(pair(I, I)), of cost 7, reproduces it.
- **switch.** Its colours are chosen from the source; the rule is in section 4.
- **Rejected candidates, with the gate's own witnesses.**
  - The rotations alone: rot180 = hmirror(vmirror(I)), cost 6; rot90 = hmirror(cmirror(I)) and rot270 =
    hmirror(dmirror(I)), cost 7.
  - Any single mirror: hmirror = vmirror(rot180(I)), cost 7.
  - replace: fill(I, b, ofcolor(I, a)), cost 7 or 8.
  - The halves (tophalf and the other three) and hconcat and vconcat are not structures of the schema language.
  - **Feasible, but not allowed by the boundary.** Two removals pass both checks, but both remove horizontal
    reflection, and they were dropped when the boundary was agreed:
    - all seven symmetries (`feasibility/W2_all_dihedral.json`);
    - the six other than rot180 (`feasibility/W2_orientation.json`).

    The first, at 14 families, was the design before the boundary. No main task had been generated and no method
    had run under it.
- **Expressibility.** S1's evaluator-only check searched 10 probe grids at 3,000,000 executions, up to cost level
  12. It found G0 programs equal to:
  - trim: subgrid(inbox(asobject(I)), I), level 10;
  - vupscale at k = 2 (excluded, see above).

  The deeper evaluator-only search runs at about the matched-search depth (150 CPU-s, levels 13 to 14;
  `feasibility/deep_macro_search*.json`). These are the G0 routes matched static search can use:
  - trim: level 10, as above;
  - upscale: hupscale(vupscale(I, k), k), level 12;
  - switch: fill(replace(I, a, b), a, ofcolor(I, b)), level 12 to 14 (the re-check below);
  - dmirror: apply(merge, hsplit(I, width(I))), level 13;
  - vupscale at k = 3: apply(last, upscale(apply(tojvec, I), THREE)), level 13;
  - hupscale at k = 2: apply(merge, apply(dmirror, pair(I, I))), level 14.

  It found none for compress, downscale, cmirror, rot90, rot270 or hupscale at k = 3. For switch, the 10 probe grids
  of the first check contain no colour 0, so replace(I, b, ZERO) matched there (level 5); S1's novelty probes contain
  colour 0, and the gate rejects that shortcut for all 45 pairs. The check was repeated for switch on probe grids
  that hold both colours of the pair (`feasibility/deep_macro_search_switch_colour0.json`): on the 6 or 7 such probes of each pair, switch IS expressible in W3's G0,
  by fill(replace(I, a, b), a, ofcolor(I, b)), at level 12 for the pairs (0, 1) and (0, 5) and level 14 for
  (1, 2), found in 13 to 125 CPU-s. switch is therefore a sixth route family, and the first check's level-5 match
  was an artifact of its probes.

  These routes are reported per family and do not change the analysis.

**Links between families.**
- **W1 and W3.** No family's operation can be composed from another family's operation and the world's G0 at cost
  7 or less.
- **W2.** The four removed symmetries form one coset of the kept subgroup {identity, hmirror, vmirror, rot180}.
  Any one of them, added with the kept mirrors, gives the other three within cost 7. For example, with dmirror:
  - rot90 = vmirror(dmirror(I)) and rot270 = hmirror(dmirror(I)) are within cost 7;
  - cmirror = rot180(dmirror(I)) is within cost 7.

  W2's four families are therefore one linked group, and three consequences follow:
  - transfer among them is expected, and the per-family transfer table shows it;
  - S-shuffled, whose donor is the next W2 family in name order (S1's rule), can succeed there, because its donor's
    structure also composes into the task's own operation;
  - the primary's family-clustered interval is also reported with W2's four families merged into one cluster
    (section 6, sensitivity only).

## 4. Tasks, pools and seeds

**Input pools** (`cas/pools.py`, written to `config/POOLS.json` before the pilot).
- **Candidates.** The project's S_train (520) and S_select (176) splits, which are 696 tasks of
  arc-agi_training_challenges.json. The 120 public evaluation tasks are a different file and are never read.
- **Excluded from both pools.** The 61 tasks S1 used, as sources or as real previously solved tasks.
- **Pools.** The remaining 635 ids, in sha256("cas-pools-20261105|" + id) order:
  - the first 100 form the **pilot pool** (sha256 of the sorted id list
    d321d80236842ee5925d06df0899f207058e6b6efd31a60d677665de242926e9). It is used only in phase 1 and is excluded
    from the study;
  - the other 535 form the **main pool** (sha256 a740f6a359cd219ff9a75b30726b097cf6edea1de401d2975a53fb631765ff27).

**Generator** (`cas/generate.py`). It is S1's `cgrow/tasks.py` with the world's removed set, parameters and pool.

These rules are unchanged from S1:
- the three templates, using input grids only;
- the five filters:
  1. the program runs on every input;
  2. X changes its argument on at least two thirds of the inputs;
  3. no demonstration output equals its input, and the outputs are not all equal;
  4. G0 plus the reference fits the demonstrations and predicts the query at the base budget;
  5. G0 finds no fit at the base budget;
- inputs at most 12 x 12 and outputs at most 16 x 16;
- at most 4 demonstrations;
- at most 60 candidates per template for a slot, after which a T2 or T3 slot moves to its next composite template
  (a T1 slot has one template);
- composite templates are not shared between partitions;
- no source serves two tasks;
- D tasks are G0 programs that the base budget misses and 4x the budget finds;
- U tasks are 8 derived and 6 real training tasks, re-verified under each world's G0;
- the order is sha256(salt + key).

These rules are new:
1. **Sources per world.** Each world has its own used-set, so no source serves two tasks of one world. Worlds are
   separate experiments with separate languages and may share a source. Real U tasks are reserved before the
   families (in S1 one real U task shared its inputs with an E task). A world builds its families in the configured
   order, the most size-constrained first:
   - W1: upscale, downscale, compress, trim;
   - W2: dmirror, cmirror, rot90, rot270;
   - W3: vupscale, hupscale, switch.

   **The reason.** S1's size caps admit few sources (see Capacity below). One study-wide used-set would exhaust them
   in W1 and W2, as a dry run of the build on the pilot pool showed.
2. A and B range over S1's 11 composite operations plus compress and trim, minus the world's removed set:
   - W1: exactly S1's list (11 operations);
   - W2: hmirror, vmirror, rot180, the four halves, compress and trim (9);
   - W3: all 13.
3. switch takes its colours p = (a, b) from the source: the two most frequent colours over the task's input grids
   (up to four demonstration inputs and the query input), ties to the smaller colour, written with arc-dsl's colour
   constants.
4. A slot with no qualifying candidate is recorded as unfilled (S1 raised an error).
5. Opaque task ids include the world name.

**Quotas, per family.**
- M: 9 (T1, T2, T3, three times);
- V: 2 (T2, T3);
- E: 6 (T1, T1, T2, T2, T3, T3).

Per world: D 4 and U 14 (8 derived, 6 real).

**Planned task counts.**

| | per family | 11 families |
|---|---|---|
| M | 9 | 99 |
| V | 2 | 22 |
| E | 6 | 66 |
| family tasks | 17 | 187 |

D and U are added per world: up to 4 + 14 each.

**Capacity** (`cas/capacity.py`, `pilot/POOL_CAPACITY.json`). Only 187 of the 535 main sources have every input at
most 12 x 12, the cap of S1's size filter. A world needs at most 4 x 17 + 4 + 8 = 80 sources (W1, the largest), so
one used-set per world fits. A single study-wide used-set would not have fitted. Composite templates suffice too:
each family needs 6 T2 and 6 T3 templates, and W2, the smallest list, has 9 of each.

**Dry run.** The final build code ran on the pilot pool with a reduced quota (M 2, V 1 and E 1 per family)
(`checks/generator_dry_run_pilot/`): every slot was filled, 28, 28 and 24 tasks in W1, W2 and W3, in 423 CPU-s. The pilot pool holds none of the 15 training tasks A2 solved, so
real U tasks were not exercised there; that path was tested on S1's own six real U tasks instead.

**Seeds and salts.**
- generator salts cas-W1-20261105, cas-W2b-20261105 and cas-W3-20261105 (W2's salt was renamed when its removed
  set changed under the boundary; section 14);
- pool salt cas-pools-20261105;
- structure orders S1's `random.Random("s1-order-" + str(s))` for seeds s = 0, 1, 2;
- PYTHONHASHSEED=0 for every process.

**Pilot** (`cas/pilot.py`; `pilot/PILOT_RESULTS.json`; pilot pool only; run with this configuration and the
corrected slot loop of revision 2).
- **Slots.** All 33 pilot slots (11 families x T1, T2, T3) were filled from 1,131 candidates. Generation used
  168 CPU-s: 3.5, 1.8 and 11.7 CPU-s per kept task in W1, W2 and W3.
- **Controller.** It sent 30 of the 33 to construction (share 0.91) and used 5.0 CPU-s per task on average,
  sketches included. The three tasks sent to deeper search were downscale T1, trim T1 (as in S1) and dmirror T1.
- **Typed holes.** Every pilot task has 3 sketches (identity, an outer and an inner inverse of an invertible G0
  operation).
- **No method ran on any pilot task.**

Three earlier pilots are kept, superseded: `pilot_v1_superseded/` and `pilot_v2_superseded/` used the 14-family
design that the boundary replaced; `pilot_v3_superseded/` used this configuration with revision 1's slot loop.

**Expected counts.** About 99 x 0.91 = 90 motivating tasks. Low-yield slots, such as vupscale composites, which
need inputs of at most 5 rows, may stay unfilled; every unfilled slot is reported.

## 5. Methods (S1's code, unchanged)

Phase 2 runs S1's frozen functions through `cas/run_world.py`. `cas/env.py` points S1's folder constants at one
world folder; no S1 file is changed.
- **Controller.** `cgrow.controller.analyze` runs on every system task: the base search, the 4x deeper probe, the
  closest program and the typed-hole sketches (identity, B(?(I)) and ?(A(I)) with A and B invertible G0
  operations, top 3 by score).
- **Specification methods** (`s1.spec_candidates` and `s1.run_spec_unit`). For each stored sketch in rank order,
  every structure in the seed's order that maps every hole input exactly to its target is a candidate. Each
  candidate passes four gates in turn:
  1. novelty (S1's gate);
  2. a retry of the motivating task with G0 plus the structure at the base budget (at most 3 retries per unit);
  3. regression on every previously solved task (a lost fit or a changed first prediction means rolled back);
  4. validation on the other unsolved system tasks in hash order (one new fit means promoted).

  The unit stops at the first promoted structure. S-hole uses all sketches, S-demo the identity sketch only, and
  S-shuffled the donor's sketches.
- **S-enum** (`s1.run_enum_unit`). Every structure, in the seed's order, is added to G0 and the task is searched at
  the base budget, until 60 charged CPU-s per unit (reference CPU-seconds, section 10). The gates are the same.
- **C7m (matched static search).** G0 alone is searched on the demonstrations, with 10^9 executions and a 150 CPU-s
  cap (reference CPU-seconds, section 10), in a child process limited to 12 GB of address space. The search is deterministic, so it runs once per
  task. It runs on motivating tasks (the primary) and on E tasks (the secondaries).
- **Budgets (S1's).**

  | search | executions | CPU cap |
  |---|---|---|
  | base search | 150,000 | 20 CPU-s |
  | deeper probe | 600,000 | 80 CPU-s |
  | novelty gate | 200,000 | 10 CPU-s |
  | kind check | 1,000,000 | 30 CPU-s |

  Added structures have cost 3 and charge 1.

**Committed outputs (label-blind; `run_world.committed_outputs`).** A growth unit's retries each return the
predictions of the first two fitting programs of the search over G0 plus the candidate structure. The unit commits
the two predictions of the retry of the structure it keeps:
- the promoted structure, if there is one;
- otherwise the first quarantined structure in candidate order;
- a rolled-back structure commits nothing.

Promotion uses the regression set and the validation pool, never the query label, and candidate order is sketch
rank then the seed's structure order; both are label-blind. The rule is the same for S-hole, S-demo, S-shuffled
and S-enum, per arm, seed and task. Matched static search commits the two predictions of its one search. Every
method is therefore scored on at most two outputs per query. In S1's own record no unit held more than one fitting
candidate and every fitting candidate was promoted, so this rule leaves S1's counts unchanged
(`power/COMMITTED_POLICY_S1_CHECK.json`).

**The commit stage (`run_world.commit`).** Before any query label is read, a separate stage writes every unit's
committed predictions and every matched search's two predictions to `runs/cas_commit/COMMITTED_PREDICTIONS.json`
with its sha256 (`COMMITTED_SHA256`). It first checks completeness: every growth arm on every motivating task and
seed, and every matched search on every motivating and excluded task, must be present; otherwise it writes
`INCOMPLETE.json`, stops, and nothing is written in place of the missing work. Scoring (`run_world.evaluate`) reads
that file, verifies its digest, and compares each committed prediction with the query output. The digest is carried
into the world's results and checked again by the analysis.

**CPU accounting.** Two quantities are recorded for every growth unit and kept apart:
- **charged CPU** (logical): the task's diagnosis (the controller's base search, 4x probe, closest program and
  sketches, measured once per task and charged to every growth unit on it, because every growth method runs only
  after the controller's decision), plus the specification enumeration (every structure checked against the hole
  pairs), plus S1's gate charges (novelty, retries, regression, validation). A cached gate result is charged at the
  CPU of its first computation. S1 charged the regression check with the time of its loop, so retries served from
  the cache were charged nothing (a check with two cached 15 s retries charged 0.001 s); here the regression check
  is charged the stored CPU of its retries over the regression set, cached or not (`run_world.AccountedGates`, a
  subclass; S1's files are untouched). The charged total is the complete cost of growth on the unit;
- **actual CPU**: the process CPU the unit used, which is lower when gate results came from the cache.

Per world, the kernel driver also records the actual CPU and wall time of every stage, and every matched search
records its executions per CPU-second.

**Matched search budget.** A motivating task's matched search gets 150 reference CPU-s, or S-hole's largest
complete charged CPU on that task over its three seeds when that is larger (`run_world.c7m_budget`), both in the
kernel's own seconds. Matched static search therefore never has less CPU than growth had, and in practice far more:
in S1 the complete charged total of S-hole was at most 37.3 CPU-s per unit (mean 17.7), about a quarter of 150.
So the
comparator is a fixed strong baseline with at least growth's complete compute, not an equal-compute baseline, and
that favours the "matched search beats S-hole" and "refuted" outcomes over the positive one. Excluded tasks get
150 reference CPU-s. The budget used is recorded with every result.

**Machine factor (`cas/bench.py`).** S-enum's 60 s and C7m's 150 s are stated in reference CPU-seconds (Athe,
where S1 ran). Each kernel first runs a fixed 200,000-execution search alone (5 repeats) and then four copies at
once, the process count of its busiest stage (3 repeats each; the median of the four per-process medians). The
factor is r = concurrent median / Athe's lone reference (1.281 CPU-s, `bench/BENCH_ATHE_REFERENCE.json`), clipped
to [1, 3]; both stops are multiplied by r, so hardware threads sharing cores do not shorten the comparator or the
blind-enumeration control. The clip is one-sided: a machine faster than Athe gives the search methods no more than
their reference budgets, and one more than three times slower under concurrency gives them less; the record shows
either case, because every matched search records its executions per CPU-second beside the benchmark's. The
benchmark runs again at the end of the kernel.

**Child processes and guards.** Each matched search runs in a child limited to 8 GB of address space; at most two
run beside other processes, three alone (Kaggle's CPU kernels have four cores and about 30 GB). A child that runs out
of memory beside others is run once more alone, and that result stands. A child that exceeds six times its cap
plus 60 s of wall time is killed and recorded as timed out: a failure, never a budget. A missing matched search
makes the world INCOMPLETE (the commit stage); it is never recorded as "not recovered".

**Plumbing check** (`cas/equivalence.py`, `checks/EQUIVALENCE.json`; re-run with revision 2's code). It used
only S1's own tasks and records, never a pilot or main task. The phase 2 runner (controller, specification
methods, S-enum seed 0, commit, evaluation) and the analysis, pointed at a copy of S1's world, reproduce S1:
- the controller: 38 of 38 decisions and typed holes identical;
- the specification methods: 99 of 99 units identical (candidate rows, outcomes, retries, promotions);
- S-enum seed 0: 9 of 11 promotions identical; two units (t1990d3f8, t83286f67) stopped one structure earlier on
  their charged-CPU limit, which S-enum's CPU-time stop allows (S1's own records show the same effect);
- the 9 promoted structures: family, excluded-task fits, kind and contract verdict identical to S1's record;
- committed outputs equal oracle reach on every S1 unit (S-hole 8, S-demo 4, S-shuffled 0, S-enum 9 by majority);
- the primary: S1's task-level record exactly (8 against 5 of 11, discordant 4 : 1, conditional p = 0.375,
  dependence-aware interval [-0.2, 0.667] over S1's four families, source-clustered [-0.091, 0.636];
  "inconclusive");
- S-hole's complete charged CPU: mean 17.7 CPU-s per unit (diagnosis 5.4, gates 12.3, enumeration 0.01), at most
  37.3, against 4.1 actual; the matched-search budget rule would not have raised any S1 budget;
- the grown grammars solve all 24 of S1's excluded tasks by reuse (two committed outputs) and 1 by transfer;
- the 5 matched-search fits of S1, re-run once at S1's budget to recover their predictions: 5 fits again, 4 with
  the same program.

Matched search was not rerun in that check: S1's recorded results stood in (each recorded fit re-run once at S1's
budget to recover its two predictions, since S1 kept none), and none existed for E tasks, which are recorded as
failed searches there.

## 6. Primary contrast

**S-hole against C7m, majority criterion, on all motivating tasks of all three worlds.**
- **Unit.** One motivating task; seeds are within-task replicates (S1's task-level correction).
- **Dependence.** Tasks are not all independent: W2's four families are one linked group (section 3), and the three
  worlds draw sources from one pool, so two tasks of different worlds can share their input grids. The inference is
  therefore clustered.
- **Statistics.** S1's code (`testib_rest._compare`) gives the exact two-sided McNemar test on the discordant
  tasks, the mean paired difference, and percentile bootstrap 95% intervals of the mean paired difference over
  10,000 draws (seed 1 over units, seed 7 over clusters). Three cluster definitions are computed:
  - **dependence-aware (decision-bearing):** the families, with W2's four linked families as ONE cluster; 8
    clusters, resampled with replacement;
  - 11 families, as in S1 (reported);
  - source-input clusters: tasks that share a source input grid, within or across worlds, in one cluster
    (reported).

  The McNemar p-value assumes exchangeable tasks and is reported as **conditional** on that; it is a necessary part
  of the positive and reversed outcomes, never sufficient alone.
- **Decision.** One outcome only:
  - **S-hole beats matched search:** McNemar p < 0.05 and the dependence-aware interval lies entirely above 0;
  - **matched search beats S-hole:** McNemar p < 0.05 and the dependence-aware interval lies entirely below 0;
  - **S1-sized advantage refuted:** neither of the above, and the dependence-aware interval's upper end is below
    3/11 = 0.273 (S1's task-level difference, 8 - 5 of 11). Any advantage is then smaller than S1's;
  - **inconclusive:** otherwise.

## 7. Secondary contrasts (Holm over these four, no decision weight)

Each secondary uses the same statistics as the primary. It holds when its Holm-adjusted conditional p < 0.05 and
its dependence-aware interval excludes 0.
1. **S-hole against S-shuffled.** Majority criterion, motivating tasks. A task whose family has no donor family
   with a motivating task has no S-shuffled unit (not applicable): it is left out of this contrast and counted.
2. **S-hole against S-enum.** All-3 criterion for both methods, motivating tasks.
3. **Reuse on excluded tasks.**
   - Unit: an E task of family f.
   - The grown grammar of f is G0 plus every structure that S-hole promoted on a motivating task of f in at least
     2 of 3 seeds. One base search with that grammar commits its two predictions; S-hole succeeds when one of them
     is correct. A family with no such structure has an empty grown grammar and fails on every one of its E tasks.
   - Comparison: C7m on the same E task (two committed outputs).
   - switch: a COLOUR structure carries fixed colours and switch's colours come from each source, so an excluded
     switch task is solvable by reuse only when its colour pair was promoted on a motivating task. Its rows are
     expected to fail for that reason; they stay in the contrast and are also reported separately.
4. **Transfer to other families.** As 3, with the grown grammar of the other families of the same world (every
   structure S-hole promoted for them under the same rule). In W2 transfer is expected (section 3).

**Descriptive only.** These outputs carry no test:
- every method's counts under the any-seed, majority and all-3 criteria;
- oracle reach, per method and criterion, and on excluded tasks (the union over the family's promoted structures
  tried alone), with no contrast;
- per-structure fits on excluded tasks (as S1 reported them);
- the CPU accounting of section 5: per method, mean charged and actual CPU with their parts; per world, the stage
  CPU; the matched-search budgets used, how many motivating tasks needed more than 150 reference CPU-s, and the
  executions per CPU-second of every matched search against the kernel's benchmark;
- the number of matched-search failures, of not-applicable units and of sources shared between worlds;
- S-hole against S-demo;
- S-enum against C7m;
- per-world and per-family tables;
- each promoted structure's agreement with every removed reference (E inputs plus 40 probe grids; for a COLOUR
  structure the agreement is at the excluded tasks' colour pairs, which is why it is expected to be low), its kind
  (macro or expansion relative to G0, by a 1,000,000-execution search) and its verdict from CAST's contract checker;
- the controller's decisions;
- unfilled slots;
- the C7m cost levels reached.

## 8. Power (`cas/power.py`; `power/*.json`)

The model is S1's task-level effect, from its 11 tasks:
- both methods recovered 4;
- S-hole only 4;
- C7m only 1;
- neither 2.

Each simulated study has 11 families x m M tasks per family, in the design's 8 clusters (W1 four, W2 one, W3
three), and each task becomes motivating with probability 11/12. There are 4,000 simulated studies per row and
2,000 bootstrap draws each, and the decision rule is that of section 6 (McNemar and the 8-cluster interval).

| scenario | m | about N motivating | S-hole beats matched search | S1-sized advantage refuted | inconclusive |
|---|---|---|---|---|---|
| A: S1's pooled effect | 8 | 81 | 0.93 | 0.03 | 0.04 |
| **A (chosen)** | **9** | **91** | **0.96** | **0.02** | **0.02** |
| B: S1's between-family spread | 9 | 91 | 0.29 | 0.08 | 0.62 |
| N: no effect | 9 | 91 | 0.018 | 0.92 | 0.05 |
| C: design-based, two G0 routes (trim, upscale) | 9 | 90 | 0.95 | 0.00 | 0.05 |
| C: design-based, five G0 routes | 9 | 90 | 0.39 | 0.12 | 0.50 |
| C: design-based, six G0 routes (switch too) | 9 | 90 | 0.16 | 0.32 | 0.53 |

The rows come from `power/POWER_CLUSTERED_RULE.json` (scenarios A, B, N) and
`power/POWER_DESIGN_C_CLUSTERED_TWO_ROUTES.json`, `..._FIVE_ROUTES.json` and `..._SIX_ROUTES.json` (the C rows;
motivating share 0.91 from the pilot). Revision 1's rows, under an 11-family interval, are kept in `power/POWER_S1_EFFECT*.json` and
`power/superseded/`; they are not the rule any more.

**The scenarios.**
- **A** treats tasks as independent, with S1's pooled shares.
- **B** copies one of S1's four families into each new family and draws that family's tasks from it.
- **N** exchanges the two methods' outcomes at random within each task.
- **C** is assumption-laden and is not S1's observed effect. It models each of the 11 planned families:
  - S-hole's chance by template class from S1: T1, 3 of 3; a composite with an invertible operation, 5 of 5; a
    composite with a non-invertible operation, 0 of 3;
  - each world's share of invertible composite operations;
  - C7m's chance: 4 of 5 (S1's trim and upscale) in families with a G0 route at matched-search depth (section 3),
    and 1 of 6 otherwise.

  The five-route row treats dmirror, hupscale and vupscale like trim and upscale, and the six-route row switch as
  well. Those routes cost 12 to 14, so matched search can reach them mainly on T1 tasks, which the controller often
  sends to deeper search. The truth is expected to lie between the two-route row and the six-route row.

**The committed-output rule and S1's effect.** Revision 2 changed what "recovered" means. Applied to S1's own
units, the rule gives the same task-level counts as S1's record (S-hole 8, matched search 5, blind enumeration 9
by majority and 3 by all seeds): no S1 unit held more than one fitting candidate, and every fitting candidate was
promoted. The power model is therefore unchanged by that rule; what changed it is the clustering.

**The choice.** m = 9 keeps S1's 1 : 1 : 1 template mix. It gives 0.96 at S1's observed effect under the 8-cluster rule (0.93 with m = 8). With no
effect, the study refutes an S1-sized advantage with probability 0.92 and calls a false positive with probability
0.018.

**The limit.** If the new families differ from one another as much as S1's four did (where trim favoured matched
search), the clustered interval caps power near 0.30 whatever m is. If matched search finds all six G0 routes as
often as it found trim's and upscale's in S1, power falls to 0.16 and the study ends "S1-sized advantage refuted"
with probability 0.32: a real advantage smaller than S1's would then be called refuted. Only more families would
raise the first cap, and the boundary leaves 11 (section 3). These limits are stated now so that an inconclusive
or refuted result is read correctly.

## 9. What would change the conclusion

Nothing after the GO changes:
- the removed sets, the families or the quotas;
- the pools, the seeds or the salts;
- the methods or their budgets;
- the decision rule.

Unfilled slots, tasks the controller sends to deeper search and families with no motivating task reduce N; they
are reported and never replaced.

## 10. Compute, stop rules and route

**Estimate,** from S1's measured costs and the pilot:

| stage | CPU-h |
|---|---|
| generation (Athe) | 0.3 |
| controller (about 175 system tasks) | 0.3 |
| specification methods | 0.3 |
| S-enum (about 90 x 3 units, at most 60 reference CPU-s each) | at most 4.5 |
| C7m on about 90 motivating and 66 excluded tasks (150 reference CPU-s each) | 6.5 |
| commit and evaluation | about 1.2 |
| **total** | **about 13 reference CPU-h** |

On Kaggle, expect about 20 CPU-h, because the two CPU stops scale with the machine factor (section 5; about 1.4
alone in the S1 replay, more under four-way concurrency). Even at r = 3 the total would be about 36 CPU-h.

**Stop rules,** in CPU time or counts, never wall clock, except the two wall-time guards named as such:
- the per-search caps of section 5;
- 3 retries per specification unit;
- 60 charged CPU-s per S-enum unit (times r);
- 150 CPU-s per C7m task (times r), or S-hole's complete charged CPU on that motivating task when larger (section
  5); a C7m child that runs out of memory beside others is run once more alone, and that result stands; a child
  that exceeds six times its cap plus 60 s of wall time is killed and counts as a failure (a guard, not a budget);
- 15 CPU-h per world kernel (no new stage starts after it; the world is then INCOMPLETE), so at most 45 CPU-h for
  the study; Kaggle's 12-hour session is the other wall-time guard, and a world it cuts is INCOMPLETE.

**Evidence for the factor.** In the S1 replay on Kaggle (3 Nov), matched search ran 1.40 times fewer executions per
CPU-second than on Athe. That is the median over the 10 tasks stopped by its CPU cap (from the replay's own output,
downloaded read-only), with the matched searches running one at a time. The benchmark takes 1.281 CPU-s on Athe
alone (`bench/BENCH_ATHE_REFERENCE.json`, median of 5). Under four-way concurrency the factor will be larger; the
kernel measures it (section 5).

**Route.**
1. Generation runs on Athe in one CPU slot (`scripts/with_cpu_slot.sh`, nice 19).
2. Everything else runs in three private Kaggle kernels, one per world, CPU only, internet off, under the account
   chimdiwalter.
3. Each kernel is built by `cas/kaggle_build.py`, the S1 replay's route: a deterministic .tar.gz of the frozen files
   at their repository paths, embedded with its sha256, which the notebook checks before unpacking.
4. The kernel runs `cas/kaggle_main.py`, at most four processes at a time. It first verifies the world's task files
   against their manifest and the configuration, and measures the machine factor; then:
   - controller;
   - specification methods, beside C7m on E tasks (2 child processes);
   - S-enum, its 3 seeds in parallel, beside the first 12 matched searches on motivating tasks (1 child process;
     these need the finished S-hole units, for the budget rule of section 5);
   - the remaining matched searches on motivating tasks (3 child processes);
   - commit (the committed predictions, before any label);
   - evaluation, which includes the reuse and transfer searches.

   After every stage the outputs are packed to the kernel's output folder, so a session cut by Kaggle's limit keeps
   what finished; every stage records the project modules it executed with their digests (`runs/module_pins/`).
5. Outputs come back with `kaggle kernels output`; each kernel's `runs/` is placed inside its committed world
   folder `runs/generated/<world>/`. Before the analysis, `cas/analysis.py` verifies each world: the task files
   equal the committed manifests, and the kernel record names that manifest's digest and the package digest of
   `runs/kaggle/PACKAGE_MANIFEST.json`; the kernel record is complete (every stage done); every file under `runs/`
   has the sha256 of its `OUTPUT_MANIFEST.json`; every module-pin record is ok against `FREEZE.json`; the
   committed-predictions digest chain holds; every unit, seed, matched search and excluded task is present. Any
   failure makes the study INCOMPLETE: the analysis writes `INCOMPLETE.json` and stops. Nothing is substituted.

Kaggle ran Python 3.13 in the replay. Expected wall time per kernel, at r = 1.4, is about 3 hours (W3 2.2, W1 2.7,
W2 2.8), and up to about 6 hours at r = 3, inside Kaggle's 12-hour session. Step B, GPUs and anything public are
untouched.

## 11. Phase 2 procedure

1. **GO.** The coordinator writes `GO_CAS` in this folder. Its first two lines must be exactly
   `protocol_sha256 <sha256 of PROTOCOL.md>` and `freeze_sha256 <sha256 of FREEZE.json>`.
2. **Generation.** `PYTHONHASHSEED=0 python -m cas.generate build` runs in one CPU slot. The gate (`cas/gate.py`,
   stage generate) checks the GO and every frozen file, refuses while `runs/generated/` exists, then writes
   `runs/RUN_CLAIM.json`, so the GO is used once. The output is `runs/generated/<world>/`.
   - **Recovery rule, pre-declared.** Generation is deterministic. If the build fails after the claim was written
     (a crash, an interruption), the coordinator may once remove the partial `runs/generated/` and the claim, log
     that in `PROGRESS.md` with the reason, and run step 2 again under the same GO. A second failure ends phase 2.
3. **Commit.** `runs/RUN_CLAIM.json`, `runs/generated/BUILD_SUMMARY.json` and each world's `PARTITIONS_MANIFEST.json`
   (the digests of its task files and removed set) are committed before any method runs.
4. **Kernels.** `python3 -I cas/kaggle_build.py` runs the gate's package stage, which checks the claim, the task
   digests, the removed sets and salts against the configuration. The three kernels are pushed privately; their
   statuses are polled with retries; their outputs are downloaded.
5. **Analysis.** `python -m cas.analysis runs/analysis <three world folders>` runs the gate's analyse stage and the
   verification of step 5 of section 10, then writes `ANALYSIS.json`. It is followed by a report and an independent
   recomputation.

## 12. Deviations from S1, all decided before any main task exists

1. There are three worlds instead of one, 11 families instead of 4, and 9 M tasks per family instead of 3.
2. The tasks are new: S1's 61 tasks and the pilot pool are excluded.
3. Generator rules 1 to 5 of section 4 are new.
4. No neural method runs (S1's S1F is dropped). The methods are S-hole, S-demo, S-shuffled, S-enum and C7m.
5. S-enum's three seeds run as separate processes, each with its own copy of the gate cache made after the
   specification methods. S1 ran one process; charged CPU can differ slightly as a result.
6. C7m also runs on E tasks, for secondaries 3 and 4.
7. The two machine-dependent CPU stops are scaled by the measured factor r.
8. The unit is the task, with the majority criterion (S1's correction), and the decision rule adds "S1-sized
   advantage refuted".
9. Every process runs with PYTHONHASHSEED=0.
10. The boundary with the companion study (section 3) fixed W2's removed set. The earlier 14-family design, which
    removed all seven symmetries of the square, was dropped before any main task existed.
11. Scoring is on committed outputs, at most two per query for every method (section 5), frozen by a commit
    stage before any label is read. S1 scored a unit as recovered when any retried candidate's prediction was
    correct; on S1's own record the two rules agree, and that rule is kept as oracle reach, descriptive.
12. Reuse and transfer are one base search per excluded task with the grown grammar, not a union over structures.
13. Growth's charged CPU includes the diagnosis, the specification enumeration and the stored CPU of cached
    regression retries, and the matched search on a motivating task gets at least that total.
14. The inference is clustered: W2's four linked families form one cluster of the decision-bearing interval; the
    McNemar p-value is conditional on task exchangeability; a source-input-clustered interval is reported.
15. Completeness is enforced: missing work makes a world INCOMPLETE; recorded failures count as not recovered;
    nothing is substituted. Every stage verifies the task files and records its executed modules.
16. The machine factor is measured under four-way concurrency and clipped to [1, 3].

## 13. Files

- **Frozen:** this file, `cas/*.py`, `config/STUDY_CONFIG.json` and `config/POOLS.json`, and revision 1's two
  files, `PROTOCOL_REVISION_1.md` and `FREEZE_REVISION_1.json`, kept byte for byte.
- **Phase 1 records:**
  - feasibility: `feasibility/`;
  - pilot and capacity: `pilot/`, with the superseded pilots in `pilot_v1_superseded/` and `pilot_v2_superseded/`;
  - power: `power/`;
  - the benchmark: `bench/`;
  - the plumbing check on S1's own world: `checks/EQUIVALENCE.json` and `checks/ANALYSIS.json`, and the smoke
    test of the matched-search driver with the budget rule: `checks/C7M_BUDGET_SMOKE.json`;
  - the two reviews of revision 1 that this revision answers: `reviews/`;
  - the generator's dry run on the pilot pool: `checks/generator_dry_run_pilot/` and `checks/DRY_RUN_CONFIG.json`;
  - the phase 1 launch scripts: `launch/`.

All of these files are listed with their sha256 in `FREEZE.json`, together with:
- every file outside this folder that phase 2 reads (S1's code and records, A2, CAST, arc-dsl, the split manifest);
- the two ARC training data files;
- the seeds and salts.

`cas/gate.py` re-checks every digest before each phase 2 stage.

## 14. Change log

**Revision 2 (6 Nov 2026), before any main task was generated and before any method ran.** It answers the two
exact-byte reviews of revision 1: the project's own (`reviews/INDEPENDENT_PRE_RUN_REVIEW.md`, commit 7ae0cb1c,
HOLD; its finding numbers are used below) and the companion study's (its interim note 0457 and full note 0458
with five blockers, B1 to B5). Revision 1's bytes are kept as `PROTOCOL_REVISION_1.md` and
`FREEZE_REVISION_1.json` (digests in the header).

1. **The primary measured reach, not pass at 2** (finding 1; B1). Revision 1 counted a growth unit as recovered
   when any of up to three retried candidates, each with two predictions, gave the right query output, so an
   earlier rolled-back candidate could be credited when the kept structure's pair was wrong; matched search had
   one pair. Revision 2 scores every method, per arm, seed and task, on at most two committed outputs chosen by
   one label-blind rule and frozen by a commit stage before any label is read (section 5). The earlier measure
   is kept as oracle reach, descriptive only, under S1's endpoint name (section 7). On S1's own record the two
   rules agree (section 8).
2. **Reuse and transfer unioned over promoted structures** (finding 2; B1). Revision 2 runs one base search per
   excluded task with the grown grammar and commits its two predictions (section 7, items 3 and 4); the union is
   kept as oracle reach.
3. **CPU accounting** (finding 3; B2). Charged (logical) CPU and actual CPU are kept apart; the charged total now
   includes the diagnosis, the specification enumeration and the stored CPU of cached regression retries (the
   regression check's loop time had charged cached retries nothing). A motivating task's matched search gets 150
   reference CPU-s or S-hole's complete charged total, whichever is larger; the protocol now states that this is a
   fixed strong baseline with at least growth's compute, four to eight times it in S1, not an equal-compute
   baseline (section 5). The kernel's stage order runs those matched searches after the S-hole units.
4. **The W2 salt** (finding 4; B4). Revision 1's text and freeze record named `cas-W2-20261105`; the executable
   configuration said `cas-W2b-20261105`. The salt was renamed to W2b when W2's removed set changed under the
   boundary, so that the new world's task order could not be mistaken for the dropped one's, and the text was not
   updated. The final pilot and the generator dry run ran with `cas-W2b-20261105`, and revision 2 names it in the
   text, the configuration and the freeze record.
5. **Completeness and custody** (B3; findings 8, 10, 11). The commit stage and the analysis refuse on any missing
   arm, seed, matched search, stage, manifest or module-pin record (INCOMPLETE); a recorded matched-search timeout,
   memory stop or child failure counts as not recovered; nothing is substituted. The analysis verifies every
   downloaded output against its manifest, the task files against the committed manifests, and the committed
   predictions' digest chain. Matched-search children have a wall-time guard, and outputs are packed after every
   stage.
6. **The generator's slot loop** (B4). With revision 1's loop, a slot with several parameter values could try one
   candidate more than `max_tries` per further parameter value (the check came after the attempt). The check now
   comes before every attempt, so at most `max_tries` candidates are tried per composite template for a slot, in
   all. The pilot and the dry run were re-run with the corrected loop (section 4); the earlier pilot is kept as
   `pilot_v3_superseded/`.
7. **Donor families** (B4). S1's donor rule divides by the number of motivating tasks of the next family; a family
   with none would have stopped the run. The rule is guarded: such families are skipped, and a task with no donor
   has a not-applicable S-shuffled unit (section 7).
8. **Manifests and pins** (B4). The gate's package stage and every kernel stage verify `REMOVED.json`, the task
   files, the salts and the worlds against the configuration; every stage records the project modules it executed
   with their digests, and the analysis requires them to equal the freeze. The sandbox for model-written code is
   replaced by the same inert stub everywhere (on Athe as in the kernel), so the executed code is the same in the
   plumbing check and in the kernels.
9. **Dependence** (B5). The decision-bearing interval clusters W2's four linked families as one (8 clusters); the
   McNemar p-value is reported as conditional on task exchangeability; a source-input-clustered interval is
   reported for the sources shared between worlds (sections 6 and 8). The power simulation was re-run under this
   rule.
10. **The machine factor** (finding 5). The benchmark now runs four copies at once, the kernel's busiest stage,
    and the factor is the concurrent median over Athe's lone reference, clipped to [1, 3]; every matched search
    records its executions per CPU-second (section 5).
11. **switch** (findings 6 and 7). The deep G0 search was repeated for switch on probe grids that hold both colours
    (section 3), and switch's reuse rows are pre-declared as expected failures (section 7).
12. **Kernel memory** (finding 9). Matched-search children are limited to 8 GB; two run beside other processes,
    three alone.
13. **Recovery after a failed build** (finding 12). Pre-declared in section 11; the gate refuses to build over a
    partial build.

Also in revision 2: the plumbing check on S1's world was re-run with the revised code (section 5). Nothing else
changed: the removed sets, families, quotas, pools, seeds, methods, budgets and the structure of the decision rule
are those of revision 1.

**Work by a parallel session.** During the repair a second copy of this session ran in the same folder until
about 22:02Z on 5 Nov and committed the checkpoint 40a89c5f. Its hunks were reconciled with `git diff`: the
concurrent benchmark (`cas/bench.py`, lone and concurrent modes) and the switch deep check (`cas/feasibility.py`
`deep_switch`, with `launch/run_deep_switch.sh`) come from that copy and were kept, with the benchmark's docstring
and factor rule edited to this design; a duplicate `deep_switch` written here was dropped. Everything else in
revision 2 is this session's.
