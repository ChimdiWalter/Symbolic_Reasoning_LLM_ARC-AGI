# Pre-run review: T5 signalling logic models (transfer_signalling_20261108)

- **Date:** 8 November 2026.
- **Reviewer:** independent pre-run reviewer, reporting to the coordinator.
- **Freeze reviewed:** commit 72f31059f186d82947c78bc50c491fb6e3a87945; FREEZE.json sha256
  fb5a8cc3a17be9a79faece61492295286a3872fc0b705402c6e5b1170c6f9516. Repository HEAD at review time:
  2cc28b8f14af5847ca4f4f72af95d3208ccbce2c.
- **Read:** PROTOCOL.md, FREEZE.json, PROGRESS.md, DATA_MANIFEST.md, ADAPTER_CARD.md, both configurations, all of
  `t5/` and `scripts/`, the reused core files (`u6/__init__.py`, `u6/bn.py`, `u6/stats.py`),
  `scripts/run_detached.sh`, `scripts/with_cpu_slot.sh`, and the development and dry-run outputs.
- **Run:** hash checks, git queries limited to these paths, read-only analyses of the development outputs, structural
  counts on the design-only datasets, a three-node test of the checker, and a listing of the edges the generator can
  remove. No held scoring was run, no held task or held fold was generated, and no DREAM measured value was printed
  (counts only).

## Verdict: FAIL (one blocking defect, fixable before GO)

The design, the freeze binding, the statistics and the labels pass. One implementation defect can stop the single
scored run: the checker disagrees with the simulator on any final program that does not settle, and the run then
stops. The fix is one line in a frozen file, so it needs a new freeze and a short review of the change before GO. The
salt change recommended below should go into the same freeze.

## Blocking finding: the checker stops the run on any program that does not settle

**Evidence.**
- On a cyclic space, `simulate` in `t5/model.py` runs ceil(1.2 x nodes) synchronous steps and marks bits that are
  still changing as NA. The checker, `simulate_core`, runs one step more (`range(math.ceil(1.2 * space.N) + 1)`).
  For a program that never settles, the two return different values, `check_models` raises `AssertionError`, and
  `score_held.py` writes FAILED and stops. The protocol (section 5) treats an NA prediction as a mismatch to be
  scored, not as a reason to stop.
- **Test.** Nodes a, r1 and r2, with r1 = a AND NOT r2, and r2 = r1. `simulate` marks r2 as NA, `simulate_core`
  marks r1 as NA, and `check_models` raises "simulator and core checker disagree".
- **The required condition happens.** Pieces built in the same round go into different readouts, and each one only
  checks that its own source is not downstream of its own readout. Together they can close a loop. In development
  task `dev|syn_dream|132`, the kept grown program held the loop akt, mek12, erk12, p38 and back to akt, through the
  pieces `p38+pi3k=akt` and `!erk12+tgfa=p38`. That loop contains a negated input, which is the kind of loop that can
  keep changing under synchronous updates. It settled in every condition, so development never reached the crash.
- **How often.** Development had 1 such loop among the 320 grown and shuffled final programs of the 160 DREAM tasks
  with 5% noise, and none among the 80 without noise. About one is therefore expected among the 400 in the primary. If it fails to settle in any condition, held or training, the
  run stops. That chance is probably small, but development cannot bound it.
- **Stale claim.** The docstring of `grow.py`, "the space stays acyclic", is false for pieces added in the same
  round.
- **Consequence.** A stop in the primary makes the single run a failure under stop rule 1. It also leaves the held
  outcomes of the finished tasks in `results_held/tasks.jsonl`, so a rerun on the same salt would score items already
  seen.

**Exact fix.**
1. In `t5/model.py`, `simulate_core`, change `for _ in range(math.ceil(1.2 * space.N) + 1):` to
   `for _ in range(math.ceil(1.2 * space.N)):`.
   - Both simulators then apply the same oscillation rule over the same number of steps.
   - The checker still recomputes every expression independently with `u6.bn.evaluate`.
   - Predictions come from `simulate`, so no prediction can change. No development number changes either, because
     development never reached a disagreement.
2. Add a regression test in `tests/` with the three-node program above. `check_models` must pass, the NA mask must not
   be empty, and `Obs.errors` must count the NA bit as wrong.
