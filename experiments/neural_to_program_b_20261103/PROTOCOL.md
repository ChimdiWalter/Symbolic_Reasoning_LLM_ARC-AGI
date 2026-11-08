# Test B protocol: neural guesses turned into verified programs

Draft for independent blind re-review, 3 Nov 2026. Nothing has run, and no code for it exists yet. The sha256 of this
file and of every input it names is in `PROTOCOL_FREEZE.json`, with paths relative to the repository root.

**Revision 3.** It answers the blind review `INDEPENDENT_PROTOCOL_REVIEW_V1.md` (sha256 `fbc39380…`, verdict HOLD on
six issues). Revision 2 (sha256 `8d50e45f…`) is kept unchanged as `PROTOCOL_REVISION_2.md`, with its freeze record as
`PROTOCOL_FREEZE_REVISION_2.json`. The six changes:

1. **No expressibility claim.** An arm with no fit is labelled "no fit within the declared search"
   (`NO_FIT_IN_BOUNDED_PROPOSAL`), with separate complete-search, execution-budget and CPU-limit flags. It is never
   counted as a language expressibility failure.
2. **Random targets always terminate.** The random target has a finite deterministic fallback, and degeneracy is
   recorded.
3. **Shuffled targets always share the shape.** They are shape-matched, or the unit has no shuffled target. The
   shuffled contrast runs on that pre-declared same-shape cohort, with the full assignment denominator reported.
4. **CPU guards cover all work.** Per-arm and whole-run guards include the constructor and all child work. A
   truncated run is `INCOMPLETE`.
5. **Scoring is gated.** It needs an output freeze, an independent output-chain review, a separate `GO_SCORE` and an
   exclusive score claim before any answer is read.
6. **Task-level correctness follows ARC scoring.** A task is correct only when every one of its test outputs is
   exactly correct.

## 1. Question and claim limit

**Short names, used throughout:**
- **The CORA-only entry:** the scored ARC-AGI-2 entry 57902131. It runs CORA's fixed program search and a second CORA
  solver, with no neural model.
- **The neural entry:** the scored entry 57867631. Its neural method is NVARC's, by Ivan Sorokin and Jean-Francois
  Puget, re-implemented by us on their checkpoint, with CORA on attempt 2.
- **The construction code:** the frozen code of the project's construction test (Test S1 in its records): its
  typed-hole writer, its fixed menu of 211 grid operations, and its search.

**Question.** On the 120 public ARC-AGI-2 evaluation tasks, can CORA's construction code turn the neural entry's
guesses into verified programs? A verified program is one that reproduces every demonstration and outputs the guess
on the test input.
- Are guesses verified more often than control targets?
- When no program fits, did the declared search finish, or did a budget stop it?

**Claim limit.**
- **Descriptive.** The public evaluation set has been examined before: both entries' outcomes on it are known. Every
  result on it is reportable but descriptive.
- **Prior exposure.** The neural checkpoint may have been exposed to these public puzzles during its training. This is
  a separate provenance limit.
- **Verified is not correct.** A verified program shows only that a guess is consistent with the demonstrations
  within the declared search, not that it is correct.
- **No language claim.** An arm with no fit within the declared search is not evidence that CORA's language cannot
  express the task.
- **Training tasks.** The development arm on training tasks reports only reachability and search outcome, never
  accuracy. The official rubric excludes training-set performance.
- **No neural run:** no GPU and no new neural run.

## 2. Inputs (pinned in `PROTOCOL_FREEZE.json`)

**Primary: the public evaluation set**

| input | file | sha256 |
|---|---|---|
| tasks (120 tasks, 172 test outputs) | `outputs/score_first/data/arc-agi_evaluation_challenges.json` | `e7c62a4b…` |
| answers, opened only by the scorer, only after `GO_SCORE` (section 6) | `<ARC data folder>/arc-agi_evaluation_solutions.json` | `84be4f4f…` |
| the CORA-only entry's public-evaluation run | `outputs/score_first/runs/op2_rehearsal_v1/submission.json` | `d1899a46…` |
| its score record, which lists its correct outputs | `kaggle/score_first_2026/configs/results/op2_rehearsal_v1/score.json` | `c2624d36…` |
| the neural entry's attempts (attempt 1 per test output) | `outputs/score_first/runs/h_rehearsal_v1/submission_A.json` | `558b6ab1…` |
| the neural entry's saved candidate pools (120 files, 1,053 grids) | `outputs/score_first/runs/h_rehearsal_v1/guarded_run_6e8af1765c0f47f58baa2ae857bf1645/pools/*.json` | combined digest `81b1957d…` |

