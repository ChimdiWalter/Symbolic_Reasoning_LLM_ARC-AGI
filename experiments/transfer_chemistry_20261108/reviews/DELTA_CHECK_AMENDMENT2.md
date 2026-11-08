# Delta review: Amendment 2 of test T3, enzyme reaction rules from three examples

Study: `experiments/transfer_chemistry_20261108/`. Test T3 (chemistry) of the 8 November transfer tests. Study
author: Chimdi Walter Ndubuisi.

An independent reviewer wrote this delta review on 8 November 2026, about 07:23Z to 07:45Z. It covers only the
parts that Amendment 2 changed. Everything else stands as the pre-run review (`reviews/PRE_RUN_REVIEW.md`,
commit `f879320c`) found it. The review was read-only outside this file.

**Bytes reviewed**
- Amendment 2 freeze commit: `cdc493584b8a8eeffa2d150d33d765c87f00a2b5`;
- `FREEZE.json` sha256: `3935b00a67547cd877f5b7857a639236af2713d12a4598156a25d8fc2895e055`;
- `PROTOCOL.md` sha256: `51c0956c49712a6b3513f2a1edc7d20c1cb75cdf920c1166cd33199b5f349adc`;
- `t3chem/chem.py` sha256: `81a059177172d989958dfd56f3bae49d92f81256b4e46cd2a6091b882ad2da19`;
- `t3chem/run.py` sha256: `47862a65b2c6e4c0ccefcbd2d8130e74a605395cb6c81608bd651e035a661206`;
- `launch/run_score.sh` sha256: `46c620dd3db59b3d2cf904b5c24251c12d100c84e193fe830a75de94b1c0ef7d`;
- the original GO: commit `190756a6fab499af19b762c4d0cb6046abe49152`, sha256 (the salt)
  `8f91d8e54350686fc0ce3ce7da7cb7de5941c911597dc5a0b0955843de9089bf`.

**Verdict: PASS.**
- There is no blocking finding.
- The coordinator may write `runs/GO_AMENDMENT2` with this review's commit as `delta_review` (section 3).
- The notes in section 4 are for `RESULT.md` and the post-score audit.

**What this review did not do.**
- It did not read attempt 1's family records. It took their git blob ids and their line count only.
- From attempt 1's `run.status` it extracted only the salt and freeze-commit fields of the STARTED line. It also
  read the launcher's error trace.
- It scored nothing and computed no salted order.
- It read no `*_LOCAL.json` file and nothing under a folder named `private`, and it touched no other job and nothing
  in other projects' job folders.
- In the real folder it ran the amended runner once, with `--check-only` and without writing bytecode (`-B`). That
  run writes nothing. Everything else ran on scratch copies or read development items only.
- The one exception is a set of robustness counts over the scoring pool (note 3). They cover parsing and the
  failure-description step only, print counts only and apply no rule.
- The review's scripts used about 3 CPU-minutes at nice 19.

**Terms used below.**
- **Attempt 1** is the held run started at 07:11:22Z that stopped after 3 of 40 families.
- An **extraction** is one rule cut from one example reaction at one specificity level. The levels **L0 to L6** run
  from the changed atoms alone to a radius-2 neighbourhood with full atom features.
- The **salt** is the sha256 of the committed bytes of the original `runs/GO`. The **frozen extractor** is
  `extract_rule` at the Amendment 1 freeze `4eae13e5`. The **amended extractor** is the one at `cdc49358`.

## 1. Checks

### Check 1. The re-freeze and the diff: PASS

**The re-freeze.**
- `FREEZE.json` is byte-identical in the working tree, at `cdc49358` and at HEAD; its sha256 is `3935b00a...`.
- The last commit on HEAD that changed it is `cdc49358`. The file has changed three times: at `70d6a9a6`,
  `4eae13e5` and `cdc49358`.
- All 18 file hashes were recomputed. Every working copy matches. The 13 tracked files also match their blobs at
  `cdc49358`, and the 5 untracked data files match on disk.
- The code, configuration and manifest digests match, and `protocol_sha256` equals the `PROTOCOL.md` entry.

