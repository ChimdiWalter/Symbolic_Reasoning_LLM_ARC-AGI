# Independent pre-run review of the construction test at scale (revision 3)

Review commissioned by the coordinator, 6 Nov 2026 (UTC, about 01:50Z to 03:00Z). Object reviewed: revision 3 of
the pre-registration, frozen in commit 67322f40, folder `experiments/construction_at_scale_20261105/`. Every
statement about code cites the line numbers of that commit; the files were read from a scratch mirror made with
`git archive 67322f40`, whose code files equal their `FREEZE.json` digests. The reviewer did not design the study.
Earlier reviews: this project's own of revision 1 (`reviews/INDEPENDENT_PRE_RUN_REVIEW.md`, HOLD) and the companion
study's of revisions 1 and 2 (revision 2: HOLD on five points, its `REPORT.md` under
`<companion study folder>/construction_at_scale_revision2_independent_review_20261105/`).

**Verdict: PASS WITH FIXES.** The freeze is sound: both digests verify from the committed bytes, every digest in
`FREEZE.json` verifies, revisions 1 and 2 are kept byte for byte, and the gate refuses without a GO and enforces one
use. All five points of the companion's revision 2 review are fixed in substance, each confirmed in code and by a
check. Nothing reads the ARC evaluation set, no main task exists and no arm has run on any task of this study. The
primary does not union candidates, the CPU accounting has no gap, every seed is fixed and the Kaggle kernels are
private with internet off. There is no high-severity finding. Two medium findings must be fixed before any GO:
the matched-search memory limit can fail the comparator and its pre-declared remedy cannot recover that failure
(Finding 1), and three boundaries of the strict verification remain open, each of which changes the primary when a
kernel output is corrupted (Finding 2). One low finding also needs action before the GO: rule 6 is stated more
broadly than the generator enforces (Finding 3). The other findings are corrections for the report or procedure.

**State of the tree.** After this review began, commit 31ede42a ("revision 4 in progress", about 02:24Z) changed
`PROTOCOL.md` (live sha256 2b0df50e...), `cas/analysis.py`, `cas/run_world.py`, `cas/equivalence.py`,
`cas/freeze.py` and `checks/strict_fixture.py`; `FREEZE.json` is still revision 3's, so the gate now refuses until
revision 4 is frozen. Revision 3 is kept as `PROTOCOL_REVISION_3.md` (6a30ac31...) and `FREEZE_REVISION_3.json`
(9d56be8b...), both verified byte-identical. A GO on revision 3 is therefore no longer possible as the tree stands;
the fixes below belong in revision 4 (section 7 says which ones its change log already covers).

Labels used below. S1 is the original construction test (`experiments/capability_growth_20261027/`). A2 is the
project's bottom-up program search over arc-dsl, and G0 is the starting language (A2's grammar minus a world's
removed operations). The worlds are W1 (S1's four crop and resize operations), W2 (the quarter turns and diagonal
reflections) and W3 (the one-axis stretches and the colour exchange). The task partitions are M (motivating), V
(system validation), E (excluded, evaluator-only), D (search-level decoys) and U (previously solved tasks, the
regression set); a real U task is an ARC training task that A2 solved, kept with its real output. The methods are
S-hole (growth from CORA's own typed holes), S-demo (the identity hole only), S-shuffled (another task's holes),
S-enum (blind enumeration of the structure space) and C7m (matched static search over G0 alone). "Committed
outputs" are the at most two predictions per arm, seed and task frozen before scoring; "oracle reach" is the
descriptive any-candidate endpoint. "The companion" is the companion study; its labels for its five revision 2
points were C1 (completeness), C2 (manifests and pins), C3 (committed reuse and transfer predictions), D1 (the
S-enum cap) and S1 (inference scope, a different use of "S1" from the construction test).

## 1. Hashes and freeze integrity (verified)

