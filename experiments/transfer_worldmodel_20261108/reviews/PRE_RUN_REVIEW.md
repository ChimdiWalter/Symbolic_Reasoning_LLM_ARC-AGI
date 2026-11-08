# Pre-run review: test T4, world-model induction on public ARC-AGI-3 games

Study: `experiments/transfer_worldmodel_20261108/`. Test T4 of the 8 November transfer tests predicts the exact next
frame of real public ARC-AGI-3 games from observed transitions. Study author: Chimdi Walter Ndubuisi.

An independent pre-run reviewer wrote this review on 8 November 2026, about 06:50Z to 07:05Z. The review was
read-only outside this file.

**Bytes reviewed**
- freeze commit: `82a9ae48c82bae82a82c356c04a8ed283cbf9177`;
- `FREEZE.json` sha256: `9779bc66eefb12eb44a9ae82304fb2b8fd32c754641ee84413e9cbe71abce9b6`;
- `PROTOCOL.md` sha256: `78b887dc2ccb40d363e5328173d00c087eee484347d67259cfa8d8af4634eccd`;
- the held-run kernel file `kernel/probe_held.py`, sha256:
  `c4b126bd55ca6c12dc6d1ef5dec87614a7cddc6c6c0ff29a150fbbaa5f1f2682`.

**Verdict: PASS-WITH-NOTES.**
- There is no blocking finding.
- The held run may start once the coordinator commits the GO file exactly as section 3 gives it. The GO binds the
  six conditions listed there.
- One amendment is recommended but not required (section 2).
- The notes in section 4 are for `RESULT.md` and the post-score audit.

**What this review did not do.**
- It ran nothing on Kaggle.
- It ran no game, toolkit or engine code on Athe.
- It opened no held-game data. None exists outside Kaggle, because no held transition has been collected.
- It read no `*_LOCAL.json` file and nothing under a folder named `private`.
- It did not rerun the frozen analysis. The development numbers were checked against the stored output of kernel
  version 4. The review's scripts, kept in the reviewer's scratch folder, only hashed files and parsed JSON.

**Terms used below.**
- An **item** is one (game, episode) pair. Its first 30 transitions are *observed*. The ones after those, up to 50,
  are *test* transitions.
- A **kind of piece** is one of the 23 combinations of selector, effect and trigger that the loop can build.
- The **partner** of an item is the item whose failure ranking the shuffled arm borrows.

## 1. Checks

### Check 1. The freeze binds the code, the kernel source, the configuration and the split rule: PASS

**The digests.**
- `FREEZE.json` hashes to `9779bc66...` in the working tree and at the freeze commit.
- All 15 files in its list were hashed again. Every working copy and every blob at `82a9ae48` matches.
- The four top-level digests (protocol, configuration, data manifest and held-run file) equal their entries in that
  list.
- No tracked file in the study folder has changed since the freeze, and no later commit touches the folder. Git
  ignores only `data/kernel_output/` and `wm/__pycache__/`.

**The kernel source.**
- `kernel/probe.py` and `kernel/probe_held.py` were rebuilt in memory from `kernel/probe_template.py` and `wm/*.py`,
  exactly as `kernel/build.py` builds them. Both rebuilds are byte-identical to the frozen files.
- The two kernel files differ in one line only, line 24, which sets `MODE = "held"`.
- The study code embedded in `probe_held.py` equals the frozen `wm/__init__.py`, `envs.py`, `model.py`, `induce.py`
  and `arc3.py`.

**The configuration.**
- No code reads `config/STUDY_CONFIG.json`. It is a record.
- Every value in it equals the constant in the frozen code:
  - 6 episodes with seeds 0 to 5, each of at most 80 steps;
  - 30 observed transitions, at most 50 test transitions, and at least 31 transitions per item;
  - block sizes 8, 4, 2 and 1;
  - 3 pieces per round, 4 rounds and 5 held checks;
  - the caps of 1,024 cells and 600 cells, and 23 kinds of piece;
  - 300 seconds per item and 4 workers;
  - `arc-agi==0.9.9` and `arcengine==0.9.3`;
  - 10,000 bootstrap resamples from `default_rng(0)`.

