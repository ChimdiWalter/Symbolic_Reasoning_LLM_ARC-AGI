# T5 result: signalling logic models (CellNOpt network and DREAM data)

**What this file reports.** This is the single held scoring run under PROTOCOL.md, amendment 1. Every number is
held unless it is marked development.

**Custody record.**

| Step | Record |
|---|---|
| Freeze | commit cdd06c763a82fd06d06250c54d65a4289d0b1f12; FREEZE.json sha256 56640e776b5671c1d17d9028b51c93ed1ca0dab7f81df04a56471f4e630dd670 (25 files) |
| Pre-run review | FAIL on the first freeze, 72f31059 (commit ddd52d70) |
| Delta check | PASS on amendment 1 (commit 154831a3) |
| GO | GO.json, committed once and alone (commit 6ae7f578, 06:41:36Z) |
| Salt | sha256(GO.json) = ef7c8b8e641d14b36c48b37bf907933f1c835e45de846b0dcab063cb6b3055e3 |
| Run | launched by the coordinator at 06:41:36Z; got a CPU slot at 06:45:17Z; primary done at 06:50:57Z; ended at 06:51:16Z with exit 0 and no secondary failure |
| CPU | 358.4 CPU-seconds of the 1,800 cap (the primary alone, 339.8) |
| Results | `results_held/` (status.txt, tasks.jsonl, P1_RESULT.json, RESULT.json), committed at once as 7c343d56 |

RESULT.json records the provenance: Python 3.12.3, numpy 2.4.3, the GO and freeze commits and hashes, and git HEAD at
the start (413a6e52).

**Scope.** Any positive claim below is limited to "reconstruction of one removed prior edge (one of 6) on the DREAM
network and design", for three reasons:
- **Only 6 edges can be removed.** After CellNOpt preprocessing, only 6 of the 58 DREAM edges can be removed by the
  generator.
- **The static arm cannot win.** The removed edge is one the truth uses, so the static space cannot represent the
  truth, and grown against static is favoured by construction.
- **The primary was chosen after development.** It replicates a development finding on new draws.

## 1. Primary: synthetic tasks on the real DREAM network and experimental design

These results are held, synthetic and reconstruction. There are 200 tasks (200 seeds tried, none skipped), with 5 held
conditions per task, scored against the noise-free truth. Training values carry 5% flips.

| Arm | Exact held conditions |
|---|---|
| Static (prior network only) | 731/1000 |
| **Grown (built from the failure)** | **863/1000** |
| Shuffled-failure control | 805/1000 |
| CellNOpt-style comparator | 728/1000 |

| Hypothesis | Tasks won, lost, tied | Sign test p | Holm-adjusted p | Held conditions won and lost, McNemar p | Difference in exact proportion, 95% task bootstrap |
|---|---|---|---|---|---|
| H1: grown against shuffled | 50, 11, 139 | 4.6e-7 | 4.6e-7 | 84 and 26, 2.6e-8 | +0.058 [+0.037, +0.079] |
| H2: grown against static | 62, 12, 126 | 2.9e-9 | 5.7e-9 | 158 and 26, 2.9e-24 | +0.132 [+0.095, +0.171] |

**Decision rule.** The script computes it: Holm-adjusted p at most 0.05, and grown wins more tasks than it loses.
- H1 is supported (50 tasks won, 11 lost).
- H2 is supported (62 tasks won, 12 lost).

Both hold, so within the scope above, the loop transfers and the content of the failure matters.

Most of this gain comes from the 58 tasks that removed mek12 → erk12. Without them, the gain is 2.0 points over both
static and shuffled, and it is not significant (sign tests p = 0.15 and 0.17).

**What the shuffled control is, exactly.** In each growth round, one Sattolo cycle (a single cycle with no fixed
point) moves each failure description's condition sets.
- **Which columns move:** the cycle runs over the training columns, t1 and t0 together, so a moved condition can
  change time point.
- **What is kept:** the readout and the direction (ON or OFF) of each failure, the simulated state that scores the
  pieces, the repair and the acceptance, all on the real training data.
- **Strength:** this is a weaker control than a shuffle within each time point, because moved sets often land on t0
  columns, where most nodes are off. In this run, the shuffled arm kept a piece in its main growth in 50 of 200 tasks
  and passed acceptance in 48. The grown arm did so in 159 and 119.
- **What H1 shows:** that the content of the failure (which conditions, at which time point) matters, given the right
  readout and direction.

### 1a. Per removed edge (pre-registered, no gate)

