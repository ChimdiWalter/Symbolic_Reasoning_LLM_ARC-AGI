# Test B protocol: neural guesses turned into verified programs

Draft frozen 3 Nov 2026 for independent blind review. Nothing has run, and no code for it exists yet. The sha256 of
this file and of every input it names is in `PROTOCOL_FREEZE.json`, with paths relative to the repository root.

**Revision 2, before any review.** It replaces revision 1 (sha256 `bdd0b037…`):
- the primary population is now all 120 public evaluation tasks;
- the tasks the CORA-only entry fails or abstains on become a pre-declared subgroup;
- a development arm on the 8 training tasks that have frozen neural candidates is added, reporting only
  reachability and gap type;
- every unproved arm is given a gap type.

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
- When no program fits, is the gap one of expressibility, or a search or budget limit?

**Claim limit.**
- **Descriptive.** The public evaluation set has been examined before: both entries' outcomes on it are known. Every
  result on it is reportable but descriptive.
- **Verified is not correct.** A verified program shows that a guess is consistent with the demonstrations in CORA's
  language, not that it is correct; that is outcome 3.
- **Training tasks.** The development arm on training tasks reports only reachability and gap type, never accuracy.
  The official rubric excludes training-set performance.
- **No neural run:** no GPU and no new neural run.

## 2. Inputs (pinned in `PROTOCOL_FREEZE.json`)

**Primary: the public evaluation set**

| input | file | sha256 |
|---|---|---|
| tasks (120 tasks, 172 test outputs) | `outputs/score_first/data/arc-agi_evaluation_challenges.json` | `e7c62a4b…` |
| answers, read once by the scorer only | `<ARC data folder>/arc-agi_evaluation_solutions.json` | `84be4f4f…` |
| the CORA-only entry's public-evaluation run | `outputs/score_first/runs/op2_rehearsal_v1/submission.json` | `d1899a46…` |
| its score record, which lists its correct outputs | `kaggle/score_first_2026/configs/results/op2_rehearsal_v1/score.json` | `c2624d36…` |
| the neural entry's attempts (attempt 1 per test output) | `outputs/score_first/runs/h_rehearsal_v1/submission_A.json` | `558b6ab1…` |
| the neural entry's saved candidate pools (120 files, 1,053 grids) | `outputs/score_first/runs/h_rehearsal_v1/guarded_run_6e8af1765c0f47f58baa2ae857bf1645/pools/*.json` | combined digest `81b1957d…` |

**Development: the training tasks that have frozen neural candidates**

| input | file | sha256 |
|---|---|---|
| the neural entry's commit run: 8 training tasks, one test output each | `outputs/score_first/runs/h_entry_v1/guarded_run_21d1b5c4a63d45d4a7aa2491a81d04cd/challenges_used.json` | `001e337f…` |
| its pools (8 files, 9 grids) | `.../h_entry_v1/guarded_run_21d1b5c4a63d45d4a7aa2491a81d04cd/pools/*.json` | combined digest `ed9232ff…` |
| the training set, used only to confirm the 8 tasks are identical to it | `<ARC data folder>/arc-agi_training_challenges.json` | `779eaba8…` |

- These are the only frozen neural-entry candidates on training tasks in the project's records. They are its pools
  from the Kaggle commit run, on the placeholder test set.
- No training answer is read.

**Code.** The construction code is pinned as 38 files: 33 imported modules, including the unused neural-arm
sandbox, and 5 arc-dsl files. None has changed since commit 63d85732.

**Subgroup.**
- The CORA-only entry's score record lists exactly 3 correct outputs: 62593bfd:0, 62593bfd:1 and 981571dc:0.
- The pre-declared subgroup is the 169 outputs on 118 tasks where it fails or abstains. It reads that existing
  record, not the answers.

## 3. Arms

Each test output is one **unit**, with test input x. A unit runs four arms. The arms differ only in the **target**,
an extra pair (x, target) added to the demonstrations:

| arm | target |
|---|---|
| neural | the neural entry's attempt 1 for this output |
| shuffled | another task's neural candidate (rule below) |
| random | a random grid of the attempt-1 grid's shape (rule below) |
| no target | none: CORA's own construction search on the demonstrations alone, at matched compute |

**Shuffled donor rule.** Donors come from the same set, evaluation or training. Other tasks are tried in
sha256("donor:" + task id) order.
1. The donor is the first task with an attempt-1 grid of the same shape as this unit's attempt 1.
2. If there is none, it is the first task with any pool candidate of that shape.
3. Otherwise it is the attempt-1 grid whose height and width differ least, with ties broken by that order.

Results are also reported for the units with a same-shape attempt-1 donor.

**Random rule.** The grid has the attempt-1 grid's shape. Its cells are drawn uniformly from the colours in that
grid, with `random.Random(sha256("random:" + task id + ":" + output index))`. A draw equal to attempt 1 is redrawn
from the same generator.

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
   - CPU-s.

**Outcomes per arm.**
- **Target arms:** verified means a program fits every pair in P. It then outputs the target on x by construction.
- **No-target arm:** reachable means a program fits every demonstration. Its first prediction on x is CORA's own
  answer.