**The split rule.**
- The frozen kernel holds `SALT = "989cb0ca9c21811144356d83955cae5ca76ec6c6"`.
- Its split code (template lines 155 to 159) is the rule in `DESIGN_NOTE.md`.
- Sorting the 25 listed ids by `sha256(salt + "|" + id)` gives exactly the protocol's 12 held games and 13
  development games, in the protocol's order.

**Not bound.** Some files are outside the freeze. None affects the held run:
- `run.py`, `freeze.py` and `wm/classical.py`, which serves the substitute only;
- `dev/*.json`, `FEASIBILITY.md` and `PROGRESS.md`.

Inside the kernel, three versions are not pinned: numpy, uv and the Python 3.12 patch release. numpy's version is not
written to the outputs (section 4, note 4).

### Check 2. The held games were unseen: PASS

**The rule and its salt came before any frame.** The commit times, in UTC:

| Time | Commit or event | What it holds |
|---|---|---|
| 06:06:14 | `a72cb453` | the feasibility record: no ARC Prize code run, no key fetched |
| 06:08:21 | `3f7d5f0a` | the ledger line that quotes the author's go-ahead |
| 06:11:00 | `989cb0ca` | the design note with the hash rule; this commit's hash is the salt |
| 06:12:54 | `cc212acf` | the collection kernel, with the salt as a constant |
| 06:14:17 to 06:14:41 | files of `data/kernel_output/v1/` written on Athe | the first outputs |
| about 06:34, 06:40 and 06:45 | outputs of versions 2, 3 and 4 | development games only |
| 06:46:20 | `82a9ae48` | the freeze |

- Every later study commit descends from `989cb0ca`.
- Across all refs, only `989cb0ca` has ever touched `DESIGN_NOTE.md`.
- The HEAD reflog from 05:50Z to 06:50Z shows one design-note commit, and no amend, reset or rebase of `master`.
  There is no sign that the salt was ground.

**What the development kernels fetched.** The toolkit source kept in `data/raw/` was read, never run. It is the GitHub
main copy; the 0.9.9 wheel was not kept. It shows:
- in NORMAL mode, building `Arcade` fetches an anonymous key and the game list: ids, titles, tags and baseline action
  counts;
- `make()` downloads a game's code only for the game it makes.

So no held game's code was downloaded, even inside the kernel.

**The development outputs contain only development games.** In each of versions 1 to 4:
- all 78 npz files come from the 13 development games, and none from a held game;
- concatenated in name order, the npz files hash to `f81ddf9ef717...` in all four versions;
- `summary.json` lists 25 games and the protocol's held list;
- the episodes in `summary.json` are from development games only, and versions 3 and 4 record `mode: dev`;
- `analysis.json` (versions 2 and 4) has 73 rows, all from development games, and no held id appears anywhere in it;
- held ids appear only in the split lists: one log line (`games: 25 held: [...]`) and, in `summary.json`, the fields
  `held_games` and `order_by_hash`.

**What "unseen" covers.**
- It means that no held transition was collected or seen in this study.
- People can play the public games on the ARC Prize website, so prior familiarity cannot be ruled out.
- That risk is small here, for two reasons:
  - the 23 kinds of piece are byte-identical to those at `a72cb453`, which came before any ARC-AGI-3 frame;
  - no model code changed after the first development numbers. Versions 2 and 4 agree item by item on counts,
    fitted models and accepted pieces.

### Check 3. The arms are matched, and what the shuffled control shuffles: PASS, with a wording condition

**The same transitions.**
- Every arm is fitted on the item's first 30 transitions. The tabular arm memorises the same 30 (frame, action) pairs.
- The block size is chosen from frames 0 to 30 only.
- One function scores every arm on the same test transitions. No arm fits on a test frame.

