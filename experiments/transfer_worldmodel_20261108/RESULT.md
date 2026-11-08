# T4 world-model probe on 12 held public ARC-AGI-3 games: result

**Labels.**
- This is the held run of a probe on public ARC-AGI-3 games. It is not a score.
- It tests world-model induction (predicting the next frame exactly from 30 observed transitions), not game play.
- It is reconstruction of the games' own rules, not discovery.
- "Held" and "unseen" mean that no transition from these games was collected in this study before the run. The games
  themselves are public.
- Every number below comes from the kernel's own `analysis.json`: kernel `chimdiwalter/t4-arc-agi-3-world-model-probe`,
  version 5, private.

## Headline

1. **The primary did not pass.** On 12 held games, grown beat static on 302 transitions and lost on none. The exact
   next-frame rate rose from 0.285 to 0.380 (+0.095). But the pre-registered 95% interval from the bootstrap over games
   is [0.0, 0.232]. A lower bound printed as 0.0 is not above 0, so the claim is not supported.
2. **The gains sit in 3 of the 12 games and come from two kinds of piece.**
   - "The first cell of a colour, in scan order, turns into another colour": a step counter, in lf52 (+202
     transitions) and tu93 (+21).
   - "The cells the actor leaves turn one colour": a trail, in dc22 (+79).
3. **Grown against shuffled.** This comparison is the only basis for judging the failure description's contribution.
   - Grown beat shuffled on 79 transitions and lost on none, +0.025 with interval [0.0, 0.076].
   - All 79 are in dc22. There, the item's own ranking reached the trail piece, and the other game's ranking did not
     reach it within the budget.
   - In lf52, tu93 and tn36 both arms kept the same kind of counter piece.
   - So the item's own ranking gave grown an advantage in one held game, dc22, and in no development game. The
     failure description's contribution is not established.
4. **Development context.** All 23 development gains came from one piece type in 4 of 13 games. That type was the step
   counter, in bp35, r11l, s5i5 and vc33.

## Validity: the void rule

The run counts. Every condition in the GO was checked against the kernel's outputs:
- `summary.json` shows mode `held`, salt `989cb0ca9c21811144356d83955cae5ca76ec6c6` and `n_games` 25;
- `held_games` are exactly tu93, su15, re86, lf52, sb26, ka59, ar25, tn36, sc25, cn04, ft09, dc22, in that order;
- all 72 episodes and all 72 npz files come from those 12 games only;
- the log says `key-scan: clean`.

## Run record

**Kernel versions.** Each time is the push time.

| Version | Time | What it was |
|---|---|---|
| 1 | 06:13Z | development: collection only |
| 2 | 06:29Z | development: analysis |
| 3 | 06:36Z | development: the analysis step failed (a bug in summing) |
| 4 | 06:41Z | development: the frozen code in dev mode |
| GO commit | 07:04:12Z (ed754a3d) | after review 4330bfd9 |
| 5 | 07:05:21Z | **the held run**, finished at 07:11Z |

Version 5 is the first version after version 4 and after the GO. There was no re-push.

**The code that ran.**
- I pulled version 5's code back from Kaggle. Its sha256 is `c4b126bd55ca6c12dc6d1ef5dec87614a7cddc6c6c0ff29a150fbbaa5f1f2682`, which matches the frozen
  `kernel/probe_held.py`.
- Line endings were unchanged: the hash is the same with or without normalising them.
- The pulled metadata shows the kernel is private, with no competition or dataset source.
- The log line `games: 25 held: [...]` and the field `mode: held` in `analysis.json` cross-check this.

**Coverage.**
- 12 games had items, giving 72 items and 3,168 test transitions.
- There were no timeouts and no excluded episodes.
- Episodes: 48 reached 80 steps and 24 ended in GAME_OVER.
- Collection reported no errors.

**Cost.**
- Collection took 14.0 CPU-seconds.
- The analysis took 935 CPU-seconds in all, over 286 seconds of wall time on 4 workers, all on Kaggle.
- Athe ran no game code.

**Environment.**
- Python 3.12.3, arc-agi 0.9.9 and arcengine 0.9.3, as printed in `summary.json`.
- numpy and uv were not pinned, and numpy's version is not recorded.