**Gap type.** Every arm that finds no program gets one gap type:

| gap type | when |
|---|---|
| expressibility gap | No search stopped on its execution budget or CPU cap, and no enumeration was capped. Within its size limit, no program of the base grammar, alone or with any hole-matching menu operation, fits the pairs. This includes the case where no menu operation matches a hole. |
| search or budget limit | Some search stopped on its execution budget or CPU cap, or had its enumeration capped, so a fitting program may exist beyond it. |

Two descriptors are reported beside the gap type:
- the shape relation of the pairs;
- whether any right-shaped program was found, and its share of correct cells.

**Deliberately left out.** The 4x deeper search and the promotion gates of the construction test are not used. They
decide whether to invent and whether to keep an operation; this test asks only whether a program exists.

## 5. Order, budget, freezes

- **Compute:** CPU only, through `scripts/with_cpu_slot.sh` (nice 19), BLAS threads 1, one slot.
- **Order:**
  1. primary: 172 evaluation units, task by task, in sha256("taskB:" + task id) order, with all four arms of a task
     together;
  2. development: the 8 training units, four arms each;
  3. secondary pool stage: every other candidate in the evaluation pools, neural arm only, in pool order. It is
     descriptive.
- **Budget:** at most 80 CPU-s per arm, so about 16 CPU-h for the 720 primary and development arms if every arm used
  all of its time. Most arms should end after the base search, so the expected total is 2 to 4 CPU-h.
- **Hard stop at 10 CPU-h.** If it stops the primary stage, only tasks whose four arms all finished are analysed, and
  the report says how many. The later stages run only within what remains.
- **Freeze before scoring.** `OUTPUTS_FREEZE.json` (the sha256 of every arm's output file) is written before the
  scorer opens the evaluation answers. The scorer runs once; any second use is reported as such. It never opens
  training answers.
- **Code freeze.** The driver, rules and scorer are written after this protocol's review. They are frozen in
  `CODE_FREEZE.json` and reviewed before any run.
- **GO.** The run starts only when `runs/GO_B` holds the sha256 of this file, of `PROTOCOL_FREEZE.json` and of
  `CODE_FREEZE.json`.

## 6. Outcomes and statistics

**Primary outcomes (all 120 evaluation tasks):**
1. **Verified guesses:** the tasks, and the test outputs, where the neural target is verified.
2. **Reachability:** the tasks, and outputs, where the no-target arm finds a demonstration-consistent program.
3. **Correctness (one-use scorer):**
   - how many verified neural targets equal the true output, and their precision (correct / verified);
   - the neural entry's attempt-1 precision on the same outputs, as the neural guesses alone;
   - the no-target arm's own answers' correctness.
4. **Gap type, for every task:** a per-task table of each arm's result or gap type, with its descriptors.

**Task-level indicators** (over tasks whose arms all finished):
- V_arm: some output of the task is verified (target arms) or reachable (no-target arm).
- A_neural: a verified neural target equals the true output.
- A_cora: the no-target arm's prediction equals the true output.

**Pre-declared contrasts** (exact two-sided McNemar over tasks, Holm over the three, alpha = 0.05):

| contrast | indicators |
|---|---|
| C1 | V_neural against V_shuffled |
| C2 | V_neural against V_random |
| C3 | A_neural against A_cora (correct verified guesses against CORA's own correct answers at matched compute) |

- **Underpowered:** a contrast with fewer than 6 discordant tasks is labelled "underpowered".
- **Descriptive decision:** "neural guesses become verified programs more often than control targets" only if C1
  and C2 are both significant after Holm, in the neural arm's favour. Otherwise, "not shown".
- **C3** is reported with its own label: "verified guesses add correct answers beyond CORA alone", "CORA alone gives
  more", or "no difference shown".

**Precision.** Precision with verification and precision of the neural guesses alone are given with 95% intervals,
from a cluster bootstrap over tasks (10,000 resamples, `numpy.random.default_rng(0)`). Their difference is reported
the same way. All p-values are descriptive.

**Subgroup.** The same outcomes and contrasts are reported for the 118 tasks where the CORA-only entry fails or
abstains. They are descriptive, with no separate decision.

**Development arm (8 training tasks), reachability and gap type only:**
- per task: whether the neural target is verified;
- the shuffled and random targets' results;
- whether the no-target arm reaches a program;
- every arm's gap type.

No accuracy is computed, and no test is run on them.

**Also reported:**
- the level of each verified program (base grammar, or which menu operation);
- results for the same-shape shuffled units;
- CPU per arm;
- any arm stopped by a budget.

## 7. Claim templates

- **If shown:** "On the 120 public ARC-AGI-2 evaluation tasks, CORA's construction code turned x of the neural
  entry's guesses on y tasks into programs that reproduce every demonstration, against s with another task's guess and
  r with random grids. z of those verified guesses were correct (precision p, against q for the guesses alone). Where
  no program fitted, the gap was one of expressibility on e tasks and a search or budget limit on b. Descriptive: this
  set has been examined before."
- **Otherwise:** the counts and gap types, plainly, with "not shown" or "underpowered".
- **Training tasks:** reachability and gap types only. No accuracy statement is made for them.
