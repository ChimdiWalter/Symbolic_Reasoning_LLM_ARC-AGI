# Pre-run review: test T2, spreadsheet string transformations

Study: `experiments/transfer_spreadsheet_20261108/`. Study author: Chimdi Walter Ndubuisi. Review written on
8 Nov 2026, about 06:10Z to 06:30Z, by an independent pre-run reviewer. The review was read-only outside this file.

**Bytes reviewed**
- freeze commit (also the salt): `1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2`;
- `FREEZE.json` sha256: `d85d4b818e22941929b695aaa236b55a590476fb844c2362aad4405149fba522`;
- `PROTOCOL.md` sha256: `99964ac225c7c95e0c53d5503245df002e2d1a30cd8f67e2c7d778825c5b088d`.

**Verdict: PASS-WITH-NOTES.**
- There is no blocking finding.
- The held run may start once the coordinator writes the GO file exactly as section 3 gives it.
- The notes in section 4 are for `RESULT.md` and the post-score audit. None of them needs an amendment.

**What this review did not do.**
- It ran no held scoring and read no held example.
- The scripts below read `data/prepared/tasks.json` but printed only task names and aggregate counts.
- The only method run was the frozen code on the 30 development tasks at the primary budget. It ran in a scratch copy
  and took 15.7 CPU-seconds at nice 19.

Labels used here, as in the protocol:
- **B** is the base budget, in operation executions.
- **P1** is grown against the shuffled-failure control, both at B = 40,000.
- **P2** is grown against static, with static at 4 x 40,000 = 160,000.

## 1. Checks

### Check 1. The freeze binds everything: PASS

**Digests.**
- All 16 files listed in `FREEZE.json` were hashed again, and every working copy matches.
- 15 of the 16 also match their blobs in the freeze commit.
- The 16th, `data/prepared/tasks.json`, is not committed, by design (licence; `.gitignore`). It is bound three ways:
  - its digest is in `FREEZE.json`, in the committed `split/DEV_SPLIT.json` (`tasks_json_sha256`) and in
    `DATA_MANIFEST.md`;
  - the frozen `t2/prepare.py` was run, in a scratch folder, on the source files extracted from the pinned archive. It
    rebuilt `tasks.json` (`f6e68abb`) and `DEV_SPLIT.json` (`740bb734`) byte for byte;
  - the 210 source files match `data/SOURCE_FILES_SHA256.json` and the archive's members. The archive's sha256
    matches, and the commit id embedded in it is `13c8deb68a873635879c9a69bc78caebd340f646`.
- `FREEZE.json` and `PROTOCOL.md` have the stated digests, both in the working tree and in the freeze commit.

**History.**
- The freeze commit is the only commit that adds `FREEZE.json`.
- It touches 23 files, all inside the study folder.
- Its date, 06:08:48Z, is 11 seconds after `frozen_utc` (06:08:37Z).
- No later commit touches the study folder.
- Before this review was added, the study folder had no uncommitted change. Only the ignored `data/raw/` and
  `data/prepared/` were outside version control.

**Run-time check.** The frozen list in `t2/run.py` (`FROZEN`) is the same as the 16 keys of `FREEZE.json`. The runner's
`check_go` checks every one of them again before the run.

**Frozen code against the development record.** The frozen code was rerun at B = 40,000 on the 30 development tasks,
with development salt 1. For every task and every arm, it gave the same program and the same outcome as `dev/dev_run1`
and `dev/dev_curve_salt1/records_B40000.jsonl`:
- recoveries: static 12, grown 17, shuffled 9, classical 14, grown without leave-one-out 18;
- the same shuffled donors;
- P1 8 against 0, P2 5 against 0.

**Not frozen, and not needed for the results:**
- `scripts/run_detached.sh` and `scripts/with_cpu_slot.sh`. They only schedule the job, both were committed before the
  freeze commit, and both are unchanged;
- `ADAPTER_CARD.md` and `PROGRESS.md`, which are documentation (both committed in the freeze commit);
- the Python version (3.12.3 here), which `RESULT.md` should record.

### Check 2. The held tasks are disjoint from the development tasks: PASS

**The split** (`split/DEV_SPLIT.json`).
- There are 30 development tasks in 12 groups and 53 held tasks in 47 groups.
- No task name or group is shared.
- Every group is on the side its hash rule gives: development exactly when the hash fraction is below 0.30.

