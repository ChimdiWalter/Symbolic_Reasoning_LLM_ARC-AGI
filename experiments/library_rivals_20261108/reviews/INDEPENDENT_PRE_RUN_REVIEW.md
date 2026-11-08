# Library rivals: independent pre-run review

Reviewed: the frozen bytes of `experiments/library_rivals_20261108/` at commit d60babae (8 Nov 2026), before any
arm ran on any held task. FREEZE.json sha256 `384422feb93a0d64b0fbde41a98ab725d74a6e81ec4b06a7563e919a327e792d`;
PROTOCOL.md sha256 `09a794ed56c64b55aaf11f00a3a060a2847fc703fc4da0ccc1b9144534314b22`.

Labels used here, as in the protocol: G0 is the base grammar (the full arc-dsl grammar of A2, the project's
bottom-up arc-dsl search from the architecture sweep); S_train is A2's corpus of 194 verified arc-dsl solvers of ARC
training tasks; study A is `natural_growth_20261105`, study B is `natural_growth_b_20261105`; the GO is the
coordinator's one-use go-ahead file; S1 to S5 are the five secondary comparisons of protocol section 7. A CPU-s is
one second of process CPU time.

## Verdict: PASS WITH FIXES

The design matches the aim on every quantity it claims to match, the three libraries are reproducible from the
frozen code and use no held material, and the custody order (rows, seal, claim, digest check, decoding, scoring,
completion marker) is implemented as written. Nothing found invalidates the comparison.

Before the GO: make the five cheap code changes in findings 1 to 5, add the sentences in findings 6 and 7 to the
protocol, re-freeze, re-run the dry run, and have the diff (not the whole study) re-checked. The other findings are
recommended, not required.

## What was checked, and how

- **Freeze.** Every digest in FREEZE.json was recomputed: 102 repository files and 6 benchmark input files
  (`real.json`, `meta.json`) all match. The protocol digest in FREEZE.json matches PROTOCOL.md.
- **Libraries.** A read-only script (run inside the CPU-slot wrapper with `python -I -B`, writing nothing in the
  repository) rebuilt all three libraries in memory from the frozen code, under a fresh hash seed. The compression
  entries, both random draws, the admissible counts (299 and 259), the corpus sizes (199 and 217) and the G0 digest
  are identical to `libraries/LIBRARIES.json`.
- **No held material in the libraries.**
  - Study B's discovery records hold 460 source-half records and no held task (1D-ARC 306, ConceptARC 80, Mini-ARC
    74). The 34 with a program give at most one program per task.
  - The random admissibility test uses source-half demonstration inputs only (`lr/libraries.py` admissible_sigma).
  - The system-view files carry test inputs only: the preparation script writes `{"input": ...}` for test entries
    (`experiments/universality_similar_problems_20261102/scripts/prepare_data.py`, line 112).
- **Matched quantities.** In code, every arm has:
  - the same G0 copy, checked against the library record's G0 digest;
  - N entries per benchmark (2, 0 and 19);
  - each entry added by `cgrow.lang0.add_production` as one (Grid) -> Grid production of cost 3 and charge 1;
  - the same budget (150,000 executions, two attempts) and the same 120 CPU-s cap from the configuration.
  - The failure-kept arm builds its grammar exactly as study B's object-reuse arm did (`objgrow/gates.py` ObjPlugin.g0
    with study B's seed-independent G0). The only differences are the cap (120 against 20 CPU-s) and running in one
    process on this machine rather than in study B's kernels.
- **The sanctioned dry run**, run as instructed into `runs/review_dry`:
  - It was killed (signal 9) after the first failure-kept row, then resumed with the same command. It completed
    with no double rows, and its `RESULTS.json` is byte-identical to `checks/dry_run/RESULTS.json`. All 30 rows equal
    the frozen dry run on fit, program, executions, completed level, stop and predictions, across two more
    interpreters with different hash seeds.
  - A third run of the same command was refused at "a seal already exists" (see finding 8).
  - The highest CPU per search was 2.2 CPU-s, in any arm.
- **Imports.** A read-only script imported the run's modules as `run.py` does and built every arm's grammar. Three
  loaded modules are not in the freeze (finding 4).
- **Not opened:** no solution file, no held test output and no study B held result row. Only the sanctioned dry
  run's own scorer opened the solution files, for source tasks.