**The same budget for grown and shuffled.**
- The two loops share:
  - 3 pieces per round, 4 rounds and 5 held checks;
  - the same caps and the item's own colours;
  - the same fitting and acceptance, on the item's own transitions.
- In development, the kinds tried per item averaged 9.03 for grown and 9.25 for shuffled. Both tried at most 12.
- CPU use differs: 409 seconds for grown against 157 for shuffled, in all. Grown describes its failure again in every
  round; shuffled does not.
- Static is the base fit that both loops start from. Copy-previous and tabular are references.

**What the shuffled control shuffles.**
- It replaces one thing: the ranked list of kinds of piece, that is, which kinds to build and in what order.
- The list comes from the partner's round-0 description and stays fixed for all four rounds.
- It does not shuffle the transitions, colours, fitted parameters, error counts or acceptance checks. All of these
  still use the item's own observed transitions.
- So the shuffled arm still uses the item's own failure evidence to fit and accept pieces.
- In held mode the run contains only held games, so the partner is another held game. The protocol's "next game"
  covers this. The design note's "next development game" described the development run.

**The development evidence.**
- Shuffled did at least as well as grown: 1,001 exact frames against 995.
- Only shuffled was right on 6 transitions, and only grown on none. All 6 are in two r11l items.
- In the 23 items where grown beat static:
  - the item's own round-0 description ranked the step-counter kind first in 12 items and below sixth in 11;
  - the partner's ranking had that kind in its top six in 21 of the 23.
- So the gain came from trying up to 12 of the 23 kinds under the checks. It did not come from the description
  pointing to the right kind.

**Is the primary limited to "language growth"?**
- The decision sentence, "grown beats static on unseen games", is about growth: building new pieces and checking
  them.
- The protocol makes the shuffled comparison a report, not a gate, and expects a tie.
- But its "Claim under test" paragraph describes the full six-step loop, including step 3, describing what is
  missing. If the primary passes and shuffled ties, that paragraph claims more than the data show.
- A tie also does not show that failure evidence is useless, because both arms use the item's own errors to fit and
  accept pieces.
- A win over shuffled would show only that the item's own ranking of kinds helps.
- The decision rule needs no change. Condition 5 of the GO fixes the wording of `RESULT.md`, so no amendment is
  needed.

### Check 4. The statistics and the decision rule are pre-registered: PASS

**What is fixed.** The frozen `PROTOCOL.md` states:
- the primary;
- the interval: a 95% bootstrap over held games, with 10,000 resamples from numpy `default_rng(0)`, where games are
  drawn with replacement and their transitions pooled;
- the decision rule: supported if the lower bound is above 0;
- the exact McNemar test, which is reported and ignores clustering;
- grown against shuffled, which is reported and is not a gate;
- the reference comparisons and the secondary measures.

The frozen kernel computes exactly these (template lines 94 to 121):
- grown against static is computed first, so its resamples are the first 10,000 draws;
- the interval is the 2.5 and 97.5 percentiles, with numpy's default interpolation;
- McNemar is the exact two-sided sign test on the discordant transitions.

Every number in the protocol's two development tables matches the stored version 4 output:
- the five arm totals and their changed-cell counts;
- the three differences and their intervals;
- the discordant counts and the p-values.

**When it was fixed.**
- The statistics were written after the development numbers (version 3, `8876c410`), but before any held data.
  `ADAPTER_CARD.md` discloses this.
- The design note had planned comparisons paired over items. The game bootstrap is the more conservative choice.

**Three points to settle now.** They need no code change. Condition 3 of the GO settles them:
1. The kernel prints the bound rounded to 4 decimals. A printed `0.0` is not above 0.
2. The bootstrap runs over the held games that have at least one scored item. The number of those games is reported.
3. The kernel also writes item-level sign tests and a comparison of static against copy-previous. The protocol does
   not list them, so they are labelled unregistered.

