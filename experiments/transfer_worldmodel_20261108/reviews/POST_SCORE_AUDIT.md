# Post-score audit: test T4, world-model induction on public ARC-AGI-3 games

Test T4 asks whether CORA's loop can predict the exact next frame of real public ARC-AGI-3 games from observed
transitions.

- **Auditor.** The independent reviewer who wrote `reviews/PRE_RUN_REVIEW.md` (commit `4330bfd9`). The auditor is not
  the study's designer.
- **Audited.**
  - the GO commit `ed754a3d`;
  - the held run: private Kaggle kernel `chimdiwalter/t4-arc-agi-3-world-model-probe`, version 5. Its outputs are in
    `data/kernel_output/v5/`, which git ignores;
  - the RESULT.md commit `cb8e58b5`, which also adds the PROGRESS.md entries for the run.
- **Date.** 8 November 2026, about 07:15Z to 07:35Z.

## Verdict: FAIL, for RESULT.md only

- **What passes:**
  - custody and all six GO conditions (check 1);
  - every number (check 2).

  The run is valid. The primary is correctly reported as not supported.
- **What fails:** RESULT.md (check 3). It has one explanation that the kernel's own output contradicts, and three
  sentences that claim more than the data show.
- **How it turns to PASS:**
  - RESULT.md makes the four edits in check 3, word for word or with the same content;
  - no rerun, no rescoring and no further audit is needed. The coordinator only confirms the edits.
- **The sentences the papers may use** are in section 4. They hold in either case.

## Method

**What was done.**
- Committed files were read with `git show` at the audited commits.
- The outputs were hashed.
- `summary.json`, `analysis.json` and the log were parsed with `python -I` from a scratch folder.
- The statistics were recomputed from the per-transition flags in `analysis.json` by an independent implementation
  (numpy 2.4.3). It uses one `default_rng(0)`, drawn in the kernel's order of comparisons.
- The held npz files were hashed and listed by name. Their frames were not opened.

**What was not done.**
- No game, toolkit or engine code ran.
- Kaggle saw one read-only call, `kaggle kernels list -m -s world-model-probe`, at 07:21Z. Nothing was pushed to Kaggle
  or run there.
- Nothing was written to the repository except this file.

## 1. Custody and the six GO conditions: PASS

**The GO.**
- Exactly one commit, on any ref, touches `GO`: `ed754a3d`, at 07:04:12Z. It adds only `GO`.
- The pre-run review, `4330bfd9`, is an ancestor of it.
- The file is the accepted text, with its two open values filled in:
  - `pre_run_review_commit=4330bfd934663843e41da388c28e51c1db982370`;
  - `written_utc=2026-11-08T07:04:12Z`.
- It has no nonce, and it is unchanged at HEAD.
- No frozen file changed between the freeze and HEAD. Before RESULT.md, the study folder gained only `GO`, the review
  and new PROGRESS.md entries.

**Condition 1: one run.**
- The push folder in the session scratch, `t4_held_push.QItVrS`, holds exactly `probe.py` and `kernel-metadata.json`.
  - Both were written at 07:05:21Z, 69 seconds after the GO.
  - Their sha256 values are `c4b126bd...2682` and `0582ad83...7927`. The folder's saved sums file records the same.
- Kaggle lists the kernel's last run at 07:05:24Z, after the GO. As of 07:21Z there is no later run, so there was no
  re-push.
- This audit cannot see Kaggle's version list. The number 5 rests on the push message recorded in PROGRESS.md.
- The earlier push folders, written at 06:29:13Z, 06:36:10Z and 06:41:00Z, match the run record's versions 2 to 4.
  None of their kernel files is in held mode.
- Collection had no errors, no timeouts and no excluded episodes.

**The code that ran.**
- The copy pulled back from Kaggle at 07:12:23Z is byte-identical to the frozen `kernel/probe_held.py`, sha256
  `c4b126bd55ca6c12dc6d1ef5dec87614a7cddc6c6c0ff29a150fbbaa5f1f2682`.
- It contains no carriage returns, so Kaggle changed no line endings.
- The pulled metadata shows a private kernel with internet on and no GPU. It has no competition, dataset, kernel or
  model source.