Exact held conditions per arm, and tasks won and lost by grown:

| Removed edge | Tasks | Held conditions | Static | Grown | Shuffled | Comparator | H1 won, lost | H2 won, lost |
|---|---|---|---|---|---|---|---|---|
| mek12 → erk12 | 58 | 290 | 128 | 246 | 202 | 127 | 34, 3 | 45, 3 |
| mkk4 → p38 | 44 | 220 | 192 | 199 | 192 | 187 | 7, 3 | 8, 4 |
| map3k1 → mkk4 | 26 | 130 | 100 | 105 | 100 | 105 | 4, 1 | 4, 1 |
| map3k1 → ikk | 25 | 125 | 102 | 105 | 102 | 98 | 5, 3 | 5, 3 |
| mkk4 → jnk12 | 30 | 150 | 131 | 131 | 131 | 136 | 0, 0 | 0, 0 |
| map3k7 → mkk4 | 17 | 85 | 78 | 77 | 78 | 75 | 0, 1 | 0, 1 |

### 1b. Without mek12 → erk12 (pre-registered, no gate)

This analysis covers 142 tasks and 710 held conditions.

| Arm | Exact held conditions |
|---|---|
| Static | 603/710 |
| Grown | 617/710 |
| Shuffled | 603/710 |
| Comparator | 601/710 |

| Comparison | Tasks won, lost, tied | Sign test p | Held conditions won and lost, McNemar p | Difference, 95% CI |
|---|---|---|---|---|
| H1: grown against shuffled | 16, 8, 118 | 0.15 | 30 and 16, 0.054 | +0.020 [+0.003, +0.038] |
| H2: grown against static | 17, 9, 116 | 0.17 | 31 and 17, 0.060 | +0.020 [+0.001, +0.039] |

### Result, lesson, direction (primary)

- **Result.** Both pre-registered hypotheses are supported. Most of the gain comes from one edge:
  - mek12 → erk12 gives 118 of the 132 net held conditions of grown over static, and 44 of the 58 over shuffled;
  - development predicted this (113 of 134 over static).

  Without that edge, the gain is 14 of 710 held conditions (+2.0 points) against both static and shuffled. The sign
  tests are not significant (p = 0.15 and 0.17). The bootstrap intervals only just exclude zero.
- **Lesson.** The loop's pieces go only into failing readouts, from nodes in the learner's network. Of the 6
  removable edges, only mek12 → erk12 can be rebuilt exactly that way. Erk12 is a readout, and mek12 is a designated
  node (a readout and an inhibitor target), which preprocessing keeps. The grown arm rebuilt it and kept it in 51 of
  58 tasks. For mkk4 → p38 and mkk4 → jnk12, the target is a readout, but removing the edge lets preprocessing
  compress mkk4 out of the learner's network, so the edge cannot be rebuilt exactly. Their gains were +7 of 220 and
  0 of 150 held conditions. The other 3 edges feed intermediate nodes (map3k1 → mkk4, map3k1 → ikk, map3k7 → mkk4),
  with gains of +5, +3 and -1. This reading is descriptive; we did not test it separately.
- **Direction.**
  1. Let pieces target the ancestors of the failing readouts, with a failure description that pools several readouts.
  2. Test on larger prior networks where more edges can be removed, for example the 99-hyperedge ExtLiverPCB network
     already in `data/raw`.
  3. Until then, the primary supports transfer for reconstructing a removed prior edge that the pieces can rebuild
     exactly, which here is one of the 6 removable edges (mek12 → erk12). It does not show transfer for edges in
     general.

## 2. Secondary 1: the 25 real DREAM conditions

These results are held but labelled "development-exposed (format check printed the file at 05:31Z); underpowered".
They are real data, and a recovery here is a prediction of measured responses.

| Arm | Exact held conditions |
|---|---|
| Static | 14/25 |
| Grown | 14/25 |
| Shuffled | 14/25 |
| Comparator | 14/25 |

- **The pre-registered test.** For grown against static, the McNemar test is exact: 1 condition won (TNFa with the
  p38 inhibitor) and 1 lost (TNFa with the IKK inhibitor), p = 1.0. The fold-level sign tests and bootstrap are not
  pre-registered for this family, and no claim uses them.
- **What growth did.** It built pieces in all 5 folds and passed acceptance in 4. The shuffled arm passed in 0 of 5.
  Training errors fell in 4 of 5 folds:

