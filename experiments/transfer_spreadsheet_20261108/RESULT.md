# Test T2, spreadsheet string transformations: result of the held run

Study folder: `experiments/transfer_spreadsheet_20261108/`. Author: Chimdi Walter Ndubuisi. Written on 8 Nov 2026,
after the one held run and before the independent post-score audit.

**Label.** Held results, reconstruction of known benchmark functions, not discovery. Of the 53 held tasks, 46 are real
forum problems and 7 come from families written by the benchmark authors (bikes, univ_1 to univ_6).

**In one paragraph.**
- On 53 unseen tasks at the pre-registered budget, the grown arm recovered 22, against 17 for static searched 4 times
  deeper, and 17 for pieces built from another task's failure.
- Neither primary reached significance after the Holm adjustment (both adjusted p = 0.125).
- The leave-one-out acceptance rule, which the test specification requires, cost 6 correct answers and prevented 1
  wrong one. Without it, the loop would have recovered 28 of 53. That count is a pre-registered descriptive
  secondary; comparing it with the other arms is exploratory, not a pre-registered result.
- The static search caught up with the grown arm's 22 at 2,560,000 executions. The gain at the pre-registered budget
  is therefore mainly faster search.

## Provenance

| item | value |
|---|---|
| protocol | `PROTOCOL.md`, sha256 `99964ac225c7c95e0c53d5503245df002e2d1a30cd8f67e2c7d778825c5b088d` |
| freeze | `FREEZE.json`, sha256 `d85d4b818e22941929b695aaa236b55a590476fb844c2362aad4405149fba522`, committed in `1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2` |
| salt | the freeze commit hash, `1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2`. `runs/held/summary.json` names this salt (checked) |
| pre-run review | `reviews/PRE_RUN_REVIEW.md`, PASS-WITH-NOTES (commit 89a5fde4). Its notes are answered below |
| GO | `runs/GO_T2`, written by the coordinator (commit fccbb0ff, 06:25Z), sha256 `630940303a326a7fb4489c112d2305ed882c34a54d36880784a5648dba2aa822` |
| run | one detached run via `sh launch/run_held.sh` (`scripts/run_detached.sh t2_held_score --slot`). The detached status reads START 06:25:59Z, then EXIT 0 at 06:50:43Z. The run waited for a CPU slot until 06:43:40Z, then ran all four passes |
| completeness | every pass ran all 53 tasks; no pass stopped early |
| CPU | 423 CPU-seconds in total; the primary pass took 31.6. The cap was 1,700 |
| environment | Python 3.12.3 (`/usr/bin/python3.12`), Linux 7.0.0-42 x86_64. See `runs/held_environment.txt` |
| outputs | `runs/held/` (run.status, summary.json, records_B20000/40000/160000/640000.jsonl), committed in 8246aefe right after the run |
| tables below | `analysis/result_tables.py`, which writes `runs/held_analysis/RESULT_TABLES.json` |

**Held checks** (pre-run review, note 1).
- 40 of the 53 held tasks have exactly one held check: all 26 that train on 2 examples, and 14 of the 27 that train
  on 3.
- 6 tasks have 2 to 5 held checks, and 7 have 6 or more (at most 16). There are 158 held checks in all.
- For most tasks, "recovered" therefore rests on one unseen example.

**Pieces per held task** (note 2).
- From 5,645 to 37,936. Seven held tasks exceed the development maximum of 6,794 pieces: 43120683, stackoverflow11,
  univ_2, univ_3, univ_4, univ_5 and univ_6.
- They exceed it because the task's own short constants join the delimiter list, as the frozen rule says.
- This changes no rule. It mainly dilutes the classical comparator's search on those tasks.

**Searches stopped by the CPU cap** (note 3). None:
- none of the base, static or classical searches, at any budget;
- none of the 238 retry searches recorded in the candidate rows of the grown and shuffled arms (64 at 40,000, 61 at
  20,000, 60 at 160,000 and 53 at 640,000).

## Primary result (pre-registered; B = 40,000; 53 of 53 tasks ran)

Recovered means the arm's program reproduces every held check of the task exactly.

