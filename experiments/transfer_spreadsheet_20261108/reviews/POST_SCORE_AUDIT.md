# Post-score audit: test T2, spreadsheet string transformations

Study: `experiments/transfer_spreadsheet_20261108/`. Study author: Chimdi Walter Ndubuisi. Audit written on
8 Nov 2026, about 06:55Z to 07:10Z, by the independent reviewer who wrote `reviews/PRE_RUN_REVIEW.md`. The audit was
read-only outside this file. It ran no search; its only computations were statistics and evaluations of the recorded
programs, done in a scratch folder.

**Bytes audited**
- `RESULT.md`, sha256 `285aaf524df6b33396d00fee2e02053d6be6fa2437caa469f28315213d15cb79` (commit 8758efdb);
- run outputs (commit 8246aefe):
  - `runs/held/summary.json`: `603e423f7ffd1d1e38a619f33c5fe20462a3cd84568d2d65b363fcf3d60671d2`;
  - `records_B40000.jsonl`: `ce229a95876dcb4041da4556db98cb3cda0f878740ee8087bba351be4d71d0ab`;
  - `records_B20000.jsonl`: `45ca74fe73eb76e3b3c6b1c98c287d7c2fcf0e9bfaf449ff29cbeff615992b12`;
  - `records_B160000.jsonl`: `f95d88a7a7745653760c9f7f22ee64baf6a996a329e9f7f25956b1e29dc9fa30`;
  - `records_B640000.jsonl`: `eb146172f4c343d517de151dd396046d6363473e8d12e1c7c0e66e333a8ac7f4`;
- `runs/GO_T2`, sha256 `630940303a326a7fb4489c112d2305ed882c34a54d36880784a5648dba2aa822` (commit fccbb0ff);
- `outputs/detached/t2_held_score/` (`run.status`, `cmd.txt`, `cwd.txt`, `stdout.log`, `stderr.log`).

**Verdict: PASS.**
- Custody holds.
- Every number in `RESULT.md` recomputes from the run records, and re-evaluating every recorded program on its held
  checks reproduces every recorded outcome.
- `RESULT.md` reports both primaries as not significant and claims no success.
- Two sentences in `RESULT.md` need a wording correction (section 4). Neither changes a number or a conclusion.
- The papers should use only the sentences in section 5.

Labels, as in the protocol:
- **B** is the base budget, in operation executions.
- **P1** is grown against the shuffled-failure control, both at B = 40,000.
- **P2** is grown against static, with static at 4 x 40,000 = 160,000.
- "Static" is the base language without new pieces. "Shuffled" uses pieces built from another task's failure.

## 1. Custody: PASS

### A single GO

- `runs/GO_T2` was added once, by fccbb0ff (06:25:23Z), and never changed. That commit touches no other file.
- It holds exactly the three lines the pre-run review specified, and the file is read-only.
- The GO was written 38 seconds after the pre-run review commit (89a5fde4, 06:24:45Z).

### The salt

- `runs/held/summary.json` names the salt `1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2`.
- `git log --diff-filter=A` shows that only that commit added `FREEZE.json`.
- The run order in every pass equals the order of sha256(salt + "|order|" + task).
- Each shuffled donor is the next failing task in that order.
- The training and check counts of every task equal those given by `grow.split_examples(task, salt)`, and every
  recorded program fits its training examples under that split.

### The frozen files

- All 16 files listed in `FREEZE.json` are unchanged in the working tree.
- The 15 committed ones are unchanged at 8246aefe, at 8758efdb and at HEAD.
- No commit after the freeze touches a frozen path.
- `FREEZE.json` and `PROTOCOL.md` keep their frozen digests.
- `summary.json` records the same configuration as `config/CONFIG.json`.

### A single run, exit 0, no relaunch

- **The detached runner.** `run.status` reads START 06:25:59Z, then EXIT 0 at 06:50:43Z. `stderr.log` is empty.
- **No sign of a relaunch.** `cmd.txt` and `cwd.txt` date from 06:25:59Z. A relaunch rewrites both files and restarts
  `run.status`.
- **The run's own status.** `runs/held/run.status` has a single RUNNING line (06:43:40Z, after the wait for a CPU
  slot), four PASS lines and DONE at 06:50:43Z, at 423.14 CPU-seconds.
- **Where the outputs went.** The runner creates `runs/held/` with `exist_ok=False`, and it was committed once, by
  8246aefe, 30 seconds after the run ended.
- **The log copy.** The copy of `stdout.log` in the study matches the original (sha256 `c2c028b9`), and its numbers
  equal those in `summary.json`.
- **Only one held run.** No other detached run of this study exists.

### Compute

- The passes ran in the frozen order: 40,000, then 20,000, 160,000 and 640,000.
- Every curve pass started below 1,200 CPU-seconds.
- The total was 423 of the 1,700-CPU-second cap.
- Every pass ran all 53 tasks.
- No search was stopped by the CPU cap: not the base, static or classical searches, and none of the 238 retry searches.

## 2. Recomputation: PASS