| check | result |
|---|---|
| `PROTOCOL.md` at 67322f40 | 6a30ac318e4feca7f5147a59a8114d7c4fe2ed469226ec2b6e82968b0b52d46f, as stated; equals `FREEZE.json` "protocol_sha256" |
| `FREEZE.json` at 67322f40 | 9d56be8b4946cb92f73f00d8ab0ef6a89a77a225fa0d81948f54bfa44b093235, as stated |
| 98 study files in "files_sha256" | all 98 equal the bytes committed at 67322f40, and equalled the live bytes when checked (before the revision 4 work) |
| 44 dependencies (S1's code and records, A2, the harness, CAST, arc-dsl, the CPU-slot script) | 37 equal the committed bytes; the 7 untracked in git (`a2/out/corpus.json`, `a2/out/traces.jsonl`, the five arc-dsl files) equal the live bytes; all 44 identical to the records of revisions 1 and 2 |
| 2 ARC training data files | equal the live bytes; identical to revisions 1 and 2 |
| seeds and salts | identical to revision 2 (W2 salt cas-W2b-20261105) |
| revision 1 kept | `PROTOCOL_REVISION_1.md` (b3759bfc...) and `FREEZE_REVISION_1.json` (260ee753...) equal `PROTOCOL.md` and `FREEZE.json` of revision 1's freeze commit 6b5fb6f8 |
| revision 2 kept | `PROTOCOL_REVISION_2.md` (885bbcc8...) and `FREEZE_REVISION_2.json` (c7c586fa...) equal `PROTOCOL.md` and `FREEZE.json` of revision 2's commit ecafd841 |
| "supersedes" in `FREEZE.json` | lists the same four digests; the protocol header (lines 10 to 13) prints them |
| after the freeze | commit 1b40a376 added only `checks/strict_fixture.py`, `checks/STRICT_FIXTURE_REVISION_3.json` and a `PROGRESS.md` entry, none of them frozen |

Changed from revision 2, by digest: `PROTOCOL.md`, `cas/analysis.py`, `cas/freeze.py`, `cas/generate.py`,
`cas/kaggle_build.py`, `cas/run_world.py`, `config/STUDY_CONFIG.json`, the dry-run and plumbing-check records and two
launch scripts. `cas/gate.py`, `cas/env.py`, `cas/bench.py`, `cas/kaggle_main.py`, the pools and the power files are
unchanged from revision 2.

## 2. The gate (verified)

`cas/gate.py` changed in revision 2, so it was exercised again, on the scratch mirror with `CAS_STUDY` pointing at
it. No file named `GO_CAS` was written anywhere: the module's GO path was pointed at a token file with another name
in the reviewer's scratch folder, holding the two required lines.

| step | outcome |
|---|---|
| no token, stage generate | `FAIL generate: no GO_CAS` |
| token with the two lines, generate | `ok generate`; `runs/RUN_CLAIM.json` written with the token's sha256 |
| generate again | `FAIL generate: the GO was already used (runs/RUN_CLAIM.json exists)` |
| stage analyse | ok |
| one line appended to the token, analyse | `FAIL analyse: RUN_CLAIM.json names other GO bytes` |
| wrong freeze line, analyse | `FAIL analyse: GO_CAS does not bind the live PROTOCOL.md and FREEZE.json` (and the claim mismatch) |
| claim removed, `runs/generated/` present, generate | `FAIL generate: runs/generated/ exists: a partial build must be removed deliberately first` |
| claim and `runs/generated/` removed, generate | ok (the pre-declared recovery path) |
| package, with the pilot dry-run worlds standing in for a task set | ok |
| package, one byte added to W3's `TASKS_EVAL.json` | `FAIL package: W3: task files differ from their manifest` |
| package, W3 missing / an extra world W4 | `FAIL package: built worlds [...] differ from the configuration` |
| package, W1's removed set edited (manifest re-hashed) | `FAIL package: W1: REMOVED.json or salt differ from the configuration` |
| one byte appended to `cas/analysis.py` / to S1's `cgrow/s1.py`, analyse | `FAIL analyse: frozen file changed or missing` / `dependency changed or missing` |
| everything restored, analyse | ok |

So the gate refuses without a GO, binds the GO to the live protocol and freeze, re-checks every study file,
dependency and data digest (lines 56 to 70), enforces one use through the claim, created in exclusive mode (lines 72
to 77, 115), refuses to build over `runs/generated/`, and its package stage checks the world set, the task digests,
the removed sets, the families and the salts (lines 86 to 109). Two limits stand: the claim is the only token of
use, so the one-time recovery is procedural (a second removal would pass too), and the package stage does not check
that the task set came from the main pool (Finding 6).

## 3. The companion's five revision 2 points

**(a) Strict reconciliation of worlds, tasks, arms, seeds and endpoints. Fixed, with three open boundaries
(Finding 2).**
- Worlds: the given directories, after `realpath`, must equal exactly the `analysis_world_dirs` that packaging
  recorded, with no duplicate, and their names must equal the configured worlds (`cas/analysis.py` lines 132 to
  141); each world's directory, manifest and results must name the same world, and its removed set, families and
  salt must equal the configuration (lines 195 to 208). Packaging records that list only after checking one
  complete folder per configured world, named as in its manifest (`cas/kaggle_build.py` lines 103 to 118).
- Tasks: the expected motivating tasks are the partition M tasks of the hashed `TASKS_EVAL.json` with the
  construction decision in the controller summary; the expected excluded tasks are its partition E (lines 79 to
  89). The results must hold exactly those task ids (lines 161 to 163, 180 to 182), with family and source equal to
  the task file (lines 168, 190).
- Arms, seeds, endpoints: every arm and seed needs a boolean "recovered", None being accepted only for an S-shuffled
  unit that records "not_applicable" (lines 170 to 177); the matched search needs a boolean endpoint and failure
  flag (line 178); each excluded task needs boolean matched-search, reuse and transfer endpoints (lines 187 to 189);
  the commitment must hold exactly the expected unit and matched-search keys and every reuse and transfer key (lines
  262 to 270). Any problem writes `INCOMPLETE.json` and exits before any statistic (lines 377 to 381).
- Checks run: the author's fixture (`checks/strict_fixture.py` of commit 1b40a376) run unchanged on the scratch
  mirror: the complete fixture passes and all 12 single defects return INCOMPLETE, as its record says. The
  reviewer's own fixture (same base, 23 cases) adds a pin record with ok true but a non-empty mismatch list, an
  output changed after its manifest, an extra motivating task, an untyped matched-search endpoint on an excluded
  task, and two worlds whose motivating tasks share sources: all INCOMPLETE. Three further cases pass and change the
  primary (Finding 2).

**(b) Output-manifest coverage and module-pin validation. Fixed.**
- The output manifest must exist and be non-empty, its keys must equal every file under `runs/` (other than `.tmp`
  files and itself), every required output must be listed, and every digest must equal its file (lines 226 to 246).
  The kernel writes it in the same format (`cas/kaggle_main.py` lines 50 to 61, 119, 130).
- `_check_pins` (lines 96 to 124) requires all nine records, each with modules, an empty mismatch list and ok true,
  the entry module `cas/run_world.py` and eight required modules; it then validates every recorded path and digest
  against the bound `FREEZE.json` itself, study files and dependencies, and accepts a stub only for the four sandbox
  module names. The record's own flag is required but not trusted.
- Checks run: the fixture cases for a changed digest, an unpinned module, a missing record, an empty manifest, a
  file outside the manifest, a file changed after the manifest and a non-empty mismatch list all return INCOMPLETE.
  In a package built from the mirror (section 5), the real pin writer recorded 33 modules, all inside the package,
  with ok true and no mismatch.

**(c) Reuse and transfer predictions committed before any label. Fixed.**
- The commit stage builds the grown grammars from S-hole's promotion records only (a structure promoted on one of
  the family's motivating tasks in at least 2 of 3 seeds; `cas/run_world.py` lines 414 to 431), then runs one base
  search per excluded task with the family's grammar (reuse), with the other families' grammar of the same world
  (transfer), and with each promoted structure alone (lines 436 to 457). The searches see the demonstrations and
  query inputs only (`X.as_task`, which returns no output). At most two predictions are kept for each, and they are
  written with the units and matched searches into `COMMITTED_PREDICTIONS.json`, with a content digest and a file
  digest (lines 459 to 466), after the completeness check (lines 379 to 409).
- The evaluator verifies the digest (lines 487 to 492), refuses if its own grown grammars differ from the committed
  ones (line 594), and scores only the saved predictions (lines 553 to 554, 597 to 611); its only searches are the
  kind checks on probe grids (line 584).
- Checks run: the plumbing check's saved files were re-scored independently. The digest chain holds; there are 132
  unit, 35 matched-search and 288 grown-grammar records, none with more than two predictions; every recorded
  endpoint (units, matched searches on motivating and excluded tasks, reuse, transfer) equals a fresh scoring of the
  committed predictions against S1's task outputs, with no mismatch; reuse solves 24 of 24 excluded tasks and
  transfer 1.

**(d) S-enum's cap behaviour pre-declared and its overshoot recorded. Fixed; the wording is inexact (Finding 4).**
- `PROTOCOL.md` lines 329 to 333 state S1's rule: the charged CPU is checked before each candidate (`cgrow/s1.py`
  line 249), and a candidate started below the cap completes with its whole charge. `cas/run_world.py` lines 192 to
  198 record the scaled cap and the overshoot of every unit; the evaluator summarises the units with overshoot, the
  mean and the maximum (lines 629 to 632). The scaled cap reaches S1's loop through the module constant it reads at
  call time (line 235).

