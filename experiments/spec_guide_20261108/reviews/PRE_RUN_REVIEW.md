# Specification-reading guide test: pre-run review

Independent pre-run review, 8 Nov 2026, about 07:40Z to 08:05Z, of `experiments/spec_guide_20261108/` at freeze
commit 4ba64f0cc78d1709e9592d019d55a6fae0acc16d (FREEZE.json sha256
f397e0bbbf48c0583978a72c75c56313b85b83bebcd1824c36a34fb5358b47de, 114 files).

**Verdict: PASS-WITH-NOTES.** There is no blocker. The freeze, the held isolation, the arms, the decision rule, the gate
and the compute plan hold. Six conditions (section 3) bind the GO, the run and the report. None needs a refreeze. Two
of them correct the frozen text without changing it:
- one development number pair in PROTOCOL.md section 1 is reversed;
- the oracle named in the claim is computed nowhere in the frozen code.

I ran no held generation and no scoring. I wrote nothing outside this file and a scratch area. I did not touch CORA
Step B or /tmp/reserved, and I opened no `*_LOCAL.json` file and no folder named private.

## 1. Checks and evidence

### 1.1 The freeze

- **Freeze commit.** `git log -n 1 HEAD -- FREEZE.json` gives 4ba64f0c, rechecked at 07:54Z with HEAD at 9342688c.
  - The commit before it that changed FREEZE.json was 2dfd2015, an autosave at 07:25Z holding the earlier freeze
    6d247728.
  - No commit after 4ba64f0c touches the study folder.
- **FREEZE.json.** It hashes to f397e0bb in both the working tree and at 4ba64f0c.
- **The 114 hashes, recomputed.**
  - All 114 match in the working tree.
  - The 107 files tracked at 4ba64f0c match their blobs.
  - The 7 untracked files match in the tree: the public training challenges (779eaba8), the arc-dsl files and the a2
    corpus.
  - `protocol_sha256` and `design_note_sha256` equal their file entries.
- **The frozen weights.**
  - `models/spec_guide.pt` (2b52b7b1) is byte-identical to `dev/v2/model.pt`, the v2 run (block head, success labels,
    `dev/v2/cfg.json`).
  - `models/block_models.json` has the same content as `dev/block_models.040240ab55c2.json`, differing only in key
    order. That file holds success labels on 281,529 block rows from the four traced training files and the natural
    training units.
- **The smoke-test package.** The smoke test and the refusal check ran on `runs/kaggle/package_candidate.tar.gz`
  (47a885ea). Its 63 members are the 62 frozen files the package carries, each with its frozen hash, plus FREEZE.json
  f397e0bb.
- **The environment.** The venv runs Python 3.12.3, numpy 2.4.3 and torch 2.11.0+cu128, as recorded in the freeze.
- **Nothing held exists.**
  - `runs/` holds only `kaggle/` and `kaggle_dev/`. There is no GO, `held/`, SEALED_PREDICTIONS, SCORED or rehearsal
    output.
  - `git log --all` on those paths is empty.
  - There is no `outputs/detached/sg_held` or `sg_score`.
  - The real gate (`run.py gate check`) refuses with "no runs/GO".

### 1.2 Held isolation

- **The partition rules came first.**
  - DESIGN_NOTE.md was first committed in f042260f at 05:04:01Z on 8 Nov.
  - Its only later change, 39aefebb 11 seconds after, corrects the stated writing time from 05:20Z to 05:04Z.
  - The first development data came later: Kaggle outputs from 05:16Z, and the code commit 1ce4c152 at 05:19Z.
- **The code implements those rules.**
  - The family rule (sha256 of "spec-family:" + family; 0 to 5 training, 6 and 7 validation, 8 and 9 held) and the
    pool rule (sha256 of "spec-pool:" + id, mod 2) are `sgd/gen.py` `family_partition` and `pool_of`.
  - The natural split is `sgd/data.py` `natural_split`.
- **The generator's refusals.**
  - `pools("held")` raises unless `allow_held=True`.
  - `make_task(partition="held")` raises unless the generator carries `held_ok`, which only `held.gen` sets, and only
    outside rehearsal.
  - `write_cheap` and `write_traced` always use the development pool.
  - The only caller that opens the held pool is `held.gen`, after `require_go`.
