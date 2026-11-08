# Pre-run review: test T3, enzyme reaction rules from three examples

Study: `experiments/transfer_chemistry_20261108/`. Test T3 (chemistry) of the 8 November transfer tests asks whether
CORA's learn-from-failure loop transfers to enzyme chemistry: from k = 3 example reactions of one enzyme rule family,
find what changed, build a rule and predict the exact product of held substrates. Study author: Chimdi Walter
Ndubuisi.

An independent pre-run reviewer wrote this review on 8 November 2026, about 06:57Z to 07:20Z. The review was
read-only outside this file.

**Bytes reviewed**
- freeze commit (Amendment 1 re-freeze): `4eae13e5cf2c88ff8a43c7fec47cd440500f2014`;
- `FREEZE.json` sha256: `77d2a9575544417735f898c6ad93bff227e574a30e13e0c5144a49e6c23fa68d`;
- `PROTOCOL.md` sha256: `f9b9237f09769a826daca29da4dc548cb76143b4d342d69b7da0af2d496bf5f4`;
- `t3chem/run.py` sha256: `8b6a1a22b12ebdce53c3f2593fb42ddab2e4e0de9137e43e83884ea9ecc73872`;
- `t3chem/arms.py` sha256: `eddd27c5655199a1982ddd19901a00f8e9cbff8e5bebc67eb772634f8c45ec8b`;
- `launch/run_score.sh` sha256: `629f0680e3cb7d4ca593783ed6cd30eddcb537de7e629cfe4305b6d5b58a7920`.

**Verdict: PASS-WITH-NOTES.**
- There is no blocking finding.
- The held run may start once the coordinator commits the GO file exactly as section 3 gives it.
- The notes in section 4 are for `RESULT.md`, the post-score audit and future studies.

**What this review did not do.**
- It scored nothing, chose no held item and computed no salted order of the scoring pool.
- It did not run the frozen runner in the real study folder. The runner writes `runs/score/run.status` when it
  refuses, so the refusal tests ran on a scratch copy (check 5).
- It read no `*_LOCAL.json` file and nothing under a folder named `private`, and it touched no other running job
  and nothing in other projects' job folders.
- The review's scripts, kept in the reviewer's scratch folder, hashed files, parsed JSON and ran `--check-only`
  on the scratch copy. They used under 2 CPU-minutes, at nice 19.

**Terms used below.**
- A **family** is an EC (Enzyme Commission) number, to four levels, plus an EnzymeMap rule id, written `EC|rule`.
- An **item** is one (main substrate, main product) pair of a family. Its **pair** key is the two SMILES strings (the
  standard line notation for molecules) without stereochemistry.
- The **salt** is the sha256 (64 hex characters) of the committed bytes of `runs/GO`. The **nonce** is the
  64-character random hex string inside `runs/GO`.
- The specificity levels **L0 to L6** run from the changed atoms alone (element and aromatic flag) to a radius-2
  neighbourhood with element, aromaticity, charge, hydrogens, degree and ring membership.
- **Leave-one-out** here means: build from two of the three examples, then test on the third.

## 1. Checks

### Check 1. The freeze: PASS

**`FREEZE.json` and the freeze commit.**
- `FREEZE.json` is byte-identical in the working tree, at `4eae13e5` and at HEAD (`90d2cfb4` when checked); its
  sha256 is `77d2a957...`.
- `git log -n 1 --format=%H HEAD -- .../FREEZE.json` prints `4eae13e5`. Only two commits ever changed the file:
  `70d6a9a6` (the first freeze) and `4eae13e5`.
- Since `4eae13e5` the only commit touching the study folder is `d5e0fa65`, which changes `PROGRESS.md` only.
  No tracked file of the study differs from HEAD in the working tree.

**Every hash in `FREEZE.json`.**
- All 18 file hashes were recomputed. Every working copy matches.
- The 13 tracked files also match their blobs at `4eae13e5`.
- The 5 untracked data files (the item cache, the two EnzymeMap files and the two Pickaxe files the code reads) match
  in the working tree. Git ignores only `data/raw/`, `data/cache/`, `__pycache__/` and `*.pyc`.