**(e) No cross-world source link for the primary; the excluded-task secondaries scoped. Fixed for the primary; the
text claims more than the code does (Finding 3).**
- The generator builds the motivating tasks of all worlds first (W3, W1, W2), each builder excluding every source
  already used by any world's motivating task (`cas/generate.py` lines 182 to 185, 384 to 389), and asserts at the
  end that no source serves motivating tasks of two worlds (lines 400 to 406). The analysis checks the same on the
  results (`cas/analysis.py` lines 158 to 159, 274 to 276).
- The reuse and transfer contrasts carry the label "conditional on no cross-world source link among excluded tasks"
  (lines 443 to 445; `PROTOCOL.md` lines 488 to 492), with a joint source-and-family interval over the connected
  components of cluster and source links (lines 303 to 319, 344 to 349), reported when there are at least 4
  components; the number of excluded sources shared between worlds is reported (lines 468 to 471).
- Checks run: in the dry run on the pilot pool no motivating source is shared with any task of another world (37
  sources, no link). A two-world fixture whose motivating tasks share all 11 sources returns INCOMPLETE with 11
  link messages. A test of the real `build()` with stubbed filters and synthetic source ids (no ARC grid read, no
  search, nothing written) found no motivating-to-motivating link in 12 of 12 trials, and the assertion fired when
  the cross-world exclusion was switched off.

