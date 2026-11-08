# Construction test at scale: pre-registration

Study folder: `experiments/construction_at_scale_20261105/`. Author: Chimdi Walter Ndubuisi.

Frozen on 5 Nov 2026, before any main task was generated and before any method ran on any task of this study. The
sha256 of this file, of the code, of the configuration and of the seeds is recorded in `FREEZE.json`. Phase 2
(generate, run, score) starts only after two independent exact-byte reviews and a one-use GO file written by the
coordinator (section 11).

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
- **Recovered.** A unit is recovered when a retried structure makes the task fit and its pass@2 query prediction
  is correct (S1's rule).
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
  - dmirror: apply(merge, hsplit(I, width(I))), level 13;
  - vupscale at k = 3: apply(last, upscale(apply(tojvec, I), THREE)), level 13;
  - hupscale at k = 2: apply(merge, apply(dmirror, pair(I, I))), level 14.

  It found none for compress, downscale, cmirror, rot90, rot270 or hupscale at k = 3. For switch, the 10 probe grids
  of this check contain no colour 0, so replace(I, b, ZERO) matched there (level 5). S1's novelty probes contain
  colour 0, and the gate rejects that shortcut for all 45 pairs.

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

**Dry run.** The final build code ran on the pilot pool with a reduced quota (M 2, V 1 and E 1 per family) and
filled every slot: 28, 28 and 24 tasks in W1, W2 and W3, in 419 CPU-s (`checks/generator_dry_run_pilot/`). The
pilot pool holds none of the 15 training tasks A2 solved, so real U tasks were not exercised there; that path was
tested on S1's own six real U tasks instead.

**Seeds and salts.**
- generator salts cas-W1-20261105, cas-W2-20261105 and cas-W3-20261105;
- pool salt cas-pools-20261105;
- structure orders S1's `random.Random("s1-order-" + str(s))` for seeds s = 0, 1, 2;
- PYTHONHASHSEED=0 for every process.

**Pilot** (`cas/pilot.py`; `pilot/PILOT_RESULTS.json`; pilot pool only; run with this configuration).
- **Slots.** All 33 pilot slots (11 families x T1, T2, T3) were filled from 1,140 candidates. Generation used
  168 CPU-s: 3.5, 1.9 and 11.5 CPU-s per kept task in W1, W2 and W3.
- **Controller.** It sent 30 of the 33 to construction (share 0.91) and used 5.3 CPU-s per task on average. The
  three tasks sent to deeper search were downscale T1, trim T1 (as in S1) and dmirror T1.
- **Typed holes.** Every pilot task has 3 sketches (identity, an outer and an inner inverse of an invertible G0
  operation).
- **No method ran on any pilot task.**

Two earlier runs are kept, superseded. Both used the 14-family design that the boundary replaced:
- `pilot_v1_superseded/`, with S1's family order;
- `pilot_v2_superseded/`, with the final family order.

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

**Plumbing check** (`cas/equivalence.py`, `checks/EQUIVALENCE.json`). It used only S1's own tasks and records,
never a pilot or main task. The phase 2 runner and analysis, pointed at a copy of S1's world, reproduce S1:
- the controller: 38 of 38 decisions and typed holes identical;
- the specification methods: 99 of 99 units identical (candidate rows, outcomes, retries, promotions);
- S-enum seed 0: 10 of 11 promotions identical. The other unit (t83286f67) stopped one structure earlier on its
  charged-CPU limit (16 structures and 61 charged CPU-s, against S1's 17 and 78). S-enum's CPU-time stop allows
  this, and S1's own records show the same effect;
- the 10 promoted structures: family, excluded-task fits, kind and contract verdict all identical;
- the primary contrast: S1's task-level record exactly (8 against 5 of 11, discordant 4 : 1, p = 0.375,
  "inconclusive").

Matched search was not rerun in that check: S1's recorded results stood in, and none existed for E tasks.

## 6. Primary contrast

**S-hole against C7m, majority criterion, on all motivating tasks of all three worlds.**
- **Unit.** One motivating task; seeds are within-task replicates (S1's task-level correction).
- **Statistics.** The statistics are S1's code (`testib_rest._compare`):
  - the exact two-sided McNemar test on the discordant tasks;
  - the mean paired difference;
  - a unit bootstrap 95% interval;
  - a family-clustered bootstrap 95% interval: the 11 families resampled with replacement, 10,000 draws, seed 7,
    percentile method. As a sensitivity analysis only, the same interval is also reported with W2's four linked
    families merged into one cluster (8 clusters).
- **Decision.** One outcome only:
  - **S-hole beats matched search:** p < 0.05 and the family interval lies entirely above 0;
  - **matched search beats S-hole:** p < 0.05 and the family interval lies entirely below 0;
  - **S1-sized advantage refuted:** neither of the above, and the family interval's upper end is below 3/11 = 0.273
    (S1's task-level difference, 8 - 5 of 11). Any advantage is then smaller than S1's;
  - **inconclusive:** otherwise.

## 7. Secondary contrasts (Holm over these four, no decision weight)

Each secondary uses the same statistics as the primary. It holds when its Holm-adjusted p < 0.05 and its family
interval excludes 0.
1. **S-hole against S-shuffled.** Majority criterion, motivating tasks.
2. **S-hole against S-enum.** All-3 criterion for both methods, motivating tasks.
3. **Reuse on excluded tasks.**
   - Unit: an E task of family f.
   - S-hole succeeds when G0 plus one structure that S-hole promoted for family f fits and predicts the query at the
     base budget. Each structure is tried alone; a structure counts when S-hole promoted it on a motivating task of
     f in at least 2 of 3 seeds.
   - Comparison: C7m on the same E task.
4. **Transfer to other families.** As 3, with the structures S-hole promoted for the other families of the same
   world.

**Descriptive only.** These outputs carry no test:
- every method's counts under the any-seed, majority and all-3 criteria;
- S-hole against S-demo;
- S-enum against C7m;
- per-world and per-family tables;
- each promoted structure's agreement with every removed reference (E inputs plus 40 probe grids), its kind
  (macro or expansion relative to G0, by a 1,000,000-execution search) and its verdict from CAST's contract checker;
- the controller's decisions;
- unfilled slots;
- charged and measured CPU per method;
- the C7m cost levels reached.

## 8. Power (`cas/power.py`; `power/*.json`)

The model is S1's task-level effect, from its 11 tasks:
- both methods recovered 4;
- S-hole only 4;
- C7m only 1;
- neither 2.

Each simulated study has F families x m M tasks per family, and each task becomes motivating with probability
11/12. There are 4,000 simulated studies per row and 2,000 bootstrap draws each, and the decision rule is that of
section 6.

| scenario | F | m | about N motivating | S-hole beats matched search | S1-sized advantage refuted | inconclusive |
|---|---|---|---|---|---|---|
| A: S1's pooled effect | 11 | 5 | 50 | 0.80 | 0.04 | 0.17 |
| A | 11 | 6 | 61 | 0.86 | 0.04 | 0.09 |
| A | 11 | 8 | 81 | 0.96 | 0.03 | 0.02 |
| **A (chosen)** | **11** | **9** | **91** | **0.97** | **0.02** | **0.01** |
| A, one family lost | 10 | 9 | 83 | 0.96 | 0.02 | 0.02 |
| A, 8 families of 7 (a lower bound if W2's four count as one) | 8 | 7 | 51 | 0.79 | 0.05 | 0.16 |
| B: S1's between-family spread | 11 | 9 | 91 | 0.30 | 0.07 | 0.63 |
| N: no effect | 11 | 9 | 91 | 0.019 | 0.94 | 0.03 |
| C: design-based, two G0 routes (trim, upscale) | 11 | 9 | 90 | 0.99 | 0.00 | 0.02 |
| C: design-based, five G0 routes | 11 | 9 | 90 | 0.39 | 0.09 | 0.52 |

The rows come from four files:
- `power/POWER_S1_EFFECT_F10_F11_M8_M9.json` (m = 8 and 9);
- `power/POWER_S1_EFFECT_F8_F11.json` (m = 4 to 7);
- `power/POWER_DESIGN_C_TWO_ROUTES.json` and `power/POWER_DESIGN_C_FIVE_ROUTES.json` (the C rows; motivating share
  0.91, from the pilot);
- `power/POWER_S1_EFFECT.json`, which holds the 12- and 14-family rows of the design the boundary replaced.

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

  The five-route row treats dmirror, hupscale and vupscale like trim and upscale. Their routes cost 13 to 14, so
  matched search can reach them mainly on T1 tasks, which the controller often sends to deeper search. The truth
  is expected to lie between the two C rows.

**The choice.** m = 9 keeps S1's 1 : 1 : 1 template mix. It gives 97% power at S1's observed effect, 96% if one
family yields nothing. With only 8 families of 7 tasks, a lower bound for counting W2's four linked families as
one, it still gives 0.79. With no effect, the
study refutes an S1-sized advantage with probability 0.94 and calls a false positive with probability 0.019.

**The limit.** If the new families differ from one another as much as S1's four did (where trim favoured matched
search), the family-clustered interval caps power near 0.30 whatever m is. The same holds if matched search finds
the new G0 routes as often as it found trim's and upscale's. Only more families would raise it, and the boundary
leaves 11 (section 3). This limit is stated now so that an inconclusive result is read correctly.

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
| evaluation | about 1.2 |
| **total** | **about 13 reference CPU-h** |

On Kaggle, expect about 18 CPU-h, because the two CPU stops scale with the machine factor (below, r of about
1.4). Even at r = 2 the total would be about 26 CPU-h.

**Stop rules,** in CPU time, never wall clock:
- the per-search caps of section 5;
- 3 retries per specification unit;
- 60 charged CPU-s per S-enum unit;
- 150 CPU-s per C7m task (a C7m search that runs out of memory beside others is run once more alone, and that
  result stands);
- 15 CPU-h per world kernel (no new stage starts after it; the world is then INCOMPLETE), so at most 45 CPU-h for
  the study.

**Machine factor.** S-enum's 60 s and C7m's 150 s are stated in reference CPU-seconds (Athe, where S1 ran).
1. Each kernel first runs `cas/bench.py`, a fixed 200,000-execution search repeated 5 times.
2. The factor is r = median / Athe reference (`bench_reference_cpu_s` in the configuration), clipped to [1, 2].
3. Both stops are multiplied by r, so a slower machine does not handicap the search methods. The specification
   methods stop on execution counts and are unaffected.
4. r and a second benchmark run at the end are recorded.

**Evidence for the factor.** In the S1 replay on Kaggle (3 Nov), matched search ran 1.40 times fewer executions per
CPU-second than on Athe. That is the median over the 10 tasks stopped by its CPU cap (from the replay's own output,
downloaded read-only). The benchmark takes 1.281 CPU-s on Athe (`bench/BENCH_ATHE_REFERENCE.json`, median of 5).

**Route.**
1. Generation runs on Athe in one CPU slot (`scripts/with_cpu_slot.sh`, nice 19).
2. Everything else runs in three private Kaggle kernels, one per world, CPU only, internet off, under the account
   chimdiwalter.
3. Each kernel is built by `cas/kaggle_build.py`, the S1 replay's route: a deterministic .tar.gz of the frozen files
   at their repository paths, embedded with its sha256.
4. The kernel runs `cas/kaggle_main.py`:
   - controller;
   - specification methods, beside C7m on motivating tasks (2 child processes);
   - S-enum, its 3 seeds in parallel;
   - C7m on E tasks (2 child processes);
   - evaluation.
5. Outputs come back with `kaggle kernels output` and are checked against their manifest before the analysis
   (`cas/analysis.py`) runs on Athe.

Kaggle ran Python 3.13 in the replay. Expected wall time per kernel, at r = 1.4, is about 3 hours (W3 2.2, W1 2.7,
W2 2.8), well inside Kaggle's 12-hour session. Step B, GPUs and anything public are untouched.

## 11. Phase 2 procedure

1. **GO.** The coordinator writes `GO_CAS` in this folder. Its first two lines must be exactly
   `protocol_sha256 <sha256 of PROTOCOL.md>` and `freeze_sha256 <sha256 of FREEZE.json>`.
2. **Generation.** `PYTHONHASHSEED=0 python -m cas.generate build` runs in one CPU slot. The gate (`cas/gate.py`,
   stage generate) checks the GO and every frozen file, then writes `runs/RUN_CLAIM.json`, so the GO is used once.
   The output is `runs/generated/<world>/`.
3. **Commit.** The task-file digests (`BUILD_SUMMARY.json` and each `PARTITIONS_MANIFEST.json`) are committed before
   any method runs.
4. **Kernels.** `python3 -I cas/kaggle_build.py` runs the gate's package stage, which checks the claim and the task
   digests. The three kernels are pushed privately; their statuses are polled with retries; their outputs are
   downloaded and verified.
5. **Analysis.** `python -m cas.analysis runs/analysis <three world folders>` writes `ANALYSIS.json`. It is followed
   by a report and an independent recomputation.

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

## 13. Files

- **Frozen:** this file, `cas/*.py`, `config/STUDY_CONFIG.json` and `config/POOLS.json`.
- **Phase 1 records:**
  - feasibility: `feasibility/`;
  - pilot and capacity: `pilot/`, with the superseded pilots in `pilot_v1_superseded/` and `pilot_v2_superseded/`;
  - power: `power/`;
  - the benchmark: `bench/`;
  - the plumbing check on S1's own world: `checks/EQUIVALENCE.json` and `checks/ANALYSIS.json`;
  - the generator's dry run on the pilot pool: `checks/generator_dry_run_pilot/` and `checks/DRY_RUN_CONFIG.json`;
  - the phase 1 launch scripts: `launch/`.

All of these files are listed with their sha256 in `FREEZE.json`, together with:
- every file outside this folder that phase 2 reads (S1's code and records, A2, CAST, arc-dsl, the split manifest);
- the two ARC training data files;
- the seeds and salts.

`cas/gate.py` re-checks every digest before each phase 2 stage.