**Game versions.** The held games' version ids were not recorded. They were the versions served on 8 November 2026.

**Output digests (sha256).** The files are in `data/kernel_output/v5/`, which git ignores. They are private and kept
out of any public snapshot.

| File | sha256 |
|---|---|
| log `t4-arc-agi-3-world-model-probe.log` | `3f9185efb156545556e8ee21ac4731227a73438f29ae227eb7c245063cda4906` |
| `summary.json` | `e529820f102c7a17f5c862777837387294f8ebefe66dd625e2b3a0ba77c756e2` |
| `analysis.json` | `40fa49b9528962bb25c1df83e03765dd78dc3bdbdd79a06c7108b9b1d2c325f0` |
| the 72 npz files, concatenated in name order | `cbfa6792b2c621723d901cee86f92873c1562f413ff42c8c5adba87549f9c95d` |

## Numbers (held; from `analysis.json`)

**Exact next frames.** A test transition counts when the whole 64 by 64 frame is predicted exactly.

| Arm | Exact next frames | Rate | Changed-cell accuracy | Within a level: exact |
|---|---|---|---|---|
| copy-previous | 930/3168 | 0.294 | 0/78521 | 923/3144 |
| tabular | 930/3168 | 0.294 | 0/78521 | 923/3144 |
| static | 902/3168 | 0.285 | 10587/78521 (13.5%) | 896/3144 |
| grown | 1204/3168 | 0.380 | 11567/78521 (14.7%) | 1197/3144 |
| shuffled | 1125/3168 | 0.355 | 10911/78521 (13.9%) | 1118/3144 |

**Pre-registered comparisons.** These use transitions, with the interval from 10,000 bootstrap resamples over games.

| Comparison | Difference | 95% interval | Transitions only the first got right | Only the second | Exact McNemar p (ignores clustering) |
|---|---|---|---|---|---|
| **grown against static (primary)** | +0.0953 | **[0.0, 0.2316]** | 302 | 0 | 2.5 x 10^-91 |
| grown against shuffled | +0.0249 | [0.0, 0.0764] | 79 | 0 | 3.3 x 10^-24 |
| grown against tabular | +0.0865 | [-0.0105, 0.2289] | 302 | 28 | 3.4 x 10^-59 |
| grown against copy-previous | +0.0865 | [-0.0108, 0.2296] | 302 | 28 | 3.4 x 10^-59 |

**Unregistered item-level sign tests.** These were not pre-registered.
- Grown beat static on 17 items and lost on 0 (p = 1.5 x 10^-5).
- Grown beat shuffled on 6 items and lost on 0 (p = 0.031).
- Static against copy-previous, on exact frames: static was higher on 0 items and lower on 5 (p = 0.0625).

**Per game, exact next frames.**

| Game | Test transitions | copy-previous | tabular | static | grown | shuffled | Pieces grown kept (items) |
|---|---|---|---|---|---|---|---|
| ar25 | 300 | 48 | 48 | 48 | 48 | 48 | none |
| cn04 | 270 | 54 | 54 | 51 | 51 | 51 | none |
| dc22 | 300 | 71 | 71 | 71 | **150** | 71 | trail (6) |
| ft09 | 300 | 261 | 261 | 236 | 236 | 236 | none |
| ka59 | 300 | 32 | 32 | 32 | 32 | 32 | none |
| lf52 | 300 | 0 | 0 | 0 | **202** | 202 | counter (6) |
| re86 | 300 | 5 | 5 | 5 | 5 | 5 | none |
| sb26 | 300 | 199 | 199 | 199 | 199 | 199 | none |
| sc25 | 192 | 33 | 33 | 33 | 33 | 33 | none |
| su15 | 300 | 227 | 227 | 227 | 227 | 227 | none |
| tn36 | 186 | 0 | 0 | 0 | 0 | 0 | counter (6), neighbour toggle (1) |
| tu93 | 120 | 0 | 0 | 0 | **21** | 21 | counter (6) |

The shuffled arm kept a counter piece in lf52, tn36 and tu93 (6 items each), and kept nothing in dc22. In tn36 the
counter piece was kept in all 6 items, yet no arm predicted any frame exactly (0 of 186): a kept piece fixes observed
cells, and it need not give an exact frame.