**Overlap, counts only.** No held example equals a development example, input and output together. No held task shares
even one exact input with a development task.

**Composition** (matches the protocol).
- Held: 27 tasks train on 3 examples and 26 on 2. 45 come from the forum folder and 8 from the 2018 folder (11440431,
  bikes, univ_1 to univ_6).
- Development: 25 tasks train on 3 examples and 5 on 2.

**No held output was read in development**, as far as the files show:
- the 14 record files under `dev/` hold only development task names;
- no held task name appears anywhere under `dev/`;
- neither `runs/` nor `outputs/detached/t2_held_score/` exists.

Beyond these files, the protocol's statement that no held example was printed cannot be checked.

**Related tasks by name.** Being disjoint by group does not make the tasks disjoint by function. From their names alone,
several held tasks look like relatives of development tasks, for example:
- get-first-name-from-name, get-last-name-from-name and get-middle-name-from-full-name, against firstname and lastname;
- get-first-word against get-last-word;
- create-email-address-from-name against create-email-address-with-name-and-domain.

The protocol's claim limit (section 1, "unseen tasks of the same benchmark") already covers this.

### Check 3. The arms differ only in the intended factor: PASS, with one wording note

**The same examples.**
- Every arm uses the same training examples and the same held checks, from `grow.split_examples(task, salt)`. They are
  computed once per task and are the same at every budget.
- The shuffled arm searches the receiving task's own training examples and is scored on that task's own held checks.

**The same meter.**
- Every search is `dsl.search`. It counts one execution per operation per training example, or one when every argument
  is constant, and it checks the budget before each execution.
- The maximum program size is 30 in every arm.
- The CPU caps scale with the budget: 20 CPU-seconds per search at B, and 80 at 4 x B.

**Matched spending.**
- Static and classical get 4 x B, the grown arm's maximum (B plus 3 retries of B).
- When the base search fits, static reuses that program. This equals a search at 4 x B, because the budget is only a
  cutoff on a deterministic enumeration.

**Work the meter does not count.**
- The failure description, the building of pieces and the leave-one-out rebuilding are not counted as executions. On
  the meter, this favours the grown and shuffled arms.
- The CPU-seconds secondary (protocol section 6.4) measures this work. In the development rerun the grown arm used 3.4
  CPU-seconds and static 4.9.

**The shuffled control.**
- What it shares with grown: the base search, the cap of 3 candidates, the retry budget and the acceptance procedure.
- It does not swap only the failure description. It reuses the donor's candidates, which were built from:
  - the donor's argument strings;
  - the donor's delimiter list: the fixed list plus the donor's own short constants.
- Its leave-one-out rebuilds the pieces from the donor's pairs, with that same list.
- Its number of retries follows the donor's number of candidates.