The answers file's sha256 was taken once, by hashing only (nothing was parsed), when revision 1 pinned the inputs.
This revision copies that value and does not read the file. The scorer re-hashes it only after its exclusive claim
(section 6).

**Development: the training tasks that have frozen neural candidates**

| input | file | sha256 |
|---|---|---|
| the neural entry's commit run: 8 training tasks, one test output each | `outputs/score_first/runs/h_entry_v1/guarded_run_21d1b5c4a63d45d4a7aa2491a81d04cd/challenges_used.json` | `001e337f…` |
| its pools (8 files, 9 grids) | `.../h_entry_v1/guarded_run_21d1b5c4a63d45d4a7aa2491a81d04cd/pools/*.json` | combined digest `ed9232ff…` |
| the training set, used only to confirm the 8 tasks are identical to it | `<ARC data folder>/arc-agi_training_challenges.json` | `779eaba8…` |

- These are the only frozen neural-entry candidates on training tasks in the project's records.
- No training answer is read.

**Code.** The construction code is pinned as 38 files: 33 imported modules, including the unused neural-arm
sandbox, and 5 arc-dsl files. None has changed since commit 63d85732.

**Subgroup.** This is an outcome-selected descriptive slice.
- The CORA-only entry's score record lists exactly 3 correct outputs: 62593bfd:0, 62593bfd:1 and 981571dc:0.
- The slice is the 169 outputs on 118 tasks where that entry fails or abstains.
- It is chosen by a known score, so it is labelled outcome-selected and descriptive.

## 3. Arms

Each test output is one **unit**, with test input x. A unit has up to four arms. The arms differ only in the
**target**, an extra pair (x, target) added to the demonstrations:

| arm | target |
|---|---|
| neural | the neural entry's attempt 1 for this output |
| shuffled | another task's neural candidate of the same shape (rule below), or no shuffled arm |
| random | a random grid of the attempt-1 grid's shape (rule below) |
| no target | none: CORA's own construction search on the demonstrations alone, at matched limits |

**Shuffled rule: always the same shape.** Donors come from the same set, evaluation or training. Other tasks are tried
in sha256("donor:" + task id) order.
1. The donor is the first task whose attempt-1 grid for any output has the same shape as this unit's attempt 1.
2. If there is none, it is the first task with any pool candidate of that shape.
3. If neither exists, the unit has **no shuffled arm**. It is recorded as "unmatched" and is outside the shuffled
   cohort.

**The shuffled cohort** is the set of units with a same-shape donor. It is fixed by this rule, from the frozen
attempt and pool grids, before any search runs. The report gives the assignment denominator: all units, matched by
rule 1, matched by rule 2, and unmatched.

**Random rule: a finite, deterministic, valid grid.**
1. The grid has the attempt-1 grid's shape. Its cells are drawn uniformly from the colours in that grid, with
   `random.Random(sha256("random:" + task id + ":" + output index))`.
2. At most 100 draws are made, and the first draw that differs from attempt 1 is used.
3. If all 100 equal attempt 1, as they always do for a one-colour attempt 1, the target is attempt 1 with its top-left
   cell changed to the colour (that colour + 1) mod 10.
4. The unit records `random_degenerate: true` and the palette size.

The target is always a valid grid of the same shape, with colours 0 to 9.

## 4. One arm's procedure (identical for every arm)

The pairs P are the task's demonstrations, plus (x, target) for the three target arms. All functions are the
construction code's, called unchanged:

1. **Grammar.** G = `lang0.build_g0([])`, CORA's base program grammar with no operation removed.
2. **Base search.** `search.run(G, P, [x], track_partial=True)` at the construction code's base budget: 150,000
   executions, 20 CPU-s. A fit ends the arm: verified in the base grammar.
3. **Typed holes.** Otherwise, `controller.sketches(P, G)` writes up to three typed holes from the pairs. Then
   `s1.spec_candidates(schema.seeded_order(0), holes)` lists the menu operations that reproduce a hole's pairs.
4. **Retries.** Up to `s1.M_RETRIES` = 3 candidates are tried, in order:
   - G plus the operation, added with the construction code's own wrapper (`s1.Gates.fn` and
     `lang0.add_production`, as in its retry step);
   - `search.run` on P at the base budget.

   The first fit ends the arm: verified in the base grammar plus that operation.
