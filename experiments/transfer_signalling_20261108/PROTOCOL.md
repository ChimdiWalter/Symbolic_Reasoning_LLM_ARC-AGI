# T5 protocol: signalling logic models (CellNOpt network and DREAM data), amendment 1

**Status.**
- This protocol is frozen by the latest commit that changes FREEZE.json in this folder (the freeze commit).
- The salt of every held split is the sha256 of GO.json. The coordinator commits GO.json alone, after the review of
  this amendment (section 9).
- No held item is generated or scored before that commit.
- Amendment 1 replaces the freeze of commit 72f31059, which the pre-run review failed (commit ddd52d70). Section 12
  lists the changes.

## 1. Question

Does CORA's loop transfer to signalling logic models through an adapter? The loop runs:
1. propose a program;
2. check it on the observations;
3. on failure, describe what is missing;
4. build the missing piece;
5. check again;
6. keep the piece only if it helps on held checks.

In this domain, a program is a logic model over a prior network. Each node is an OR of terms, and each term is an
AND of signed inputs. The failure is the set of unexplained readouts. The pieces are new edges or gates. The test
asks two things:
- Does growing the model space from the failure improve exact predictions of held perturbation conditions over the
  static prior-network space?
- Does the content of the failure matter, judged against the same procedure fed a shuffled failure?

## 2. Data

DATA_MANIFEST.md gives sources, licences and checksums.
- **The real DREAM network and design:**
  - the 58-edge prior network of the HepG2 liver data;
  - its 25 perturbation conditions: no stimulus or one of 4 stimuli, crossed with no inhibitor or one of 4
    inhibitors;
  - 7 readouts.

  The real DREAM measurements are used only in secondary 1 (section 3).
- **The CellNOpt toy network and design:** 9 conditions and 7 readouts, used in secondary 2. The toy measurements
  were development data and are not scored again.

## 3. Families, labels and scope

**Primary (P1): synthetic tasks on the real DREAM network and experimental design.** These tasks are held,
synthetic and test reconstruction.
- **Number:** 200 tasks, generated after GO. Task i uses the label `held|<salt>|P1|<i>` for i = 0, 1, 2, and so on.
  A seed with no qualifying edge is skipped and counted, up to 2,000 seeds.
- **Truth:** a random program over the full preprocessed DREAM space, with each term on with probability 0.5.
- **Removed edge:** one prior edge that the truth uses, chosen so that removing it changes at least 2 readout values
  over the design. The count covers both t1 and t0 columns. The truth must also have at least 2 readouts that vary
  across the design.
  - The edge is taken out of the learner's prior network, which is then preprocessed in the same way.
  - A seed gets up to 200 truth draws to find a qualifying edge.
- **Data:** the truth's steady states. Each training value, t1 and t0, is flipped with probability 0.05.
- **Held conditions:** 5 per task, the 5 with the smallest sha256 of "label|condition key". They are scored against
  the noise-free truth, and the other 20 conditions train.

The generator is `t5.tasks.synthetic_task`. Development used the same generator under labels `dev|syn_dream|<i>`, and
no held label can equal a development label.

**Scope of the primary.** The pre-run review established three limits:
- **Only 6 edges can be removed.** After preprocessing, only 7 of the 58 DREAM edges survive unchanged, and removing
  one of them (ikk to ikb) always fails the build. So every primary task removes one of 6 edges:
  - mek12 to erk12;
  - mkk4 to p38;
  - map3k1 to mkk4;
  - mkk4 to jnk12;
  - map3k1 to ikk;
  - map3k7 to mkk4.
- **The static arm cannot win.** The removed edge is one the truth uses, so the static space cannot represent the
  truth. Grown against static is therefore favoured by construction.
- **The primary was chosen after development.** It was chosen after development showed this family positive and the
  toy family null. It replicates a development finding on new draws.

Any positive claim is therefore limited to "reconstruction of one removed prior edge (one of 6) on the DREAM network
and design".

**Secondary 1 (S1): the 25 real DREAM conditions.** These are real data, labelled "development-exposed (format check
printed the file at 05:31Z); underpowered".
- **Folds:** each condition is held once. The conditions are ranked by sha256("salt|LiverDREAM|condition key") and
  dealt round-robin into 5 folds of 5.
- **Training:** each fold trains on the other 20 conditions, with their time-0 rows.
- **What a recovery means:** a recovery is a prediction of measured responses in held conditions. It is not a
  discovery.
- **First contact:** this family meets the real DREAM values for the first time in the scored run. The file has 10
  missing t1 values, which the code handles.

**Secondary 2 (S2): the toy-network family.** These tasks are held, synthetic and test reconstruction.
- **Number:** 100 tasks with labels `held|<salt>|S2|<i>`.
- **Generator:** the same as the primary, on the toy network and design, with 2 held conditions per task. 7 of the 9
  surviving toy edges can be removed.