**Only the intended changes** (`git diff -M 4eae13e5 cdc49358`, 20 paths in the study folder).
- **Frozen files changed:**
  - `t3chem/chem.py`: the fix, 15 added lines and nothing removed;
  - `t3chem/run.py`: the authorization checks;
  - `t3chem/freeze.py`: its docstring and the `salt_rule` text;
  - `launch/run_score.sh`: the detached name and comments;
  - `PROTOCOL.md`: Amendment 2;
  - `FREEZE.json`.
- **Frozen files unchanged:** `arms.py`, `library.py`, `stats.py`, `build_items.py`, `__init__.py`, the
  configuration, `DATA_MANIFEST.md`, the item pool, the item cache and the raw data.
- **Unfrozen files changed:** `ADAPTER_CARD.md` (the L0 wording only), `PROGRESS.md`, `RESULT.md`, the development
  check and its output, the pre-run review, `runs/GO` and `runs/score_attempt1/`.
- **In `run.py`, outside the checks,** only status and summary fields change. `select()`, `load_families()`, the arm
  loop, the 30 CPU-minute cap and the statistics are untouched.

**The fix cannot change a rule that already worked.**
- **By construction:**
  - The fix clears chiral tags, bond directions and bond stereo, then runs the frozen body unchanged (now named
    `_extract`).
  - That body reads only element, aromaticity, charge, hydrogen count, degree, ring membership, bond type and map
    numbers. None of these depends on the cleared flags.
  - It writes the rule from explicit atom and bond symbols, with stereochemistry output off.
  - The new `try` turns into "no rule" only an exception, which ended the frozen run.
- **Checked by this review on every development item:**
  - 5,178 items, 4,075 of them with stereo marks, and 36,246 extractions in all.
  - The full rule dictionaries are identical in all 36,160 extractions where the frozen extractor works, 28,439 of
    them on items with stereo marks. None differs.
  - The frozen extractor raised on 86 extractions, and the amended one returns a rule on all 86. The amended
    extractor never raised.
- **The owner's evidence:**
  - `dev/amendment2_check.py` reads development items only and compares with `chem.py` taken from `4eae13e5`.
  - Its output matches the protocol: 1,500 items and 10,500 extractions, of which 10,473 are identical and 27 failed
    and now give rules.
  - In the synthetic test, 100 of 635 fragments fail before clearing and 0 after.
  - It is a subset of the check above and agrees with it.

### Check 2. Attempt 1 did not inform the amendment: PASS

**Commit order and times** (UTC; each commit is an ancestor of the next, and all are ancestors of HEAD):
- the GO `190756a6` at 07:11:14Z, then the launch at 07:11:22Z and exit code 1 at 07:11:55Z;
- the records commit `2d9803ef` at 07:13:04Z, which touches only `runs/score/families.jsonl` and
  `runs/score/run.status`;
- the RESULT.md commit `37ebdf9f`, with the proposed amendment, at 07:16:19Z;
- the fix files, written from 07:18:01Z to 07:20:39Z;
- the freeze `cdc49358` at 07:22:05Z.

**The records are unchanged.**
- `families.jsonl` has the same blob, `39abaedc...`, at `2d9803ef`, at `cdc49358` (a pure rename to
  `runs/score_attempt1/`) and in the working tree. `run.status` likewise keeps blob `b406aa82...`.
- `families.jsonl` has 3 lines, one record per family.
- The launcher's records in `runs/score_attempt1/launcher/` are byte-identical to
  `outputs/detached/transfer_chemistry_held/`.

**The access evidence.**
- The file system (NFS, `relatime`) records one read of `families.jsonl` after it was written, at 07:12:01Z, 7
  seconds after the crash. `relatime` records only the first read after a write, so later reads leave no trace,
  and no read shows what was displayed. That read fits the disclosed line count.
- `RESULT.md` discloses one use by a program: checking that the 3 recorded families are the first 3 of the salted
  order, "made without reading any held outcome". That reads family keys, which the committed GO fixes anyway.
- After 07:11Z the only files that changed in the study are the records and the amendment files. There is no new
  log, no detached job other than `transfer_chemistry_held`, and no running T3 process.