| primary | grown | other arm | grown only | other only | exact McNemar p | Holm-adjusted p | bootstrap 95% interval of the difference | success |
|---|---|---|---|---|---|---|---|---|
| P1: grown against pieces built from another task's failure | 22/53 | 17/53 | 6 | 1 | 0.125 | 0.125 | 0.000 to 0.189 | no |
| P2: grown against static at 4 x 40,000 = 160,000 executions | 22/53 | 17/53 | 5 | 0 | 0.0625 | 0.125 | 0.019 to 0.170 | no |

**Neither primary succeeds.** Both differences point the way development did, but neither is detectable at this size
after the two-primary correction.

**How the arms got their answers at 40,000:**
- **Base search.** It fitted 18 of the 53 tasks, and 16 of those fits were right. The static, grown and shuffled arms
  share these 16. The classical comparator runs its own search and recovered 9 of them.
- **Grown arm.** Constructed pieces were accepted on 7 tasks, and 6 of them were recovered.
- **Shuffled arm.** Pieces built from another task's failure were accepted on 1 task (exceljet4), which was recovered.
- **Static arm.** The 4 times deeper search added 1 recovery beyond the base search.

**The discordant tasks:**
- **P1, grown only:** clean-and-reformat-telephone-numbers, strip-html-from-text-or-numbers, 43606446,
  remove-text-by-position, exceljet1, get-last-name-from-name.
- **P1, shuffled only:** exceljet4. The grown arm's leave-one-out rule rejected the correct piece there.
- **P2, grown only:** the first five P1 tasks.

**About the shuffled-failure arm** (review, check 3 and note 5).
- It uses the pieces built from another task's failure: that task's argument strings, delimiter list and pairs. It
  does not use the other task's failure description alone.
- It was a weak contrast in development: 2 of 30 tasks were recovered through another task's pieces. Here it was 1 of
  53.
- So P1 mostly compares building pieces from the task's own failure with getting almost no usable piece. It does not
  compare selection driven by the failure with selection that ignores the task; the classical comparator below is the
  reference for that.

## Secondary results (pre-registered, descriptive; exact McNemar p-values unadjusted)

### 1. Budget curve: faster search, or new ability?

Static and classical run at 4 x B executions; grown and shuffled run at B.

| base budget B | static | grown | pieces from another task's failure | classical | grown without leave-one-out |
|---|---|---|---|---|---|
| 20,000 | 17/53 | 21/53 | 15/53 | 21/53 | 27/53 |
| 40,000 (primary) | 17/53 | 22/53 | 17/53 | 21/53 | 28/53 |
| 160,000 | 19/53 | 24/53 | 18/53 | 22/53 | 30/53 |
| 640,000 | 22/53 | 25/53 | 19/53 | 24/53 | 31/53 |

| comparison | grown only | other only | exact p |
|---|---|---|---|
| grown at B against static at 4 x B, B = 20,000 | 5 | 1 | 0.22 |
| same, B = 40,000 | 5 | 0 | 0.0625 |
| same, B = 160,000 | 7 | 2 | 0.18 |
| same, B = 640,000 | 5 | 2 | 0.45 |
| grown at 40,000 against static at 80,000 executions | 5 | 0 | 0.0625 |
| grown at 40,000 against static at 160,000 | 5 | 0 | 0.0625 |
| grown at 40,000 against static at 640,000 | 5 | 2 | 0.45 |
| grown at 40,000 against static at 2,560,000 | 4 | 4 | 1.0 |

- **Catch-up budget: B = 640,000.** Static at 2,560,000 executions recovers 22 of 53, as many as grown at 40,000.
  The grown arm's gain at the primary budget is therefore faster search: the static language reaches the same number
  of tasks with 16 times the search.
- **Tasks that may show new ability.** These are tasks the grown arm recovers at 40,000 that static recovers at no
  budget up to 2,560,000 executions. There are 4: 43606446, clean-and-reformat-telephone-numbers,
  remove-text-by-position and strip-html-from-text-or-numbers.
  - The classical comparator also recovers all 4. In both arms, each answer is a single piece of the structure
    space that the base grammar cannot reach within 2,560,000 executions:
    - the last alphabetic token (43606446);
    - keep the digits (clean-and-reformat-telephone-numbers);
    - field 4 of a "/" split (remove-text-by-position);
    - the text between ">" and "<" (strip-html-from-text-or-numbers).
  - Each rests on one held check, and 3 of the 4 train on 2 examples.
  - They are candidates, not established new ability.