**Method.**
- All of this was recomputed from `runs/held/records_B*.jsonl` with an audit script, independently of
  `analysis/result_tables.py`, using the frozen `t2/stats.py`.
- Separately, each of the 514 recorded programs (every arm, every pass) was parsed back from its printed form and
  evaluated on its task's training examples and held checks. All 514 fit their training examples, and all 514 held-check
  results match the records. There were 0 mismatches.

| item | RESULT.md | recomputed |
|---|---|---|
| P1 recoveries; discordant | 22 against 17 of 53; 6:1 | same |
| P1 exact p; Holm p; 95% bootstrap interval | 0.125; 0.125; 0.000 to 0.189 | same |
| P2 recoveries; discordant | 22 against 17 of 53; 5:0 | same |
| P2 exact p; Holm p; 95% bootstrap interval | 0.0625; 0.125; 0.019 to 0.170 | same |
| success flags | no, no | no, no (`summary.json` agrees) |
| discordant task lists for P1 and P2 | as listed | same |
| base fits at 40,000; right; grown accepted and right; shuffled accepted and right; static beyond the base | 18; 16; 7 and 6; 1 and 1 (exceljet4); 1 | same (the static extra is get-last-name-from-name) |
| budget curve, all 20 cells | as tabled | same |
| grown at B against static at 4 x B; grown at 40,000 against static at each 4 x B | as tabled | same |
| catch-up budget | B = 640,000; static at 2,560,000 recovers 22 | same (`summary.json`: 640,000) |
| possible new ability | 43606446, clean-and-reformat-telephone-numbers, remove-text-by-position, strip-html-from-text-or-numbers | same |
| caveats on those 4 | single piece; classical recovers all 4; 1 held check each; 3 of 4 train on 2 | same. Classical recovers all 4 at every B, with the same single piece. Static gives no fitting program at any budget |
| classical against grown | 21/21, 22/21, 24/22, 25/24; p = 1.0, 1.0, 0.80, 1.0 | same |
| leave-one-out cost | 6 correct rejected, 1 wrong prevented, net -6, at every B; task lists | same, including the 640,000 substitutions |
| wrong answers at 40,000 | 3, 3, 2, 3, 4 | same |
| exploratory, no leave-one-out against static / shuffled / classical | 28 against 17 (11:0, p = 0.001); 28 against 17 (11:0); 28 against 21 (7:0, p = 0.016) | same |
| CPU per arm, 16 values | as tabled | same |
| recoveries at about equal CPU | 4 rows, as tabled | same, under the rule in `analysis/result_tables.py` |
| split by source (46 forum, 7 author families) and by training size | as tabled | same |
| held checks; pieces per task | 40 single-check tasks, 158 checks; 7 tasks above 6,794 pieces, up to 37,936 | same, with the same 7 task names |

**When the equal-CPU rule was fixed.** The matching rule is in `analysis/result_tables.py`. The file's timestamp,
06:26:48Z, is before the first pass wrote its records at 06:44:11Z. The file itself was committed only with
`RESULT.md`, so its timing rests on the file timestamp.

## 3. RESULT.md against the protocol and the pre-run review: PASS

**The primaries.**
- Both are reported as "no detectable difference", with every number the protocol requires (section 5).
- No success is claimed.
- The summary, the primary section and the reading all say the same thing.

**The 28 against 17** is labelled exploratory and not confirmatory, in the summary and in secondary 3.

**Faster search.** It is stated plainly, as protocol section 6.1 requires. The 4 tasks are called "candidates, not
established new ability".

**The pre-run review notes are all carried:**
- held checks per task (note 1);
- the held range of pieces (note 2);
- CPU-cap stops, including retry searches (note 3);
- completeness (note 4; no pass stopped);
- what P1 can show and the wording of the shuffled arm (note 5 and check 3);
- the Python version, the immediate commit and the copy of the detached logs (note 6);
- the possible-new-ability list, the split by source and the stated equal-CPU rule (check 5).

**The wording rules hold.** "Discovery" appears only as "not discovery". There is no claim of general reasoning and none
of transfer beyond this benchmark.

**The licence check before release** (check 7). This audit ran it:
- none of the 291 held examples has an input or output string of 6 or more characters that appears in the held
  records, `summary.json` or `RESULT_TABLES.json`;
- in `RESULT.md`, the only match is an ordinary English word in its title;
- programs carry only short constants.

## 4. Corrections to RESULT.md (wording only; no number changes)

1. **"All arms share these 16."**
   - **Where:** primary result, "How the arms got their answers".
   - **The problem:** the claim is true for the static, grown and shuffled arms and for grown without leave-one-out.
     It is not true for the classical comparator, which runs its own search: it recovered 9 of the 16. The 7 it missed
     are create-email-address-from-name, 38664547, 19558979, get-first-word, univ_1, remove-unwanted-characters and
     35016216.
   - **Replace with:** "The static, grown and shuffled arms share these 16. The classical comparator runs its own
     search and recovered 9 of them."