- The diagnosis needs only the launcher's error trace. It names the shuffled arm's calls (`grow`, `build`, the
  partner's `rule`, `extract_rule`), RDKit's `MolFragmentToSmiles` and the failed precondition in `Canon.cpp`
  line 364. It contains no molecule and no outcome.

**Why the records could not have shaped the fix.**
- Every extraction in attempt 1's 3 completed families succeeded, because any failure ended the run. The amended
  extractor returns the identical rule wherever the frozen one succeeds (check 1), so the rerun recomputes those 3
  families exactly.
- The fix acts only where the frozen code raised, and that happened only after the recorded families.
- The held set is fixed by the committed GO.
- So the 15 recorded outcomes hold no information about how the fix changes any rerun outcome. Keeping the same held
  set is the option with no free choice in it.

### Check 3. The same salt and held set: PASS

**The original GO.**
- One commit, `190756a6`, touches `runs/GO`, and it touches nothing else. The file is unchanged since.
- Its bytes match the exact pattern of the pre-run review, section 3.

**The salt.**
- The salt, sha256(`runs/GO`) = `8f91d8e5...`, equals the salt in the STARTED line of attempt 1's `run.status`, and
  the value in `PROTOCOL.md`, `PROGRESS.md` and `RESULT.md`.
- The amended runner takes the salt only from `runs/GO` (the value returned by `checks()`).
- `runs/GO_AMENDMENT2` has no nonce and does not enter the salt.

**The selection inputs are unchanged.**
- The code of `select()` and `load_families()` is untouched.
- The configuration is untouched: 40 families, k = 3, 5 held targets, at least 8 items per family.
- The item cache and pool hashes are the same.

So the rerun uses the same 40 families, examples, held targets and shuffle partners as attempt 1. Nothing is
redrawn.

### Check 4. The runner's GO_AMENDMENT2 checks: PASS

**Reading the code.** `checks()` refuses unless all of the following hold, in this order:
- `runs/score/` does not exist;
- the original GO is valid: ASCII, first line `GO`, all fields, this study, `written_utc` form, equal to its blob at
  HEAD, one commit, committed alone, nonce, a review commit, and a freeze commit that holds the `FREEZE.json` the GO
  names;
- `runs/GO_AMENDMENT2` passes the same file checks;
- its `original_go_commit` is the GO's commit;
- its `freeze_json_sha256` matches `FREEZE.json`;
- its `freeze_commit` is the last commit on HEAD that changed `FREEZE.json` and holds the same bytes;
- `delta_review` is a commit;
- the chain runs in order: first freeze, pre-run review, GO, new freeze, delta review, GO_AMENDMENT2;
- every frozen hash matches;
- the Python and RDKit versions match.

Development options are refused in score mode before these checks. `--check-only` writes nothing. A refusal in a
real launch goes to `runs/refusals.log`.

**In the real folder.** The amended runner with `--check-only` refused at "no runs/GO_AMENDMENT2". So every
earlier check passes on the real repository, including that the original GO was committed alone. The run wrote
nothing.

**Scratch tests.**
- **The scratch repository, in this order:**
  - the first freeze (the tree of `4eae13e5`) and a placeholder review;
  - a GO committed alone;
  - placeholder attempt-1 records (the real records were never copied);
  - the Amendment 2 freeze (the files of `cdc49358`);
  - a placeholder delta review;
  - `runs/GO_AMENDMENT2` committed alone.
- **The cases:** 33, all behaving as intended: 3 accepted, 28 refused under `--check-only`, and 2 refused real
  launches. They include the owner's 15.
- **Accepted:**
  - the full chain (the printed salt equals the sha256 of the GO);
  - later unrelated commits;
  - `delta_review` naming the new freeze commit itself (a gap, below).
- **Refused, each with the intended message:**
  - no GO_AMENDMENT2; GO_AMENDMENT2 written but uncommitted, not committed alone, changed after its first commit,
    or edited in the working tree;
  - another original GO commit; a wrong `FREEZE.json` sha256; a stale or abbreviated freeze commit;
  - a delta review before the new freeze, on a side branch, or not a commit;
  - another study; a wrong first line; a missing or malformed `written_utc`; a non-ASCII byte;
  - `runs/GO` edited, or changed by a second commit;
  - `runs/score/` present, with a file or empty;
  - the development options `--tie-break` and `--slice`;
  - a changed `chem.py`; `FREEZE.json` edited, or changed and committed; a changed launcher;
  - a new freeze committed before the GO.
- **What the runs wrote:**
  - no `--check-only` case wrote any file;
  - both real-launch refusals (no GO_AMENDMENT2; `--nn-level`) wrote one line to `runs/refusals.log`;
  - none created `runs/score/`.

**Gaps (non-blocking).**
- The order test uses `git merge-base --is-ancestor`, which accepts equal commits, and nothing checks that
  `delta_review` adds this file. So the new freeze commit, or any commit between it and GO_AMENDMENT2, would pass as
  `delta_review`.
- The GO's freeze commit no longer has to be the last change of `FREEZE.json` before the GO. For the committed GO
  it was: `4eae13e5`, whose next change is `cdc49358`, after the GO.

### Check 5. The protocol discloses the amendment: PASS

**The Amendment 2 section states:**
- what happened: the GO commit, the launch and exit times, 3 of 40 families, the shuffled arm, and the RDKit error;
- the cause and the fix;
- the development evidence, whose numbers equal `dev/amendment2_check_development.json`;
- the same held set, with the salt value;
- that attempt 1 is kept unopened and disclosed in every report;
- the GO_AMENDMENT2 format, the runner rules, the launcher name and the list of unchanged parts.

**The other sections.** Section 6 (integrity) and section 7 (custody: a delta review, GO_AMENDMENT2, one rerun with
the same salt) are updated.

**The no-rerun rule.** Section 6 allows a rerun only after a dated amendment written before any held outcome is
opened. Amendment 2 is that amendment.

## 2. Blocking findings

None.

## 3. The GO_AMENDMENT2 file

**The exact file.** Write `experiments/transfer_chemistry_20261108/runs/GO_AMENDMENT2` as these seven lines, in
this order:

```
GO_AMENDMENT2
study: transfer_chemistry_20261108
freeze_commit: cdc493584b8a8eeffa2d150d33d765c87f00a2b5
freeze_json_sha256: 3935b00a67547cd877f5b7857a639236af2713d12a4598156a25d8fc2895e055
delta_review: <40-character hash of the commit that adds this file>
original_go_commit: 190756a6fab499af19b762c4d0cb6046abe49152
written_utc: <YYYY-MM-DDTHH:MM:SSZ, the UTC time of writing>
```

**Its format:**
- plain ASCII, LF line endings, and a newline after the last line;
- `key: value` with one space after the colon;
- no blank line and no extra field.

**`delta_review`.** It is the hash printed by
`git log --diff-filter=A --format=%H -- experiments/transfer_chemistry_20261108/reviews/DELTA_CHECK_AMENDMENT2.md`.

**Writing it in one step.** Write and commit it alone in one command, so the 30-minute autosave cannot catch a
partial file. From the repository root:

```sh
P=experiments/transfer_chemistry_20261108/runs/GO_AMENDMENT2
REV=$(git log --diff-filter=A --format=%H -- experiments/transfer_chemistry_20261108/reviews/DELTA_CHECK_AMENDMENT2.md)
T=$(date -u +%Y-%m-%dT%H:%M:%SZ)
[ ! -e "$P" ] && [ ${#REV} -eq 40 ] && [ ${#T} -eq 20 ] &&
printf 'GO_AMENDMENT2\nstudy: transfer_chemistry_20261108\nfreeze_commit: cdc493584b8a8eeffa2d150d33d765c87f00a2b5\nfreeze_json_sha256: 3935b00a67547cd877f5b7857a639236af2713d12a4598156a25d8fc2895e055\ndelta_review: %s\noriginal_go_commit: 190756a6fab499af19b762c4d0cb6046abe49152\nwritten_utc: %s\n' "$REV" "$T" > "$P" &&
git add -- "$P" && git commit -q -m "T3 chemistry: GO_AMENDMENT2 for the held rerun" -- "$P"
```

**Then, before launching:**
- From the study folder, `python3 -I t3chem/run.py --mode score --check-only` must print
  `checks passed: salt 8f91d8e54350686fc0ce3ce7da7cb7de5941c911597dc5a0b0955843de9089bf freeze_commit
  cdc493584b8a8eeffa2d150d33d765c87f00a2b5 go_commit 190756a6fab499af19b762c4d0cb6046abe49152
  go_amendment2_commit <its commit>`.
- Any other salt means stop.
- Then launch once with `launch/run_score.sh`. Its detached name is `transfer_chemistry_held_a2`.

## 4. Notes for RESULT.md and the post-score audit (non-blocking)

1. **The word "unopened".** The final `RESULT.md` should say exactly what happened: no held outcome was opened;
   the file was read by a program for its line count and its family keys (the first read after writing is at
   07:12:01Z).
   - Its proposal paragraph describes GO_AMENDMENT2 as holding "a nonce and the sha256 of runs/GO". The adopted
     file has `original_go_commit` and no nonce, as `PROTOCOL.md` says, and the final text should follow
     `PROTOCOL.md`.
2. **A determinism check after the rerun.** Once the rerun's results are final, the audit may compare the rerun's
   first 3 family records with attempt 1's, ignoring `cpu_s`. Check 2 predicts that they are identical.
3. **Residual crash risk.**
   - Over all 14,391 scoring-pool items, the following raised nothing: parsing the four SMILES fields (the molecule
     strings), the failure-description step (`reaction_centre`, `describe_centre`), the substrate fingerprint and the product
     composition. These are the per-item calls that sit outside a `try` in the scored path. The check printed
     counts only.
   - The other RDKit calls in the scored path are already wrapped.
   - A crash inside RDKit itself (a segmentation fault) cannot be caught. Its risk is small but not zero, and a
     second stop would need Amendment 3.
4. **The audit should confirm the GO_AMENDMENT2 custody:**
   - `delta_review` equals this review's commit (see the gap in check 4);
   - its commit touches only `runs/GO_AMENDMENT2`;
   - the reflog shows no other commit of that file;
   - `summary.json` records the salt `8f91d8e5...`, the freeze `cdc49358`, the GO commit `190756a6` and the
     GO_AMENDMENT2 commit.
5. **A lesson that applies to the pre-run review too.** That review checked custody, splits, arms and refusal
   rules, but did not run every per-item code path over the whole development pool. This delta review ran the
   extractor over the whole development pool. Future pre-run reviews should do the same for every per-item library
   call.

## 5. Evidence log (commands; outputs summarised above)

- **The freeze:**
  - `sha256sum` of `FREEZE.json` in the working tree, at `cdc49358` and at HEAD;
  - `git log -- FREEZE.json`;
  - the hashing script over `files_sha256` against the working tree and the blobs at `cdc49358`;
  - `git diff -M --stat 4eae13e5 cdc49358`;
  - the full diffs of `chem.py`, `run.py`, `freeze.py`, `run_score.sh` and `PROTOCOL.md`.
- **Attempt 1 custody:**
  - `git rev-parse` of the record blobs at `2d9803ef` and `cdc49358`, and `git hash-object` of the working copies;
  - `wc -l`;
  - `stat` access, modify and change times;
  - `find -newermt 07:11Z`;
  - `ps`;
  - sha256 of the launcher records against `outputs/detached/transfer_chemistry_held/`;
  - `git merge-base --is-ancestor` along the chain.
- **The salt:** `sha256sum runs/GO`; the salt field of attempt 1's STARTED line; `git log -- runs/GO` and its
  files.
- **The extractor:** a script that loads `chem.py` from `4eae13e5` and from `cdc49358` and compares full rule
  dictionaries on all 5,178 development items at the seven levels (105 CPU-seconds); then the robustness counts
  over the pool (24 CPU-seconds).
- **The runner:**
  - one `--check-only -B` run in the real folder;
  - a scratch git repository with the 33 cases of check 4, using the launcher's interpreter.