- The three group digests (code, configuration, data manifest), recomputed with the rule in `t3chem/freeze.py`,
  match. `protocol_sha256` equals the `PROTOCOL.md` entry.
- All ten raw-file sha256 values in `DATA_MANIFEST.md` match. The two EnzymeMap files match the md5 values that the
  Zenodo record lists today. The Pickaxe rule file and `LICENSE` are byte-identical to the upstream files at the
  pinned commit `25acc1c8`.
- Not hashed, and they need not be: `ADAPTER_CARD.md`, `PROGRESS.md`, `.gitignore`, the `dev/` scripts, the
  development outputs, and the two shared scheduling scripts outside the study (`scripts/run_detached.sh` at
  `c23d22a0`, `scripts/with_cpu_slot.sh` at `e34f8dd8`). The scheduling scripts decide when and how nicely the run
  starts, not what it computes.

**Nothing held exists.**
- There is no `runs/GO`, no `runs/score/` and no `outputs/detached/transfer_chemistry_held/`.
- No commit on any ref, and no reflog entry, has ever touched `runs/GO` or `runs/score/`.

### Check 2. The held items: PASS

**Chosen only by the GO-derived salt.**
- In score mode the only salt is the value returned by `checks()`: `hashlib.sha256(go).hexdigest()`, where `go`
  is the working-tree `runs/GO` after it is shown to equal the blob at HEAD (`run.py` lines 122 and 148). The
  development salt is read only in development mode, and there is no `--salt` option.
- `select()` orders the scoring-pool families by sha256(salt + "|family|" + family) and keeps 40. Within each it
  orders the items by sha256(salt + "|item|" + family + "|" + pair): the first 3 are the examples and the next 5
  the held targets. Every pool family has at least 8 items (the minimum is 8), so there are 40 x 5 = 200 held
  targets unless the CPU cap stops the run.
- There is no other source of chance. The bootstrap seed is fixed and is used only for the interval. Python's string
  hashing does not reach the results: outcome sets are compared as sets, and every order comes from sorted lists or
  file order.

**Disjoint from development** (recomputed from `data/cache/items.jsonl.gz`).
- The development rule (the first 12 hex characters of sha256("t3chem-dev-20261108|" + family) read as a
  fraction below 0.15) gives 903 development families, 151 of them with at least 8 items. The stored flags show 0
  mismatches.
- The flags that mark an item whose pair occurs in any development family show 0 mismatches.
- The recomputed scoring pool has 681 families and 14,391 items and equals `data/POOL.json` exactly. It shares no
  family with the development set, and none of its items has a pair that occurs in a development family.
- The 31 families of `runs/dev_c40/` and their 31 shuffle partners are all development families. None of their
  pairs is in the scoring pool.

**Development exposure of the held families: none at the family or item level.**
- Every development path reads only development-family items: `run.py` in development mode, `dev/selfcheck.py` and
  `dev/equiv.py`. The pool builder read every family but applied no rule and ran no arm; it writes counts.