## Evaluation of the stated deviations

1. **The compression corpus is widened with S_train.**
   - **Disclosed and honest** (protocol section 3, "Why the corpus is widened").
   - **Fair?** It is the only way to reach the same size with closed fragments. The consequence is not stated: on
     1D-ARC only one entry (the flip program) comes from the benchmark's own successes. The other 18 come from ARC
     training solvers or are padding, and on ConceptARC both entries come from the training solvers.
   - **Required wording:** every claim names the rival as "compression of source-half successes plus ARC training
     solvers", never just "compression of successes".
2. **On 1D-ARC, 10 of 19 entries have negative utility and are kept to reach the same size.**
   - **Disclosed and honest**, with a few inaccuracies (finding 7).
   - **Fair?** The padding spends executions but adds few new programs. The cost is probably small, but nothing
     measures it.
3. **The random entries come from the schema space; the failure-kept operations come from the builder's
   object-level space.**
   - **Disclosed and honest** ("What it controls for").
   - **Fair?** It is a weak control. A win over the random arms cannot be read as "selection from failures beats
     random selection of object-level operations" (finding 6).
4. **The held halves are previously used.**
   - **Disclosed and honest** (exposure label). "Held" is correctly defined as held out from the construction of the
     libraries, not as unopened.
   - **Missing:** study B's success-derived library (its arm 2, the "promoted" library) was also scored on these
     halves. The compression arm's main entry, the 1D-ARC flip program, is very likely the operation that arm
     promoted (protocol section 10 cites its 22 flip tasks). So the main component of both rivals' held outcomes was
     known when the rival was designed (finding 6).
5. **The failure-kept arm repeats study B's object-reuse arm, whose outcome (227 of 624) is known.**
   - **Disclosed and honest.** A small difference from 227 is possible if study B's 20 CPU-s cap ever bound.
   - Recommendation in finding 15.
6. **Fresh tasks are not used.** Disclosed, with a sound reason.

## Findings

Severity: **High** would invalidate or block the result; **Medium** could block the run, or leaves a custody or
honesty claim untrue; **Low** concerns robustness, clarity or record-keeping. No finding is High.

### 1. Medium: a legitimate wrong answer outside the colour range would stop the whole study at the seal

**Where:** `lr/phase.py` lines 73 to 79 (`valid_preds`), used by `seal` at lines 96 to 103.

**What is wrong:**
- The seal refuses any fitting row whose prediction has a cell outside 0 to 9, and a refused seal cannot be
  resumed: the same deterministic search writes the same row again.
- Such predictions are possible. The guard `a2/arcdsl.py` valid() checks only grid size and shape, not cell values.
  G0 contains the constants NEG_ONE, NEG_TWO and TEN and colour arithmetic (increment, add, multiply), so a program
  can fit the demonstrations exactly and still predict colour 10 or -1 on a test input.
- Study B applied the same rule (`ngb/report.py` valid_grid) and completed, so the case is rare. The new arms change
  which fitting programs a budget-stopped search reaches, so the risk is new, small and blocking. The only way out
  after the GO would be a code change after the freeze.

**Cheapest fix:** accept any integer cell in `valid_preds`. Pre-register that such an attempt is scored as given
(it can only be wrong), and count these rows per arm in the report.

### 2. Medium: the one-use GO is enforced only within one output folder

**Where:** `lr/report.py` lines 63 to 70 and `lr/phase.py` lines 84 to 85.

**What is wrong:** the claim, the completion marker and the seal live in OUT_DIR. `run.py phase all runs/other`
with the same GO would run every arm again and score a second time. "A second scoring is refused" (protocol line 170)
holds only per folder.

**Cheapest fix:** in `require_go` or `main`:
- refuse any OUT_DIR other than `runs/main`; or
- also write the claim at the study root (`SCORING_<GO digest>` next to GO) and refuse if it exists.

### 3. Medium: the promised audit of the statistics cannot be done without opening the answers a second time

**Where:** `lr/report.py` lines 91 to 114.

**What is wrong:** RESULTS.json holds only totals and test outputs. The per-task correct counts (the `tab` list) are
never written. An auditor can check the McNemar p from the two discordant counts. The family-clustered interval and
the per-task scoring cannot be recomputed without a second scoring, which the protocol forbids.