**Condition 2: the void rule.** Every item holds, so the run counts:
- `summary.json` shows mode `held`, salt `989cb0ca9c21811144356d83955cae5ca76ec6c6` and `n_games` 25;
- `held_games` are exactly the 12 games in the GO, in the GO's order, and `order_by_hash` equals the frozen order of
  all 25;
- there are 72 episodes, seeds 0 to 5 for each held game, and 72 npz files whose names equal the episode keys. No
  development game appears;
- the log shows `key-scan: clean`, exit code 0 for both collection and analysis, and the line `games: 25 held: [...]`;
- the log, `summary.json` and `analysis.json` contain no UUID-shaped token and no "anonymous", "api_key" or "REDACTED".

**The output digests.** All four match PROGRESS.md and RESULT.md:

| File | sha256 (first 16 characters) |
|---|---|
| log | `3f9185efb1565455` |
| `summary.json` | `e529820f102c7a17` |
| `analysis.json` | `40fa49b9528962bb` |
| the 72 npz files, concatenated in name order | `cbfa6792b2c62172` |

**Condition 3: the decision.**
- The printed lower bound for grown against static is `0.0`. So the primary is not supported, as RESULT.md says.
- RESULT.md reports the games, items, test transitions, timeouts and exclusions.
- It labels the item-level sign tests as unregistered.

**Condition 4: every number comes from `analysis.json`.**
- Every number in RESULT.md recomputes from the kernel's output (check 2).
- No saved script in the session scratch read the held npz files between the fetch and the RESULT.md commit.
- Nothing ran game code on Athe:
  - the scratch holds no toolkit or engine files;
  - its `localtest4` folder is a different study's run (the ARC-AGI-2 verification notebook).
- One RESULT.md sentence cannot be derived from the kernel's output (check 3, edit 1).

**Condition 5: wording.** Partly met. See check 3.

**Condition 6: the outputs stay private.**
- The kernel is private, per the pulled metadata.
- `data/kernel_output/` is git-ignored. Under `data/`, git tracks only the 14 MIT source files in `data/raw/`.
- The public snapshot script builds from files tracked on master, so the held outputs cannot enter it.

## 2. The numbers: PASS

Every value below was recomputed from the per-transition flags in `analysis.json`. Each one matches the kernel's
summary and RESULT.md.

| Arm | Exact next frames, of 3,168 | Changed cells predicted right, of 78,521 |
|---|---|---|
| copy-previous | 930 | 0 |
| tabular | 930 | 0 |
| static | 902 | 10,587 |
| grown | 1,204 | 11,567 |
| shuffled | 1,125 | 10,911 |

**Grown against static (the primary).**
- Grown alone was right on 302 transitions; static alone was right on none.
- The difference is +0.0953.
- The independent bootstrap gives [0.000000, 0.231563], and the kernel printed [0.0, 0.2316].
- 307 of the 10,000 resamples are exactly 0. The expected share is (9/12)^12 = 3.2%, so the 2.5th percentile is 0.
- The primary is not supported.

**Per game.** Grown and static differ in three games only: lf52 +202, dc22 +79 and tu93 +21.

**Grown against shuffled.**
- Grown alone was right on 79 transitions; shuffled alone was right on none.
- The difference is +0.0249, with interval [0.0, 0.0764].
- All 79 transitions are in dc22.

**The references.** Grown alone was right on 302 transitions and the reference alone on 28, for both references:
- against tabular: +0.0865, with interval [-0.0105, 0.2289];
- against copy-previous: +0.0865, with interval [-0.0108, 0.2296].

**Static below copy-previous.**
- cn04: static 51, copy-previous 54.
- ft09: static 236, copy-previous 261.
- In cn04, copy-previous was right and static wrong on 3 transitions; in ft09, on 25. The reverse never happened.
- In every item of both games, grown's model is the static model.

**What happened in dc22.**
- In all 6 items, the item's own round-0 description ranked the trail kind first, and grown kept it in round 0.
- The borrowed ranking came from ft09, a click game. It tried 12 kinds and never the trail kind.
- In lf52, tn36 and tu93, both arms kept the counter kind in all 6 items.

**Tests that are reported but are not the gate.**
- The exact McNemar p-values match: 2.5 x 10^-91 against static, 3.3 x 10^-24 against shuffled, and 3.4 x 10^-59
  against each reference. They ignore clustering by game.