3. Run the dry run again, regenerate FREEZE.json with `scripts/make_freeze.py`, commit the new freeze, and send the
   diff for a short review before GO.

## Salt recommendation

**The current salt (the freeze commit hash).**
- **What it does well:** it was unknown during development, which is its main job, and its entropy is ample.
- **Grinding:** it is not adequate against the designer. The designer controls the commit's content and timestamps,
  so they can make many candidate hashes and evaluate the primary under each one, at about 8 CPU-minutes per
  candidate.
- **Peeking:** anyone with the repository has been able to compute the held outcomes since 06:07:52Z, before GO, and
  the repository would not show that anyone had.
- **No sign of either:**
  - FREEZE.json was written at 06:07:35Z and committed 17 seconds later, and the second dry run (salt DRYRUN) ran in
    those seconds.
  - No file in the study folder or in `outputs/detached/` contains the freeze hash.
  - Neither `results_held/` nor `outputs/detached/t5_held_score/` exists.
- **Re-freezing keeps the old salt.** Under the current code, a re-freeze that edits FREEZE.json keeps the salt at
  72f31059..., because `git log --diff-filter=A` still returns the commit that first added the file.

**Recommendation: take the salt from a GO file, in the same re-freeze as the blocking fix.**
1. **The GO file.** After the review of the change, the coordinator writes `GO.json` in the study folder and commits
   it on its own. It holds:
   - the new freeze commit;
   - the FREEZE.json sha256;
   - the sha256 of this review and of the change review;
   - the UTC time;
   - a 256-bit nonce, drawn by the coordinator at GO time
     (`python3 -c "import secrets; print(secrets.token_hex(32))"`) and shown to no one before the commit.
2. **The salt** is the sha256 of the committed GO.json bytes. The scored run starts right after the GO commit.
3. **The check in `score_held.py`.** The script refuses to start unless:
   - GO.json matches its committed copy;
   - GO.json's FREEZE.json hash equals the sha256 of the working FREEZE.json, and FREEZE.json matches its committed
     copy;
   - GO.json's freeze commit is the last commit that changed FREEZE.json, and an ancestor of the GO commit;
   - `--salt` equals sha256(GO.json).

   Labels and folds then use the salt exactly as now.
4. **The amendment.** Amend PROTOCOL.md sections 9 and 10, the `salt_rule` and `run` strings in `make_freeze.py`, and
   the run command (`--salt <sha256 of GO.json>`).

This takes the salt out of the designer's hands and keeps the held items unknown to everyone until GO, after which no
change is allowed.

**If the coordinator keeps the commit rule:**
- the salt stays 72f31059f186d82947c78bc50c491fb6e3a87945, even after the re-freeze;
- GO should be written and the run launched promptly;
- RESULT.md should state that the salt was public from 06:07:52Z.

## The checks

### 1. The freeze binds everything that matters: pass, with notes

**Evidence.**
- **Hashes.** For all 23 files listed in FREEZE.json, the sha256 of the working copy and of the blob at the freeze
  commit both equal the recorded hash (23 of 23). FREEZE.json in the working tree is byte-identical to the committed
  copy.
- **History.** 72f31059... is the only commit that added FREEZE.json, and it is an ancestor of HEAD. No later commit
  touches the study folder, `u6/`, `scripts/run_detached.sh` or `scripts/with_cpu_slot.sh`. The study folder has no
  uncommitted or untracked changes.
- **Imports.** All of the run's own code is frozen:
  - `score_held.py` imports `t5.data`, `t5.tasks` and `u6.stats`;
  - `t5.tasks` imports `t5.grow`, `t5.model` and `t5.search`;
  - `t5.model` imports `u6.bn`;
  - `u6/bn.py` imports nothing, and `u6/stats.py` imports only math and numpy;
  - no other `t5` or `u6` package sits on the inserted paths.
- **Data.** The four data files the run reads are frozen. The other files in `data/raw/` match DATA_MANIFEST.md.
- **Environment.** `<python environment>` has Python 3.12.3 and numpy 2.4.3, as recorded.

**Notes.**
- **FREEZE.json itself.** The script checks the files against the working FREEZE.json, not against the committed
  one, so editing both together would pass. Before launch, confirm the sha256 of FREEZE.json against the value in
  GO. The GO check above closes this gap in code.