## 4. Exposure and state (verified)

- **The ARC evaluation set is never read.** The only reference in the study code is `cas/pools.py` line 28, which
  reads the evaluation ids from the split manifest to assert that they overlap no pool. The loader opens the
  evaluation file only for the split ARC_eval_dev (`harness/data.py` line 62), which no study code passes. The pools
  are unchanged since revision 1 (pilot 100, main 535, disjoint; sorted lists hash to d321d802... and a740f6a3...).
- **Held outputs.** As in S1, the system-side stages load the evaluator file for partition and family labels
  (`s1.motivating`; `cas/run_world.py` lines 246, 368), but every search receives only demonstrations and query
  inputs (`X.as_task`); a query output is first compared in the evaluation stage. This is a property of the code,
  not a process boundary, unchanged from S1.
- **No main task.** The study folder has no `runs/` and no `GO_CAS`. Across its 81 JSON files there are 98 distinct
  task sources: 37 from the pilot pool (pilot, superseded pilots, dry run) and 61 of S1's own (the plumbing-check
  copies); none is a main-pool id, and no log mentions one.
- **No arm has run on a study task.** The only arm outputs are the plumbing check on S1's own world
  (`checks/s1_world/`); the pilot record holds controller results only.
- **Dry run.** 22, 22 and 17 tasks in W1, W2 and W3, with 8, 8 and 6 motivating tasks; 298.1 CPU-s; the two W3
  excluded T1 slots (vupscale, hupscale) unfilled; the disjointness flag true; no excluded task in a system file;
  salts as configured; every manifest digest equal to its file. All as stated in `PROTOCOL.md` lines 281 to 285.

## 5. Other risks to reportability

- **Does the primary union candidates? No.** A growth unit commits the two predictions of one structure's retry,
  the promoted one, else the first quarantined one, else nothing (`cas/run_world.py` lines 347 to 357); matched
  search commits the two predictions of its one search (line 281); both are scored on those saved outputs only
  (lines 513, 523). Promotion uses the regression set and the validation pool, and the regression check compares
  with the controller's own base predictions, never a label (`cgrow/s1.py` lines 163 to 176). The S1 records
  re-scored above have at most two predictions everywhere.
