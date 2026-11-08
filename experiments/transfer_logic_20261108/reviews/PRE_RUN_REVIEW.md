# Pre-run review: logic recovery transfer study (transfer_logic_20261108)

- Study folder: `experiments/transfer_logic_20261108/`. The protocol calls the study T1.
- Freeze commit reviewed: `cb4369883501797581ff201a102923cefc2f43ef`.
- FREEZE.json sha256: `ecce4beb65be906935170b566aa01e62db78b46967a9ed7558c2895fb27cedd1`.
- Review type: the independent pre-run review required by PROTOCOL.md section 7, step 2. Date: 8 November 2026.

## Verdict: FAIL as frozen

The design itself passes:
- the freeze hashes all match;
- the split is disjoint by file;
- the arms differ only in the intended factor;
- the pre-registered statistics are sound;
- the caveats are declared;
- every development number reproduces from the committed development results.

Two custody defects block the scored run:
1. **The salt.** The frozen run does not bind the salt to the freeze commit: it accepts any commit object that has the frozen tree. The freeze commit was also chosen by the designer, who could have ground it.
2. **The launch line.** The frozen launch line fails before Python starts, and it bypasses the program's detached launcher.

Both have exact fixes below. Fix 1 needs a small amendment and a re-freeze, which costs nothing scientifically because no held item has been chosen. Fix 2 changes no frozen file. After the re-freeze, a delta check of the changed lines should be enough for PASS. A full re-review is not needed.

## Scope and method

**Read:**
- PROTOCOL.md, FREEZE.json, PROGRESS.md, DATA_MANIFEST.md, ADAPTER_CARD.md and config.json;
- all of `tlogic/`, score_held.py, make_freeze.py, the development scripts and the unit tests;
- the reused statistics module (`experiments/universality_boolean_bbm_20261103/u6/`, from the earlier CORA universality study, called U6 in the program);
- `scripts/run_detached.sh` and `scripts/with_cpu_slot.sh`;
- the licence files inside the data archives.

**Run:** everything ran from a scratch folder outside the repository, with `python -I -B` and a scratch bytecode cache:
- the hash recomputation;
- pool and split counts;
- structural overlap checks;
- a recomputation of the development statistics from `dev_results/`;
- the unit tests (all 5 pass);
- a demonstration of the salt check on a throwaway repository that holds a copy of the frozen files.

**Not done:**
- No salt was used, nothing was ranked, and no arm was run on any held-candidate item.
- The pool-level checks read the 489 held-candidate functions only to compare them with development functions.
- Nothing was written in the repository except this file.

## Checks

### 1. The freeze binds everything that matters: PASS

- **FREEZE.json.** Its sha256 is `ecce4beb...cedd1`, both in the working tree and at the freeze commit (`git show cb43...:experiments/transfer_logic_20261108/FREEZE.json`).
- **The listed files.** All 19 files listed in FREEZE.json were recomputed, and 19 of 19 match the working tree.
  - The 17 tracked files also match their blobs at the freeze commit. These include the two reused statistics files, `u6/__init__.py` and `u6/stats.py`.
  - The two data archives are gitignored by design, so they are not in the commit. Their hashes match FREEZE.json, DATA_MANIFEST.md and fetch_data.sh.
- **The commit.** The freeze commit is the only commit, on any branch, that touches the folder. It adds all 26 files.
  - `git diff cb43... -- .` is empty, and the only untracked paths are the ignored `data/` and bytecode caches.
  - The reflog for FREEZE.json has one ordinary commit entry and no amend.
- **Import closure.** The scored run imports score_held.py, then `tlogic/` (8 files), then `u6/stats.py` and `u6/__init__.py`. All are hashed. Only numpy and scikit-learn are external.
- **Environment.** FREEZE.json records Python 3.12.3, numpy 2.4.3 and scikit-learn 1.8.0, and the recorded interpreter has exactly these versions today. The run does not check them itself (note 3).
- **Not hashed, and not needed by the scored run:**
  - PROGRESS.md and `dev_results/*.jsonl`, both inside the freeze commit's tree;
  - make_freeze.py, run_dev.py, run_dev_budget.py, dev_summary.py and .gitignore;
  - the two launch scripts.
- **Bytecode caches.** The cached bytecode in `tlogic/__pycache__` matches the current source modification time and size for every module, so a stale cache cannot run in place of the hashed source.