**What the rule needs.**
- If no game's gain is negative, a resample that draws no game with a gain gives exactly 0.
- With 12 games, k of them with a gain, that happens in ((12 - k)/12)^12 of the resamples:
  - for k = 3, it is 3.2%, so the bound prints `0.0` and the claim is not supported;
  - for k = 4, it is 0.8%.
- So the primary needs a gain in at least 4 held games.
- In development, the gains came from 4 of 13 games: bp35, r11l, s5i5 and vc33.

### Check 5. Isolation and terms: PASS

**Keys.** The kernel protects the key in four ways:
- the toolkit's logger is replaced by a silent one, and logging is disabled;
- the key is never written to a file;
- every output file is scanned for the key, and any copy found is replaced;
- the printed output of the child processes is cleaned of every token of 24 or more characters.

The toolkit source shows that the anonymous key is fetched while `Arcade` is built. It is kept in `arc_api_key`,
which is the value the kernel scans for. The game list cannot be fetched without the key. Versions 1 to 4 listed 25
games, so their scans had a key to look for.

This review scanned the four logs and every JSON output. It found:
- no UUID-shaped token;
- no long token other than hex digests and code labels;
- no "anonymous", "api_key" or "REDACTED".

`[token hidden]` appears 11 times in the version 2 log and 15 times in the version 4 log. Every instance is a
comparison label, such as `transitions_grown_vs_static`, that the cleaning step hid. `analysis.json` keeps those
labels.

Two small gaps remain (section 4, note 7):
- `analysis.json` is written after the scan. It is computed only from scanned files, by a process that never holds
  the key;
- "key-scan: clean" would also print if no key had been found.

**No rules accepted.**
- `kernel-metadata.json` lists no competition source and no dataset source.
- The kernel runs in NORMAL mode and has no submission code.
- The toolkit opens, reads and closes scorecards on the server only in ONLINE or COMPETITION mode.
- The only server calls here fetch the key, the game list, a game's metadata and a game's source.

**Terms.** The game files' terms are recorded as "not stated" in `DATA_MANIFEST.md`, in the limits section of
`PROTOCOL.md` and in `DESIGN_NOTE.md`.

**The held run executes only on Kaggle.**
- `probe_held.py` does anything only when pushed. It installs the toolkit in its own environment and writes to
  `/kaggle/working`.
- The toolkit and the engine are not installed on Athe.
- `run.py arc3-dev` reads npz data only, so it runs no game code. It still must not produce held numbers
  (condition 4).

**The held outputs.**
- They will hold frames of games whose terms are not stated.
- Condition 6 keeps them out of public view. The kernel stays private, the data folder stays git-ignored, and no
  output enters a public snapshot.

### Check 6. The development caveat is pre-declared: PASS

`PROTOCOL.md`, in "What development showed" and "Expected outcome", states:
- every gain comes from one kind of piece, "the first cell of a colour, in scan order, turns into another colour".
  This is a step counter or energy bar, seen in 23 items;
- the shuffled arm accepted the same piece;
- the primary is likely to be supported if the held games show counters;
- grown against shuffled is likely a tie.

The version 4 output confirms this:
- all 23 pieces that grown accepted are of that kind: selector `first`, effect `recolour_to`, any action, applied
  after the move;
- shuffled accepted 24 of them, plus one region recolouring after a click.

Two facts are not in the protocol and belong in `RESULT.md` (section 4, note 5):
- the gains came from only 4 of the 13 development games;
- the counter kind was written for the substitute's "energy" family, which copies the engine's public `complex_maze`
  example. The games' publisher wrote that example, so the kind rebuilds a display convention that was known in
  advance.

### Check 7. The launch procedure, and whether the GO can steer the held games: PASS, with conditions

**The procedure.** The protocol fixes it:
- the run is one new version of `chimdiwalter/t4-arc-agi-3-world-model-probe`, pushed from `kernel/probe_held.py`;
- the file is copied as `probe.py` into an empty folder, together with `kernel/kernel-metadata.json`;
- the version number and status of that run stand in for `run.status`;
- one re-push of the same file is allowed, and only if the run fails before the analysis finishes.

