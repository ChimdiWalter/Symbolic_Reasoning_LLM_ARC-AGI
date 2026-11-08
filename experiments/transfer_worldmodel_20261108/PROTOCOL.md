# T4 world-model probe on real ARC-AGI-3 games: protocol for the held run

**Labels.**
- This is a probe on public ARC-AGI-3 games held out by a hash rule.
- It tests world-model induction, that is, predicting the next frame from 30 observed transitions. It is not game
  play.
- It is reconstruction of the games' own rules, not discovery.
- It is not a competition score.

**Claim under test.** CORA's loop transfers to interactive game environments through an adapter. The loop has six
steps:
1. propose a model from the current building blocks;
2. check it on the observed transitions;
3. on failure, describe what is missing;
4. build the missing piece;
5. check again;
6. keep the piece only if it helps on a held check.

## Games, items and data

**Games.**
- The 25 games come from the toolkit's public list.
- The hash rule in DESIGN_NOTE.md split them. Its salt is `989cb0ca9c21811144356d83955cae5ca76ec6c6`, the commit of the
  design note, and it was fixed before any frame was seen.
- **Held, 12 games:** tu93, su15, re86, lf52, sb26, ka59, ar25, tn36, sc25, cn04, ft09, dc22.
- **Development, 13 games:** m0r0, r11l, lp85, wa30, ls20, sk48, s5i5, bp35, sp80, vc33, g50t, tr87, cd82.
- No transition from a held game has been collected or seen. Their ids appear in the development kernel's log, and
  nothing else about them does.

**Collection.** Collection is the same as in development and is set by `config/STUDY_CONFIG.json`:
- 6 episodes per game, with seeds 0 to 5, each of at most 80 steps;
- random available actions, excluding RESET;
- a click (ACTION6) takes, with equal chance, a uniform pixel or a uniform pixel not of the frame's most common colour.

**Item.** One item is one (game, episode) pair with at least 31 transitions.
- The *observed* transitions are the first 30.
- The *test* transitions are the ones after those, up to 50. They are never used for fitting.

**Representation.** The grid is the frame reduced by the largest block size s, from {8, 4, 2, 1}, at which every
observed frame is constant on s by s blocks. Predictions are scored at full 64 by 64 resolution.

## Arms

All arms see the same observed transitions.
- **copy-previous:** the next frame equals the current frame.
- **tabular:** memorise each (frame, action) pair seen in the observed transitions. An unseen pair gets copy-previous.
- **static:** the base rule language, fitted by search.
  - Move: an actor's colour shifts by a displacement learned for each non-click action, through passable colours.
  - ClickMap: the colour of a clicked cell changes by a learned map.
- **grown:** the loop.
  1. Fit the base language.
  2. Describe the wrong cells: rank 23 kinds of piece (one selector, one effect, one trigger) by how well each
     footprint matches the wrong cells.
  3. Build the top 3 kinds.
  4. Keep a piece only if three things hold: it lowers the wrong cells; it breaks no transition that was right; and it
     passes a held check, which refits the piece without one transition the piece fixes and requires that transition
     to be predicted exactly (at most 5 tries).

  The loop runs at most 4 rounds.
- **shuffled:** the same loop, but the ranking of piece kinds comes from the round-0 description of another game's
  item. The partner is the same episode in the next game (in sorted order) whose ranking is not empty.

## Pre-registered analysis

All statistics are computed inside the kernel by the frozen code.

**Primary.** The exact next-frame rate on the held test transitions, grown minus static.
- A test transition counts when the whole 64 by 64 frame is predicted exactly.
- The 95% interval comes from a bootstrap over held games: 10,000 resamples, numpy `default_rng(0)`, resampling games
  with replacement and pooling their transitions.
- **Decision rule.** The claim "grown beats static on unseen games" is supported if the lower bound of the interval is
  above 0.
- The exact McNemar test on paired transitions is also reported. It ignores clustering.