### 2. No held item was seen during development

#### 2a. The split is disjoint by file, not only by output: PASS

**Pool, recomputed with the frozen code:**
- 573 eligible items in 44 files.
- Exclusions: 91 outputs with don't-cares, 45 repeated functions, 14 constant outputs, and 70 files outside 6 to 12 inputs.
- Two identical files were excluded: b7, a copy of b11, and ex7, a copy of b9.

**Split:**
- Development: 9 files with 84 items (alu1, br2, dc2, inc, m2, m4, max128, newapla2, newill).
- Held candidates: 35 files with 489 items.
- Summing min(8, items) over the held-candidate files gives 217, as stated.

**Disjoint by file:**
- The rule is a function of the file name, and the two file sets do not intersect.
- No held-candidate file is byte-identical to a development file.

**Disjoint by function:**
- 0 functions are shared, because repeats are removed globally.
- One held-candidate output, `f51m/7`, is the complement of the development output `dc2/6`. It depends on a single input, a lone literal that every arm recovers, so it cannot affect a comparison.

**Family resemblance (not leakage):**
- Name families straddle the split: br1 against br2; m1 and m3 against m2 and m4; max46, max512 and max1024 against max128; newapla and newapla1 against newapla2.
- 53 held-candidate outputs share a coarse signature with 13 development outputs (br2/2, dc2/6, m2/8, m2/9, m4/0, m4/8, and newapla2/0 to newapla2/6).
  - The signature is unchanged by permuting or negating inputs or negating the output, so a match is necessary for equivalence but does not prove it.
  - The 53 come from ex5 (28), b11 (9), pope.rom (6), luc (3), exps (2), and one each from br1, f51m, m1, m3 and risc.
  - The circuit arms were fixed before the first development run (timeline below), so this resemblance cannot carry tuning. It can only make some held items correlated with development items.
- No alu file is held: alu2 and alu3 are excluded for don't-cares. So the file that gave 8 of grown's 12 development recoveries has no relative in the held pool.

**Development touched only development items:**
- Every row of the development results is a development item: `dev1.jsonl` (84 circuits and 48 policies), `dev_c_0.125.jsonl` (84), `dev_c_0.5.jsonl` (84) and `dev2_policy.jsonl` (48).
- Every probe count matches the stated fraction. For example, 1,024 of 4,096 at 25%.
- There is no `results/` folder and no GO file.
- The companion cofactor engine's folder and the other experiments in this repository contain no reference to the Espresso, MCNC or ClassBench data.

**Timeline, from the bytecode cache headers:**
- The circuit code (core.py, arms.py, classical.py, pla.py and data.py) last changed between 05:42Z and 05:46Z. That is before the first development run, written at 05:47:47Z. This supports the claim that the circuit arms were set before the first development run.
- policy.py last changed at 05:59:49Z, before the version 2 policy run at 06:04:40Z.
- config.json was last written at 06:07:26Z, after all development runs. The version 2 rows contain the version 1 arms (`grown_arity`, `shuffled_arity`), which the frozen configuration drops. Arms are independent, with per-call seeds, so dropping them changes no other arm's output.

#### 2b. The salt is adequate: FAIL

**The frozen check does not bind the salt to the freeze commit.**
- `score_held.checks()` accepts any commit object whose tree holds the current FREEZE.json, provided its first parent does not hold an identical one.
- On a throwaway repository holding a copy of the frozen files, the frozen `checks()` accepted:
  - the freeze commit;
  - two parentless commits, made with `git commit-tree <freeze tree>`, that differ only in their messages.
- A commit without FREEZE.json was refused.
- So whoever launches can mint any number of valid salts without changing a file. This contradicts PROTOCOL.md section 7 ("the run refuses when the salt is not the freeze commit").

**Even when bound, the freeze commit hash is the designer's choice.**
- How much of the held set depends on the salt:
  - 17 of the 35 held-candidate files have more than 8 items, so 136 of the 217 held items are chosen by the salt, from 408 candidates;
  - the other 81 held items, from 18 files, are held whatever the salt.
- The designer holds all code and data. All 489 candidates can be evaluated offline in roughly a CPU-minute; development took about 3 CPU-seconds per 84 circuit items per fraction. After that, each candidate commit costs only a ranking, so grinding commit messages or timestamps is cheap.
- The record shows no sign of grinding: one ordinary commit, no amend in the reflog, and a commit time (06:08:32Z) that matches the decision time in PROGRESS.md. But the record cannot exclude it.