- **Not frozen:**
  - the launcher scripts, which cannot change results and have not changed since their commits (c23d22a0 and
    e34f8dd8);
  - the interpreter and numpy, which are recorded but not checked at run time. RESULT.json records only the Python
    version.
- **Frozen documents.** Any edit to PROTOCOL.md, ADAPTER_CARD.md or DATA_MANIFEST.md, even a typo, makes the run
  refuse to start. Put corrections in PROGRESS.md, which is not frozen, or in the amendment.

### 2. No held item exists or was seen: pass (for the salt, see above)

- **Labels.** Held labels are `held|<salt>|P1|<i>` and `held|<salt>|S2|<i>`, and secondary 1 deals its folds by
  sha256("salt|LiverDREAM|condition key"). Every development label in every development file is one of
  `dev|syn_dream|0` to `159`, `dev|syn_toy|0` to `29`, or `dev|toy|loco|0` to `8`, so no development label can equal
  a held one.
- **DREAM runs.** Every development run on the DREAM network used the design-only dataset (`LiverDREAM_design` in
  every record). The dry run used the salt DRYRUN and ran the secondary-1 code path on the toy data, not on DREAM.
- **No held output.** Neither `results_held/` nor `outputs/detached/t5_held_score/` exists. No file in the study
  folder or in `outputs/detached/` contains the freeze hash.
- **Disclosure.** PROTOCOL.md section 12 and DATA_MANIFEST.md disclose the display of the DREAM file at 05:31Z.
- **Note.** `results_dryrun/tasks.jsonl` holds two dry runs, with every task twice, because the log opens in append
  mode. This is harmless here; see check 6.

### 3. All arms get the same budget, data and conditions: pass, with notes

**Evidence.**
- **Data.** Every arm fits only the training columns, that is, the t1 and t0 rows of the training conditions:
  - `static_fit` uses `task.train_all`;
  - the comparator scores a sub-design of those columns;
  - failure descriptions, piece scores, repairs and acceptance folds are masked to `train_all` or to its fold subsets.

  Only `held_outcomes` reads the held t1 columns, and every arm is scored on the same held conditions.
- **Static against grown.** The grown and shuffled arms start from the static arm's program, the same memoised fit,
  and return it when the growth is not kept. Growth, with its acceptance check, is the only difference.
- **Grown against shuffled.** Both arms run one code path, `grow(..., shuffled=...)`, with the same static fits, the
  same fold assignment (`<task>|folds`) and the same caps: 3 rounds, 2 pieces per failure, 6 per round, 4 folds and a
  bar of 0. The arm's label enters only the shuffle's random generator.
- **The shuffled control.** In each round, one Sattolo cycle (a single cycle with no fixed point) over the current
  training columns moves the "want" and "keep" sets of every failure entry. Everything else is real: the readout, the
  direction (ON or OFF), the simulated state that scores pieces, the repair and the acceptance. Inside each acceptance
  fold, the shuffle is redrawn over that fold's training columns. So the control shuffles the failure description and
  nothing else.
- **Comparator.** It uses the same space and training columns, with a different objective and search, as intended.

**Notes.**
- **The shuffle crosses time points.** The cycle runs over the t1 and t0 columns together, so about half of the moved
  columns change time point, while the readout and the direction are kept.
  - This matches the protocol ("over the training columns").
  - It is a weaker control than a shuffle within each time point. Moved "want" sets often land on t0 columns, where
    most nodes are off, so the shuffled pieces rarely lower the real training errors. In development, the shuffled
    arm kept nothing in its main growth in 115 of 160 DREAM tasks.
  - RESULT.md should describe the control exactly. H1 (grown against shuffled) shows that the content of the failure
    (which conditions, at which time point) matters, given the right readout and direction.
- **Compute.** It is not equal, and cannot be. The grown and shuffled arms also run 4 rebuilt folds with static
  refits, and the comparator runs up to 500 generations.
  - The comparator searches the static space far harder, and it matched static in development (563 against 562 of
    800). So the gain in H2 (grown against static) does not come from more search.
  - CPU per arm is descriptive only, because the fold refits are memoised and paid by whichever arm needs them first.

### 4. The primary is pre-registered and sound: pass, with notes

- **Sign tests.** `binom_two_sided` is the exact two-sided binomial test at 0.5 on wins and losses, with ties dropped.
  `u6.stats.holm` is a correct Holm step-down, with the adjusted p taken as a running maximum.