5. **Record.** For each arm, from the frozen search's own outputs:
   - fit, program, the level (base grammar, or plus which operation), and the prediction on x;
   - each search's stop reason (`budget`, `cpu_cap`, or none when its enumeration finished) and whether its
     enumeration was capped;
   - the number of hole-matching menu operations;
   - the closest right-shaped program found and its share of correct cells;
   - `controller.shape_relation(P)`;
   - the arm's child-inclusive CPU receipt (section 5).

**Outcome per arm:**
- **Target arms:** verified means a program fits every pair in P. It then outputs the target on x by construction.
- **No-target arm:** reachable means a program fits every demonstration. Its first prediction on x is CORA's own
  answer.

**No fit within the declared search** (`NO_FIT_IN_BOUNDED_PROPOSAL`). This is the label of every arm that finds no
program. It says only that the declared search (the base search, up to three holes, up to three retries) found no
fit. It carries four flags:

| flag | means |
|---|---|
| `complete_search` | every search in the arm finished its enumeration, with no budget stop and no capped enumeration |
| `execution_budget_stop` | some search stopped on its 150,000-execution budget |
| `cpu_limit_stop` | some search stopped on its 20 CPU-s cap, or the arm hit its CPU guard |
| `enumeration_capped` | some search capped its enumeration |

Two descriptors are reported beside it:
- the shape relation of the pairs;
- whether any right-shaped program was found, and its share of correct cells.

It is never reported or counted as a language expressibility failure.

**Deliberately left out.** The 4x deeper search and the promotion gates of the construction test are not used. They
decide whether to invent and whether to keep an operation; this test asks only whether the declared search finds a
program.

## 5. Order, CPU guards, completeness

**Compute.** CPU only, through `scripts/with_cpu_slot.sh` (nice 19), BLAS threads 1, one slot.

**Order.**
1. **Primary:** 172 evaluation units, task by task, in sha256("taskB:" + task id) order, with all of a task's arms
   together.
2. **Development:** the 8 training units.
3. **Secondary pool stage:** every other candidate in the evaluation pools, neural arm only, in pool order. It is
   descriptive.

**Per-arm guard, child-inclusive.**
- Each arm runs in its own child process, with a hard limit of 100 CPU-s (`RLIMIT_CPU`) and a 400 s wall backstop.
  The limit covers everything the arm does: grammar construction, the four searches (20 CPU-s each by their own
  caps), hole writing, candidate enumeration and bookkeeping.
- The arm's receipt is the child's user and system CPU from `resource.getrusage`.
- An arm stopped by the guard is recorded as `CPU_GUARD`: no fit within the declared search, with `cpu_limit_stop`.
- The limit is identical for every arm, so the no-target arm's matched limit is the same 100 CPU-s.

**Whole-run guard.**
- The run stops when the summed child-inclusive receipts, plus the driver's own CPU, reach 10 CPU-h. If every arm
  used its full limit, the 720 primary and development arms would need about 20 CPU-h; most arms should end after the
  base search, so the expected total is 2 to 4 CPU-h.
- **`INCOMPLETE`.** If the guard stops the primary stage before every arm of all 120 tasks has finished:
  - the run is `INCOMPLETE`;
  - it makes no full-population decision and no 120-task claim;
  - every assigned task stays in the denominator, and unfinished tasks and arms are listed as unfinished;
  - results on the finished tasks are reported only as an `INCOMPLETE` descriptive slice.
- The later stages run only within what remains.

## 6. Freezes, reviews and gates

**Code freeze.**
- The driver, rules and scorer are written after this protocol's re-review. They are frozen in `CODE_FREEZE.json`.
- Before any GO, they are independently reviewed with synthetic adversarial cases, covering:
  - the random fallback;
  - the shuffled assignment;
  - the CPU guards and `INCOMPLETE`;
  - the score claim.
- The review confirms that the inference process has no path that reads answers. The driver also refuses at run time
  to open the answers file.

**Run gate.** `runs/GO_B` holds the sha256 of this file, of `PROTOCOL_FREEZE.json` and of `CODE_FREEZE.json`.

**Output freeze.** When the inference stages end, `OUTPUTS_FREEZE.json` records the sha256 of:
- every arm's output file and CPU receipt;
- the assignment record;
- the completeness record.

No answer has been opened at that point.