- The item-level sign tests also match, but they were not pre-registered:
  - grown above static in 17 items and below in 0 (p = 1.5 x 10^-5);
  - grown above shuffled in 6 items and below in 0 (p = 0.031);
  - static above copy-previous in 0 items and below in 5 (p = 0.0625).

## 3. RESULT.md: FAIL, with four edits

**What is in scope:**
- **The labels.** It says the run is a probe on public games, not a score; that it is world-model induction; and that it
  reconstructs the games' rules. It defines "held" and "unseen".
- **The primary.** It is reported as not supported, with its interval and the decision rule.
- **The failure description.** Its contribution is called not established, judged from grown against shuffled only.
- **The framing.** All four findings are framed as result, lesson and direction.
- **The pre-run review's section 4.** Every note is carried: one run, the code that ran, the game versions, the
  environment, the interpretation, the three record corrections, and the log and key scan.

**Four edits are required.** Edit 1 corrects a factual error. Edits 2 to 4 remove claims that go beyond the data. No
edit changes a number.

1. **Section "1. Primary", direction.**
   - Current: "The main gaps are multi-colour sprites, animations and level redraws."
   - Problem:
     - the kernel's output does not measure sprites or animations;
     - it rules out level changes. 78,318 of the 78,521 changed cells (99.7%) lie in transitions within a level;
     - only 24 test transitions leave a level, the same number as the episodes that ended in GAME_OVER. So no level
       was completed in a test transition.
   - Replace with: "Which changes are missed was not measured. 99.7% of the changed cells (78,318 of 78,521) lie in
     transitions within a level, and no level was completed in a test transition, so the missed changes happen
     inside levels. Finding them needs an exploratory look at the held frames."
2. **Headline, item 3, its last two sentences.**
   - Current: "So the failure description helped in one held game and in no development game. Its contribution is not
     established."
   - Replace with: "So the item's own ranking gave grown an advantage in one held game, dc22, and in no development
     game. The failure description's contribution is not established."
3. **Section "2. The failure description", lesson.**
   - Current: "a step counter is common enough that any game's ranking reaches it within 3 pieces per round over 4
     rounds. The item's own description mattered only for a rarer kind, the trail."
   - Problem:
     - "any game's ranking" goes beyond the three games where the counter was kept;
     - "mattered" rests on one game whose interval reaches 0.
   - Replace with: "in the three games where grown kept the step-counter piece, the borrowed ranking also reached it
     within its 12 tries. Only in dc22 did the item's own ranking reach a kind that the borrowed ranking never tried,
     the trail. One game cannot establish a contribution."
4. **Section "4. Transfer of piece kinds", lesson.**
   - Current: "piece kinds written for public example rules do transfer to unseen ARC-AGI-3 games, but only to the
     games that share those display conventions."
   - Problem:
     - the pre-registered test of the gain did not pass;
     - "only to the games that share those display conventions" was not tested.
   - Replace with: "two piece kinds written for public rule sets were kept on unseen ARC-AGI-3 games and raised exact
     predictions in 3 of the 12. The pre-registered test of that gain did not pass, so this describes the run and does
     not establish transfer."

**Non-blocking notes.**
1. **"A base rule that hurts".**
   - "The loop adds pieces but never revises or drops a base rule" is loose.
   - The loop refits the base rule's parameters after it keeps a piece, but it never drops or re-chooses the base
     rule.
   - In cn04 and ft09 it kept no piece, so grown's model is static's.
2. **"Both arms built the same counter piece".**
   - The audit could check only that both arms kept the same kind and got the same exact counts.
   - The shuffled arm's fitted parameters are not stored, so write "the same kind of counter piece".
3. **tn36.**
   - The counter piece was kept in all 6 items, yet no arm predicted any frame exactly (0 of 186).
   - A kept piece fixes observed cells. It need not give an exact frame.

## 4. Sentences the papers may use

These need no internal labels and no other source. Every number is exact. Use them as written, or shorten them
without dropping a denominator or a label.

**Setup.**
1. "We applied CORA's build-and-check loop, through an adapter, to real public ARC-AGI-3 games: from 30 transitions
   observed under random actions, a model must predict the exact next 64 by 64 frame. This is world-model induction,
   not game play, and it reconstructs the games' own rules rather than discovering new ones."