- **McNemar.** The test is exact, on discordant held conditions.
- **Bootstrap.** `u6.stats.Bootstrap` uses default_rng(0) and 10,000 resamples of tasks, and gives a percentile 95%
  interval for the difference in exact proportions.
- **Noise.** Each training value, t1 and t0, is flipped with probability 0.05. Held values are the noise-free truth.
- **Held conditions.** Each primary task holds 5 conditions, the 5 smallest by sha256("label|condition key"), and
  trains on 20. Secondary 2 holds 2 per task.
- **Seeds.** A seed gets up to 200 truth draws, with up to 2,000 seeds, and skips are counted.
- **Development power table.** The table matches the development files:

  | Comparison | Won | Lost | Tied | Sign test p |
  |---|---|---|---|---|
  | Grown against shuffled | 49 | 13 | 98 | 4.8e-6 |
  | Grown against static | 61 | 13 | 86 | 1.4e-8 |

- **Settings.** config_held.json equals config_dev.json on every shared key, and every synthetic development result
  records that configuration.

**Notes.**
- **The decision.** It needs "grown wins more tasks than it loses", which the script does not compute. RESULT.md must
  apply it: a hypothesis is supported when its Holm-adjusted p is at most 0.05 and grown wins more tasks than it
  loses.
- **The removed edge.** It is one of only 6 edges (check 7).
- **Minimum effect.** "Changes at least 2 readout values over the design" counts t0 columns as well as t1. RESULT.md
  should say so.

### 5. The secondaries are honestly labelled: pass, with notes

- **Secondary 1 (the 25 real DREAM conditions).**
  - Sections 3 and 13 label it "development-exposed (format check printed the file at 05:31Z); underpowered", and as
    prediction, not discovery.
  - Its pre-registered test is the exact McNemar test over the 25 conditions. The script also computes sign tests and
    a bootstrap over the 5 folds. These are not pre-registered for this family, and no claim should use them.
  - By design, this family meets real DREAM values for the first time in the scored run. Its code path ran only on
    the toy data, but it handles missing values, and the file has 10 missing t1 values.
- **Secondary 2 (the toy-network family).** The development null and the expectation of no specificity are stated in
  advance.
- **Secondary 3 (the CellNOpt-style comparator).** It is labelled "Python re-implementation, not checked against R",
  and as a reference, not a gate. Add one point to that label: it has no wall-clock stop. CellNOptR's gaBinaryT1 also
  stops at maxTime, 60 s by default. Leaving that stop out keeps the comparator deterministic.

### 6. The run command: pass, with notes

- **Command.** `sh scripts/run_detached.sh t5_held_score --slot python3 -I
  experiments/transfer_signalling_20261108/scripts/score_held.py --salt <salt>`, run from the repository root.
- **The CPU slot.** `--slot` wraps the command in `scripts/with_cpu_slot.sh`: one of two shared slots, at nice 19 and
  idle I/O, waiting for a slot to free up.
- **The launcher.** `run_detached.sh` refuses to start while a job of the same name has no EXIT line. It writes
  cmd.txt, cwd.txt, stdout.log, stderr.log and run.status under `outputs/detached/t5_held_score/`.
- **Results** go to `results_held/` in the study folder: status.txt, tasks.jsonl and RESULT.json.
- **CPU cap.** The cap is 1,800 CPU-seconds of process time, checked after every task of the primary and of
  secondary 2. Exceeding it stops the run as a failure.
  - Expected use is about 8 CPU-minutes. Development took 1.7 to 2.6 CPU-seconds per DREAM task, and the dry run took
    7.0 CPU-seconds.
  - CPU time does not grow with machine load.
- **Refusals.** The script refuses to start if the salt is wrong, if any frozen file has changed, or if RESULT.json
  exists.

**Notes.** The first three fixes below belong in the re-freeze.
- **The refusal is too narrow.** The script refuses only when RESULT.json exists, so after a crash it would start
  again and append to tasks.jsonl. It should refuse whenever `results_held/` exists.
- **A secondary stop loses the primary.** RESULT.json is written only at the end, so a stop in secondary 1 or 2 loses
  the primary's statistics and, under stop rule 1, the whole run. The fix:
  - write the primary's statistics to disk before the secondaries run;
  - record a secondary failure without voiding a completed primary;
  - amend stop rule 1 to match.