- **Every development record, re-derived.** I checked all 127,994 generated development tasks: 104,000 cheap training,
  12,000 cheap validation, 2,104 traced validation and 9,890 traced training. For each one:
  - the family recomputed from the stored operation equals the stored family;
  - the family's partition is the file's: 113,890 training, 14,104 validation, 0 held;
  - the source task is in the development pool (all 127,994);
  - no grid occurs only in the held pool.
  The counts match PROGRESS.md: 4,800 traced training tasks admitted, 7,389 with a trace, and 1,000 validation tasks
  admitted.
- **The natural units** are the guided-construction study's 425 source units (74 ConceptARC, 68 Mini-ARC, 283 1D-ARC,
  `dev/pass1/units.*.jsonl`), from the source halves only.
- **The salt.**
  - `held.run_all` takes the salt from `git_checks`: the sha256 of the GO bytes, once the GO is shown to be committed
    at HEAD and unchanged.
  - `gen` seeds with int(salt[:16], 16) x 1000 + 0, through `require_go` on the same file.
  - `run.status` records the salt and the freeze commit. In my scratch run (case "valid GO", section 1.5) the
    recorded salt equals the sha256 of the committed GO bytes.

### 1.3 The arms

- **The same step and the same budgets.**
  - `held.run` builds one HoleState per task. For each arm it calls `engine.run_hole(hs, order, B)` at each B in the
    CONFIG budgets 125, 500 and 2,000.
  - `run_hole` resets the operation counter.
  - The orders come from `policy.hand` or `policy.by_scores`. Both return a permutation of the same blocks, with ties
    in hand-set order.
  - No result carries between arms. The shared segmentation memo changes segment counts and CPU only (note 2).
- **The same data.**
  - The frequency table, the linear model and the small guide were fitted on the block rows of the four traced
    training files plus the natural training units (`devsim.block_models`).
  - The guide's block head was trained on the same rows: `train.py` sets `keyed = traced + nat_tr`, with the same
    files listed in `dev/v2/cfg.json`.
  - The guide's encoder was also pre-trained on the 104,000 cheap training-family tasks, as the protocol states.