2. "The loop starts from a fixed rule language (an actor that moves and a colour map for clicks). It describes the
   cells it predicts wrongly, builds candidate pieces of 23 kinds, and keeps a piece only if the piece fixes cells,
   breaks no transition that was right, and passes a leave-one-out check."
3. "Twelve of the 25 public games were held out by a hash rule fixed before any frame was collected. No transition
   from them was seen before a single pre-registered run in a private Kaggle kernel."

**Primary result.**

4. "On the 12 held games, the grown language predicted 1,204 of 3,168 test frames exactly, against 902 for the fixed
   language (0.380 against 0.285, a difference of +0.095). It was right on 302 transitions where the fixed language
   was wrong, and never the reverse."
5. "The pre-registered test did not pass: the 95% bootstrap interval over games was [0.0, 0.232], and its lower bound
   is not above zero."
6. "The gains came from 3 of the 12 games. In lf52 (+202 transitions) and tu93 (+21), they came from a piece that
   turns the first cell of a colour, in scan order, into another colour, as a step-counter display does. In dc22
   (+79), they came from a piece that recolours the cells the actor leaves, as a trail does."
7. "Because the gains sit in 3 of 12 games, a resample of 12 games misses all three with probability (9/12)^12, about
   3.2%. That is more than the 2.5% tail, so a bootstrap over games cannot exclude zero."

**The failure description.**

8. "The same loop guided by another game's failure ranking predicted 1,125 of 3,168 frames exactly. The loop's
   advantage over it, +0.025 (95% interval [0.0, 0.076]), came entirely from one game, dc22, so the contribution of an
   item's own failure description is not established."

**References and negatives.**

9. "Copying the previous frame predicted 930 of 3,168 frames exactly, and so did memorising the observed (frame,
   action) pairs."
10. "Among pixels that changed, the grown language predicted 14.7% exactly (11,567 of 78,521), the fixed language
    13.5% (10,587) and copying none."
11. "The fixed language was less exact than copying in two games (cn04: 51 against 54 frames; ft09: 236 against 261),
    because its fitted rule changed frames that did not change. The loop kept no piece in those games and inherited
    the errors."

**Development context.**

12. "In development, on 13 other games, every gain also came from the step-counter piece, in 4 of the 13 games."

**Lesson and direction.**

13. "Gains from growing the language appeared only where a game showed a regularity that the piece kinds could
    express. A test at the level of games needs more games or a wider set of piece kinds."

**Label.**

14. "These are probe results on public games, not a competition score."

**Do not write:**
- that the loop beats the fixed language on unseen games, or that the gain is significant. The test did not pass, and
  the McNemar p-values ignore clustering by game;
- that the failure description helped or mattered, except as "in one game, dc22";
- that piece kinds transfer to ARC-AGI-3 games;
- that the missed changes are sprites, animations or level redraws;
- the item-level sign tests, which were not pre-registered;
- "game play", "score" or "discovery" for this result.

## 5. Evidence log (commands; outputs summarised above)

- **Custody:**
  - `git log --all` on `GO`, and `git show --name-status` of `ed754a3d`;
  - `git merge-base --is-ancestor` for review, then GO, then RESULT.md;
  - `git diff` of the frozen paths from `82a9ae48` to HEAD;
  - `git check-ignore` on the v5 outputs, and `git ls-files` under `data/`;
  - the scratch push folder (file list, times, sha256 and sums file) and the pulled copy (`cmp` against
    `kernel/probe_held.py`, carriage-return count, metadata fields);
  - one read-only Kaggle listing for the last run time.
- **Outputs:**
  - sha256 of the log, `summary.json`, `analysis.json` and the npz files concatenated in name order;
  - the void-rule fields of `summary.json`;
  - npz names against episode keys;
  - the log's key-scan, exit-code and games lines;
  - token-pattern counts over the log and both JSON files.
- **Numbers:**
  - arm totals rebuilt from the rows;
  - the four bootstraps recomputed in kernel order, with counts of resamples equal to 0;
  - exact McNemar and sign tests;
  - per-game differences;
  - the copy-right and static-wrong transitions in cn04 and ft09;
  - kept pieces, tried kinds and ranking positions in dc22 and tn36;
  - changed cells within and outside a level.
- **RESULT.md:** read in full against the numbers above and against the GO's conditions 3 to 6.