**Can the GO steer which games are held?**
- No. The kernel reads no input. `SALT`, `MODE` and `OUT` are constants, and they are the only arguments its child
  processes receive.
- So no line of the GO can change which games are held.
- For that reason the GO must carry no salt and no nonce, unlike the GO files of the logic and signalling tests. A
  nonce would do nothing here, but it would suggest that the GO picks the games.

**Three risks remain.** None of them is a choice anyone on the study can make.
1. **The public game list could change.**
   - At run time, the held set is recomputed from the server's current list (template lines 155 to 159). It is not
     checked against the frozen 12.
   - The list stayed at the same 25 games from about 06:13Z to 06:45Z.
   - If games were added, the cut at floor(n/2) would move. One or two new games that sort last would put the
     development game m0r0 into the held set. New games could also enter it.
   - Condition 2 makes such a run void. Section 2 gives a check that would stop it before any frame is collected.
2. **The wrong file could be pushed.** Pushing the `kernel/` folder as it stands would push `probe.py`, the
   development kernel. The procedure in section 3 uses a fresh folder and checks the hashes.
3. **There could be more than one push.** The audit lists every kernel version after version 4 (section 4,
   note 1).

**A gap in the record** (section 4, note 3): `summary.json` records the full version ids of the development games
only. The held games' version ids will not be recorded.

## 2. Blockers and the recommended amendment

**Blockers: none.**

**Recommended amendment (optional).**
- It stops a run on a changed game list before any game is made, so the held games stay unused.
- Make it if the held run might not start within a few hours. Otherwise condition 2 is enough.
- It needs:
  - a dated amendment;
  - a rebuild of both kernel files, with `python3 -I kernel/build.py` and `python3 -I kernel/build.py held`;
  - a new `FREEZE.json`, from `python3 -I freeze.py 4`;
  - a delta check.

In `kernel/probe_template.py`, inside `COLLECT`, insert these lines right after
`held, dev = order[: n // 2], order[n // 2:]`:

```python
FROZEN_HELD = ["tu93", "su15", "re86", "lf52", "sb26", "ka59", "ar25", "tn36", "sc25", "cn04", "ft09", "dc22"]
if sys.argv[3] == "held" and (n != 25 or held != FROZEN_HELD):
    print("split-check: FAILED, the public game list changed; no game was made")
    sys.exit(3)
```

Also add `"full_ids": full,` to the `summary` dictionary, so that the version id of every game is recorded, held
games included.

With these lines, the collector exits before it makes any game, and the kernel skips the analysis.

## 3. The GO file I would accept

**Before writing it, check that:**
- `git log --diff-filter=A --format=%H -- experiments/transfer_worldmodel_20261108/FREEZE.json` prints only
  `82a9ae48c82bae82a82c356c04a8ed283cbf9177`;
- `git status --porcelain -- experiments/transfer_worldmodel_20261108` prints nothing;
- `sha256sum` gives the digests below for `FREEZE.json`, `kernel/probe_held.py` and `kernel/kernel-metadata.json`.

**The file.** Write `experiments/transfer_worldmodel_20261108/GO` with exactly these lines. Fill in only the two
values in angle brackets.

```
GO
study=transfer_worldmodel_20261108
freeze_commit=82a9ae48c82bae82a82c356c04a8ed283cbf9177
freeze_json_sha256=9779bc66eefb12eb44a9ae82304fb2b8fd32c754641ee84413e9cbe71abce9b6
held_run_file_sha256=c4b126bd55ca6c12dc6d1ef5dec87614a7cddc6c6c0ff29a150fbbaa5f1f2682
kernel_metadata_sha256=0582ad8357a50818b0f8b423dacef7c852a575745ea0e5733e63edaa68cf7927
kernel=chimdiwalter/t4-arc-agi-3-world-model-probe
last_dev_version=4
held_split_salt=989cb0ca9c21811144356d83955cae5ca76ec6c6
held_games=tu93,su15,re86,lf52,sb26,ka59,ar25,tn36,sc25,cn04,ft09,dc22
pre_run_review_commit=<the commit that adds reviews/PRE_RUN_REVIEW.md>
conditions=reviews/PRE_RUN_REVIEW.md section 3, conditions 1 to 6
written_utc=<the time of writing, as YYYY-MM-DDTHH:MM:SSZ>
```

