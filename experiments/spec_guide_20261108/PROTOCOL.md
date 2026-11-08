# Specification-reading guide test: protocol

Written 8 Nov 2026 at about 07:30Z, after development on validation data only and before any held task existed.
The held tasks cannot exist before the GO: they are drawn from a salt equal to the sha256 of the coordinator's
committed GO file. This protocol builds on `DESIGN_NOTE.md` (commit f042260f), which was committed before any data.
Code lives in `sgd/`; the log is `PROGRESS.md`.

## 1. Question, claim and framing

**Background: the object-level step.** It searches **blocks** in a fixed hand-set order, up to a budget of
**counted operations**.
- A block is one view (a way of cutting grids into objects), together with one edit or one whole-output form.
- A counted operation is one application of a candidate program to a grid.

**The question.** Earlier, a small learned guide reading coarse block features tied a frequency table on natural
tasks: 320 against 318 correct outputs. Can a learned, **specification-reading guide** order these blocks better than
fixed rules at a binding budget? It reads a failure's full specification, meaning the input and target grid pairs
that the missing operation must map.

**The claim tested.** A learned guide trained on the right distribution orders the step's operations close to the
oracle, and better than the strongest simple order (the hand-set order, the frequency table and the linear model).

**Framing, stated before the held run:**
- **Development found** that the raw specification adds no measurable ordering information beyond the step's own
  block features, which come from the step's own analysis of how objects change. On validation:
  - the guide gained 9 tasks and lost 4 against the small guide at 125 operations (p = 0.27);
  - with correct-answer labels it gained 3 and lost 7;
  - the same learner with and without the specification summary scored 985 and 979.
  The small guide's result is therefore pre-registered as a key secondary, with a tie expected.
- **The earlier tie was a ceiling effect.** The 320 against 318 tie on natural tasks came from every learned order
  sitting near the reachable ceiling. It does not mean the features cannot tell operations apart: trained on the right
  distribution, the small guide scores 980 of 1,000 at 125 operations against the frequency table's 879.
- **The open question** is steering decisions that the step's deduction does not already settle, such as predicates
  and parameters inside a block. This test does not address it.
- **Naming.** This is a learned, specification-reading guide: a step toward neural guidance for program synthesis,
  not "the transformer for program synthesis".
- **Precedents:** DeepCoder; RobustFill; BUSTLE; CrossBeam and LambdaBeam; neural-guided deductive search.

## 2. Tasks, partitions and custody (from DESIGN_NOTE.md)

- **Generated task.** One operation of the object step's own language (a single-rule paint in one of the 12 views, or
  a crop) is applied to four input grids of one public training task: three demonstrations and one test input. Only
  inputs are read from the ARC-AGI-2 public training challenges, sha256 779eaba8....
- **Family.** A task's family is `edit type | parameters | predicate kind | view`.
- **Partitions.**
  - Families are split by hash: training 60%, validation 20%, held 20%.
  - Grids are split by hash into a development pool and a held pool.
  - The held partition and the held pool were reserved in the design note and never used in development; the code
    refuses them without the GO.
- **Admission.** A generated task is admitted when the frozen step, in the hand-set order at 20,000 operations, is not
  capped and answers the test input correctly. At 20,000 with no cap every order yields the same candidates, so
  admission is the same for all arms. It uses the generated test output inside the generator, before any arm runs.
- **Held set.**
  - Held tasks are drawn after the GO, with seed = salt × 1000, from held families on held-pool grids. The salt is
    the sha256 of the committed GO file, and the seed uses its first 16 hex digits as an integer.
  - They are **capped at 60 admitted tasks per edit type**, within 10,800 seconds of generation.
  - Reason for the cap: the admitted mix is 56% recolor, delete and outline, which would make any frequency prior
    strong. The cap tests the order where the specification must identify the operation. The capped validation view
    gave the same conclusions as the full one.
  - The tasks file (demonstrations and test input) and the solutions file (test output and generating operation) are
    written separately. The runner never reads the solutions.
- **Natural tasks.** The source units of the earlier tests were used for training and validation only. The held
  halves of ConceptARC, Mini-ARC and 1D-ARC are consumed and not used.
- **Exposure statement.**
  - Development physically loaded every task's demonstrations and test inputs of the three benchmarks, held tasks
    included, through study A's loader; only source units were used.
  - The public training challenges are public, and their solutions file is never read.
  - No pretrained model is used.

## 3. The arms (all frozen; trained on the same development data)

The training data are the traced training tasks (9,890, of which 7,389 have a trace) plus the natural training units.
Labels are "the block yields a verified multi-pair candidate". Every arm uses the frozen step's blocks, budget and
verification, and differs only in order.

1. **Hand-set order.** The frozen order.
2. **Frequency table.** By (kind, view, edit type): (successes + 1) / (trials + 2), times exp(-mean log(1 +
   operations)).
3. **Linear model.** The earlier test's linear model on the block features.
4. **Small guide.** The earlier test's small guide: two hidden layers of 32 units on the block features, the same
   recipe.
