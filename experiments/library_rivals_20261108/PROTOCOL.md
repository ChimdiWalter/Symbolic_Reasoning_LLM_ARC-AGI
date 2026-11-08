# Library rivals: a library kept from failures against a library compressed from successes, at matched size and work (pre-registration)

Study folder: `experiments/library_rivals_20261108/`. Author: Chimdi Walter Ndubuisi. Written on 8 Nov 2026 before
any arm of this test ran on any held task. Revised the same day, still before any held run:
- after the independent pre-run review (`reviews/INDEPENDENT_PRE_RUN_REVIEW.md`, PASS WITH FIXES);
- after its re-check (PASS, with five further protective changes, A to E, made before the GO).

The sha256 of this file, the code, the configuration, the built libraries and every reused input are in
`FREEZE.json`. The run starts only after the review and a one-use GO with a nonce, written by the coordinator
(section 8).

**Terms.**
- **arc-dsl** is the domain-specific language of grid operations used throughout the project.
- **A2** is the project's bottom-up program search over arc-dsl.
- **G0** is A2's full base grammar, with integer prior costs estimated from 194 verified solver programs of ARC
  training tasks (S_train).
- **The builder** is the project's object-level operation builder (`experiments/object_growth_20261105/`).
- **Study A and study B** are the natural-task growth test and the library-transfer test.

**Exposure label.**
- The held halves are previously used:
  - study B scored them once on 7 to 8 Nov 2026;
  - every task of the three benchmarks was run and scored once on 2 Nov 2026 by the project's submitted entries (the
    universality evaluation);
  - every task was also run and scored once by the companion study's R1 evaluation, its evaluation of a different
    frozen system on these cohorts.
- "Held" here means held out from the construction of all three libraries. It does not mean unopened.
- The failure-kept arm repeats study B's object-reuse arm (the same operations, the same G0, the same execution
  budget, a larger CPU-time safety cap; section 4). That arm scored 227 of 624 correct outputs, so its outcome is
  known.
- The rivals are new: a same-size library compressed from solved programs, and same-size random libraries.
- **Fresh tasks are not used.** No honest generator exists for these benchmarks, and writing one now would risk
  shaping the tasks to one library's operations. This is a pre-registered comparison on previously used held halves,
  and it is reported as such.

## 1. Question and claim limit

**Question.** CORA keeps what fills a typed hole: operations constructed from its own failures. Does a library kept
from failures help the same static search more than a library compressed from solved programs, when both have the
same number of entries, enter the grammar the same way and get the same counted-operation budget?

**Claim limit.**
- **Two concrete libraries.** The comparison is between two libraries built here: the builder's admitted operations,
  and a simple, faithful, single-step compression of the solved programs available (section 3). It is not a
  comparison with DreamCoder or Stitch as systems.
  - DreamCoder alternates search and compression over many rounds; Stitch searches abstractions with holes. Neither
    is reproduced here.
- **What is matched, and what is not.** The rivals are matched in:
  - number of entries;
  - cost per entry;
  - type;
  - charge per execution;
  - search budget per task.

  They are not matched in:
  - the material they were built from: failures on the source halves on one side; source-half successes plus a
    training corpus on the other;
  - the work spent building them: about 9,300 CPU-s of construction and gates for the builder's 1D-ARC registry and
    6,100 for ConceptARC's, against seconds for the compression.
- **What a win can and cannot support.** Each comparison mixes three things: the operation space (object-level edits
  against arc-dsl fragments against schema structures), the source material and the selection. A win shows that
  this failure-kept library beats this compression library under matched use. It cannot be credited to "kept from
  failures" as such.
- **The design was not blind.** It was written knowing study B's held results:
  - the failure-kept operations scored 227 correct outputs;
  - study B's library of promoted successes scored 37, of them 22 on 1D-ARC flip tasks.
- **Where the compression entries come from.** On 1D-ARC only the first compression entry (the flip program) comes
  from the benchmark's own successes. Neither ConceptARC entry does.

## 2. Data

- **Benchmarks and split:** study A's (`experiments/natural_growth_20261105/split/SPLIT.json`), unchanged.
  - ConceptARC: 80 held tasks, 240 outputs.
  - Mini-ARC: 75 held tasks, 75 outputs.
  - 1D-ARC: 309 held tasks, 309 outputs.
  - Total: 464 held tasks, 624 outputs. The searches see demonstrations and test inputs only.