- **Provenance.** Record in RESULT.json the numpy version, git HEAD, the FREEZE.json sha256 and the GO sha256.
- **Cap timing.** The cap is checked only between tasks, not inside a task or during secondary 1. That is fine at
  these sizes.

### 7. Leakage paths: no leak found in the code; three design choices favour the grown arm

- **Code.** No held value reaches any fit (check 3).
  - Seeds come from the sha256 of labels.
  - The arms share the static fits and the folds, and the only arm-specific seed is the shuffle's.
  - Development and held labels cannot coincide.
- **Development choices.** The two changes, minimal repair and the bar of 0, were made on the toy data.
  config_dev.json, `grow.py` and `tasks.py` were last written at 05:53:18Z, before the first synthetic development
  outputs at 05:54Z. Every synthetic development result records the frozen configuration. This is consistent with the
  disclosure.
- **First design choice: the generator builds the setting the loop is made for.** The removed prior edge is one the
  truth uses, so the static space cannot represent the truth, and H2 is favoured by construction. RESULT.md should
  scope any positive claim to "reconstruction of one removed prior edge on the DREAM network and design".
- **Second design choice: only 6 prior edges can be removed.**
  - After CellNOpt preprocessing, only 7 of the 58 DREAM edges survive unchanged. Removing one of them, ikk to ikb,
    always fails the build and is skipped.
  - Every primary task therefore removes one of these edges: mek12 to erk12, mkk4 to p38, map3k1 to mkk4, mkk4 to
    jnk12, map3k1 to ikk, or map3k7 to mkk4.
  - Development saw all 6, and one edge carries most of the gain. Mek12 to erk12 appeared in 48 of the 160 tasks. It
    gave 43 of the 62 net held conditions of grown over shuffled, and 113 of the 134 of grown over static.
  - Erk12 is a readout, and mek12 is not downstream of it, so a piece can restore that edge exactly.
  - The held primary is therefore a fresh-sample replication on the same 6 cases. It guards against overfitting the
    development seeds, but not against success that is specific to one edge.
  - For secondary 2, 7 of the 9 surviving toy edges can be removed.
- **Third design choice: the primary was chosen after development.** The primary family was chosen after development
  showed it positive and the toy family null. The protocol shows both development tables, which is the honest course.
  RESULT.md should say that the primary replicates a development finding on new draws.

## Other fixes to make in the same re-freeze (not blocking)

1. Adopt the GO-file salt, including the check on FREEZE.json itself (see the salt recommendation).
2. Make the run refuse to start whenever `results_held/` exists, and write the primary's statistics before the
   secondaries run, with stop rule 1 amended to match (check 6).
3. Record provenance in RESULT.json, and compute the decision flags there: Holm-adjusted p at most 0.05, and wins
   greater than losses.
4. Pre-register two analyses:
   - a descriptive table per removed edge: tasks, and wins and losses for H1 and H2;
   - a sensitivity analysis of H1 and H2 without the mek12 to erk12 tasks, with no gate.
5. Correct stale text:
   - the ADAPTER_CARD.md status line ("Nothing has been frozen");
   - the `grow.py` docstring ("the space stays acyclic");
   - the shuffle description in PROTOCOL.md: state that the t1 and t0 columns are moved together, and that the
     readout and direction are kept.

## Labels RESULT.md must carry

- **Scope.** The primary is reconstruction of one removed prior edge, one of 6 possible edges, on the DREAM network
  and design. H2 is favoured by construction, and the primary replicates a development finding on new draws.
- **The shuffled control,** described as in check 3.
- **Secondary 1.** The McNemar test over the 25 conditions is the pre-registered test. The fold-level statistics are
  not pre-registered.
- **Secondary 3.** Python re-implementation, not checked against R, with no wall-clock stop.
- **CPU per arm.** Descriptive only.
- **PROGRESS.md.**
  - Its section "What a full custody test would need" describes a plan that PROTOCOL.md has replaced.
  - Its "155 wins and 21 losses" and "84 wins and 22 losses" count held conditions, not tasks.

## Before launch (coordinator)

1. FREEZE.json's sha256 equals the value in GO.
2. Neither `results_held/` nor `outputs/detached/t5_held_score/` exists.
3. Launch from the repository root with the exact command, then commit the results right after the run ends.