**Cheapest fix:** write `tab` to a scores file before RESULTS.json: per task, its benchmark, cluster and outputs, and
for each arm its correct count, answered count and stop. Add a field to RESULTS.json that holds that file's digest.

### 4. Medium: the freeze does not cover everything the run executes

**Where:** `lr/freeze.py` lines 29 to 37; the protocol's custody list (section 8.1).

**What is wrong:**
- `cgrow/lang0.py` imports `a2.corpus`, which imports `harness.paths` and `harness.data` from
  `experiments/architecture_sweep_20261026/harness/`. These three files (with `__init__.py`) are executed on every run
  and are not frozen. I confirmed this by import: they are the only loaded repository modules outside FREEZE.json.
- The launchers that section 8.4 actually runs, `scripts/run_detached.sh` and `scripts/with_cpu_slot.sh`, are not
  frozen either.
- The risk to the result is low, because the harness modules only define constants and functions at import. Still,
  the freeze's own statement ("every file the run executes or reads") is not true.

**Cheapest fix:**
- Add `harness/__init__.py`, `harness/paths.py` and `harness/data.py` (and the two scripts) to the reused list.
- Optionally, before the seal, hash every loaded module file under the repository and refuse if any is outside the
  freeze.

### 5. Medium: the scorer and the statistics are loaded about an hour after the only freeze check

**Where:** `lr/phase.py` lines 113 to 117.

**What is wrong:** `require_go()` checks the freeze once, at the start. `lr.report`, `ngrow.analysis` and
`ngrow.score` are imported only after all searches and the seal. A change to any of them during the run would score
the study unnoticed.

**Cheapest fix:** import `lr.report` at the top of `lr/phase.py`, and call `GT.check_freeze()` again (and recompute
the GO digest) at the start of `score()` for the main run. Record the freeze digest in RESULTS.json.

### 6. Medium: the claim limit should state four facts that bound what the primary can mean

**Where:** PROTOCOL.md section 1 (lines 27 to 33) and section 10.

**What is missing:**
- **The rival was not designed blind.** The compression and random libraries were designed by people who knew study
  B's held results for the failure-kept arm (227) and for study B's success-derived library arm (22 flip tasks).
  The outcome of the primary is therefore largely foreseeable. It is a pre-registered measurement of the gap, not a
  blind confirmatory test, and its p-value should be read that way.
- **Construction work is not matched.** The failure-kept registry for 1D-ARC cost about 9,300 CPU-s to build
  (construction and gates, from its registry record). The compression library cost seconds over existing
  successes.
- **The compression is a single step.** There are no repeated rounds of compressing, re-searching the source
  failures with the new library, and compressing again, so it is not library learning in DreamCoder's full sense.
- **Each comparison confounds three things:** the operation space (object-level edits against arc-dsl fragments or
  schema structures), the source material (failures against successes) and the selection rule. A win cannot be
  attributed to "kept from failures" as such.

**Cheapest fix:** four sentences in section 1, and the same limits in RESULT.md.

### 7. Low: the description of the 1D-ARC compression entries is slightly inaccurate, and the padding is not described

**Where:** PROTOCOL.md lines 79 to 81; `libraries/LIBRARIES.json`.

**What is wrong:**
- **The positive-utility list is incomplete.** The "seven fragments with positive utility (tilings, crops,
  object-based crops)" also include `bottomhalf(I)` and a blank canvas `canvas(ZERO, shape(I))`.
- **The ten negative entries are not all single base operations.** Seven are; two are `replace` with fixed colours;
  one is `hconcat(I, I)`.
- **What the padding costs is not stated:**
  - `tophalf(I)` duplicates a G0 production at the same cost (3), so it only spends executions;
  - six entries (rot90, rot180, rot270, compress, lefthalf, righthalf) are cost-3 aliases of cost-4 G0 productions.

**Cheapest fix:**
- Correct the two sentences.
- Pre-register one descriptive table, computable from the rows' program text without any answer: for each arm, how
  often each library entry appears in fitting programs. This shows whether the padding or the training fragments
  were ever used.

### 8. Low: three ways a "restart of the same command" does not resume

**Where:** `lr/phase.py` lines 36 to 42, 63 and 84 to 85; `scripts/run_detached.sh` line 12.

**What is wrong:**
1. **A restart after the seal is refused.** The review run demonstrated this: a third run stopped at "a seal already
   exists". An interruption between the seal and the claim, or an error after the seal, therefore cannot be
   resumed.