- **What development showed:** in development, the shuffled control matched the grown arm on this network:

| Training noise | Grown | Shuffled | Development tasks |
|---|---|---|---|
| None | 36/60 | 37/60 | 30 |
| 5% | 28/60 | 34/60 | 30 |

  We therefore expect no specificity on this small network, and the result is reported whatever it is.

**Secondary 3 (S3): the CellNOpt-style comparator.** It runs in every family and is labelled "Python
reimplementation, not checked against R; no wall-clock stop". CellNOptR's gaBinaryT1 also stops at maxTime, 60 s by
default. Leaving that stop out keeps the comparator deterministic. It is a reference, not a gate.

**The toy case.** This is a development case, already run and not scored again. In leave-one-condition-out on the
CellNOpt toy data:

| Arm | Exact held conditions |
|---|---|
| Grown | 9/9 |
| Static | 7/9 |
| Shuffled | 7/9 |
| Comparator | 7/9 |

The grown arm built Akt to NFkB. It stands in for the documented missing link PI3K to NFkB, because Akt follows PI3K
in every toy condition.

## 4. Arms

The arms are identical in every family; ADAPTER_CARD.md describes them in full.

**Static.** This is the prior-network space after CellNOpt preprocessing:
- remove nodes that are not observable or not controllable;
- compress single-input and single-output nodes;
- expand AND gates of up to 2 inputs.

The program is chosen by iterated local search with fixed seeds. It must have:
1. the fewest wrong training data points, with an NA prediction counted as wrong;
2. then the fewest inputs;
3. then the smallest bit string.

**Grown.**
- **Start and failure:** start from the static program. Describe the failure as, per readout, the training conditions
  measured ON but predicted OFF, or measured OFF but predicted ON, with the conditions that must not change.
- **Pieces:** build pieces into the failing readout: a new signed edge, a new 2-input AND gate, or a gate that
  extends an active term with one more input.
  - Each source must not be downstream of its readout in the current space.
  - That check is made per piece, so pieces added in the same round can still close a loop between readouts, and a
    grown program can be cyclic.
  - A cyclic program is simulated by synchronous iteration for ceil(1.2 × nodes) steps. Bits that do not settle are
    NA and count as wrong.
- **Ranking:** rank by want columns fixed minus kept columns broken. Take at most 2 pieces per failure and 6 per round.
- **Repair:** add each piece, in rank order, only if it lowers the training errors. A gate replaces the term it
  extends when that is better. Run at most 3 rounds.
- **Acceptance:** rebuild the whole growth inside 4 internal folds of the training conditions. Keep the grown program
  only if the rebuilt growth's fold errors are no worse than the static programs' (bar 0). Otherwise, return the
  static program.

**Shuffled control.** The same as grown, except that, in each round, one Sattolo cycle (a single cycle with no fixed
point) moves each failure description's condition sets before pieces are built.
- **Which columns move:** the cycle runs over the training columns, t1 and t0 together, so about half of the moved
  columns change time point.
- **What is kept:** the readout and the direction (ON or OFF) of each failure, the simulated state that scores pieces,
  the repair and the acceptance. All of these use the real training data.
- **Inside acceptance folds:** the cycle is redrawn over each fold's training columns.
- **Strength:** this is a weaker control than a shuffle within each time point, because moved sets often land on t0
  columns, where most nodes are off. H1 therefore tests whether the content of the failure (which conditions, at
  which time point) matters, given the right readout and direction.

**Comparator.** This is CellNOpt's objective over the static space, under CellNOpt's binary genetic algorithm with
the gaBinaryT1 defaults. The best string predicts.

**Compute.**
- It is not equal across arms. The grown and shuffled arms also run 4 rebuilt folds, and the comparator runs up to
  500 generations.
- CPU per arm is descriptive only, because fold refits are memoised and paid by whichever arm needs them first.

## 5. Outcome

**Exact held condition.** A held condition is exact when every measured readout matches. Each readout's predicted
steady-state value is compared with the value binarised at 0.5 (at least 0.5 means 1). An NA prediction counts as a
mismatch.

**Per-task outcome.** The number of exact held conditions: 0 to 5 in the primary, 0 to 2 in secondary 2.

## 6. Primary analysis

There are two hypotheses, Holm-adjusted at alpha 0.05 as a family of 2:
- **H1, grown against shuffled:** does the failure's content matter?
- **H2, grown against static.**

**Test.** An exact two-sided sign test over tasks on the per-task difference in exact held conditions, with ties
dropped. Each test is reported with:
- an exact McNemar test on conditions, which ignores clustering within tasks (a sensitivity check);
- a 95% percentile bootstrap interval for the difference in exact proportions, resampling tasks: 10,000 resamples,
  numpy default_rng(0), using `u6.stats` from the Boolean-network core.