- At every budget the grown arm stays 3 to 5 tasks ahead of static at the same base, but no single comparison is
  significant.

### 2. Classical comparator (reference, not a gate)

| B | grown | classical | grown only | classical only | exact p |
|---|---|---|---|---|---|
| 20,000 | 21/53 | 21/53 | 6 | 6 | 1.0 |
| 40,000 | 22/53 | 21/53 | 7 | 6 | 1.0 |
| 160,000 | 24/53 | 22/53 | 9 | 7 | 0.80 |
| 640,000 | 25/53 | 24/53 | 10 | 9 | 1.0 |

**The two arms differ by training size** (at 40,000):

| tasks | n | static | grown | classical |
|---|---|---|---|---|
| train on 2 examples | 26 | 6 | 10 | 13 |
| train on 3 examples | 27 | 11 | 12 | 8 |

### 3. Net cost of the leave-one-out acceptance rule

At every budget, the rule rejected 6 correct answers and prevented 1 wrong answer, for a net of 6 fewer recoveries.

| B | correct answers rejected | wrong answers prevented | grown | grown without the rule |
|---|---|---|---|---|
| 20,000, 40,000, 160,000 | 6: remove-leading-and-trailing-spaces-from-text, 31753108, strip-non-numeric-characters, exceljet4, exceljet2, get-last-line-in-cell | 1: 11604909 | 21, 22, 24 | 27, 28, 30 |
| 640,000 | 6: as above, with 17212077 in place of remove-leading-and-trailing-spaces-from-text | 1: 35744094 | 25 | 31 |

- At 40,000, 5 of the 6 rejected correct answers are tasks that train on 2 examples, so the piece was rebuilt from a
  single example. All 6 rest on one held check.
- The prevented wrong answer (11604909) trains on 3 examples.
- **Wrong answers at 40,000:** static 3, grown 3, pieces from another task's failure 2, classical 3, grown without
  the rule 4.

**Exploratory, not pre-registered.** Without the acceptance rule, at 40,000, the loop recovered:

| comparison | without the rule | other arm | only without the rule | only the other arm | exact p |
|---|---|---|---|---|---|
| against static | 28/53 | 17/53 | 11 | 0 | 0.001 |
| against pieces from another task's failure | 28/53 | 17/53 | 11 | 0 | 0.001 |
| against classical | 28/53 | 21/53 | 7 | 0 | 0.016 |

These are not confirmatory: this arm was a secondary, and the rule was dropped only after seeing that it cost answers.

### 4. CPU-seconds per arm (process time summed over the 53 tasks)

| B | static | grown | pieces from another task's failure | classical |
|---|---|---|---|---|
| 20,000 | 5.62 | 4.38 | 5.43 | 5.41 |
| 40,000 | 10.96 | 6.75 | 9.28 | 9.80 |
| 160,000 | 41.64 | 17.53 | 26.99 | 32.43 |
| 640,000 | 110.11 | 39.03 | 65.70 | 92.30 |

- The base search counts in every arm that uses it, and the shuffled arm is also charged the other task's
  construction time.
- The execution budget does not count failure description, construction or leave-one-out rebuilding. These are
  counted here in CPU time.

**Recoveries at about equal CPU.**
- **Matching rule** (fixed in `analysis/result_tables.py` before these tables were computed; the protocol said only
  "about equal CPU"):
  - the grown arm's total CPU at each B is matched to the static pass whose total static CPU is nearest;
  - ties go to the smaller budget.

| grown at B (CPU-s) | matched static (CPU-s) | grown | static | grown only | static only | exact p |
|---|---|---|---|---|---|---|
| 20,000 (4.38) | 80,000 executions (5.62) | 21/53 | 17/53 | 5 | 1 | 0.22 |
| 40,000 (6.75) | 80,000 executions (5.62) | 22/53 | 17/53 | 5 | 0 | 0.0625 |
| 160,000 (17.53) | 160,000 executions (10.96) | 24/53 | 17/53 | 7 | 0 | 0.016 |
| 640,000 (39.03) | 640,000 executions (41.64) | 25/53 | 19/53 | 6 | 0 | 0.031 |

At about equal CPU, the grown arm is 4 to 7 tasks ahead, with no task going the other way except one at 20,000. The
matching is loose in one row: at 160,000, the paired runs differ 1.6 times in CPU (17.53 against 10.96
CPU-seconds).