2. **A killed write can leave a partial last line,** and `read_rows` then fails with a decoding error on every
   restart. ConceptARC rows with two attempts of three grids can exceed one 8 KB buffer write.
3. **An exception that escapes a search stops the run** and recurs on every restart, with no pre-registered
   handling. This is unlikely, because production errors are caught inside the search.
4. **After a reboot, `run_detached.sh` refuses to start again** ("still running") until its status file is cleared.

**Cheapest fix:**
- If a valid seal exists and no claim exists, verify the seal and go on to scoring.
- In `read_rows`, drop and truncate an unparsable last line.
- Wrap `run_task` so that an exception writes a row with stop "error" and no fit, and count these rows per arm.
- Add one line to the protocol on clearing a stale status file after checking that no process runs.

### 9. Low: the determinism evidence is thin

**Where:** `checks/DETERMINISM.json`.

**What is wrong:**
- Only 2 of the 30 compared rows contain a fit. The other 28 stopped at the budget without a fit, and those fields do
  not depend on the enumeration order. My two extra interpreters agree, but on the same 30 rows.
- No frozen script produced the record.

**Cheapest fix:** before the GO, repeat the comparison in two interpreters on source tasks where fits occur. For
example, use the 23 solved 1D-ARC source tasks under the compression and failure-kept arms (a few CPU-minutes). Commit
the comparison script.

### 10. Low: the solution-file digest is checked after the claim is written

**Where:** `lr/report.py` lines 69 and 78.

**What is wrong:** a mismatch would use up the one claim without scoring.

**Cheapest fix:** hash the three files before writing the claim. Hashing decodes nothing.

### 11. Low: inherited environment variables could silently redirect the split or the data

**Where:** `lr/env.py` lines 19 to 22; `ngrow/env.py` (NG_DATA).

**What is wrong:** `setdefault` keeps any NG_STUDY, NG_DATA, OG_STUDY or NG_PACKAGE already set in the operator's
shell. `DT.half` would then read a split file that is not frozen. None of these is set in the current shell.

**Cheapest fix:** assign the values (or assert them), and check that the data root equals FREEZE.json's `data_root`.

### 12. Low: the CPU safety cap is unlikely to bind; if it does, it binds against the failure-kept arm

**Where:** `config/CONFIG.json` (`cpu_safety_cap_s` 120).

**What is wrong:**
- **Why it is unlikely to bind:** the dry run's highest CPU was 2.2 CPU-s per search, and study B's protocol
  describes its 20 CPU-s cap as one that "never binds in practice". Every arm gets the same cap.
- **If it binds anyway:** it stops arms with costly operations first. That is the object-level operations (charged
  1 per execution, whatever their internal work), so it would bias against the failure-kept arm, which is
  conservative for the primary. It would also make the outcome depend on machine load.

**Cheapest fix:** report each arm's highest and total CPU next to the cap stops.

### 13. Low: the Holm family contains a comparison that is a tie by construction

**Where:** CONFIG.json secondaries; S4 (Mini-ARC, where every arm is G0, so its p is 1).

**What is wrong:** keeping S4 multiplies the smallest secondary p by 5 instead of 4. This is conservative, not
wrong.

**Cheapest fix:** keep it as pre-registered, or move S4 to the descriptive results before the freeze.

### 14. Low: wording

- **Section 9 (line 178), "no held task is read".** The dry run loads every task's demonstrations and test inputs,
  and its scorer reads the whole solution file's text, decoding only the requested source tasks. Better: "no held
  task is searched, and no held output is decoded".
- **Line 152, "not hashed by this study".** The scorer does hash the files. Better: "not hashed by this study's
  freeze".
- **Undefined labels.** "R1 evaluation" (line 11) is not defined. "A2" is not defined. "G0" is used in section 3
  before section 4 defines it.
- **Report output.**
  - `REPORT.md` prints a rounded p as "0.0": print "< 1e-6" instead.
  - The descriptive comparisons carry a `decision_raw` field that reads like a decision: rename it or drop it.

### 15. Low: record the comparison with study B's arm and the interpreter

**What is missing:**
- The failure-kept arm is said to repeat study B's object-reuse arm, but no check of that is pre-registered.
- Nothing records the Python interpreter or its version.