| Fold | Training errors, static | Training errors, grown |
|---|---|---|
| 0 | 13 | 9 |
| 1 | 12 | 8 |
| 2 | 5 | 5 (growth rejected) |
| 3 | 13 | 7 |
| 4 | 9 | 7 |

  The pieces kept most often were igf1 → akt and sos → akt, which reach Akt without PI3K, and tnfa → ikb, a direct edge
  from TNFa to IkB. These are data-driven links, not tested hypotheses, and they come from development-exposed data.
- **Result.** On real data, growth lowered the training errors but did not change held exact recovery: 14 of 25 in
  every arm.
- **Lesson.** Here the pieces explain training conditions that do not carry over to the held ones. With 25 conditions
  and 7 readouts, a single fit can neither confirm nor rule out the bypass links.
- **Direction.** Test the bypass links (for example, Akt activity under PI3K inhibition) on an independent real
  dataset with more conditions, such as the cellnopt HepG2 and primary-hepatocyte sets. Pre-register this with an
  unexposed held split.

## 3. Secondary 2: the toy-network family

These results are held and synthetic, testing reconstruction. There are 100 tasks with 2 held conditions each.

| Arm | Exact held conditions |
|---|---|
| Static | 104/200 |
| Grown | 118/200 |
| Shuffled | 121/200 |
| Comparator | 104/200 |

| Comparison | Tasks won, lost | Sign test p | Held conditions won and lost, McNemar p | Difference, 95% CI |
|---|---|---|---|---|
| Grown against shuffled | 11, 13 | 0.84 | 22 and 25, 0.77 | -0.015 [-0.080, +0.045] |
| Grown against static | 22, 9 | 0.029 (no gate) | 40 and 26, 0.11 | +0.070 [-0.005, +0.145] |
| Shuffled against static | 18, 5 | 0.011 | 26 and 9, 0.006 | +0.085 [+0.030, +0.140] |

- **Result.** As predicted from development, the shuffled control matches the grown arm on the 12-node toy network.
- **Lesson.** In a small network, almost any piece that lowers the real training error helps. The content of the
  failure adds nothing measurable there.
- **Direction.** Judge the loop's specificity on larger networks only, and keep the toy network as a known null.

## 4. Secondary 3: the CellNOpt-style comparator

This comparator is a Python re-implementation, not checked against R, and it has no wall-clock stop. It is a
reference, not a gate.

| Family | Comparator | Static |
|---|---|---|
| Primary | 728/1000 | 731/1000 |
| Secondary 1 | 14/25 | 14/25 |
| Secondary 2 | 104/200 | 104/200 |

In the primary, the comparator against static won 12 tasks and lost 21 (p = 0.16).

- **Result.** CellNOpt's objective, under its own genetic algorithm over the static space, matches the static arm
  everywhere.
- **Lesson.** The gains of the grown arm come from growing the model space, not from a better search of the prior
  space.

## 5. The toy case (development, not scored again)

In leave-one-condition-out on the CellNOpt toy data:

| Arm | Exact held conditions |
|---|---|
| Grown | 9/9 |
| Static | 7/9 |
| Shuffled | 7/9 |
| Comparator | 7/9 |

The grown arm built Akt → NFkB. It stands in for the documented missing link PI3K → NFkB, because Akt follows PI3K in
every toy condition.

## 6. Descriptive notes

- **CPU per arm** in the primary, in CPU-seconds:

| Arm | CPU-seconds |
|---|---|
| Static | 65.8 |
| Grown | 212.1 |
| Shuffled | 1.3 |
| Comparator | 59.4 |

  These are descriptive only. The fold refits are memoised and paid by whichever arm needs them first.
- **Generator seeds:** 200 tried and none skipped in the primary; 100 tried and none skipped in secondary 2.
- **Correction (cosmetic).** ADAPTER_CARD.md gives 466 lines of scripts, but the frozen scripts have 469. The card is
  frozen, so it is not edited; this file and PROGRESS.md carry the correction.
- **Deviations from the protocol:** none. The run used the frozen files, one GO commit and one scored run.

## 7. Labels

| Result | Status | Data | Kind |
|---|---|---|---|
| Primary | held; replicates a development finding on new draws | synthetic tasks on the real DREAM network and design | reconstruction of one removed prior edge (one of 6) |
| Secondary 1 | held, development-exposed, underpowered | real | prediction of measured responses |
| Secondary 2 | held | synthetic tasks on the toy network | reconstruction |
| Secondary 3 | reference | Python re-implementation, not checked against R; no wall-clock stop | comparator |
| Toy case | development | real file, illustrative data | reconstruction |