- `held_split_salt` and `held_games` record values that were fixed at `989cb0ca` and `82a9ae48`. They are not chosen
  here, and no code reads them.
- The GO must have no nonce line and no other free text.
- Commit the GO alone, with git limited to its path, before the push.
- If the amendment in section 2 is made, the freeze lines change to the new freeze, and the GO must also name the
  delta check.

**The conditions the GO binds.**
1. **One run.**
   - The held run is the first kernel version after version 4, pushed after the GO commit.
   - A re-push is allowed only under the frozen stop rule, that is, when the run failed before the analysis finished.
     It must use the same file, happen once, and be documented in `PROGRESS.md` first.
   - Collection errors that leave a held game with no items are reported. They do not justify a re-push.
2. **When the run is void.** The run counts only if all of these hold:
   - `summary.json` shows `mode` `held`, `salt` `989cb0ca9c21811144356d83955cae5ca76ec6c6` and `n_games` 25;
   - its `held_games` are exactly the 12 in the GO, in the same order;
   - its episodes and the npz file names come only from those 12 games;
   - the log shows `key-scan: clean`.

   Otherwise the run is void. `RESULT.md` says why, and no held number is claimed.
3. **The decision.**
   - The primary is decided from the kernel's own `analysis.json`. The value
     `summary.transitions_grown_vs_static.ci95_game_bootstrap[0]`, as printed, must be above 0. A printed `0.0` is
     not above 0.
   - `RESULT.md` reports the games with items, the items, the test transitions, the timeouts and the excluded
     episodes.
   - The item-level sign tests and the comparison of static against copy-previous are labelled unregistered.
4. **Where the numbers come from.**
   - Every reported held number comes from that `analysis.json`.
   - Any local analysis of the held npz files, including `run.py arc3-dev`, waits until `RESULT.md` is committed, and
     is labelled exploratory.
5. **Wording.**
   - If the primary is supported, the claim is: "growing the rule language through the loop's build-and-check steps
     beat the fixed rule language at exact next-frame prediction on 12 held-out public ARC-AGI-3 games". It is a
     probe, it reconstructs the games' own rules, and it is not a score.
   - The failure description's contribution may be claimed only from grown against shuffled, which is reported and is
     not a gate.
   - If grown and shuffled tie, the sentence is: "the item's own ranking of kinds added nothing measurable over
     another game's ranking". It adds that both arms fit and accept pieces on the item's own errors.
   - If the held gains come from one kind of piece, the headline sentence names it.
6. **Custody of the outputs.**
   - The kernel stays private.
   - Outputs are fetched into `data/kernel_output/v<version>/`, which git ignores.
   - The sha256 values of the log, `summary.json`, `analysis.json` and the concatenated npz files go into
     `PROGRESS.md` and `RESULT.md`.
   - None of these files enters a public snapshot.

**The launch after the GO.** Run this from the repository root, with the Kaggle CLI on Athe:

```bash
S=experiments/transfer_worldmodel_20261108
KG=kaggle
W=$(mktemp -d -t t4_held_push.XXXXXX)          # a new, empty folder outside the repository
cp $S/kernel/probe_held.py $W/probe.py
cp $S/kernel/kernel-metadata.json $W/kernel-metadata.json
ls -A $W                                        # exactly: kernel-metadata.json probe.py
sha256sum $W/probe.py $W/kernel-metadata.json   # must be c4b126bd...2682 and 0582ad83...7927; otherwise stop
$KG kernels push -p $W                          # once; record the version number it prints
$KG kernels status chimdiwalter/t4-arc-agi-3-world-model-probe
# poll until COMPLETE or ERROR; retry on a transient permission error; a long queue is not a failure
mkdir -p $S/data/kernel_output/v<N>
$KG kernels output chimdiwalter/t4-arc-agi-3-world-model-probe -p $S/data/kernel_output/v<N>   # before any other push
```