**Cheapest fix:**
- Pre-register a descriptive agreement count: the tasks on which the failure-kept rows' predictions equal study B's
  object-reuse rows. This compares predictions only and needs no answer.
- Write `sys.executable` and `sys.version` into the seal.

## Files written by this review

- This file.
- `runs/review_dry/`: the sanctioned dry run, with its kill and resume. It is not frozen and is not committed.

Nothing else in the study folder was changed, no GO file was written, and `phase all` was not run.

## Re-check of the fixes (diff d60babae to f8a177b3)

Re-checked on 8 Nov 2026, before any held run. The new FREEZE.json (sha256
`59ec4a8b498c9a343ea36c9868ca912f1a20eed9532e85c09bc671cc1045c258`) verifies: 121 files and the 6 benchmark input
files, all digests equal. PROTOCOL.md (`1a3c5f3022477a20a70c85e203694ca599ea7e8eeb024b9d85590907d48764e9`) is the
version the freeze records. The `reviews/` and `runs/` folders are not frozen, so this section changes no frozen file.
(`runs/review_dry`, described above as not committed, was committed with the fixes.)

**How.**
- I read the whole diff of the code, the configuration, the launchers and the protocol.
- **New dry run.** I ran the sanctioned dry run once more into `runs/review_dry2` (2 source tasks per benchmark), and
  it completed:
  - its 30 rows equal the frozen dry run's rows for the same tasks;
  - the per-task table's digest equals the one in RESULTS.json;
  - the seal records Python 3.12.3 and the platform;
  - the usage table counts the one failure-kept entry found in the 2 fits;
  - the descriptive comparisons carry `rule_outcome_no_weight`;
  - a dry run's claim and marker stay in its own folder.