## Result → lesson → direction

1. **Primary.**
   - *Result:* the pre-registered test of language growth by build-and-check did not pass on the 12 held games. The
     point gain is +0.095 and grown never lost a transition to static (302 against 0). But the interval over games is
     [0.0, 0.232].
   - *Lesson:* the gains live in 3 of 12 games, so a bootstrap over games cannot exclude zero. A resample of 12 games
     misses all three with probability (9/12)^12, about 0.032, which is above 0.025. Growth helps only where a game
     shows a regularity the piece kinds can express.
   - *Direction:*
     - test on more games (the next public release, or a larger pool), with a game-level analysis pre-registered to
       match where the effect lives;
     - widen the piece kinds toward the changes that are not yet modelled. Changed-cell accuracy is only 14.7%.
       Which changes are missed was not measured. 99.7% of the changed cells (78,318 of 78,521) lie in transitions
       within a level, and no level was completed in a test transition, so the missed changes happen inside levels.
       Finding them needs an exploratory look at the held frames.
2. **The failure description.**
   - *Result:* grown beat shuffled only in dc22, by 79 transitions, interval [0.0, 0.076]. Elsewhere both arms kept
     the same kind of counter piece.
   - *Lesson:* in the three games where grown kept the step-counter piece, the borrowed ranking also reached it within
     its 12 tries. Only in dc22 did the item's own ranking reach a kind that the borrowed ranking never tried, the
     trail. One game cannot establish a contribution.
   - *Direction:* tighten the control (a smaller build budget, or ranking against a pool of games that lack the kind)
     and add games. Until then, the failure description's contribution stays unestablished.
3. **A base rule that hurts.**
   - *Result:* static was less exact than copying in cn04 (51 against 54) and ft09 (236 against 261). Its fitted move
     or click rule fires where nothing changes. Grown inherits those errors: in cn04 and ft09 it kept no piece, so its
     model is static's. The loop refits the base rule's parameters after it keeps a piece, but it never drops or
     re-chooses the base rule.
   - *Lesson:* an over-general base rule costs exactness that copying keeps.
   - *Direction:* let the loop revise or drop a base rule (the REVISE actions of the shared diagnostician), under the
     same held check.
4. **Transfer of piece kinds.**
   - *Result:* the counter kind traces back to the publisher's own public example game, the energy bar of ARCEngine's
     complex_maze, which the substitute imitated. It was kept in 3 held games and raised exact predictions in 2 of them
     (lf52 and tu93). The trail kind came from a substitute family (trail painting) and was first used on a held game.
   - *Lesson:* two piece kinds written for public rule sets were kept on unseen ARC-AGI-3 games and raised exact
     predictions in 3 of the 12. The pre-registered test of that gain did not pass, so this describes the run and does
     not establish transfer.
   - *Direction:* grow the kind library from failures across games, not per item, with a held check across games.

## Notes the review asked for (section 4)

- **Interpretation.**
  - In development, the gain was one display convention, a step counter, in 4 of 13 games. On held games it was two
    conventions (counter and trail) in 3 of 12.
  - With 12 games a percentile bootstrap over games can be narrow, and McNemar ignores clustering. That is why the
    McNemar p-values are tiny while the interval reaches 0.
- **The log and the key scan.**
  - The cleaning step in the kernel hides long tokens, including the comparison labels in the log, so `analysis.json`
    is the source.
  - "key-scan: clean", read together with `n_games` = 25, shows that a key was present (the anonymous route worked)
    and was found in no output file.
- **Records corrected.** These records are frozen or pre-data, so they are left unchanged and corrected here:
  - `DESIGN_NOTE.md` names the kernel `t4-arcagi3-worldmodel-probe`. The kernel is `t4-arc-agi-3-world-model-probe`,
    because Kaggle derived the slug from the title at the first push.
  - The ledger line committed at 06:08:21Z says "author 06:40Z". That is a typo: a line committed at 06:08Z cannot
    report 06:40Z.
  - In `DATA_MANIFEST.md`, "no game code" should read "no ARC-AGI-3 game code". The kept files include the MIT example
    and test games, which were read and never run.

## What comes next

- An independent post-score audit.
- Any local analysis of the held npz files is allowed only from this commit on, and is labelled exploratory.