Then check condition 2 and record the hashes in condition 6, before writing `RESULT.md`.

## 4. Notes for RESULT.md and the post-score audit (non-blocking)

1. **One run.** List the kernel's versions with their times. Versions 1 to 4 must come before the GO, and the held
   version must be the first after it.
2. **The code that ran.**
   - Pull that version's code and compare its sha256 with `c4b126bd...`.
   - If Kaggle changes line endings, compare after normalising them, and say so.
   - The log line `games: 25 held: [...]` and the field `mode: held` in `analysis.json` cross-check it.
3. **Game versions.** The held games' version ids are not recorded. State that the games were the versions served
   on the run date.
4. **Environment.**
   - numpy and uv were not pinned, and the Python 3.12 patch release may differ. Versions 1 to 4 used 3.12.3.
   - Report the versions printed in `summary.json`, and say that numpy's version is not recorded.
5. **Interpretation.**
   - In development, the gain was one display convention, a step counter, in 4 of 13 games.
   - The counter kind traces back to the publisher's own public example game.
   - "Unseen" means not collected in this study.
   - With 12 games, a percentile bootstrap over games can be narrow, and McNemar ignores clustering.
6. **Records to correct.**
   - `DESIGN_NOTE.md` names the kernel `t4-arcagi3-worldmodel-probe`, but the kernel is
     `t4-arc-agi-3-world-model-probe`. The note is a pre-data record, so leave it unchanged and state the difference.
   - The ledger line committed at 06:08:21Z says "author 06:40Z". That is impossible for a line committed at 06:08Z,
     so it must be a typo.
   - In `DATA_MANIFEST.md`, "no game code" should read "no ARC-AGI-3 game code". The kept files include the MIT
     example and test games, which were read and never run.
7. **The log and the key scan.**
   - The cleaning step hides the comparison labels in the log. `analysis.json` is the source.
   - Read "key-scan: clean" together with `n_games` = 25, which shows that a key was present.

## 5. Evidence log (commands; their outputs are summarised above)

- **Digests:**
  - sha256 of every `FREEZE.json` entry, in the working tree and through `git show 82a9ae48:<path>`;
  - `kernel/probe.py` and `kernel/probe_held.py` rebuilt in memory from the template and `wm/*.py`;
  - a line diff of the two kernel files.
- **History:**
  - `git log` with ISO dates on the study folder, and `git merge-base --is-ancestor`;
  - `git log --all` on `DESIGN_NOTE.md`;
  - the HEAD and branch reflogs for 05:30Z to 06:50Z;
  - the file times of `data/kernel_output/v1` to `v4`;
  - `git log -S` on the go-ahead quote in `records/`.
- **Split:** the sha256 ordering of the 25 ids under the frozen salt.
- **Development outputs:**
  - for versions 1 to 4: the npz names and their concatenated hash, the `summary.json` fields, and the
    `analysis.json` rows and statistics;
  - an item-by-item comparison of versions 2 and 4;
  - the accepted pieces and the ranking positions.
- **Keys:**
  - pattern counts over the four logs and every JSON output;
  - the text around `[token hidden]` in the version 4 log.
- **Code read:**
  - `kernel/probe_template.py`, `kernel/build.py`, `kernel/kernel-metadata.json`, `wm/arc3.py`, `wm/induce.py`,
    `wm/model.py`, `freeze.py` and the start of `run.py`;
  - in the toolkit source kept in `data/raw/`, the key, list, download and scorecard paths;
  - the engine's action enumeration.