- **The shuffled control.** `held.run` scores the task's own blocks and features with the specification of task
  (i + n // 2) mod n, in task-id order, as `CONFIG.shuffle_rule` says.
- **The oracle.**
  - It is not computed at run time, which is correct. It is not computed at scoring either: no frozen module computes
    an oracle on held tasks, and the held files do not keep the admission trace that one would need.
  - The only oracle figure is development's. I reproduced it from the frozen traced validation file. The order puts
    first the blocks whose candidates include the true output, cheapest first, then follows the hand-set order. It
    scores 999 of 1,000 at 125 and 1,000 at 500.
  - The same simulation gives the hand-set order 854, 877, 910 and 965 at 32, 125, 500 and 2,000, matching
    PROGRESS.md.
  - Condition 4 covers the report.

### 1.4 The primary and the decision rule

- **The primary.** In `score.py`, at 125 operations the guide is compared with each of the hand-set order, the
  frequency table and the linear model through `ngrow.analysis.compare`.
  - `beats_all_three` requires the decision "spec_guide@125 beats X@125" for all three.
  - `compare` gives that decision only when two things hold: the exact two-sided sign test on discordant tasks has
    p < 0.05, and the lower end of the 95% percentile interval of the total difference is above 0.
  - The interval uses 10,000 draws with `random.Random(20261105)`, clustered by the generating edit type, in one
    stratum.
  - 500 operations is computed and reported with the same three comparisons. It is not part of the decision.
- **The secondaries, Holm over their three sign-test p-values.**
  1. The guide against the small guide.
  2. The guide against the shuffled control.
  3. The probe: 5-fold softmax regression of the edit type on the encoder's summary. It compares the trained encoder
     with the same architecture at random weights (`torch.manual_seed(1)`).
  The small guide's expected tie is stated in section 1 of the protocol, and as prediction "spec-2" in section 4.
- **The records behind the protocol's development numbers.** They match `dev/v2/devsim.json` and
  `dev/v3/devsim.json`.
  - v2 at 125: hand-set 877, frequency 879, linear 950, small guide 980, guide 985, shuffled control 943.
  - v2 guide against the small guide: 9 gained, 4 lost (p 0.27). Against the linear model: 37 and 2. Against the
    shuffled control: 45 and 3.
  - v3 guide against the small guide: 3 gained, 7 lost.
- **The capped validation view** that the protocol cites is not stored as a record. I rebuilt it from the first 60
  tasks per edit type in file order, 586 tasks. At 125:
  - the guide beats the hand-set order (81 against 2, interval 38 to 127);
  - it beats the frequency table (81 against 0, interval 25 to 154);
  - it beats the linear model (28 against 0, interval 5 to 58);
  - against the small guide it is 8 against 3 (p 0.23).
  These are the same conclusions as the full set.

### 1.5 The gate

- **The code.**
  - `read_go` checks four things: the first line is GO; `freeze_json_sha256` equals the current FREEZE.json; the nonce
    is 64 lowercase hex; the freeze commit has 40 characters.
  - `check_freeze` checks every frozen hash.
  - `git_checks` checks three things: the GO bytes equal HEAD's blob; exactly one commit touches the GO; its freeze
    commit is the last commit on HEAD that changed FREEZE.json, and FREEZE.json there equals the file.
  - `held all` runs `git_checks`, `check_freeze` and the held-output check before anything else.
  - `score` runs `require_go` and `git_checks`, then compares the seal, then takes the exclusive marker. Only then does
    it open the solutions.
- **The developer's checks never exercised the git checks.** `checks/GATE_REFUSAL.json` (6 of 6 refused) and
  `checks/SMOKE_TEST.json` (rehearsal pass, 67 tasks, second scoring refused) ran without git.
- **My rerun.** I built a scratch git repository from the frozen package and ran it in held mode. A harness turned any
  call to the pool reader, the task generator, the tracer or a solutions-file open into an error. I ran 26 cases.
  Every case with an expected outcome gave it, and three cases produced the findings listed last.
  - **Refused:**
    - no GO (`gate check` and `held all`);
    - a GO written but not committed;
    - a GO changed after its commit, both uncommitted and recommitted (`held all` and `score`);
    - a stale freeze: the GO names an earlier commit, and FREEZE.json was later changed and restored (`held all` and
      `score`);
    - FREEZE.json changed after the GO;
    - a frozen file changed, both uncommitted and committed;
    - an existing tasks, solutions or predictions file (`held all`);
    - an uppercase nonce;
    - scoring without a seal, with a wrong seal, after the marker, and with a changed GO.
  - **Passed:**
    - A valid GO committed alone. `gate check` prints the salt (the GO's sha256) and the freeze commit. `held all`
      then writes STARTED with that salt and stops at the blocked pool reader, so the pool opens only after every
      check.
    - A GO naming the last freeze commit after a change and a restore.
    - A valid scoring: the marker is taken, then the blocked solutions open is reached.
  - **Found:**
    - `held gen`, called directly with tasks present, loads the held pool before its own refusal. `held all` refuses
      first.
    - A GO committed together with another file passes. The code checks for one commit, not for a single-file commit.
    - A GO with CRLF line endings passes, with a different salt.

### 1.6 Framing

- **The label.** The protocol calls it a "learned, specification-reading guide: a step toward neural guidance for
  program synthesis, not 'the transformer for program synthesis'" (PROTOCOL.md section 1, and DESIGN_NOTE.md).
- **The precedents** are named in both files: DeepCoder; RobustFill; BUSTLE; CrossBeam and LambdaBeam; neural-guided
  deductive search.
- **The converged finding** is stated in section 1. It is backed by `dev/v2/augguide.json`, `dev/v3/augguide.json`
  and the v3 simulation (`dev/v3/devsim.json`).
  - One number pair is reversed. Section 1 says the same learner "with and without the specification summary scored
    985 and 979". The record gives 979 with the summary and 985 without: 5 gained, 11 lost, p 0.21.
  - With v3 labels the record gives 979 with and 981 without (4 gained, 6 lost).
  - PROGRESS.md at 07:20Z has the same reversed order.
  - The true direction is against the specification, which strengthens the finding. Condition 3 fixes the wording.
- **The ceiling effect** is supported by the records.
  - In the guided-construction held run (its `RESULTS.json` and post-score audit), the learned orders and the table
    scored 318 to 323 at 500. The step's reachable ceiling, the hand-set order at 20,000, was 329.
  - On this study's natural validation units, every learned order sits at 102 or 103, against a ceiling of 103 to 104
    (`dev/v2/devnat.json`).
  - On generated validation tasks at 125, the small guide scores 980 against the frequency table's 879.

### 1.7 Compute and detachment

- **The command.** PROTOCOL.md section 5 and `held.py` give `sh scripts/run_detached.sh sg_held --slot env
  PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= python3 -s -B
  experiments/spec_guide_20261108/run.py held all`.
  - `--slot` wraps it in `scripts/with_cpu_slot.sh`: one of the two shared slots, at nice 19 with idle I/O.
  - `setsid nohup` detaches it, and its outputs go to `outputs/detached/sg_held/`.
- **The generation cap.** Generation stops at CONFIG `gen_limit_s` 10,800 seconds (3 hours), or earlier once all 19
  edit kinds have 60 tasks. The arms phase has no limit; the smoke test ran 67 tasks in 56 seconds.
- **CPU only.**
  - `CUDA_VISIBLE_DEVICES` is empty.
  - The weights load with `map_location="cpu"`, and every tensor stays on the CPU.
  - The smoke test ran the same way.
- **The Kaggle path is unused.** The Kaggle builder and kernel (`sgd/kaggle_held.py`, `launch/held_kernel.py`, with 4
  workers and 9,000 seconds) are frozen but not used. The run on this machine uses CONFIG: 1 worker and 10,800
  seconds.

## 2. Blockers

None.

## 3. Conditions (binding; the GO's conditions line accepts them)

1. **The GO commit.**
   - Write `runs/GO` exactly as in section 5, and commit it in the same shell command, with git limited to its path.
   - Then check two things: the GO's only commit lists exactly `experiments/spec_guide_20261108/runs/GO`, and
     `run.py gate check` passes.
   - The reason: the autosave job (`scripts/autosave_watch.sh`, running every 30 minutes until 9 Nov) stages
     everything under `experiments/`. A GO left uncommitted could be committed by it together with other files, and
     the gate would not notice.
2. **Launch only `held all`.**
   - Launch only the section 6 command, from the repository root.
   - Do not call `held gen`, `held run` or `held seal` directly.
   - If the process dies after GENERATED, record the resume in PROGRESS.md before starting it: `held run 0/1`, then
     `held seal`, detached, in the same environment.
   - If it dies during generation, the run stops and an amendment is written, since generation cannot resume.
3. **An erratum to PROTOCOL.md section 1, with no refreeze.** The sentence should read: "the same learner scored 979
   with the specification summary and 985 without (5 gained, 11 lost; p = 0.21)". Every report uses these numbers.
4. **The oracle.**
   - The held analysis has no oracle.
   - The report may cite the development oracle: 999 of 1,000 at 125 and 1,000 at 500 on validation, defined as in
     section 1.3. It must say that the held run did not measure it.
   - Any held oracle computed after scoring is labelled post hoc and descriptive, and enters no decision.
   - "Close to the oracle" is not claimed from held data.
5. **The secondaries.**
   - A secondary is significant only when its Holm-adjusted p is below 0.05 and its interval excludes 0 in the same
     direction. Use the scorer's `holm_p` field, not its unadjusted `decision`.
   - Refer to the secondaries by name: `score.py` numbers the shuffled control 1 and the small guide 2, and the
     protocol numbers them the other way round.
6. **The scoring.**
   - Score once, detached, with the section 6 command.
   - Start only after `outputs/detached/sg_held/run.status` ends with EXIT 0 and `runs/held/run.status` ends with
     SEALED.
   - If the scorer fails after it takes `runs/SCORED`, do not remove the marker; write an amendment.

## 4. Notes (not binding; for the report and the audit)

1. **Unseen families, not unseen operations.** Held families are unseen combinations of edit type, parameters,
   predicate kind and view. Their edit types, views and block keys all occur in training. Write "unseen families",
   not "unseen operations".
2. **Per-arm CPU.**
   - It depends on run order: the hand-set arm runs first, on a cold segmentation memo.
   - It leaves out the guide's encoder passes, which are counted in the row's total `cpu_s`.
   - Counted operations are exact and comparable across arms.
3. **The wall-clock cap.** Generation is capped in wall-clock time. Under load the held set is smaller, and the rare
   edit types (connect, extend, scale, fill_holes, duplicate) may fall short of 60. This does not bias the paired
   comparisons. Report the per-edit counts from `GEN_RECORD.0.json`.
4. **Grids shared by both pools.**
   - Six input grids occur in both pools under different task ids: five are 3 x 3 or 1 x 5, and one is 10 x 10.
   - 1,475 development tasks used one of them.
   - The audit should count the held tasks that use one.
5. **What the audit should confirm.**
   - The GO commit holds only `runs/GO`.
   - The STARTED line in `run.status` carries freeze_commit 4ba64f0c and a salt equal to the GO's sha256.
   - `GEN_RECORD.0.json` has seed = int(salt[:16], 16) x 1000.
   - SEALED_PREDICTIONS predates SCORED.
   - `pre_run_review` names this review's commit.
6. **Threads.** torch may use several threads inside the slot, at nice 19. `OMP_NUM_THREADS=1` would change only
   float rounding, but it is not in the frozen command. Leave the command as it is.
7. **A wrong docstring.** The docstring of `launch/smoke_test.py` says that the refusal cases ran with an empty held
   pool path. The code does not do that; the gate's order is what protects the pool. This affects the text only.

## 5. The GO file I would accept

- **Path:** `experiments/spec_guide_20261108/runs/GO`.
- **Lines:** seven lines, in this order.
- **Encoding:** ASCII, that is, UTF-8 without a BOM.
- **Line endings:** every line, the last included, ends with a single LF and no CR.
- **Spacing:** no blank lines, and no leading or trailing spaces. Each field is "key: value", with one space after the
  colon.
- **Hex:** lower case.

```
GO
study: spec_guide_20261108
freeze_commit: 4ba64f0cc78d1709e9592d019d55a6fae0acc16d
freeze_json_sha256: f397e0bbbf48c0583978a72c75c56313b85b83bebcd1824c36a34fb5358b47de
pre_run_review: <the 40-hex commit that added this file>
conditions: reviews/PRE_RUN_REVIEW.md section 3, conditions 1 to 6, accepted
nonce: <64 lowercase hex, fresh>
```

The gate checks lines 1, 3, 4 and 7. Lines 2, 5 and 6 serve custody and the audit. The salt is the sha256 of these
exact bytes.

## 6. Commands (from the repository root)

```
cd /path/to/repository
S=experiments/spec_guide_20261108
R=<the 40-hex commit that added this file>
N=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
test ! -e "$S/runs/GO" && test ! -e .git/index.lock && printf 'GO\nstudy: spec_guide_20261108\nfreeze_commit: 4ba64f0cc78d1709e9592d019d55a6fae0acc16d\nfreeze_json_sha256: f397e0bbbf48c0583978a72c75c56313b85b83bebcd1824c36a34fb5358b47de\npre_run_review: %s\nconditions: reviews/PRE_RUN_REVIEW.md section 3, conditions 1 to 6, accepted\nnonce: %s\n' "$R" "$N" > "$S/runs/GO" && git add "$S/runs/GO" && git commit -q -m "GO for the specification-reading guide test after pre-run review PASS-WITH-NOTES" -- "$S/runs/GO"
C=$(git log --format=%H -- "$S/runs/GO"); git show --name-only --format= $C    # one commit; one path
PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= python3 -s -B $S/run.py gate check
sh scripts/run_detached.sh sg_held --slot env PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= python3 -s -B experiments/spec_guide_20261108/run.py held all
# after EXIT 0 in outputs/detached/sg_held/run.status and SEALED in runs/held/run.status:
sh scripts/run_detached.sh sg_score --slot env PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= python3 -s -B experiments/spec_guide_20261108/run.py score
```