This is exactly what protocol section 4 says ("the candidates built from the failure description of the next failing
task"), so it is not a deviation. `RESULT.md` should call these "pieces built from another task's failure", not "the
failure description alone".

### Check 4. The primaries are pre-registered and sound: PASS

**Registered.** P1 and P2 are in protocol section 5. Both are computed from the B = 40,000 pass (`run.py`: `primary`).

**Tests.**
- `stats.mcnemar_exact` is the exact two-sided test: twice the binomial tail at the smaller discordant count, capped
  at 1.
- `stats.holm` is Holm's step-down method, with the running maximum.
- A primary succeeds when its Holm-adjusted p is below 0.05 and the grown arm has more of the discordant tasks than the
  other arm.
- Development values agree: 8 against 0 gives p = 0.0078 (Holm 0.0156), and 5 against 0 gives p = 0.0625.

**Chosen after development.** P1 and P2 were chosen after the development numbers were seen. The protocol says so in
sections 1 and 8.

**Faster search is pre-declared.**
- Section 6.1 defines the budget curve and the catch-up budget, and says: "If static catches up, the report says
  plainly that the gain at 40,000 is faster search."
- Section 7 ties a P2 success to that secondary.
- Section 8 records that static caught up in development at 2,560,000 executions.
- The code computes the catch-up budget over complete passes only.

**Power.** In development P2 sat near the threshold (5 against 0, p = 0.063, at salt 1). A P2 null is a live outcome,
and the interpretation rules cover it.

### Check 5. The secondaries are declared: PASS

All five are in protocol section 6. `run.py` computes them, or they come from its records:
- the budget curve and the catch-up budget (`curve`, `static_catches_up_at_base_budget`);
- the classical comparator (`grown_vs_classical` in every pass);
- the leave-one-out cost (`loo_cost`; its definitions match section 6.3);
- CPU-seconds per arm (`cpu_s`; the shuffled arm is also charged the donor's construction time);
- the split by training size (`by_k`), and the split by source from the records and the task names, as section 6.5
  says.

`RESULT.md` must compute three items from the records, exactly as defined:
- the list of tasks that may show new ability: tasks the grown arm recovers at 40,000 that static recovers at no budget
  up to 2,560,000 executions;
- the split by source;
- recoveries at about equal CPU. Section 6.4 does not define how the CPU is matched, so state the rule used and label
  the result descriptive.

### Check 6. The launcher: PASS

**`launch/run_held.sh`.**
- It refuses to start without `runs/GO_T2`, and refuses if `runs/held` exists.
- It then runs, from the project root, with `$S` the study folder:
  `sh scripts/run_detached.sh t2_held_score --slot python3 -I "$S/t2/run.py" "$S" held`.

**`scripts/run_detached.sh`.**
- It uses setsid and nohup, and writes `outputs/detached/t2_held_score/run.status`.
- `--slot` runs the job through `scripts/with_cpu_slot.sh`: one of two shared CPU slots, at nice 19, with idle I/O.

**`t2/run.py held`.** The launcher itself checks only that the GO file exists. The runner does the rest, in this order:
1. before it creates any output, it checks:
   - the GO's protocol and freeze digests;
   - that the salt is 40 hexadecimal characters naming a commit whose `FREEZE.json` has the GO's digest;
   - every frozen digest;
2. it refuses if `runs/held` exists, and creates that folder with `exist_ok=False`;
3. it writes the results into the study folder: `runs/held/run.status`, `records_B<budget>.jsonl` and `summary.json`.

**Tested on a scratch git copy** (no task run):
- the correct GO was accepted;
- the GO was refused for a wrong protocol digest, a wrong freeze digest, a missing salt, an upper-case salt and a
  changed frozen file;
- a salt that names no commit ends in an error before `runs/held` is created, so a mistyped GO does not use up the one
  run.

**Gap 1: any commit holding the same `FREEZE.json` is accepted as the salt, not only the first.**
- In the scratch copy, a later commit was accepted.
- This review's own commit will be such a commit.
- Section 3 handles this.

**Gap 2: the CPU cap is soft.**
- The 1,700 CPU-second check runs before each task, never inside one.
- It also does not run before the shuffled step at the end of each pass.
- Only the per-search caps limit an overrun.
- Expected use is far below the cap: about 500 CPU-seconds in all. The primary pass of the development rerun took 15.7
  CPU-seconds for 30 tasks.
- Any overrun must be reported.

### Check 7. The data licence: PASS

**No licence is stated.** `DATA_MANIFEST.md` records this.

**Used unchanged.** The 210 files equal the archive's members byte for byte, and `t2/prepare.py` only reads them.

**Not redistributed.**
- `data/raw/` and `data/prepared/` are ignored by git and have never been committed.
- The only tracked data file is `data/SOURCE_FILES_SHA256.json`, which holds digests.
- The committed development records hold task names, programs and counts. No output string of 6 or more characters from
  any development example appears in `dev/dev_run1/records.jsonl`.

**Constants in the records.** A program in the records can contain:
- short constants from the benchmark grammars;
- constants built from the training outputs.

Before any public release of `runs/held/`, repeat the check above on the held records.

## 2. Blocking findings

None.

## 3. Salt recommendation and the GO file

**Recommendation: keep the freeze commit hash, pinned to `1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2`. Do not switch
to the sha256 of a GO file.**

**Why.**
1. A GO-file digest is not harder to steer.
   - If the GO file holds only its fixed lines, its digest follows from the freeze, so the designer could predict it.
   - If it holds free text, the coordinator could steer it. The coordinator can also reach the held data, and chose the
     primaries after seeing the development numbers.
   - Switching moves the power to steer from one person to another. It does not remove it.
2. To steer either salt, someone would have to score the held tasks under many salts. That is itself the custody breach
   the study rules out. Given the custody the study already relies on, a salt only has to take away any choice over
   which examples train, and this salt does that.
3. The record shows no sign of grinding:
   - one commit adds `FREEZE.json`;
   - it came 11 seconds after `frozen_utc`;
   - its message is ordinary;
   - its value is now recorded independently, here and in the coordinator's brief.
4. Switching would need:
   - a code change, because `check_go` accepts only a 40-hexadecimal commit that holds `FREEZE.json`;
   - a dated amendment;
   - a new freeze;
   - a new review.

   It would also throw away the verified rerun and the held-path tests above.

**Required with it** (no file changes):
- **Before writing the GO**, check that this command prints only `1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2`:
  `git log --diff-filter=A --format=%H -- experiments/transfer_spreadsheet_20261108/FREEZE.json`.
  Do not use any later commit, such as this review's, even though the runner would accept it.
- **The GO file.** Write `runs/GO_T2` with exactly these three lines, with no spaces around `=`:
  ```
  protocol_sha256=99964ac225c7c95e0c53d5503245df002e2d1a30cd8f67e2c7d778825c5b088d
  freeze_sha256=d85d4b818e22941929b695aaa236b55a590476fb844c2362aad4405149fba522
  salt=1d8e4f4aa70cf17cc1dd6aa6b76049b3e8779ef2
  ```
- **After the run**, the post-score audit checks that `runs/held/summary.json` names this salt.

**For future studies:**
- take the salt from something no one can steer that appears only after the GO, for example the freeze commit hash
  combined with a public randomness beacon value at a time declared in advance;
- make the runner enforce "the first commit that contains `FREEZE.json`".

## 4. Notes for RESULT.md and the post-score audit (non-blocking)

1. **One held check.**
   - 40 of the 53 held tasks have exactly one held check: all 26 that train on 2 examples, and 14 of the 27 that train
     on 3.
   - For most tasks, "recovered" therefore rests on a single unseen example.
   - Report this distribution with the results.
2. **Number of pieces.**
   - Protocol section 3 and `ADAPTER_CARD.md` give 5,645 to 6,794 pieces per task. That is the development range.
   - Under the frozen rule, a task's constants of 1 to 4 characters join its delimiter list. As a result, 7 held tasks
     have more pieces, up to 37,936.
   - This changes no rule. Report the held range. The main effect is to dilute the classical comparator's search on
     those tasks.
3. **Searches stopped by the CPU cap.**
   - `summary.json` counts these only for the base, static and classical searches.
   - Retry searches record theirs in each candidate row (`stop`).
   - Count both, as protocol section 3 promises.
4. **An incomplete primary pass.**
   - The protocol does not say how to decide the primaries if the B = 40,000 pass stops early.
   - This is very unlikely: the pass needs about 40 of the 1,700 CPU-seconds.
   - If it happens, report the numbers on the tasks that ran and claim no success.
5. **What P1 can show.**
   - In development at B = 40,000, the shuffled arm recovered 9 of 30 tasks: 7 through the shared base search and 2
     through donor pieces. The grown arm recovered 10 through construction.
   - A P1 success shows that the pieces must come from the task's own failure, not from another task's.
   - It does not compare selection driven by the failure with selection that ignores the task. The classical comparator
     is the reference for that.
6. **Evidence that there was one run.**
   - git ignores `outputs/`, and a relaunch overwrites `outputs/detached/t2_held_score/run.status`.
   - Commit `runs/GO_T2` and `runs/held/` as soon as the run ends, and record the Python version.

## 5. Evidence log (commands; their outputs are summarised above)

- **Digests:** sha256 of each `FREEZE.json` entry, both in the working tree and through `git show 1d8e4f4:<path>`.
- **History**, all limited to the study folder or to one commit:
  - `git log --diff-filter=A` on `FREEZE.json`;
  - `git log` and `git status --porcelain --ignored` on the study folder;
  - `git show --name-only` on the freeze commit.
- **Data:**
  - the archive's sha256 and its pax header;
  - the 210 file digests against the manifest and against the archive's members;
  - `tasks.json` and `DEV_SPLIT.json` rebuilt with the frozen `prepare.py` in a scratch copy.
- **Split and leakage:**
  - the names, groups and hash rule;
  - counts of shared examples and shared inputs;
  - the task names in `dev/`.
- **Code:**
  - read `t2/*.py`, `launch/run_held.sh`, `scripts/run_detached.sh` and `scripts/with_cpu_slot.sh`;
  - exercised the GO checks on a scratch git copy;
  - reran the frozen code on the 30 development tasks at B = 40,000.