**Decision.** The script computes and records this rule (`decision` in P1_RESULT.json).
- A hypothesis is supported when its Holm-adjusted p is at most 0.05 and grown wins more tasks than it loses.
- The claim "within the scope of section 3, the loop transfers and the failure's content matters" needs both H1 and
  H2.
- If only H2 holds, the report says "growth helps, but the failure's content is not shown to matter".
- The other outcomes are reported as negatives: result, lesson, direction.

**Pre-registered, with no gate:**
1. **Per removed edge.** A table giving, for each removed edge, the tasks, the held conditions, every arm's exact
   count, and wins and losses for H1 and H2 (`per_removed_edge`).
2. **Without mek12 to erk12.** H1 and H2, with sign tests over tasks, McNemar tests and bootstrap intervals, on the
   tasks whose removed edge is not mek12 to erk12 (`sensitivity_without_mek12_erk12`). In development that edge
   appeared in 48 of 160 tasks, and it gave:
   - 43 of the 62 net held conditions of grown over shuffled;
   - 113 of the 134 net held conditions of grown over static.

**Expected power (development).** Over 160 development tasks:

| Comparison | Tasks won | Tasks lost | Tasks tied | Sign test p |
|---|---|---|---|---|
| Grown against shuffled | 49 | 13 | 98 | 4.8e-6 |
| Grown against static | 61 | 13 | 86 | 1.4e-8 |

## 7. Secondary analyses (no gate; no claim rests on them alone)

- **Secondary 1:** the pre-registered test is grown against static, an exact two-sided McNemar test over the 25
  conditions (`mcnemar_p`). Every arm's count is reported. The script also computes sign tests and a bootstrap over
  the 5 folds. These are not pre-registered for this family, and no claim uses them.
- **Secondary 2:** grown against shuffled and grown against static, with sign tests over tasks and bootstrap
  intervals.
- **Secondary 3:** comparator against static and grown against comparator, in each family.
- **Descriptive:**
  - pieces built and kept;
  - how often the acceptance passes, per arm;
  - training errors;
  - CPU per arm;
  - generator seeds tried and skipped.

## 8. Frozen settings

All settings are in config_held.json, and all are as in development:

| Setting | Value |
|---|---|
| Search | 4 random restarts plus the empty and full programs; 4 perturbations of 3 flips per start |
| Growth | 3 rounds; 2 pieces per failure; 6 per round; 4 internal folds; bar 0 |
| Comparator | gaBinaryT1 defaults (popSize 50, pMutation 0.5, maxGens 500, stallGenMax 100, selPress 1.2, elitism 5); sizeFac 0.0001; NAFac 1 |
| Generator | flip 0.05; term probability 0.5; minimum effect 2 |
| Binarisation threshold | 0.5 |
| CPU cap | 1,800 CPU-seconds |

## 9. Held-split hash rule and salt

**The GO file.** After the change review, the coordinator commits `GO.json` in this folder, alone. It must hold
these keys:
- `freeze_commit`: the full hash of the latest commit that changed FREEZE.json;
- `freeze_json_sha256`: the sha256 of FREEZE.json;
- `utc`: the UTC time;
- `nonce`: 64 lowercase hex characters from `secrets.token_hex(32)`, drawn at GO time and shown to no one before the
  commit;
- the review hashes, under any further keys, for example `pre_run_review_sha256` and `change_review_sha256`.

**The salt** is the sha256 of the committed GO.json bytes.
- The primary and secondary 2 task labels contain the salt, and the secondary 1 folds are dealt with it.
- No held item can be computed by anyone before the GO commit, the designer included.

**Refusals.** `score_held.py` refuses to start unless all of these hold:
1. `results_held/` does not exist;
2. GO.json and FREEZE.json are byte-identical to their committed copies at HEAD;
3. GO.json has the required keys and a valid nonce;
4. its `freeze_json_sha256` is the sha256 of FREEZE.json;
5. its `freeze_commit` is the last commit that changed FREEZE.json, and an ancestor of the commit that last changed
   GO.json;
6. every file listed in FREEZE.json has its recorded sha256;
7. `--salt` equals the sha256 of GO.json.

`tests/test_go.py` checks these refusals on a throwaway repository: a valid GO passes, and 7 invalid cases are
refused.

## 10. Custody and the run