- **Library material:**
  - source-half records only, for the failure-kept library (the builder's registries) and the compression library's
    source part (study B's discovery records, 460 source-half records);
  - the 194 S_train solvers;
  - the schema structures, applied to source-half demonstration inputs, for the random libraries.
- Nothing from a held task or from the ARC-AGI-2 evaluation set enters any library.

## 3. The libraries (`lr/libraries.py`; built record `libraries/LIBRARIES.json`)

Each benchmark has its own three libraries, of equal size N. N is the size of its failure-kept library: ConceptARC
2, Mini-ARC 0, 1D-ARC 19, 21 entries in all. The builder admitted nothing for Mini-ARC, so on Mini-ARC every arm is
G0 and contributes ties only.

- **FAILURE-KEPT.** The object-level operations the builder admitted from failures on the benchmark's source half
  (`experiments/object_growth_20261105/runs/v2/<bench>/registry.json`, frozen in study B; registry order).
  - These are edit operations from the builder's own space: views of the grid as objects, first-match rules, and
    paint, crop and other output forms. They are not schema structures.
  - In the builder's wording standard, its retried candidates are exact on all demonstrations and accepted by the
    declared proposal heuristic, with the stated exceptions.
- **COMPRESSION.** N abstractions compressed from solved programs in one step. The method is a greedy corpus
  compression over abstractions of the input grid, scored by a Stitch-style utility, with DreamCoder-style corpus
  rewriting. Its abstractions have no holes other than the input.
  - **Candidates:** the Grid-valued subtrees of the corpus programs whose only free variable is the input, other
    than the bare input.
  - **Utility of a fragment:** uses x (cost - 4) - cost.
    - cost is its A2 prior cost;
    - 4 is the cost of the new production applied to the input (3 + 1);
    - the last term is the cost of writing the fragment once;
    - uses counts the corpus programs that contain the fragment, so a subtree repeated inside one program does not
      count as frequent.
  - **Greedy step:** take the fragment with the highest utility (ties: more uses, then lower cost, then program
    text), rewrite its occurrences to the new production, and repeat until N are taken.
  - **Corpus:** the benchmark's solved source-half programs (base-budget fits, else 4x fits: ConceptARC 5, 1D-ARC 23)
    plus the 194 S_train solvers.
  - **Why the corpus is widened.** The source half alone cannot give a same-size library: 1D-ARC's 23 solved programs
    hold only 2 distinct programs, 22 of them the same flip program.
  - **What the corpus supports on 1D-ARC (19 entries):**
    - 8 entries with positive utility: the flip program `paint(I, vmirror(merge(fgpartition(I))))` (22 uses), a 3x3
      tiling, a mirrored 2x2 tiling, a 3x3 crop, `bottomhalf(I)`, a blank canvas of the input's shape, and two
      object crops;
    - 1 entry at zero, `vconcat(I, hmirror(I))`;
    - 10 entries with negative utility, kept only to reach the same size:
      - six single G0 operations on the input that become one cost level cheaper as entries: rot90, rot180,
        rot270, compress, lefthalf, righthalf (bottomhalf, above, is also such a copy);
      - `tophalf(I)`, a copy of a G0 operation at the same cost;
      - two colour replacements with fixed colours;
      - `hconcat(I, I)`.
  - **ConceptARC (2 entries):** two tiling fragments from the S_train solvers.
  - Both shortfalls are part of the result. The report counts how often each entry is used in fitting programs
    (section 7).
- **RANDOM-1 and RANDOM-2.** N entries drawn without replacement, with frozen seeds 1 and 2, from the admissible
  entries of the 211-structure schema language (`cgrow/schema.py`).
  - An entry is a structure, with its k fixed for the 44 structures that take one (k in 2, 3, 4).
  - An entry is admissible for a benchmark when it is defined and differs from its input on at least one source-half
    demonstration input of that benchmark: ConceptARC 299 entries, 1D-ARC 259.
  - **What it controls for.** The failure-kept operations come from the builder's object-level space, not from the
    schema space. So the random libraries control for adding N admissible whole-grid operations, not for drawing at
    random from the builder's own space.

## 4. Arms and the matched work (`lr/arms.py`)

- **The five arms:**
  - G0 alone (reference, descriptive);
  - G0 plus FAILURE-KEPT;
  - G0 plus COMPRESSION;
  - G0 plus RANDOM-1;
  - G0 plus RANDOM-2.
- **G0** has digest `63215cce7d07fceba6bf6930cb20d02a438c1dc836683072d4153f1a23eaddaa`. Its enumeration order is made
  independent of the interpreter's hash seed by study B's sorted-tag fix.
- **Every library entry enters the same way:** one production (Grid) -> Grid of cost 3 and charge 1
  (`cgrow.lang0.add_production`), exactly as the builder adds its operations.
- **The matched work:** every arm runs A2's search (`cgrow.search.run`) on each task's demonstrations with the same
  counted-operation budget: 150,000 primitive executions and two attempts.
- **The CPU-time safety cap** is 120 CPU-s per search. Study B used 20 CPU-s; here the execution budget is the
  matched quantity.
  - A search the cap stops keeps what it found, and its stop is recorded.
  - Stops, total and highest CPU are reported per arm.
  - The dry runs' highest CPU per search was a few seconds.
- **Search errors:** a search that raises gives an "arm_error" row with no answer, reported per arm. If any arm has
  search errors on more than 1% of the tasks, RESULTS.json carries the label "with defects"; otherwise "clean".

## 5. Outcome

- An output is correct when either of an arm's two attempts reproduces it exactly (pass@2; `ngrow.score.score_row`).
- An attempt with a cell that is not an integer from 0 to 9 is a wrong answer. It is counted incorrect even where
  Python's equality would accept it (True equals 1), and such attempts are counted per arm. They never stop the seal.
- The unit is the task, valued by its count of correct outputs (ConceptARC three per task, the others one).
- A search that finds no fitting program abstains.

## 6. Primary

- **Comparison:** FAILURE-KEPT against COMPRESSION over the 464 held tasks.
- **Test:** exact McNemar (sign) test on the tasks where the two differ.
- **Effect:** the total difference in correct outputs, with a family-clustered bootstrap 95% interval. Clusters are
  families (ConceptARC concepts, 1D-ARC types) and single Mini-ARC tasks, resampled within each benchmark: 10,000
  draws, random.Random(20261105).
- **Decision:**
  - "failure_kept beats compression" if p < 0.05 and the interval's lower end is above 0;
  - the reverse if p < 0.05 and the interval's upper end is below 0;
  - "tie" if the two differ on equally many tasks each way;
  - "inconclusive" otherwise.
- The statistics are study A's frozen functions (`ngrow.analysis`).

## 7. Secondaries and descriptive results

- **Secondaries (Holm over this fixed family of five; decisions at the adjusted p):**
  - S1: FAILURE-KEPT against RANDOM-1 (all held tasks);
  - S2: FAILURE-KEPT against RANDOM-2 (all held tasks);
  - S3: FAILURE-KEPT against COMPRESSION, ConceptARC;
  - S4: FAILURE-KEPT against COMPRESSION, Mini-ARC (a tie by construction, kept in the family, which is
    conservative);
  - S5: FAILURE-KEPT against COMPRESSION, 1D-ARC.
- **Descriptive, no decision weight:**
  - each library arm against G0;
  - COMPRESSION against RANDOM-1;
  - the primary by benchmark;
  - totals per arm and per benchmark;
  - CPU and stops per arm;
  - for every library entry, the number of tasks whose found program uses it;
  - agreement of the failure-kept rows with study B's object-reuse rows on the same held tasks. This compares
    predictions only. Study B's rows are read after the seal; their digests are taken from that run's output
    manifests and recorded in `config/CONFIG.json`.
    - This count and the library-usage table are descriptive. An error in either is recorded in RESULTS.json and
      can never stop the scoring.

## 8. Custody

1. **Freeze.** `python3 -I run.py freeze` writes `FREEZE.json`.
   - It holds the digests of:
     - this protocol, the configuration, the code, the built libraries, the launchers, and the dry runs' and
       determinism records;
     - the reused code: ngrow, cgrow, a2 with its corpus and the harness modules a2 imports, arc-dsl, objgrow, and
       the two shared scripts that run the job;
     - the split, study B's discovery records, the builder's registries, and the benchmark input files.
   - At run start and again before scoring, every module loaded from the repository must be a frozen file with its
     frozen digest.
   - The two shared launch scripts (`scripts/run_detached.sh`, `scripts/with_cpu_slot.sh`) are frozen separately.
     They are checked at launch only, so an edit to them by another job during the run cannot stop the scoring.
   - The solution files are not hashed by this study's freeze. Their digests are those study B's freeze recorded
     (`config/CONFIG.json`).
2. **An independent pre-run review** of the frozen bytes, and a re-check of the fixes.
3. **The GO.** The coordinator writes the file `GO` with four lines:
   - `protocol_sha256 <digest of this file>`;
   - `freeze_sha256 <digest of FREEZE.json>`;
   - `primary failure_kept_vs_compression`;
   - `nonce <a fresh random hex salt of at least 16 characters>`.

   The gate (`lr/gate.py`) checks every frozen digest, the data root and these four lines before any held task is
   read. It checks them again before scoring. The GO's digest, made unpredictable by the nonce, is written into
   every row, the seal and both markers.
4. **One detached run:** `sh experiments/library_rivals_20261108/launch/run_main.sh`, which calls
   `scripts/run_detached.sh` with one CPU slot at nice 19.
   - The held run writes only to `runs/main`.
   - **Seal before scoring.** The seal is written only when every arm has exactly one valid row per held task, before
     any output is opened. It records the Python version.
   - **One scoring.** The scorer first checks every solution file's digest. It then writes the one-use claim
     `SCORING_<GO digest>` at the study root, decodes each requested task's outputs in place, scores, and writes the
     per-task score table (with its digest in RESULTS.json), RESULTS.json and REPORT.md. It writes
     `SCORED_<GO digest>` at the study root last. A second scoring under the same GO is refused, whatever the folder.
   - **Resuming.** If the job ends before the seal, the same launcher resumes it: rows already written are kept, and a
     partial last line is removed. After a reboot, `run_detached.sh` refuses until its status file
     `outputs/detached/library_rivals_20261108/run.status` is removed. That file is removed only when no process of
     the job is alive.
   - **If the job stops after the seal and before any claim,** `python3 -I run.py phase score runs/main` scores from
     the existing seal under the same GO, with the same checks, and nothing is searched again. There is no other
     retry.
5. **The result.** `RESULT.md`, written as result, lesson and direction.
6. **An independent audit** of custody and statistics. The per-task table lets the audit recompute every interval
   without opening any output again.

## 9. Commands

- `python3 -I run.py build`: the libraries (before the freeze).
- `sh launch/run_dry_twice.sh`: the full path twice, on 5 source tasks per benchmark, scored against source outputs,
  then the determinism comparison (`checks/DETERMINISM.json`). No held task is searched and no held output is
  decoded. It runs only before the freeze and refuses once FREEZE.json exists.
- `python3 -I run.py freeze`: the freeze.
- `sh launch/run_main.sh`: the run, after the GO.
- `python3 -I run.py phase score runs/main`: recovery only (section 8, item 4).

## 10. Honest expectation

- **Failure-kept:** its held outcome is already known: study B's object-reuse arm, 227 of 624 correct outputs, almost
  all in 1D-ARC.
- **Compression:** its flip entry should reproduce the gains on 1D-ARC flip (22 tasks in study B). Its S_train
  fragments (tilings, crops) are unlikely to help on these held halves. We expect roughly 25 to 45 correct outputs.
- **The primary** is therefore expected to be "failure_kept beats compression". Its interval should be wide, because
  the gain sits in a few 1D-ARC families.
- **Random libraries** are expected near G0 (6 correct outputs in study B).
- **ConceptARC** is expected to show small differences either way. Mini-ARC is a tie.

This expectation is written before the run. It is not a hypothesis test.

## 11. Compute

Five arms x 464 held tasks of base searches at 150,000 executions, in one CPU slot: about 30 CPU-minutes, judging
from the dry runs (`checks/dry_run/`). There is no stop rule beyond the per-search cap. An unfinished run is reported
as unfinished.