- Score mode never ran in the real repository: no GO was ever committed and no `runs/score/` exists. Under the first
  freeze the salt (that commit's hash) was knowable for about five minutes, until Amendment 1. There is no record of
  a held selection or score made with it, and the Amendment 1 salt does not depend on it.
- **Shared reaction types (by design; note).** The EnzymeMap rule ids are coarse: there are 90 in the scoring pool.
  So 651 of the 681 pool families share a rule id with some development family, and 455 share one with the 31
  families run in development. Also, 2,871 of the 14,391 pool items share a substrate, though never a pair, with a
  development item. The held families are therefore new EC-number families of mostly familiar reaction types, and
  the development choices (the level tie-break and the nearest-neighbour level) were made on those types. This fits
  the claim limit (reconstruction within a family, not transfer across families). The tie-break alternative is
  reported as `grown_alt`.

### Check 3. The arms: PASS

**Same examples and budget.**
- Each scored family gets one `Family` object built only from its 3 examples. `static_proposal`, `grow` and
  `nn_predict` read only those examples.
- The held substrates enter only after every arm's rules are fixed (`run.py` lines 211 to 219). One function
  (`apply_rules`) and one check (the outcome set equals {true product}) score every arm, with the same limit of
  500 raw products.
- No arm has its own time limit. The CPU cap is checked between families, so every completed family has all five
  arms and the comparisons stay paired.

**Static scans the published library.**
- `load_library` reads the frozen `metacyc_generalized_rules.tsv`: 1,224 published rules, 0 unparsed, 1,789
  single-substrate variants (one for each pair of an "Any" reactant slot and an "Any" product slot that share
  mapped atoms).
- `static_proposal` scores every variant on the 3 examples and picks the one with the most exact products, then the
  most covered, then the fewest raw products, then the name.
- The file is byte-identical to the upstream file at the pinned commit. Dropping the cofactor slots is the use the
  claim limit describes.

**Shuffled uses another family's change only.**
- `grow(..., partner=...)` builds from the partner's 3 examples, with the partner's rule extractor. The checks use
  the family's own 3 examples, and the fallback is the family's own static rule.
- In the leave-one-out step the build set stays the partner's 3 examples.
- The partner is the next scored family in the salted order with a different rule id. Only its 3 examples are used,
  never its held targets.

**The grown arm's keep rule: no leakage.**
- A level is a candidate only if its piece reproduces all 3 examples.
- Its leave-one-out count builds from two examples, checks on those two and tests on the third. No held target is
  seen.
- The piece is kept only if that count beats the static rule's exact count on the same 3 examples. The static count
  is in-sample (the rule was chosen on those three) and the grown count is out-of-sample, so the rule leans toward
  static. The piece that is kept is the one built from all three.
- The verdict memo is keyed by (rule object, example). Every rule object stays alive for the whole run, so a key
  cannot be reused by another rule.

### Check 4. The primary: PASS

- `compare(records, "grown", "static", 10000, 20261108)` gives:
  - the pooled difference in exact recovery rate;
  - a family-cluster paired bootstrap: families resampled with replacement 10,000 times with seed 20261108, and the
    2.5% and 97.5% order statistics (0-based positions 250 and 9,749 of the sorted 10,000) as the 95% interval;
  - the exact two-sided McNemar p: twice the binomial tail at min(b, c) with n = b + c and probability 1/2, capped
    at 1, where b and c count the targets only one arm recovers.
- The decision rule is protocol section 5: positive when the lower bound is above 0, negative when the upper bound
  is at or below 0, otherwise inconclusive. The runner does not print this label; `RESULT.md` applies it.
- The control is grown against shuffled, and the reference is grown against nearest neighbour (not a gate), with the
  same statistics. A diagnostic compares `grown_alt` with static.
- The claim scope is stated in protocol section 1, including that the grown arm only matched nearest neighbour in
  development.
- Every development number in protocol section 8 matches `runs/dev_c40/summary.json`:
  - 27, 81, 85, 27 and 76 exact of 155;
  - 55 against 1 discordant targets, +0.348 [0.219, 0.484], p = 1.6e-15;
  - 20 against 15, +0.032 [-0.097, 0.174], p = 0.50;
  - loop status 3, 18, 1 and 9.
  The CPU per family is also confirmed: median 8.47 s, mean 29.4 s, maximum 170 s.

### Check 5. The runner's GO checks: PASS

**Reading the code.** `checks()` refuses unless every rule of protocol section 6 holds, in this order:
- no held result exists;
- `runs/GO` exists, is ASCII, starts with the line `GO`, has all six fields and names this study;
- it equals the blob at HEAD, and exactly one commit on HEAD touches it;
- `freeze_json_sha256` equals the sha256 of `FREEZE.json`;
- the nonce is 64 lowercase hex characters;
- `pre_run_review` is 40 hex characters naming a commit;
- `written_utc` has the form `YYYY-MM-DDTHH:MM:SSZ`;
- `freeze_commit` is the last commit on HEAD that changed `FREEZE.json` and holds the same bytes;
- every file hash in `FREEZE.json` matches;
- the Python and RDKit versions match.

The launcher's interpreter (`python3`, in isolated mode) reports Python 3.12.3 and RDKit
2026.03.2, as `FREEZE.json` records.

**Scratch refusal tests.**
- **The scratch repository:**
  - the study at the freeze commit (`git archive`), with the five untracked frozen data files copied in;
  - a history of an earlier commit holding the first-freeze `FREEZE.json`, then the frozen `FREEZE.json` (the
    scratch freeze commit), then a placeholder review commit.
- **The cases:** 41 cases of `python -I t3chem/run.py --mode score --check-only`. All 41 behaved as expected: 35
  refusals and 6 acceptances.
- **Accepted:**
  - a well-formed GO committed alone (the printed salt equals the sha256 of the GO bytes);
  - five tolerated variants: CRLF line endings; an extra field; a GO committed together with an unfrozen file;
    later commits that touch neither GO nor frozen files; and a `pre_run_review` that names a commit older than the
    freeze (a gap, see below).
- **Refused, each with the intended message:**
  - no GO; a GO written but not committed; a GO staged but not committed; a GO edited after its commit;
  - a first line `NO-GO`; a GO replaced by a second commit; a GO deleted and re-added with the same bytes;
  - a `freeze_commit` that is a parentless commit with the frozen tree, an earlier commit that changed
    `FREEZE.json`, an abbreviated hash, or a later commit;
  - a wrong `freeze_json_sha256`;
  - a nonce of 63 characters, in upper case, with a trailing space, or with a non-hex character;
  - a `pre_run_review` that is no object, a blob, or abbreviated;
  - an existing held `summary.json`, or an existing empty held `families.jsonl`;
  - a non-ASCII byte; another study;
  - `FREEZE.json` edited after GO, or changed and committed after GO;
  - a missing `written_utc`, or one not in the Z form;
  - a frozen code file edited after GO; a GO committed together with a code change; a changed raw data file; a
    missing item cache; the launcher edited; `PROTOCOL.md` edited;
  - a `FREEZE.json` that records RDKit 2026.03.1, or Python 3.12.4.

**Gaps (non-blocking).**
- `pre_run_review` is checked only to name a commit, not to be this review's commit or to come after the freeze.
- "Committed alone" is not enforced.
- Score mode still honours `--tie-break` and `--nn-level`, and `--slice` renames the output file. The frozen launcher
  passes none of them.

The post-score audit covers all three (section 4).

### Check 6. The launcher: PASS

**The command.**
- `launch/run_score.sh` changes to the study folder and runs `sh scripts/run_detached.sh transfer_chemistry_held
  --slot python3 -I t3chem/run.py --mode score`, with no further argument.
- `run_detached.sh` starts the job with setsid and nohup. It writes `cmd.txt`, `cwd.txt`, `stdout.log`,
  `stderr.log` and `run.status` (START and EXIT lines) to `outputs/detached/transfer_chemistry_held/`, and refuses a
  second start while one is running.
- With `--slot` it goes through `scripts/with_cpu_slot.sh`. That script waits for one of the two shared lock slots,
  then runs the job at nice 19 with idle I/O priority. Waiting costs no CPU.

**The cap.**
- In score mode `run.py` sets the cap itself: 30 x 60 CPU-seconds of `time.process_time()`. It does not come from
  an argument or the configuration.
- The cap is checked before each family. At the cap the run stops with `STOPPED_CPU_BUDGET` and summarises the
  completed prefix.
- A family that has started finishes, so the overrun is at most one family (170 CPU-seconds at most in
  development). Expected cost: 40 x 29.4 s, about 20 CPU-minutes.

**The results.**
- They go into the study folder:
  - `runs/score/families.jsonl`, written and flushed per family;
  - `runs/score/summary.json`;
  - `runs/score/run.status`, whose STARTED and final lines carry the salt and the freeze commit.
- A crash leaves `families.jsonl` behind, which blocks a rerun, as the no-rerun rule requires.

### Check 7. Licences: PASS

- **EnzymeMap v2:** CC BY 4.0, recorded in `DATA_MANIFEST.md` with the citation and the credit to BRENDA. The
  Zenodo API for record 8254726 still gives the licence id `cc-by-4.0`.
- **The Ni et al. 2021 rules shipped with Pickaxe:** MIT. The `LICENSE` file is copied, its sha256 is recorded, and
  it is identical to the upstream file at the pinned commit. The citations are recorded.
- No raw file is in git. The committed derived content is counts, family keys, hashes and development outputs, all
  with attribution recorded.

## 2. Blocking findings

None.

## 3. The GO file

**The exact file.** Write `experiments/transfer_chemistry_20261108/runs/GO` as these seven lines, in this order:

```
GO
study: transfer_chemistry_20261108
freeze_commit: 4eae13e5cf2c88ff8a43c7fec47cd440500f2014
freeze_json_sha256: 77d2a9575544417735f898c6ad93bff227e574a30e13e0c5144a49e6c23fa68d
pre_run_review: <40-character hash of the commit that adds this review>
nonce: <64 lowercase hex characters, drawn once, after this review is committed>
written_utc: <YYYY-MM-DDTHH:MM:SSZ, the UTC time of writing>
```

**Its format:**
- plain ASCII, LF line endings, and a newline after the last line;
- `key: value` with one space after the colon;
- no blank line, no extra field, and no leading or trailing spaces.

The file I would accept is exactly the bytes that match this pattern (Python `re.fullmatch` on the decoded file):

```
GO\nstudy: transfer_chemistry_20261108\nfreeze_commit: 4eae13e5cf2c88ff8a43c7fec47cd440500f2014\nfreeze_json_sha256: 77d2a9575544417735f898c6ad93bff227e574a30e13e0c5144a49e6c23fa68d\npre_run_review: [0-9a-f]{40}\nnonce: [0-9a-f]{64}\nwritten_utc: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n
```

**`pre_run_review`.** It is the hash printed by
`git log --diff-filter=A --format=%H -- experiments/transfer_chemistry_20261108/reviews/PRE_RUN_REVIEW.md`, which
must print exactly one hash.

**Writing it in one step.** The command below draws the nonce once, refuses on any empty value, writes the file and
commits it alone in the same command, so the 30-minute autosave cannot catch a half-written GO. Run it from the
repository root:

```sh
P=experiments/transfer_chemistry_20261108/runs/GO
REV=$(git log --diff-filter=A --format=%H -- experiments/transfer_chemistry_20261108/reviews/PRE_RUN_REVIEW.md)
N=$(python3 -I -c 'import secrets; print(secrets.token_hex(32))'); T=$(date -u +%Y-%m-%dT%H:%M:%SZ)
[ ! -e "$P" ] && [ ${#REV} -eq 40 ] && [ ${#N} -eq 64 ] && [ ${#T} -eq 20 ] &&
printf 'GO\nstudy: transfer_chemistry_20261108\nfreeze_commit: 4eae13e5cf2c88ff8a43c7fec47cd440500f2014\nfreeze_json_sha256: 77d2a9575544417735f898c6ad93bff227e574a30e13e0c5144a49e6c23fa68d\npre_run_review: %s\nnonce: %s\nwritten_utc: %s\n' "$REV" "$N" "$T" > "$P" &&
git add -- "$P" && git commit -q -m "T3 chemistry: GO for the held run" -- "$P"
```

**Then, before launching:**
- `git log --format=%H -- "$P"` prints one hash, and `git show --name-only --format= <that hash>` lists only
  `runs/GO`.
- From the study folder, `python3 -I t3chem/run.py --mode score --check-only` prints
  `checks passed: salt <S> freeze_commit 4eae13e5cf2c88ff8a43c7fec47cd440500f2014`, where `<S>` equals
  `sha256sum runs/GO`.
- Record the GO commit and `<S>` in `PROGRESS.md`, in a separate commit that touches neither `runs/GO` nor
  `FREEZE.json`.
- Later unrelated commits are fine (tested), but no commit may touch `runs/GO`, `FREEZE.json` or a frozen file
  before the run ends.

**Launching.** Launch once:
`sh /path/to/repository/experiments/transfer_chemistry_20261108/launch/run_score.sh`.

## 4. Notes for RESULT.md, the post-score audit and future studies (non-blocking)

1. **The nonce is the one point of trust.** Anyone holding the data could compute the held selection for many
   candidate nonces before committing one. The rule "the first committed GO is final" stops a redraw on HEAD, but
   not a reset of history before the run. The audit should therefore check four things:
   - `git reflog` shows no other commit that touched `runs/GO`;
   - the GO commit follows this review's commit;
   - its `written_utc` is close to its commit time;
   - `pre_run_review` is an ancestor of the GO commit and a descendant of `4eae13e5`.
   Future studies could take the salt from a public randomness beacon value at a time declared before the GO.
2. **The autosave.** `scripts/autosave_watch.sh` runs `git add -A` over `experiments/` every 30 minutes. If the GO
   is not written and committed in one command, an autosave may commit it with other files, or commit it half
   written. A half-written GO would be final and would block the run. Section 3's command avoids this.
3. **What the audit should confirm from the run's own records:**
   - `outputs/detached/transfer_chemistry_held/cmd.txt` is the frozen launcher command, with no extra option;
   - `summary.json` shows `tie_break` `most_general`, `nn_level` `L4`, the salt equal to the sha256 of the
     committed GO, and `freeze_commit` `4eae13e5`;
   - `run.status` has one STARTED line;
   - the family records are a prefix of the salted order.
4. **The shuffled control.** In development it equalled static on every target, because another family's piece
   never passed the family's own checks. If that recurs, `RESULT.md` should say so: grown against shuffled is then
   the primary again, not an independent test.
5. **Claim wording.** Section 1's scope sentence reads as a result. `RESULT.md` should make it conditional on the
   held primary and report grown against nearest neighbour as measured, even if grown is worse on held items.
6. **The L0 wording.** `ADAPTER_CARD.md` and `arms.py` call L0 "element only". The code also fixes the aromatic
   flag (`chem.py`, `LEVELS["L0"] = (0, "ea", {})`), so `RESULT.md` should say "element and aromatic flag".
7. **Pairs across families.** 1,613 pairs appear in more than one pool family, 131 of them under different rule ids.
   This is harmless for grown, static and nearest neighbour, which see only their own family's examples. It can only
   help the shuffled control.
8. **The CPU cap.** If the run stops at the cap, label the result "stopped at the CPU cap" and give every
   denominator as the completed prefix (protocol section 6).
9. **For future runners:**
   - check that `pre_run_review` adds the review file and lies between the freeze commit and the GO commit;
   - check that the GO commit touches only `runs/GO`;
   - refuse development-only options in score mode;
   - write `run.status` on a refusal only in a real launch, not under `--check-only`.

## 5. Evidence log (commands; outputs summarised above)

- **The freeze:**
  - `git show 4eae13e5:<study>/FREEZE.json | sha256sum`;
  - `git log -n 1 --format=%H HEAD -- <study>/FREEZE.json`;
  - `git log --all` and `git log -g` limited to `runs/GO` and `runs/score` (both empty);
  - a hashing script over `files_sha256` against the working tree and the blobs at `4eae13e5`, plus the three group
    digests;
  - `sha256sum` and `md5sum` of the raw files.
- **The upstream files:** the Zenodo API record 8254726 (licence and md5 values), and the raw `LICENSE` and
  `metacyc_generalized_rules.tsv` from GitHub at commit `25acc1c8` (sha256 equal).
- **The split:** a script over `items.jsonl.gz` and `POOL.json` recomputing the development flags, the
  development-pair flags, the scoring pool, the overlaps and the rule-id counts. It computes no salted order.
- **The refusal tests:** a scratch git repository with the 41 `--check-only` cases of check 5, using the launcher's
  interpreter.
- **The development record:** `runs/dev_c40/summary.json` and the per-family `cpu_s` fields.