1. This amended protocol and the regenerated FREEZE.json are committed together, which makes the freeze commit.
2. Report the freeze commit and the FREEZE.json sha256 to the coordinator.
3. The same reviewer checks the changed lines.
4. The coordinator commits GO.json (section 9).
5. One detached scoring run, started right after the GO commit, from the repository root:

   `sh scripts/run_detached.sh t5_held_score --slot python3 -I
   experiments/transfer_signalling_20261108/scripts/score_held.py --salt <sha256 of GO.json>`

   The run writes `results_held/`, which holds status.txt, tasks.jsonl, P1_RESULT.json and RESULT.json, and
   `outputs/detached/t5_held_score/run.status`.
   - The primary's statistics go to P1_RESULT.json before any secondary runs.
   - RESULT.json records provenance: the Python and numpy versions, git HEAD at the start, the freeze commit, the
     FREEZE.json sha256, the GO commit and the GO.json sha256.
   - The results are committed right after the run ends (this folder only, with no trailers).
6. RESULT.md.
7. An independent post-score audit.

**Before the freeze.**
- The dry run (`--dry-run`, salt "DRYRUN", 3 primary tasks, 3 secondary-2 tasks, and the secondary-1 code path on the
  toy data) was run, and its output is in `results_dryrun/`, which is not held data.
- `tests/test_checker.py` (the review's three-node program) and `tests/test_go.py` pass.

## 11. Budget and stop rules

**Expected CPU.** About 8 CPU-minutes:
- the primary: 200 tasks at 1.7 to 2.6 CPU-seconds each in development;
- secondary 1: about 10 CPU-seconds;
- secondary 2: about 15 CPU-seconds.

The cap is 30 CPU-minutes, checked after every task of the primary and of secondary 2.

**Stop rules.**
1. **One scored run.** A crash or a budget stop during the primary fails the run. A failure in secondary 1 or 2 is
   recorded in RESULT.json and status.txt, does not void a completed primary, and is reported. A rerun needs a
   written amendment, reviewed before the rerun, and must use a new GO and salt.
2. **Refusals.** If any refusal check in section 9 fails, the run does not start.
3. **No changes after GO.** No code or configuration changes after GO.
4. **Too few tasks.** If 2,000 seeds give fewer than 200 primary tasks, the primary uses the tasks made, and the
   count is reported.
5. **Inside each task.** Growth stops when there is no failure, when no piece has a positive score, when no piece
   lowers the training errors, or after 3 rounds.

## 12. Disclosures and amendment log

- **Exposure.** At about 05:31Z, before any split rule existed, the full DREAM measurement file was printed to the
  terminal to check its format. No development run used a DREAM measured value. This is why the real DREAM test is a
  secondary and not the primary.
- **Development changes.** Two changes were made on the toy data, before any synthetic run:
  - minimal repair instead of a full refit with a least-error vote;
  - an acceptance bar of 0 instead of 1.

  The synthetic development families were run after these changes, with no further change.
- **The comparator.** It is re-implemented in Python from CellNOptR's documented objective and genetic algorithm,
  because R is not installed. Its scores have not been checked against R.
- **The checker.** It recomputes every final program with the Boolean-network core's evaluator. It uses the same step
  count and oscillation rule as the simulator, so a program that does not settle is scored as a mismatch. Any other
  disagreement stops the run.
- **Amendment 1**, following the pre-run review (`reviews/PRE_RUN_REVIEW.md`, commit ddd52d70):
  1. **The blocking defect.** The checker ran one step more than the simulator and stopped the run on programs that
     do not settle. The extra step is dropped, and `tests/test_checker.py` adds the regression test. Predictions come
     from the simulator and do not change; the dry-run numbers are identical before and after the fix.
  2. **The salt.** It was the freeze commit hash; it is now the sha256 of GO.json, as set out in section 9.
  3. **The primary's results.** They are written before the secondaries; a secondary failure no longer voids the
     primary; and the run refuses to start if `results_held/` exists.
  4. **The decision rule** is computed by the script.
  5. **New analyses without a gate:** the per-removed-edge table and the analysis without mek12 to erk12.
  6. **Scope and labels.** The scope statement, the exact description of the shuffled control, the secondary 1 test
     label and the secondary 3 label are added. The ADAPTER_CARD.md status line and the `grow.py` docstring are
     corrected.

## 13. Reporting

RESULT.md uses plain words and gives every number with its denominator. Every result carries its labels:

| Family | Status | Data | Kind |
|---|---|---|---|
| Primary | held; replicates a development finding on new draws | synthetic tasks on the real DREAM network and design | reconstruction of one removed prior edge (one of 6) |
| Secondary 1 | held, development-exposed, underpowered | real | prediction of measured responses |
| Secondary 2 | held | synthetic tasks on the toy network | reconstruction |
| Secondary 3 | reference | Python re-implementation, not checked against R; no wall-clock stop | comparator |

The shuffled control is described as in section 4. Every negative is written as result, lesson and direction.