5. **Specification-reading guide (v2).**
   - Encoder: a transformer with 4 layers, width 128 and 4 heads, over the specification's cell tokens. Each pair
     contributes changed cells, then other non-background cells, up to 120 per pair, plus size headers.
   - Pre-training: edit-type and view heads on 104,000 cheap generated tasks, augmented by colour permutations of
     colours 1 to 9 and the eight symmetries of the square.
   - Key head, and a **block head** that scores each block from the specification summary, the block's own features
     and its key.
   - Training: the traced tasks and natural training units.
   - Score: p × exp(-c), from its success and cost outputs.
   - Weights: `models/spec_guide.pt`.
6. **Shuffled-specification control.** The same guide, with held task i (in task-id order) reading the specification of
   task (i + n // 2) mod n.

Arms 2 to 4 are in `models/block_models.json`. All arms run at budgets of 125, 500 and 2,000 counted operations.

**Answer.** An arm's answer is the frozen step's candidate list on the task's single hole, under the arm's order at
the budget. The two attempts are the first two distinct test predictions of its multi-pair candidates in the frozen
order. A task is correct when the true test output is one of them (pass at 2).

## 4. Analysis (one scoring, after the predictions are sealed)

**Primary.**
- At 125 operations, the guide must beat **each** of the hand-set order, the frequency table and the linear model.
  This is an intersection-union rule, so all three must hold and no multiplicity adjustment applies.
- "Beats" means the exact two-sided sign test on tasks that differ gives p < 0.05, and the 95% bootstrap interval of
  the total difference lies above 0. The interval uses 10,000 draws, with tasks clustered by the generating edit type
  (`ngrow.analysis.compare`).
- 500 operations is the second budget point, with the same three comparisons, reported.

**Secondaries (Holm over three):**
1. The guide against the **small guide** at 125. This is the key secondary; a tie is expected and stated in section 1.
2. The guide against its shuffled-specification control at 125.
3. A linear probe: 5-fold cross-validated softmax regression of the generating edit type on the encoder's summary.
   The trained encoder is compared with the same architecture at random weights, by a paired sign test over tasks.

**Descriptive:**
- every arm at every budget;
- edit-balanced shares and results by edit type;
- counted operations, edit applications and CPU for each arm;
- the guide's edit-type prediction on held tasks.

**Predictions (from development, scored once):**
- **spec-1.** The primary holds at 125 (validation: guide 985; linear model 950; hand-set 877; frequency 879).
- **spec-2.** The guide against the small guide is not significant.
- **spec-3.** The guide beats its shuffled control (validation: 45 tasks gained, 3 lost).
- **spec-4.** The probe's trained encoder beats random weights.

A loss or a tie is reported as a sharpened diagnosis.

## 5. Running, custody and checks

- **GO file.** The coordinator commits `runs/GO` alone, after the freeze and the pre-run review. It carries the line
  GO, the study, the freeze commit (the last commit that changed FREEZE.json), FREEZE.json's sha256, the review commit
  and a fresh 64-hex nonce.
- **The held run** runs on Athe in one detached process through the CPU slot, at nice 19, on CPU only:
  `sh scripts/run_detached.sh sg_held --slot env PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= python3
  -s -B experiments/spec_guide_20261108/run.py held all`. It refuses unless all of these hold:
  - the GO is committed at HEAD and unchanged since its first commit;
  - its freeze commit is the last commit on HEAD that changed FREEZE.json, and FREEZE.json there equals the current
    file;
  - every frozen file hash matches;
  - nothing held exists.
- **What the run does.**
  1. It derives the salt from the committed GO itself and records it with the freeze commit in `runs/held/run.status`.
  2. It generates the held tasks: at most 60 per edit type, within 10,800 seconds.
  3. It runs every arm at every budget.
  4. It seals the predictions' digest in `runs/SEALED_PREDICTIONS`.
  The runner never reads the solutions file.
  A private Kaggle kernel was planned, but Kaggle refuses notebooks of this size (the model's weights are 2.6 MB), so
  the run stays on Athe.
- **Scoring.** `run.py score` runs once, detached, under `runs/SCORED`. It re-checks the git custody and the seal
  before it reads any solution. An audit follows.
- **Smoke test** (before the freeze review). It runs on a scratch copy of the frozen files with their dependencies
  (`runs/kaggle/package_candidate.tar.gz`), in rehearsal mode: validation families on development-pool grids and a
  rehearsal GO. Nothing held is touched. The gate refusal check covers:
  - no GO;
  - a GO naming another freeze;
  - a bad nonce;
  - a changed file;
  - generating again;
  - scoring again.
- **Compute.**
  - Development: GPU 0 only, under its lock; CPU work through the slots.
  - Long steps run through `scripts/run_detached.sh`.
  - Never GPU 1, Step B or /tmp/reserved.
  - Nothing public, and no competition submission.
- **Timeline (UTC).**
  - Freeze by about 10:00Z on 8 Nov, then the independent review.
  - The GO, then the held run overnight.
  - The audit by about 09:00Z on 9 Nov.