**Output-chain review.** An independent review checks the output freeze against the run's records.

**Score gate.**
- Scoring needs a separate exact-byte `runs/GO_SCORE`, binding the sha256 of:
  - `OUTPUTS_FREEZE.json`;
  - the scorer in `CODE_FREEZE.json`;
  - the output-chain review.
- Before it opens or hashes the answers file, the scorer creates an exclusive claim, `runs/SCORE_CLAIM.json`. It is
  created with `O_CREAT | O_EXCL`, written with the `GO_SCORE` digest and the time, and fsynced.
- If the claim already exists, the scorer refuses.
- An interrupted or failed score attempt leaves the claim in place and fails closed: scoring cannot resume without a
  reviewed amendment.
- The scorer then checks the answers file against its pinned sha256 and scores once. It never opens training answers.

## 7. Outcomes and statistics

**Output-level outcomes (all 120 evaluation tasks):**
1. **Verified guesses:** the test outputs where the neural target is verified.
2. **Reachability:** the outputs where the no-target arm finds a demonstration-consistent program.
3. **Correctness (after `GO_SCORE`):**
   - how many verified neural targets equal the true output, and their precision (correct / verified);
   - the neural entry's attempt-1 precision on the same outputs, as the neural guesses alone;
   - the no-target arm's own answers' output-level correctness.
4. **Search outcome, per task and output:** a table of each arm's result, or its no-fit flags and descriptors.

**Task-level indicators.** These follow ARC scoring: a task counts only when every one of its test outputs counts.
- **V_neural, V_random, V_no-target:** every test output of the task is verified (target arms) or reachable (no-target
  arm).
- **V_neural (cohort), V_shuffled (cohort):** every test output of the task that lies in the shuffled cohort is
  verified. These are defined for tasks with at least one cohort output.
- **A_neural:** every test output of the task has a verified neural target that is exactly correct.
- **A_cora:** every test output of the task has a no-target prediction that is exactly correct.

Output-level counts are always reported separately.

**Pre-declared contrasts** (exact two-sided McNemar over tasks, Holm over the three, alpha = 0.05):

| contrast | indicators | over |
|---|---|---|
| C1 | V_neural (cohort) against V_shuffled (cohort) | tasks with a cohort output |
| C2 | V_neural against V_random | all tasks |
| C3 | A_neural against A_cora | all tasks |

- **Underpowered:** a contrast with fewer than 6 discordant tasks is labelled "underpowered".
- **Descriptive decision:** "neural guesses become verified programs more often than control targets" only if the run
  is not `INCOMPLETE` and C1 and C2 are both significant after Holm, in the neural arm's favour. Otherwise, "not
  shown".
- **C3** is reported with its own label: "verified guesses add exactly solved tasks beyond CORA alone", "CORA alone
  solves more", or "no difference shown".

**Precision.** Output-level precision with verification and precision of the neural guesses alone are given with 95%
intervals, from a cluster bootstrap over tasks (10,000 resamples, `numpy.random.default_rng(0)`). Their difference is
reported the same way. All p-values are descriptive.

**Subgroup.** The same outcomes are reported for the 118-task outcome-selected slice, descriptively, with no separate
decision.

**Development arm (8 training tasks), reachability and search outcome only:**
- per output: whether the neural target is verified;
- the shuffled (if matched) and random targets' results;
- whether the no-target arm reaches a program;
- every arm's no-fit flags.

No accuracy is computed, and no test is run on them.

**Also reported:**
- the level of each verified program (base grammar, or which menu operation);
- the shuffled assignment denominator;
- the random-degeneracy count;
- CPU receipts per arm;
- every guard stop.

## 8. Claim templates

- **If shown (complete run):** "On the 120 public ARC-AGI-2 evaluation tasks, CORA's construction code turned the
  neural entry's guesses into programs that reproduce every demonstration:
  - on x test outputs, and on every output of y tasks;
  - against s tasks with another task's same-shape guess, and r with random grids.

  z of the verified guesses were exactly correct (precision p, against q for the guesses alone). Where no program
  fitted, the declared search finished on c outputs and was stopped by a budget on b. Descriptive: this set has been
  examined before."
- **Otherwise:** the counts, plainly, with "not shown", "underpowered" or `INCOMPLETE`.
- **Never:** a claim that CORA's language cannot express a task.
- **Training tasks:** reachability and search outcome only. No accuracy statement is made for them.