2. **"That number is exploratory, not a pre-registered result."**
   - **Where:** "In one paragraph".
   - **The problem:** the count of 28 of 53 is a pre-registered descriptive secondary (protocol sections 4 and 6.3).
     What is exploratory is comparing it with the other arms.
   - **Replace with:** "That count is a pre-registered descriptive secondary; comparing it with the other arms is
     exploratory, not a pre-registered result."
3. **Optional precision.**
   - In reading 4, "tie" would read better as "are within 2 tasks of each other at every budget, with no detectable
     difference".
   - In the equal-CPU table, the 160,000 row matches a grown arm that used 1.6 times the static CPU. The other three
     rows match within 25%.

A dated note in `RESULT.md` can carry these. They do not touch any frozen file.

## 5. Sentences the papers may use (exact)

Each sentence is checked against the records. Use them as written, or shorten them without changing any number or
qualifier.

1. CORA's learn-from-failure loop was applied to a new domain, spreadsheet string transformations. Its six steps were
   re-implemented in a self-contained adapter: propose, check, describe the failure, build the missing piece, check
   again, and keep the piece only if it holds up. The loop was tested on 53 held-out tasks from the public SyGuS-Comp
   programming-by-example string benchmark: 46 real spreadsheet-forum problems and 7 tasks from families written by
   the benchmark authors.
2. Before any held-out task was run, the protocol, code, data split and two primary comparisons were frozen and
   independently reviewed. The held-out tasks were scored in a single run, and an independent audit recomputed every
   reported number from the run records.
3. A task counts as recovered when the program reproduces every held-out example of the task exactly.
4. At the pre-registered budget, the loop recovered 22 of the 53 tasks. It was compared with two arms, which recovered
   17 each:
   - the same search without new pieces, given four times the loop's base budget (the loop's maximum search
     spending);
   - pieces built from another task's failure.
5. Neither pre-registered comparison was statistically significant. The discordant tasks split 5 to 0 against the
   deeper search and 6 to 1 against pieces from another task's failure; both Holm-adjusted exact McNemar p-values were
   0.125.
6. Given 16 times its primary budget (2,560,000 operation executions), the search without new pieces also recovered 22
   of the 53 tasks. The loop's gain at the pre-registered budget is therefore mainly faster search.
7. Four tasks were recovered by the loop but not by the search without new pieces at any budget up to 2,560,000
   executions. These are candidates for new ability, not evidence of it:
   - each answer is a single operation from the hand-written space of spreadsheet text operations;
   - blind enumeration of that space also found all four;
   - each rests on a single held-out example.
8. The pre-registered acceptance rule rebuilds each new piece without one training example and requires the program to
   reproduce that example. It rejected 6 correct answers and blocked 1 wrong one, and 5 of the 6 rejections were on
   tasks with only two training examples.
9. Without the acceptance rule, the loop recovered 28 of the 53 tasks. Comparing that arm with the others (28 against
   17) was not pre-registered, so that comparison is exploratory.
10. Blind enumeration of every piece in the same space recovered about as many tasks as building pieces from the
    failure: 21 against 22 at the pre-registered budget, and within 2 tasks at every budget. It used more CPU time:
    9.8 against 6.7 CPU-seconds.
11. Matched by total CPU time to the nearest run of the search without new pieces, the loop recovered 4 to 7 more of
    the 53 tasks. This comparison is descriptive, and CPU time depends on machine load.
12. What failed, and what was learned:
    - with a single held-out example for most tasks, a gain of about five tasks in 53 was not detectable;
    - rebuilding a piece from one remaining example was too weak an acceptance test;
    - a confirmatory test needs more held-out examples per task and an acceptance rule suited to two or three training
      examples.
13. These results reconstruct known benchmark functions. The space of spreadsheet text operations was written with
    the development tasks in view. The results are not discoveries, and they show no transfer beyond this benchmark.

**Do not write:**
- that the loop beat either comparison arm;
- that the four tasks show new ability;
- 28 of 53 as the loop's result;
- the equal-CPU p-values as significant;
- that the original CORA code ran unchanged. The adapter re-implements the loop and imports no earlier module.

## 6. Evidence log

- **History:** `git log` on the study folder, on `runs/GO_T2`, on `runs/held` and on `RESULT.md`;
  `git log --diff-filter=A` on `FREEZE.json`; `git show --stat` on 89a5fde4, fccbb0ff, 8246aefe and 8758efdb;
  `git status --porcelain --ignored` on the study folder.
- **Digests:** the 16 frozen files in the working tree and at 8246aefe, 8758efdb and HEAD; `RESULT.md`, the GO, the
  outputs and the detached `stdout.log` against its committed copy.
- **Runner files:** `outputs/detached/t2_held_score/*` (contents and timestamps) and `runs/held/run.status`.
- **Audit scripts** (scratch, not committed): recomputation of every table from the records with the frozen
  `t2/stats.py`, and the re-evaluation of all 514 recorded programs with the frozen `t2/dsl.py`, `t2/pieces.py` and
  `t2/grow.py` on `data/prepared/tasks.json`, whose digest matches `FREEZE.json`.