- **CPU accounting: no gap found.** A unit's charged total is the task's diagnosis (base search, 4x probe, closest
  program and sketches, measured once in the controller stage), the specification enumeration and every gate charge,
  with cached results charged at their first computation and the regression check charged the stored CPU of its
  retries (lines 108 to 117, 211 to 218). Matched search on a motivating task gets the larger of 150 reference
  CPU-s and S-hole's largest charged total on that task (lines 253 to 265), and runs only after the S-hole units.
  The kernel's 15 CPU-h stop counts the CPU of every descendant process (`cas/kaggle_main.py` lines 39 to 41, 110 to
  117). The only imprecision is that charged seconds measured alone (the controller) and beside two other processes
  (the arms) are added together, while matched search runs beside up to three others; this can matter only when
  S-hole's total exceeds 150 reference CPU-s, which never happened in S1 (at most 37.3 CPU-s).
- **Seeds: all fixed.** Structure orders, bootstrap seeds 1 and 7, generator and pool salts, and the power seeds are
  fixed; the notebook sets PYTHONHASHSEED=0 for every kernel process, and the documented generation command sets it
  on Athe. The only hash-order iteration seen in A2's search (`a2/bus.py` line 332) fills a dictionary by key. The
  CPU-time stops are the only non-deterministic element, and every matched search records its executions per
  CPU-second.
- **Kaggle custody: intact.** A package was built from the mirror with `cas/kaggle_build.py` (the gate call stubbed;
  the gate is tested in section 2): `kernel-metadata.json` has private true, internet false, GPU and TPU false, and
  no data, competition, kernel or model sources (lines 127 to 130); the notebook asserts the archive digest before
  unpacking (line 74), and the embedded archive's digest equals `PACKAGE_MANIFEST.json`. Unpacked in a separate
  folder, the 57-file package verified each world against its manifest and the configuration, gave a clean pin
  record, and ran one benchmark search (200,000 executions on probe grids, 1.08 CPU-s). The kernel record names the
  archive and task-manifest digests (`cas/kaggle_main.py` lines 84 to 85), which the analysis checks
  (`cas/analysis.py` lines 220 to 224).
- **The plumbing check's other claims hold** (`PROTOCOL.md` lines 416 to 440): controller 38 of 38 decisions and
  hole sets; 99 of 99 specification units; S-enum seed 0, 11 of 11 promotions; the 10 promoted structures identical
  in family, excluded-task fits, kind and contract verdict; committed outputs equal to oracle reach (S-hole 8, S-demo
  4, S-shuffled 0, S-enum 9); the primary recomputed with S1's statistics code copied verbatim (8 against 5 of 11,
  discordant 4 : 1, p = 0.375, family interval [-0.2, 0.667], source and unit intervals [-0.091, 0.636], joint
  interval [-0.2, 0.667], "inconclusive"); S-hole's charged mean 13.8 CPU-s (diagnosis 4.6, gates 9.2), maximum
  23.9, actual 3.1; the budget rule would raise no S1 budget; 5 of 5 matched-search fits again, 4 with the same
  program. The exception is the overshoot figure (Finding 4).

## 6. Findings, by severity, with exact fixes

### Medium

**Finding 1. The matched-search memory limit can fail the comparator, and the "run once more alone" rule cannot
recover that failure.** Every matched-search child sets an 8 GB address-space limit (`cas/run_world.py` lines 58,
270 to 271). A MemoryError is recorded as `memory_capped` with no predictions (lines 282 to 283), the commit stage
marks it failed (lines 397, 405), and the evaluator scores a failed search as not recovered (lines 523, 608), as
`PROTOCOL.md` section 2 pre-declares. The remedy the protocol promises, "a child that runs out of memory beside
others is run once more alone, and that result stands" (lines 410 to 413 and 604), is lines 330 to 335, which start
the same command with the same 8 GB limit. An address-space limit does not depend on what else runs and the search
is deterministic, so the rerun reproduces the MemoryError and can never recover one. The case where running alone
would help, a child killed by the operating system when the kernel's memory runs out, leaves no result line and is
recorded as `child_failed` (line 304), which is not rerun at all. Exposure: S1 ran its matched searches at 12 GB,
one at a time (`cgrow/testib_rest.py` line 25), reaching up to 53.2 million executions in 150 CPU-s with none
memory-capped (`experiments/capability_growth_20261027/runs/ib_c7m/c7m.json`); the only measurement at 8 GB is the
smoke test, one task at 16.8 million
executions (`checks/C7M_BUDGET_SMOKE.json`); A2's bank of values has no size cap (`a2/bus.py` lines 147, 278). Every
memory failure counts against matched search, that is, toward "S-hole beats matched search". (This project's
review of revision 1, its finding 9, proposed the 8 GB limit together with the rerun rule and missed that the rerun
cannot help against an address-space limit.) Fix, before the GO, one of:
- (a) in the code: rerun a `memory_capped` search, and a `child_failed` search with return code -9, once with a
  larger limit (for example 20 GB) at a point where no other matched-search child runs; record every child's peak
  virtual memory (VmPeak, the quantity the limit bounds);
