# Test T2, spreadsheet string transformations: pre-registration

Study folder: `experiments/transfer_spreadsheet_20261108/`. Author: Chimdi Walter Ndubuisi. Written on 8 Nov 2026,
before any method ran on a held task and before any held task's examples were read.

The sha256 of this file, the code, the configuration, the split, the data manifest, the prepared task file and the
launcher are in `FREEZE.json`. The held run starts only after the steps in section 9: an independent pre-run review,
then the coordinator's GO naming the digests of this file and of `FREEZE.json`, plus the salt. Any change after the
freeze is a dated amendment with a new freeze, made before the held run.

**Label.** Held results, once run, are reconstruction of known benchmark functions, not discovery:
- 46 of the 53 held tasks are real forum problems (45 from the forum folder, and 11440431, which is counted as a
  forum problem from its name, a forum question number);
- 7 come from families written by the benchmark authors (bikes, univ_1 to univ_6).

## 1. Question and claim limit

**Question.** CORA's loop is described in `records/NOV8_NEW_DOMAIN_TRANSFER_TESTS.md`: propose, check, describe the
failure, build the missing piece, check again, keep the piece only if it holds up on held checks. Run through a
spreadsheet adapter, does that loop recover more held string-transformation tasks than:
- **(P1)** the same loop with pieces built from another task's failure, at the same budget;
- **(P2)** the static language searched with 4 times the budget?

**Claim limit.**
- The structure space (`t2/pieces.py`) and the adapter were written by the author with the development tasks in view.
  A gain shows that failure-driven selection from this space helps on unseen tasks of the same benchmark. A null says
  nothing about other structure spaces or other benchmarks.
- The two primaries were chosen by the coordinator after the development numbers were known (section 8).
- The benchmark is public and widely used. A task's function may be known to people, or to tools, trained on public
  text. This study claims only what the pre-registered comparisons show.

## 2. Data, split and held tasks

**Data.** The SyGuS-Comp programming-by-example string benchmarks, pinned at commit `13c8deb6` of
https://github.com/SyGuS-Org/benchmarks.
- The source, licence (none stated), preparation rules and digests are in `DATA_MANIFEST.md` and
  `data/SOURCE_FILES_SHA256.json`.
- The prepared tasks, `data/prepared/tasks.json` (not committed), are rebuilt by `t2/prepare.py`.