### 5. Breakdowns at 40,000

| tasks | n | static | grown | pieces from another task's failure | classical | grown without the rule |
|---|---|---|---|---|---|---|
| forum problems | 46 | 15 | 20 | 15 | 20 | 26 |
| benchmark-author families | 7 | 2 | 2 | 2 | 1 | 2 |
| train on 2 examples | 26 | 6 | 10 | 5 | 13 | 15 |
| train on 3 examples | 27 | 11 | 12 | 12 | 8 | 13 |

The benchmark-author family tasks (bikes, univ) are mostly beyond every arm: 2 of 7 at most.

## Reading: result, lesson and direction

1. **The primaries.**
   - **Result:** no detectable difference. Grown recovered 22 of 53, against 17 for each comparison arm. The
     discordant tasks split 6 against 1 (P1) and 5 against 0 (P2), and both Holm-adjusted p-values were 0.125.
   - **Lesson:** a gain of about 5 tasks in 53, where most tasks have a single held check, is too small to detect with
     two corrected primaries. The direction matches development.
   - **Direction:** a confirmatory test needs more held tasks, or more held checks per task (for example, public
     string-transformation sets with more examples per task), pre-registered with the same two primaries.
2. **The acceptance rule.**
   - **Result:** leave-one-out rebuilding cost 6 correct answers and prevented 1 wrong answer, at every budget. Five
     of the 6 losses were pieces rebuilt from a single example.
   - **Lesson:** with 2 training examples, rebuilding from the one remaining example is not a usable acceptance test.
     The first consistent piece in the fixed order is often a different piece. Development showed the same thing on a
     smaller scale.
   - **Direction:** pre-register a new test with an acceptance rule suited to 2 or 3 examples, on fresh tasks. One
     option is leave-one-out only when 3 or more examples remain. Another is a rebuild that keeps the structure and
     re-fits only its parameters. The exploratory 28 of 53 cannot be claimed from this run.
3. **Faster search, or new ability?**
   - **Result:**
     - static catches up with the grown arm's 22 at 2,560,000 executions, 16 times the primary static budget;
     - at about equal CPU, the grown arm is 4 to 7 tasks ahead;
     - 4 tasks are never reached by static within 2,560,000 executions, and all 4 are reached by the classical
       comparator.
   - **Lesson:** in this domain the loop mainly buys search efficiency. A few single pieces are far outside the base
     grammar's compact reach: the last alphabetic token, keep the digits, field 4 of a "/" split, and the text
     between ">" and "<".
   - **Direction:** report this domain as an efficiency result. Test new ability separately, on tasks whose solutions
     need pieces the base grammar cannot express at any budget.
4. **Failure-driven selection against blind enumeration of the same pieces.**
   - **Result:** grown and classical are within 2 tasks of each other at every budget (for example 22 against 21 at
     40,000). Grown
     used less CPU (6.75 against 9.80 CPU-seconds at 40,000). The classical comparator is better on 2-example tasks
     (13 against 10) and worse on 3-example tasks (8 against 12).
   - **Lesson:** with a hand-written space of about 6,000 pieces per task, enumerating every piece blindly finds as
     many answers as building pieces from the failure. The failure tells the search where to look, which saves time,
     but here it did not reach more tasks.
   - **Direction:** the contrast that would show the failure's value in selection is a much larger piece space, where
     blind enumeration cannot keep up.
5. **Pieces built from another task's failure.**
   - **Result:** they were accepted and right on 1 of 53 tasks, as weak as in development (2 of 30).
   - **Lesson:** this control mostly tests construction against no construction.
   - **Direction:** a stronger control keeps the task's own sources but takes pieces drawn at random from the
     structure space in the same number. Another option is the task's own holes with their targets permuted.

## For the post-score audit

- All numbers above come from `runs/held/summary.json` and `runs/held/records_B*.jsonl`. They are recomputed by
  `python3 -I analysis/result_tables.py .` into `runs/held_analysis/RESULT_TABLES.json`.
- The detached runner's own files are in `outputs/detached/t2_held_score/` (not under version control). Their status
  and the stdout digest are copied into `runs/held_environment.txt`, and stdout itself into
  `runs/held_detached_stdout.log`.