**Against shuffled.** The same statistics for grown minus shuffled. This tests whether the item's own failure
description matters. It is reported, not used as a gate.

**References, not gates.**
- grown against tabular;
- grown against copy-previous.

**Secondary measures:**
- changed-cell accuracy: among pixels whose true next value differs from the current frame, the share predicted
  exactly. Copy-previous scores 0 on this;
- both measures again on transitions that stay within a level;
- each game separately;
- the pieces accepted.

**Not tested here.** Two things are outside this probe:
- the pre-registered secondary on active probing, which was not built in the time available;
- game play itself.

## What development showed (development probe; not a score)

These come from kernel `chimdiwalter/t4-arc-agi-3-world-model-probe` version 4, which is the frozen code run in dev mode.
Its arm totals match version 2 exactly. The data are identical across versions 1 to 4: the npz files, concatenated, have
sha256 `f81ddf9e...`. Version 3 failed in the statistics step; that bug is fixed.

The run covered the 13 development games: 73 items and 2,933 test transitions. Five sp80 episodes were excluded because
they had fewer than 31 transitions.

| Arm | Exact next frames | Changed-cell accuracy |
|---|---|---|
| copy-previous | 636/2933 | 0/114130 |
| tabular | 636/2933 | 72/114130 |
| static | 747/2933 | 19767/114130 |
| grown | 995/2933 | 20255/114130 |
| shuffled | 1001/2933 | 20261/114130 |

Exact next-frame rate (development):

| Comparison | First arm | Second arm | Difference | 95% interval (bootstrap over games) | Transitions only the first got right | Only the second | Exact McNemar p |
|---|---|---|---|---|---|---|---|
| grown against static | 0.339 | 0.255 | +0.085 | [0.017, 0.197] | 248 | 0 | 4 x 10^-75 |
| grown against shuffled | 0.339 | 0.341 | -0.002 | [-0.007, 0.000] | 0 | 6 | 0.03 |
| grown against tabular or copy-previous | 0.339 | 0.217 | +0.122 | [0.045, 0.232] | 359 | 0 | 2 x 10^-108 |

- Grown beat static on 23 items and lost on none.
- Every gain comes from one kind of piece: "the first cell of a colour, in scan order, turns into another colour". This
  is a step counter or energy bar that loses one cell per step, seen in 23 items.
- The shuffled arm accepted the same piece, because counters are common across these games. So in development, the
  failure description added nothing over a wrong one.

**Expected outcome.** The primary is likely to be supported if held games also show step counters. Grown against
shuffled is likely a tie.

## The run, custody and stop rules

**Custody, in order:**
1. this protocol and FREEZE.json;
2. report to the coordinator;
3. an independent pre-run review;
4. the coordinator writes GO;
5. one held run;
6. RESULT.md;
7. an independent post-score audit.

**The held run.**
- The run is one new version of the kernel `chimdiwalter/t4-arc-agi-3-world-model-probe`, pushed from
  `kernel/probe_held.py`. FREEZE.json lists its sha256. To push it, copy it as `probe.py` into an empty folder with
  `kernel-metadata.json`.
- The kernel runs on Kaggle, detached from Athe. Its version number and status play the role of the `run.status` file.
  Every reported number is tied to that slug and version.

**Stop rules.**
- If the kernel fails before the analysis finishes, the same frozen file may be pushed once more. The failure is
  documented. There are no other reruns.
- An item that takes more than 300 seconds of wall time is dropped from every arm, and this is reported.
- Any change to a frozen file needs a dated amendment and a new freeze before the GO.

**Budget.**
- The kernel needs about 10 CPU-minutes. Development took 584 CPU-seconds in version 4, about 3 minutes of wall time
  on 4 workers.
- Athe runs no game code. It only reads the JSON outputs.

**Limits.**
- No competition rules are accepted and no submission is made.
- The anonymous key is fetched with silenced logging, and the outputs are scanned for it.
- The terms of the game files are not stated.
- No AI tool is named in any file.