- (b) without changing frozen bytes: measure the peak virtual memory of the 8 GB matched search on S1's 11
  motivating tasks at 150 CPU-s (phase 1 evidence on S1's own tasks), commit it, and apply (a) if any exceeds 6 GB.

In either case, pre-declare as a descriptive output beside the decision the primary recomputed without the tasks
whose matched search failed, and correct line 335, which still says 12 GB.

**Finding 2. Three boundaries of the strict verification remain open, and each changes the primary.** The
reviewer's fixture found three corrupted-output cases that pass `verify_complete` and reach the statistics:
1. **A duplicated motivating row** (the same task twice in `world_results.json`) passes, because lines 161 to 163
   compare the set of task ids while `main` iterates the list (lines 384, 390). The primary then counts 12 tasks
   instead of 11, with 5 : 1 discordant tasks and p = 0.219 instead of 4 : 1 and 0.375.
2. **A controller summary that lacks one motivating task**, with the commitment and the results consistent with it,
   passes with 10 tasks. The expected motivating set is read from `runs/prep_v4/controller_summary.json`, a kernel
   output (lines 83 to 85), which is never reconciled with the hashed system task list (`TASKS_SYSTEM.json`, or the
   manifest's "system_ids") or with the controller decisions the results carry.
3. **An endpoint that disagrees with the committed predictions** (S-hole's "recovered" set true on every seed of a
   task whose saved outputs are wrong) passes, with p = 0.219. The analysis takes every endpoint from
   `world_results.json` and checks the commitment's keys and digests (lines 250 to 273), but never re-scores the
   committed predictions against the hashed `TASKS_EVAL.json`, although it reads both.

Two minor cases also pass: a committed unit with three predictions (the two-output rule is not re-checked), and an
excluded task whose matched search has no failure flag (line 187 checks the endpoint only, unlike line 178). None of
these can arise in an intact run: the evaluator builds one row per sorted motivating task and scores from the
committed file (`cas/run_world.py` lines 499 to 527), and the controller loop covers every system task (lines 147
to 162). But they are the class of boundary the revision 3 reconciliation was written to close, and
`PROTOCOL.md` line 644 promises that "the results hold exactly the expected motivating and excluded tasks". Fix,
before the GO: in `verify_complete`, require the results' rows to be unique and exactly as many as the expected
tasks; require the controller summary's task set to equal the hashed system task ids, with every decision one of
the controller's (`cgrow/controller.py`, `analyze`), and to agree with the decisions recorded in the results;
re-score every committed unit, matched-search, reuse and transfer record against `TASKS_EVAL.json` (at most two
predictions each) and require equality with the recorded endpoints. If frozen bytes are not to change, put these
checks in the independent recomputation that section 11 step 5 already requires, as a committed script whose
sha256 is written as a third line of `GO_CAS` (the gate checks only the first two lines, and the claim binds all of
the GO's bytes), and pre-declare that any mismatch makes the study INCOMPLETE.

### Low

**Finding 3. Rule 6 is stated more broadly than the generator enforces.** `PROTOCOL.md` line 251, the
configuration's "motivating_sources" entry and `cas/generate.py` lines 26 to 31 say that a source used by a
motivating task is excluded from every task of the other worlds. The generator reserves every world's real U tasks
first, in per-world sets (lines 296 to 317, 380 to 383), and a motivating builder excludes only its own world's used
and reserved sources and the motivating sources already taken (line 184). A source reserved as a real U task in one
world can therefore serve a motivating task of another world whenever that world did not reserve it (its G0 does
not solve the task, or the task fell outside that world's six, which each world chooses in its own salted order).
Seven of the eight A2-solved main-pool tasks have every input at most 12 x 12, so they are eligible motivating
sources. In the stubbed test of the real `build()` (section 3, point (e)) such links appeared in 12 of 12 trials (1
to 5 each), while links to other worlds' V, E, D and derived U tasks stayed at zero. The primary is not affected: no
two primary units share a source, and the link runs through another world's regression set, which can couple
outcomes only weakly. But the sentence is false as written, and the analysis's shared-source counts cover motivating
and excluded tasks only (`cas/analysis.py` lines 382 to 387, 467 to 471), so these links would go unreported. Fix,
before the GO, one of: (a) in the code, exclude the union of every world's reserved real U sources while building
motivating tasks; or (b) at step 3 of section 11, before any method runs, count these links from the committed task
files, record the count, and state the rule exactly in the report ("excluded from every V, E, D and derived U task
of the other worlds; real U tasks, reserved first, may share a source with another world's motivating task").

**Finding 4. The S-enum cap is described inexactly, and its plumbing-check figure is wrong.** `PROTOCOL.md` lines
331 to 332 say "The unit's charged CPU is therefore at least 60 s and, when the last candidate fits, can overshoot
it". Units that promote early charge less (in seed 0 of the plumbing check, the eight units without overshoot
charged 14.9 to 56.4 CPU-s), and unit t6cb723d5 overshot by 2.17 s with no fitting candidate at all, so overshoot
does not need the last candidate to fit. Line 424, repeated in `PROGRESS.md`, says "3 of 33 units overshot the 60 s
cap, by 2.0 s on average and 16.3 s at most". Only the 11 seed-0 units were run by revision 3's runner and carry the
overshoot record; seeds 1 and 2 are S1's own records, in which 11 more of 22 units exceed 60 CPU-s of S1's charge,
by up to 9.1 s; and 2.0 s is the mean over all 11 seed-0 units, zeros included (the three overshoots are 2.2, 3.3
and 16.3 s, mean 7.2 s). The evaluator's summary (`cas/run_world.py` lines 629 to 632) also averages over all units.
The rule itself is S1's code and unambiguous. Fix, in the report: "a unit stopped by the threshold has charged at
least 60 s and at most 60 s plus its last candidate's charge (novelty and retry, and the promotion checks when it
fits); a unit that promotes earlier charges less"; give the plumbing figures as above; define the summary's mean as
the mean over all units.

**Finding 5. Three text inconsistencies.** `PROTOCOL.md` line 335 says the matched-search child is limited to 12 GB,
while line 410, the change log (line 785) and the code (`cas/run_world.py` line 58) use 8 GB. Line 322 says "a
changed first prediction means rolled back", while S1's regression check (`cgrow/s1.py` lines 167 to 172) rolls back
only when the earlier first prediction is no longer among the two new predictions, a weaker condition. The comment
at `cas/run_world.py` line 60 says the factor is clipped to [1, 2], while the code applies [1, 3] (`cas/bench.py`
line 35), as the protocol says. Fix: correct these in the report; none changes the analysis.

**Finding 6. Nothing confirms that the task set came from the main pool.** In the gate fixture, the pilot dry-run
worlds, built from the pilot pool, passed the package stage. Neither `cas/gate.py` (lines 86 to 109),
`cas/kaggle_build.py` nor `cas/analysis.py` checks the "pool" field of `BUILD_SUMMARY.json` or that every source is a
main-pool id, and the ungated `dry_run_pilot` command (`cas/generate.py` lines 418 to 419) writes a build to any
folder. Fix: at step 3 of section 11, record that `BUILD_SUMMARY.json` says "pool": "main" and
"motivating_sources_disjoint_across_worlds": true, that every task source is in the main pool of
`config/POOLS.json`, and that the claim's time precedes every manifest's "built_utc"; or add these checks to the
package stage.

**Finding 7. Two required outputs can be absent from a finished world.** The evaluator writes
`runs/cas_eval/struct_scores.json` only inside the loop over promoted structures (`cas/run_world.py` lines 543 to
589), so a world in which no arm promoted any structure has none; `BENCH_end.json` comes from an unchecked
subprocess after the stages (`cas/kaggle_main.py` lines 126 to 128). Both are required outputs (`cas/analysis.py`
lines 67 to 74), so either absence would make a finished world INCOMPLETE. Both are unlikely. Fix: pre-declare how
each is handled (for example, an absent `struct_scores.json` with no promoted structure, or an absent end
benchmark with every stage done, is reported and does not make the world INCOMPLETE), or write both
unconditionally.

**Finding 8. Dependence inside a world is outside the decision interval.** The decision interval treats W1's four
families and W3's three as independent clusters. Within a world they share the regression set (a structure is rolled
back if it changes one of the 14 previously solved tasks), the validation pool, the S-shuffled donors (the next
family) and, for the transfer secondary, the grammar itself (built from the other families' promotions,
`cas/run_world.py` line 451). This is weaker than the cross-world link revision 3 removed, but it is a dependence
across decision clusters. Fix: state in the report that the decision interval is conditional on the families within
W1 and W3 being independent beyond these shared parts; report, descriptively, the primary per world and with each
world left out; read the transfer secondary's "holds" as conditional in the same way.

**Finding 9. Records.** At review time, seven plumbing-check files under `checks/s1_world/runs/` (both gate caches,
`units_enum_s1.json`, `units_enum_s2.json`, `c7m_M.json`, `c7m_E.json` and `prep_v4/controller_summary.json`) were
staged in the index but not committed, although the frozen `checks/EQUIVALENCE.json` and `checks/ANALYSIS.json` rest
on them (the committed files equalled their working copies). The revision 4 re-run has since replaced the working
copies. Fix: commit the run files of whichever plumbing record is final. Also, `checks/strict_fixture.py` (line 59 of its commit
1b40a376 version) writes temporarily into the real study's `checks/` folder and loads the real study's modules; run
it only on a scratch copy, with `CAS_REPO` and `CAS_PACKAGE` set, as this review did.

**Finding 10. Procedure after the kernels.** The analysis accepts only `runs/generated/<world>` as world folders,
which is right, but nothing says whether an INCOMPLETE caused only by an argument or placement error (kernel
outputs unchanged) may be corrected and re-run; `PROGRESS.md`'s next step 4 speaks of "the three downloaded world
folders". Fix: pre-declare that such an operator error may be corrected once and logged, any INCOMPLETE about the
kernel outputs being final, and place each kernel's `runs/` at `runs/generated/<world>/runs` as section 10 says.
Commit `runs/kaggle/PACKAGE_MANIFEST.json` and the three notebooks before pushing (they fix the analysis world list
and the archive digest), and record beside each downloaded outputs archive the digest the notebook prints
(`cas/kaggle_build.py` line 89).

## 7. Before a GO

1. **Required:** Findings 1, 2 and 3, each by one of the routes given; Findings 4 and 5 corrected in the report;
   Finding 6 at step 3 of section 11. The others are recommended.
2. **Revision 4.** Its change log (read in the live `PROTOCOL.md`, not reviewed) addresses the duplicated row
   (Finding 2, case 1), a bounded saved-prediction schema with at most two predictions (Finding 2, minor case), the
   S-enum wording (part of Finding 4) and the 8 GB sentence (part of Finding 5). It does not mention Finding 1,
   Finding 2 cases 2 and 3, or Finding 3.
3. **The next check.** The frozen revision that carries these fixes needs an exact-byte check limited to its diff
   from revision 3 and the items above. Results of this review that carry over while the files stay unchanged (as of
   31ede42a, `cas/gate.py`, `cas/generate.py`, `cas/kaggle_build.py`, `cas/kaggle_main.py`, `cas/env.py`,
   `cas/bench.py`, the configuration, the pools and every dependency are unchanged): the dependency and data
   digests, the pools and exposure checks, the gate fixture, the generator's rule-6 test and the Kaggle settings. The
   package smoke test should be repeated, because `cas/run_world.py` and `cas/analysis.py` change.

## 8. Method of this review

Read-only for the study. Scripts ran one at a time under `scripts/with_cpu_slot.sh` at nice 19 (three sub-second
JSON summaries ran without it): a digest check of every `FREEZE.json` entry against `git show 67322f40` and the live
bytes; a dry-run and exposure scan; the gate fixture; the author's fixture of commit 1b40a376, unchanged, and the
reviewer's own fixture; an independent re-scoring of the plumbing check with S1's statistics code copied verbatim;
the generator test with stubbed filters and synthetic ids; a package build and smoke test. Everything that writes
ran in a scratch mirror built from `git archive 67322f40` plus the 44 dependencies, with the seven staged
plumbing-check files copied in for the fixtures; the fixture and package runs set `CAS_REPO` and `CAS_PACKAGE` so
that every import and write stayed in the mirror. No task was generated, no arm and no matched search ran (the only
search was one benchmark search on probe grids inside the package), no `GO_CAS` was written anywhere, and nothing
under Step B or anything public was touched. Scripts and outputs are in
`/tmp/scratch/rev3/` (temporary); the key numbers
are quoted above.