- **Loaded-module check.** The dry run does not call the new check, so I ran it read-only, inside the CPU-slot
  wrapper. With the held run's imports and every arm's grammar built (which loads the builder's code), it passes at
  both points where the held run calls it. The data-root check passes too.
- **Determinism.** Recomputing the record gives 75 rows, 0 differing and 5 with a fit, all five in the failure-kept
  arm on 1D-ARC.
- **Study B's rows.** The code that wrote them (`ngb/held.py`, identical in both copies) always writes `task`, `fit`
  and `preds`, which the new agreement count needs. The three files exist and are readable. I did not open them.

**Status of the 15 findings.**
1. **Fixed.** The seal accepts any integer cell, and the scorer counts an attempt with a cell outside 0 to 9 (True
   and False included) as wrong, and reports how many.
   - Residual: a cell that is not an integer would still refuse the seal, although section 5 says such attempts
     "never stop the seal". Search values make this practically impossible.
   - Fix: relax the check, or soften the sentence.
2. **Fixed.** The held run writes only to `runs/main`, and the claim and the marker are at the study root.
3. **Fixed.** The per-task table (`SCORES_PER_TASK.json`), with its digest in RESULTS.json, has everything needed to
   recompute every test and interval.
4. **Fixed.** The harness modules and the two shared scripts are frozen, and loaded modules are checked at run start
   and again before scoring. See point B.
5. **Fixed.** The scorer is imported at the start, and the GO, the freeze and the loaded modules are checked again
   before scoring.
6. **Fixed.** The claim limit now states the single step, the unmatched construction work, the mixed causes, the
   non-blind design and where the entries come from.
7. **Fixed.** The library text is accurate, and a usage table is added.
8. **Mostly fixed.**
   - A partial last line is removed on resume; a malformed middle line refuses, correctly.
   - A search error gives an `arm_error` row, counted per arm.
   - The procedure for a stale status file is stated.
   - Still open: a restart after the seal is refused (point C).
9. **Improved.** All five fits are in the failure-kept arm, so the fitting paths of the compression and random arms
   are still not compared. That is acceptable, because the sorted-tag fix applies to every production alike.
10. **Fixed.**
11. **Fixed.**
12. **Fixed.**
13. **Kept, and stated as conservative.** Accepted.
14. **Fixed.**
15. **Fixed.** See point A.

**New points (none blocking).**
- **A. Low.** The agreement count with study B's rows runs between the claim and RESULTS.json, and has never run,
  because the dry run skips it.
  - If it raised, the outputs would have been opened with no RESULTS.json and no marker.
  - The per-task table is already on disk by then, so the statistics could be recomputed without opening any output
    again. It would still be a deviation.
  - Fix: wrap the call in try/except and record any error in RESULTS.json, or compute it after the marker.
- **B. Low to Medium.** The two shared scripts (`scripts/run_detached.sh`, created today, and
  `scripts/with_cpu_slot.sh`) are now frozen, and the freeze is checked again before scoring.
  - **Why it matters:** every project uses these scripts. If another agent edits one during the run, the run stops
    after the seal, and with point C it cannot resume.
  - **Cost of recovery:** nothing would have been opened, so recovery is clean but manual: a documented deviation, a
    new freeze and GO, and a re-run of the searches. The scripts cannot change any result once the job runs.
  - **Fix:** keep their digests in FREEZE.json but leave them out of the check before scoring, or record their
    digests in the seal instead. Otherwise, ask the other agents not to edit `scripts/` until the marker exists.
  - **Origin:** this is a side effect of my own finding 4.
- **C. Low.** If a valid seal exists and no claim, verify the seal and go on to scoring. Or add one sentence to
  section 8.4 saying what the coordinator does in that case.
- **D. Low.** Section 4 labels a result "with defects" if any arm has more than 1% `arm_error` rows. RESULTS.json
  reports the counts but does not compute the label. Compute it, or state that RESULT.md applies it.
- **E. Low.** `launch/run_dry_twice.sh` starts with `rm -rf checks/dry_run checks/dry_run_repeat` and rewrites frozen
  records whose bytes now include CPU times. Run after the freeze, it would break the freeze for the held run and its
  audit. Add a guard that refuses when FREEZE.json exists.

**Verdict of the re-check: PASS.** No item blocks the GO. Points A and B are one-line changes worth making before the
GO if time allows. If either is made, a new freeze, one dry run and a diff check by the coordinator are enough.

## Delta check of changes A to E (diff f8a177b3 to 41f2a95c)

Checked on 8 Nov 2026, before any held run.

**Freeze.** The new FREEZE.json (sha256 `0ce263495c9b9c4de80360bff2682b3435c259e0f82f4327af5dcfcdee456911`) verifies:
- 119 files, the 2 launch scripts held separately under `launch_sha256`, and the 6 benchmark input files;
- PROTOCOL.md (`c26d8ed133766b50cd33c3ecd7b81018cdcb00e74ce987cedd34fa8b965572ba`) is the version it records;
- the launch scripts appear only under `launch_sha256`.

**Read-only checks.**
- The freeze check passes in both modes, at launch and before scoring.
- The loaded-module check passes.
- `require_go` refuses, as it should, while no GO exists.
- Both frozen dry runs carry the label "clean" and a computed usage table. Their agreement count ran with digests
  verified and, as expected, no overlap.
- The determinism record is unchanged: 75 rows, 0 differing.

**The changes.**
- **A. Done.** The usage table and the agreement count are each wrapped in try/except. An error is recorded as text in
  RESULTS.json and cannot stop the scoring.
- **B. Done.** The launch scripts are checked at launch only (`require_go(at_scoring=True)` skips them). Every other
  frozen file is still checked before scoring.
- **C. Done.** `phase score runs/main` scores from an existing valid seal under the same GO, after the same checks. It
  refuses without a seal, and the scorer refuses once a claim exists.
- **D. Done.** RESULTS.json carries "with defects" when any arm has search errors on more than 1% of the tasks, and
  "clean" otherwise.
- **E. Done.** `launch/run_dry_twice.sh` refuses once FREEZE.json exists.
- **Finding 1 residual. Done.** Any scalar cell now passes the seal. Only a cell that is itself a list or a mapping
  would refuse it, which the search's values make practically impossible.

**Two notes, not blocking.**
- **Exclusive claim (Low).** The claim file is created with an ordinary write, not an exclusive create. If someone ran
  the recovery command while the original job was still alive between its seal and its claim, both could score.
  - The protocol allows recovery only after the job has stopped, which `run.status` shows.
  - Cheap hardening: create the claim with an exclusive open, so a second scorer fails.
- **Study B's rows in the dry runs.** The dry runs now hash and read study B's held rows. These hold predictions only,
  not answers, and give zero overlap with the source tasks. This is consistent with the protocol and harmless.

**Verdict of the delta check: PASS.** No item blocks the GO.