**Split** (`split/DEV_SPLIT.json`, fixed before any method ran).
- **Groups.** Tasks are grouped by family. A group is a development group when sha256("transfer-spreadsheet-20261108|
  dev|" + group), read as a fraction, is below 0.30.
- **Development.** 30 tasks in 12 groups.
- **Held.** All 53 tasks of the other 47 groups:
  - 27 train on 3 examples, and 26 train on 2 because they have only 3 examples;
  - 45 come from the forum folder, 1 (11440431, named by a forum question number) from the 2018 folder, and 7
    from the benchmark-author families.
- **Not read.** No method has run on a held task, and no held example has been printed or read. Only task names and
  aggregate counts were seen.

**Held-item hash rule** (the salt is fixed after the freeze).
- **Salt.** The full 40-hexadecimal hash of the git commit that first contains `FREEZE.json` (the freeze commit). The
  coordinator writes it into `runs/GO_T2`. Before running, the runner checks that this commit holds a `FREEZE.json`
  with the digest named in the GO.
- **Training examples.** For each held task, the examples are ordered by sha256(salt + "|" + task + "|" + the
  example as JSON). The first 3 (or 2) are its training examples, and all the others are its held checks. There is
  one choice of training examples.
- **Run order.** Tasks are ordered by sha256(salt + "|order|" + task). This order also fixes the shuffled control's
  donors (section 4).

## 3. The system (`ADAPTER_CARD.md`; configuration `config/CONFIG.json`)

**Language.**
- The SyGuS-Comp string grammar of the SLIA track (strings with linear integer arithmetic), without conditionals
  (`t2/dsl.py`).
- Its leaves are the task's own grammar constants and arguments.

**Search.**
- Bottom-up by program size, with observational equivalence on the training examples.
- The budget is counted in operation executions, so results do not depend on machine load.
- A safety cap on CPU time per search: 20 CPU-seconds, or 80 for the static and classical searches at 4 times the
  budget. Every search stopped by it is counted and reported.
- Maximum program size 30.
- The answer is the first program that reproduces every training output.

**Failure description** (`t2/grow.py: failure_description`).
- **Partial programs.** When the base search fails, its string programs are ranked by the characters they explain of
  every wanted output, as a prefix, a suffix or an inner part.
- **Holes.** The whole output, and the gaps left by each of the 3 best partial programs, are holes: one (source string,
  wanted string) pair per training example. The sources are the task's string arguments.

**Construction** (`t2/pieces.py`).
- **Pieces.** A piece is one of 13 structures with fixed parameters (5,645 to 6,794 pieces per task). It qualifies
  when it maps every pair of a hole exactly. A hole that is one string on every example becomes a new constant.
- **Candidates**, in this order:
  - sketches in order: the whole output first, then the partial programs;
  - for one-hole sketches, up to 2 pieces per source;
  - for two-hole sketches, the first piece of each hole;
  - duplicate piece sets are dropped.
- **Check again.** At most 3 candidates are searched again at the base budget, with the piece added.

**Acceptance: leave-one-out rebuilding** (`t2/grow.py: loo_accept`). For each training example:
1. rebuild each piece from the other examples' pairs (the first consistent piece in canonical order);
2. put it in place of the piece in the program just found;
3. require that program to reproduce the left-out example exactly.

The first candidate that fits and passes is the grown arm's answer. If none passes, the arm abstains.

## 4. Arms (base budget B executions)

| arm | budget | role |
|---|---|---|
| grown | base search at B; on failure, up to 3 candidates searched again at B each, with leave-one-out acceptance | the loop |
| shuffled-failure control | the grown arm's base search. On failure, the pieces are the candidates built from the failure description of the next failing task in run order (cyclically), with leave-one-out over that task's pairs. Same retries and budget | is the failure's content needed? |
| static | the static language at 4 x B executions | is it only more search? |
| classical comparator | bottom-up enumeration with observational equivalence over the static language plus every piece of the structure space, 4 x B executions | reference, not a gate |
| grown without leave-one-out | the grown arm's first fitting candidate | secondary: cost of the acceptance rule |

- **Base fits.** When the base search fits, the grown and shuffled arms answer with that program, and so does the
  static arm, because enumeration is deterministic.
- **Matched spending.** The static arm gets the grown arm's maximum search spending: B plus 3 retries of B.

**Outcome.** A task is **recovered** by an arm when the arm's program reproduces every one of the task's held checks
exactly. An arm that gives no program has not recovered the task.

## 5. Primary analysis (at B = 40,000)

**The two primaries.**
- **P1:** grown against the shuffled-failure control, both at B = 40,000.
- **P2:** grown against static, with static at 4 x 40,000 = 160,000 executions.

**Test and decision.**
- Each primary uses the exact two-sided McNemar test on the discordant tasks of the 53.
- Holm's step-down adjustment is applied over {P1, P2} at a family-wise level of 0.05.
- A primary **succeeds** when its Holm-adjusted p is below 0.05 and the grown arm recovered more of the discordant
  tasks than the other arm. Otherwise it is reported as no detectable difference, with its numbers.

**Reported for each primary:**
- the recoveries of each arm out of 53;
- the discordant counts;
- the exact p and the Holm-adjusted p;
- the difference in recovery rate, with a paired bootstrap 95% interval (10,000 resamples of tasks, seed 20261108).
  The interval is descriptive.

## 6. Pre-registered secondaries (descriptive, no decision weight; exact McNemar p-values unadjusted)

1. **Budget curve: faster search, or new ability?** Every arm runs again at B = 20,000, 160,000 and 640,000 (static
   and classical at 4 x B, so up to 2,560,000 executions). Reported:
   - every arm's recoveries at each B;
   - grown at B against static at 4 x B;
   - grown at the primary 40,000 against static at each 4 x B, paired by task;
   - the **catch-up budget**: the smallest B at which static at 4 x B recovers at least as many tasks as grown at
     40,000;
   - the tasks the grown arm recovers at 40,000 that static recovers at no budget up to 2,560,000 executions. These
     are the candidates for new ability, as opposed to faster search.

   If static catches up, the report says plainly that the gain at 40,000 is faster search.
2. **Classical comparator:** grown against classical at each B.
3. **Net cost of the leave-one-out rule** at each B:
   - the correct answers it rejected (grown without leave-one-out right, grown not);
   - the wrong answers it prevented (grown without leave-one-out wrong, grown right or abstaining);
   - the net change in recoveries.
4. **CPU-seconds per arm** at each B (process time, summed over tasks). The base search counts in every arm that uses
   it; the shuffled arm is also charged the donor's construction time. Recoveries are also reported at about equal
   CPU. CPU time depends on machine load; the outcomes do not.
5. **Breakdowns:**
   - by training size (2 or 3 examples);
   - by source (46 forum tasks against the 7 tasks of the benchmark-author families);
   - computed from the records with the task names in `split/DEV_SPLIT.json`.

## 7. Interpretation rules (fixed now)

- **P1 succeeds:** the content of the task's own failure matters. Pieces built from another task's failure do not
  give the same recoveries.
- **P2 succeeds:** at this budget, growing the language beats spending the same search on the static language.
  Secondary 1 then says whether this is faster search (static catches up at a larger budget) or reaches tasks that the
  static search never reaches within 2,560,000 executions.
- **Either fails:** the report gives result, then lesson, then direction, with the numbers. For example:
  - a P1 null at 53 tasks means the content of the failure did not show an effect at this size;
  - a P2 null means the gain seen in development did not hold over a deeper static search on unseen tasks.
- **Wording.** No result is described as discovery, as general reasoning, or as transfer beyond this benchmark.

## 8. Development record (all numbers labelled development; 30 development tasks)

**Fixed from development, before this freeze:**
- the structure space;
- the failure description and the candidate order and cap;
- the acceptance rule;
- the base budget of 40,000 (the first development setting, kept);
- the budget curve.

**Primaries.** P1 and P2 were chosen by the coordinator after reading the development numbers below.

**Development results** at the development salt ("transfer-spreadsheet-20261108|dev-examples") and two further
development salts. Static and classical are at 4 x B.

| B | training examples | static | grown | shuffled | classical | grown without leave-one-out |
|---|---|---|---|---|---|---|
| 20,000 | salt 1 | 9/30 | 18/30 | 9/30 | 14/30 | 19/30 |
| 40,000 | salt 1 | 12/30 | 17/30 | 9/30 | 14/30 | 18/30 |
| 40,000 | salt 2 | 12/30 | 20/30 | 7/30 | 14/30 | 21/30 |
| 40,000 | salt 3 | 12/30 | 19/30 | 8/30 | 14/30 | 21/30 |
| 160,000 | salt 1 | 16/30 | 18/30 | 13/30 | 17/30 | 19/30 |
| 640,000 | salt 1 | 17/30 | 19/30 | 17/30 | 18/30 | 20/30 |

**Paired, at B = 40,000** (grown-only against other-only tasks, exact McNemar p):

| salt | grown against static | grown against shuffled |
|---|---|---|
| 1 | 5 against 0, p = 0.063 | 8 against 0, p = 0.008 |
| 2 | 9 against 1, p = 0.021 | 13 against 0, p = 0.0002 |
| 3 | 8 against 1, p = 0.039 | 11 against 0, p = 0.001 |

**What development showed:**
- The gain over static shrinks as the budget grows. The pieces are often shortcuts for longer base programs. For
  lastname, for example, field 2 of a space split replaced a 10-node substring program.
- Static at 4 x 640,000 = 2,560,000 executions recovered 17 of 30. That equals grown at 40,000 (17 of 30), so in
  development static catches up at the largest curve budget.
- Leave-one-out acceptance cost 1 or 2 correct answers per run. Over five runs it rejected a correct piece 6 times and
  caught 1 wrong piece.
- 3 of 30 base programs fit their training examples but fail the held checks. The loop does not revisit a fitting
  program.

**Caveats.**
- The development tasks were read while the adapter was written, so development numbers are optimistic.
- Of the 30 development tasks, 20 come from two benchmark-author families.
- The held tasks are mostly forum problems, and half of them train on 2 examples, where the development runs showed
  the acceptance rule to be weakest.

## 9. Custody, compute and stop rules

1. **Freeze.** This file and `FREEZE.json` are committed, with git limited to the study folder. The freeze commit's
   hash is the salt.
2. **Report.** The freeze is reported to the coordinator.
3. **Review.** An independent pre-run review, on the exact bytes.
4. **GO.** The coordinator writes `runs/GO_T2` with the lines `protocol_sha256=…`, `freeze_sha256=…` and `salt=…`.
5. **One detached run:** `sh launch/run_held.sh`.
   - It calls `scripts/run_detached.sh t2_held_score --slot`, which uses setsid and nohup inside one shared CPU slot
     at nice 19.
   - The detached runner's status is in `outputs/detached/t2_held_score/run.status`.
   - The run writes its results into the study folder: `runs/held/run.status`, `summary.json` and
     `records_B<budget>.jsonl`. The owner commits that folder right after the run ends.
   - Before the run starts, the runner checks the GO lines, the salt commit and every frozen digest. It refuses if
     `runs/held/` already exists.
6. **`RESULT.md`**, then an independent post-score audit.

**Compute.**
- The primary pass (B = 40,000) runs first, then the curve passes in the order 20,000, 160,000, 640,000.
- A curve pass starts only while the run's CPU time is below 1,200 CPU-seconds.
- Any pass stops when the run's CPU time exceeds 1,700 CPU-seconds (within the 30 CPU-minute limit). Its unrun tasks
  are reported as not run, and an incomplete pass is reported as incomplete.
- **Expected CPU,** scaled from the development curve run (280 CPU-seconds for 30 tasks): about 500 CPU-seconds
  (about 8 CPU-minutes, less on a lighter machine) for the 53 held tasks, of which the primary pass is about 40.

**Stop rules.**
- One run, with no rerun and no rescoring.
- A crash is written as FAILED in `runs/held/run.status` and reported. A new run needs a dated amendment, a new
  freeze and a new GO.
- A bug found after the run is reported with the numbers as they were obtained. It is not fixed silently.
- Every outcome is reported, positive or negative.

## 10. Files

| file | role |
|---|---|
| `t2/sl_parse.py`, `t2/prepare.py` | benchmark reader; tasks and development split |
| `t2/dsl.py` | static language and enumerator |
| `t2/pieces.py` | structure space |
| `t2/grow.py` | failure description, construction, leave-one-out acceptance |
| `t2/run.py` | arms, passes, primary and secondary analysis, GO and freeze checks |
| `t2/stats.py` | exact McNemar, paired bootstrap, Holm |
| `t2/freeze.py` | writes `FREEZE.json` |
| `config/CONFIG.json` | budgets and caps |
| `split/DEV_SPLIT.json` | development and held task names |
| `launch/run_held.sh` | the detached held run |
| `DATA_MANIFEST.md`, `data/SOURCE_FILES_SHA256.json` | data source, licence and digests |
| `ADAPTER_CARD.md` | what was reused and what was rebuilt |
| `PROGRESS.md`, `dev/` | development record |