### 3. The arms differ only in the intended factor: PASS

**Same probes and budget for every arm.**
- `arms.run_item` draws one probe order and one budget B per item and gives the same probe sets to every arm, the references included.
- The verify folds use the same order and B for each arm.
- The allowances are counts, identical across arms: 4,096 nodes for the circuit loop and 512 rules for policies.
  - The node allowance can never bind at 6 to 12 inputs. A node with two free inputs always fits a gate, so a tree has at most 2,047 nodes.
  - No development fit was exhausted.
- Nothing inside the learners depends on wall-clock time, so load on the machine cannot change a result.
- All sets are sorted before use, the CART reference (scikit-learn's decision tree) has a fixed random_state and the bootstrap has a fixed seed, so the run is deterministic.

**Static against grown.** These differ only in growth. `core.grow` returns the fitted base block before any growth, and static stops when nothing fits.

**Grown against shuffled.** These differ only in which input is split (circuits) or which field is required (policies). The shuffled control maps the described one through a seeded permutation.

**Active probing.**
- The arm uses the same total B: B − 3c random probes plus three rounds of c.
- Its committee is the grown program plus three shuffled-route programs.

**"Grown contains static by construction" is disclosed** in PROTOCOL.md section 4.
- The unit test asserts it for circuits.
- In development, no item was recovered by static and missed by grown, in any condition (circuits at 12.5%, 25% and 50%; policies version 1 and version 2).
- Shuffled also contains static (again 0 such items). The protocol does not say so, and it matters for interpretation (check 4).

### 4. The primary is pre-registered and sound: PASS

**Pre-registration.** PROTOCOL.md section 5 sets out the following, and `score_held.analyse` implements it as written.
- Two comparisons in one Holm family: grown against static, and grown against shuffled, on held circuits at 25%.
- The exact McNemar test: a two-sided binomial test on the discordant items.
- The difference in exact-recovery rates, with a 95% percentile interval from a cluster bootstrap over PLA files: 10,000 resamples from `default_rng(0)`, using the reused statistics module.
- "Supported" requires all three: the Holm test rejects, the point difference is above 0, and the lower bound is above 0.
- The eight secondaries form a separate Holm family.

**Development numbers reproduce exactly from `dev_results/`.**

At 25%, exact recoveries out of 84:

| Static | Grown | Shuffled | Espresso-style | CART | Grown with active probing |
|---|---|---|---|---|---|
| 1 | 12 | 2 | 10 | 12 | 16 |

| Comparison | Only first arm | Only second arm | McNemar p | File-clustered 95% interval |
|---|---|---|---|---|
| grown against static | 11 | 0 | 0.0010 | [0.018, 0.364] |
| grown against shuffled | 10 | 0 | 0.0020 | [0.018, 0.319] |
| active against random | 4 | 0 | 0.125 | |

- alu1 gives 8 of grown's 12 recoveries. Without alu1, grown recovers 4 of 76, static 1 and shuffled 1.
- The 12.5% and 50% tables, and the policy version 1 and version 2 tables, also match PROGRESS.md.
- At 12.5%, both file-clustered lower bounds in development were 0.0, so the interval criterion already bites.

**Is the file-clustered interval the deciding criterion? Yes, and it is the right one.**
- Grown contains static, so every discordant item favours grown, and McNemar's p is 2 × 0.5^b for b discordant items: 0.0156 at b = 7 and 0.0078 at b = 8.
- Each file contributes at most 8 held items, so one alu1-like file can make the Holm test reject on its own.
- The interval cannot be passed that way. Using the frozen bootstrap over the 35 held files, I computed when the lower bound for grown against static can exceed 0:
  - **Gains in 1 to 3 files:** never, for every choice of files (all enumerated). At least 362 of 10,000 replicates have zero difference, and the bound needs at most 250.
  - **Gains in 4 files:** always, in all 20,000 sampled choices. At most 192 replicates have zero difference.
- So a gain concentrated in one to three files cannot be "supported". The rule requires the gain to appear in at least 4 different held files.

**Interpretation, already implied by section 4 of the protocol.** Grown against static cannot go negative, and shuffled also contains static. A supported grown against static therefore shows only that cofactor growth adds recoveries. The claim that the failure description matters, which is the transfer claim, rests on grown against shuffled, and RESULT.md's headline should follow that.

### 5. Secondaries and caveats are pre-declared: PASS-WITH-NOTES

- **12.5% and 50% probes.** Declared in PROTOCOL.md sections 3 and 6 and in `config.json` (`scored.circuit_fractions`). They are analysed in the secondary Holm family, grown against static and grown against shuffled at each.
- **Active against random probing.** Declared in sections 4 and 6. It is run only at 25%: the code enables it only at the primary fraction.
- **Policies labelled synthetic from real seeds.** Declared in sections 1 and 2, DATA_MANIFEST.md section 2 and ADAPTER_CARD.md, and every held row carries `data_label`.
- **The one revision of the policy growth rule.** Declared in section 9, with the 17-to-17 tie and its mechanism. The rows confirm it:
  - version 1: grown 17, shuffled 17, no discordant items;
  - version 2: grown 15, shuffled 10, 5 to 0.
- **Grown only tying the decision tree in development: note.** It is stated in PROGRESS.md: "Grown ties CART ... it does not beat them". So are two related points:
  - the alu1 concentration;
  - version 2 policy growth recovering fewer policies than the full decision list (15 against 17 of 48).

  PROGRESS.md is inside the freeze commit, so these points are committed before the run. But PROGRESS.md is not hash-listed, and PROTOCOL.md does not mention them. The fix, at the re-freeze, is one line each in PROTOCOL.md section 9.
- **Note on references.** `summary.json` gives the references McNemar p-values and intervals, but the protocol declares them descriptive, with no test. Report them as descriptive only.

### 6. The run command: FAIL as written

- **The documented line fails.** The frozen line is in score_held.py's docstring, and PROTOCOL.md section 7 names the same setup: `with_cpu_slot.sh` under setsid nohup. Its output goes to `results/run.log`, but `results/` does not exist before the run. The launching shell fails at the redirection and Python never starts. Reproduced in scratch: `cannot create results/run.log: Directory nonexistent`, exit status 2.
- **It bypasses the standard launcher.** It does not use `scripts/run_detached.sh`. With `--slot`, that script runs the job detached inside `with_cpu_slot.sh` (shared CPU slot, nice 19, idle I/O). It also records the command, working directory, stdout, stderr and START and EXIT lines under `outputs/detached/<name>/`.
- **The CPU cap is correct.** `CPU_CAP_S = 1800`, measured as process CPU time, not wall-clock, so load cannot trigger it.
  - It is checked before each item and fraction row. The largest development row took 4.5 CPU-seconds, so any overshoot is negligible.
  - The expected total is about 3 CPU-minutes.
- **Results stay in the study folder.** They go to `results/`, by paths built from the script's own location.

### 7. Licences are recorded: PASS-WITH-NOTES

**Espresso archive.**
- The repository LICENSE is MIT, copyright 2016 Sébastien Cottinet, as recorded.
- The same archive also carries the original Berkeley notice, which DATA_MANIFEST.md omits. It is in `espresso-src/COPYING` and `copyright.h`: "Copyright (c) 1988, 1989, Regents of the University of California ... Use and copying of this software and preparation of derivative works ... are permitted. However, any distribution ... must include the above copyright notice."
- The example PLA files carry no licence of their own.
- They are not redistributed: `data/raw/` is gitignored.

**ClassBench.**
- `parameter_files.tar.gz` holds 12 seed files and no licence file, confirmed.
- The `db_generator` README says "This code is freely available for academic, non-commercial research and educational purposes", confirmed verbatim.
- The supporting-file hashes match the manifest: `db_generator.tar.gz` c6165163... and `index.html` 70e4c36e....
- The manifest applies these terms to the seeds:
  - no redistribution;
  - kept out of public releases.
- The seeds are gitignored, and no result row stores seed content or a truth table.

## Blocking findings and exact fixes

### Blocking finding 1: the salt is neither bound to the freeze nor out of the designer's reach

Fix it with a pre-run amendment and a re-freeze, before any held item is chosen.

**`tlogic/data.py`, `held_items`.** Accept the 64-character sha256 of the GO file, and update the module docstring to match:
```python
if len(salt) != 64 or any(ch not in "0123456789abcdef" for ch in salt):
    raise ValueError("salt must be the 64-character sha256 of the committed GO file")
```

**`score_held.py`.**
- Remove `--salt`, and derive the salt inside `checks()`.
- Replace the parent-only freeze test, so that the GO file is committed and well formed, and so that the freeze commit it names is the last commit on HEAD that changed FREEZE.json.
- Record the salt and the freeze commit in `summary.json` and `run.status`.
- Optionally, refuse when the Python, numpy or scikit-learn version differs from FREEZE.json.
```python
def checks():
    if os.path.exists(os.path.join(HERE, "results", "held.jsonl")):
        refuse("results/held.jsonl exists: one scored run only")
    go_path = os.path.join(HERE, "GO")
    if not os.path.exists(go_path):
        refuse("no GO file")
    go = open(go_path, "rb").read()
    lines = go.decode("utf-8").splitlines()
    if not lines or lines[0] != "GO":
        refuse("GO file does not start with the line GO")
    f = dict(l.split(": ", 1) for l in lines[1:] if ": " in l)
    if git("show", f"HEAD:{REL}GO").stdout != go:
        refuse("GO is not committed at HEAD or differs from it")
    fz_bytes = open(os.path.join(HERE, "FREEZE.json"), "rb").read()
    if f.get("freeze_json_sha256") != hashlib.sha256(fz_bytes).hexdigest():
        refuse("GO names a different FREEZE.json")
    nonce = f.get("nonce", "")
    if len(nonce) != 64 or any(ch not in "0123456789abcdef" for ch in nonce):
        refuse("GO nonce is not 64 hex characters")
    fc = f.get("freeze_commit", "")
    # git runs with -C HERE, so the pathspec after "--" must be absolute (a repo-relative one would not match)
    last = git("log", "-n", "1", "--format=%H", "HEAD", "--", os.path.join(HERE, "FREEZE.json")).stdout.decode().strip()
    if fc != last or git("show", f"{fc}:{REL}FREEZE.json").stdout != fz_bytes:
        refuse("GO's freeze commit is not the last commit on HEAD that changed FREEZE.json")
    for rel, h in sorted(json.loads(fz_bytes)["sha256"].items()):
        p = os.path.normpath(os.path.join(HERE, rel))
        if not os.path.exists(p) or sha(p) != h:
            refuse("hash mismatch " + rel)
    return hashlib.sha256(go).hexdigest(), fc
```

**Tested.** I ran this exact text on the scratch copy of the folder.
- It accepted a well-formed committed GO.
- It refused each of the following:
  - an uncommitted GO;
  - a committed GO edited to read NO-GO;
  - a committed GO reading NO-GO;
  - a GO naming a parentless commit that has the frozen tree;
  - a GO with a wrong FREEZE.json sha256;
  - a GO with a short nonce.

**PROTOCOL.md.**
- **Section 2.** Replace the salt sentence with: "The salt is the sha256 (64 hex characters) of the GO file. The coordinator writes and commits GO after the pre-run review. GO names the freeze commit and the FREEZE.json sha256 and carries a fresh 256-bit random nonce, so the salt is fixed after the freeze and the review, by someone other than the designer."
- **Section 7, launch step.** Use the command under blocking finding 2.
- **Section 7, refusal list.** Make it:
  - no committed GO whose first line is GO;
  - GO's freeze commit is not the last commit on HEAD that changed FREEZE.json;
  - GO's FREEZE.json sha256 differs;
  - any hash differs;
  - results already exist.
- **New paragraph.** Add "Amendment 1, 8 November 2026, made before any held item was chosen". It should give the reason (the commit salt could be ground, and the frozen check accepted any commit with the frozen tree) and name the launcher change.
- **Section 9.** Add the three development caveats from check 5.

**DATA_MANIFEST.md.** Add one line on the Berkeley notice (check 7).

**Then:**
1. Rerun `tests/test_tlogic.py` and `make_freeze.py`.
2. Commit the changed files of this folder, with the new FREEZE.json, in one path-limited commit. That commit is the new freeze commit.
3. Ask for the delta check described at the end of this file.
4. Only then does the coordinator write GO.

### Blocking finding 2: the launch line fails, and it bypasses the program's launcher

This fix changes no frozen file. From the study folder:
```sh
cd /path/to/repository/experiments/transfer_logic_20261108
sh ../../scripts/run_detached.sh transfer_logic_held --slot python3 -I score_held.py
```

- **Outputs.** The study's results go to `results/`. The launcher's log and START and EXIT status go to `outputs/detached/transfer_logic_held/`.
- **Cap.** The 30-CPU-minute cap is enforced inside score_held.py.
- **If the coordinator keeps the frozen code (the fallback below),** append `--salt cb4369883501797581ff201a102923cefc2f43ef` to the command.

## Salt recommendation

**Recommended:** take the salt from the GO file. Salt = sha256 of the committed GO file, as 64 hex characters.

**The GO file.** The coordinator writes GO after the delta check of the amendment and commits it alone (`git add GO; git commit -m "..." -- GO`). Its content:
```
GO
study: transfer_logic_20261108
freeze_commit: <40-character hash of the amended freeze commit>
freeze_json_sha256: <sha256 of FREEZE.json at that commit>
pre_run_review: <commit hash of the delta check>
nonce: <output of: python3 -c "import secrets; print(secrets.token_hex(32))">
written_utc: <YYYY-MM-DDTHH:MM:SSZ>
```

The nonce is drawn once, after the review. The first committed GO is final; it is never redrawn or replaced.

**Why this is better than the commit hash.**
- The designer can neither predict the salt nor grind it.
- It binds the held set to this freeze and this review.
- An auditor can check it later: GO is committed, `summary.json` records the salt, and the post-score audit recomputes sha256(GO).

**Optional strengthening for readers outside the program.** Add a line with a public randomness-beacon value published after the review commit, for example a drand round. Then not even the coordinator chooses the salt.

**Fallback, not recommended.** The coordinator could keep the frozen code and the commit salt `cb4369883501797581ff201a102923cefc2f43ef`. In that case:
- GO must name that exact salt;
- the post-score audit must check that `summary.json` records it, because the code would accept other salts;
- RESULT.md must state, before the results, that the designer's commit fixed the salt, and that the record shows no sign of grinding but cannot exclude it.

With that disclosure the run would rate PASS-WITH-NOTES. I do not recommend it, because the proper fix is cheap now and impossible once held items are chosen.

## Non-blocking notes

1. **The GO check is too loose.** It accepts any file containing the letters GO, including a file reading "NO-GO" (demonstrated in scratch). The amendment above fixes this. Until then, never create a file named GO unless it is a go.
2. **Crash rerun.** The protocol allows one rerun after a crash before `summary.json` exists, but the run refuses whenever `results/held.jsonl` exists. If that happens:
   1. rename `results/` to `results_attempt1/`, and keep and commit it;
   2. rerun with identical files;
   3. say so in RESULT.md.
3. **Environment.** The versions are recorded but not checked. If the amendment does not add the check, verify the versions just before launch: `python3 -I -c "import platform, numpy, sklearn; print(platform.python_version(), numpy.__version__, sklearn.__version__)"` must print `3.12.3 2.4.3 1.8.0`. The bootstrap uses numpy's generator, so the intervals depend on the numpy version.
4. **Wording.**
   - Section 7 says FREEZE.json covers "every code file". The four development and helper scripts are not hashed; they are not used by the run.
   - Section 7's "4,096-node allowance" applies to circuit fits only, and never binds. Policy fits are capped at 512 rules.
   - Section 9 says "Two points" and then lists three.
   - DATA_MANIFEST.md lists `index.html`, which `fetch_data.sh` does not download.
5. **Family resemblance across the split** (the br, m, max and newapla families and the signature matches, check 2a). Report per-family counts descriptively in RESULT.md, next to the pre-registered per-file counts.
6. **Expectation, not a defect.**
   - The file behind 8 of 12 development recoveries (alu1) has no relative in the held pool.
   - Held candidates depend on more inputs: 95 of 489 depend on 9 to 12 inputs, against 8 of 84 in development.
   - A smaller held effect than in development would therefore not be surprising, and the file-clustered rule will report it honestly.

## What the delta check after the re-freeze should verify

1. **The diff.** The diff from `cb43...` to the new freeze commit, limited to this folder, contains only the changes listed under blocking finding 1.
2. **Hashes.** All FREEZE.json hashes match, and the unit tests pass.
3. **Refusals.** On a scratch copy, the new `checks()` refuses each of the following:
   - a parentless commit with the frozen tree;
   - a GO reading "NO-GO";
   - an uncommitted or edited GO;
   - a GO naming the wrong freeze commit.

   It must accept a well-formed committed GO.
4. **No held item.** No held item has been chosen: there is no GO and no `results/`.
