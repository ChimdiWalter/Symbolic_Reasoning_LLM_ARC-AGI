# Specification-reading guide test: independent post-score audit

This audit was made on 8 Nov 2026, from about 11:17Z to 11:30Z, by the reviewer who wrote the pre-run review
(`reviews/PRE_RUN_REVIEW.md`, ab6e1378). It covers:
- `RESULT.md` (9a68c6c2, sha256 38a05df5...);
- `runs/held/RESULTS.json` (3b7f832f...);
- the sealed predictions (seal f0a05e1e...);
- `runs/SCORED`;
- the outputs commit 8753d21c;
- the GO commit 867d6096;
- `outputs/detached/sg_held/` and `sg_score/`.

**Verdict: PASS.** The custody holds from the freeze to the one scoring. Every number in RESULTS.json is reproduced by
my own scorer, built from the sealed predictions and the solutions. RESULT.md applies the pre-run conditions on three
points: the corrected 979 and 985 figures, an oracle confined to development, and secondaries named and decided by
Holm p together with the interval.

RESULT.md still contains one count error, one invalid CPU comparison and several overstatements. Section 3 gives the
exact replacement text, and those corrections are required before any paper or abstract quotes RESULT.md. Paper text
uses the sentences in section 4 and nothing in section 5.

## 1. Custody (verified)

**A single GO.**
- `runs/GO` has one commit, 867d6096 at 07:57:31Z. That commit contains exactly one path, `runs/GO`, and has no body
  and no trailers.
- The file has 7 lines, LF only, with a final LF and no CR. It names:
  - freeze_commit 4ba64f0c;
  - freeze_json_sha256 f397e0bb;
  - pre_run_review ab6e1378;
  - the conditions line;
  - a 64-character lowercase hex nonce.
- Its sha256 is 0da6cb29..., which equals the salt in `run.status`, RESULTS.json and every prediction row.

**The order of events.**
- The review was committed at 07:56:39Z and the GO at 07:57:31Z.
- `sg_held` was launched at 07:57:33Z, with `run.py held all` and `PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES=`, from the
  repository root.
- The autosave snapshots of 08:25Z, 08:56Z and 10:57Z show it running under `flock cpu_slot2.lock nice -n 19
  ionice -c3`.
- `run.status` records:
  - STARTED 07:57:37Z, with the salt and freeze commit 4ba64f0c, so the git custody checks had passed;
  - GENERATED 10:57:38Z, after the full 10,800-second limit;
  - ARMS_DONE 11:13:11Z;
  - SEALED 11:13:15Z.
- `sg_held` exited 0 at 11:13:19Z.

**The held set came from the salt.**
- `GEN_RECORD.0.json`:
  - seed 983696947230794157000, which equals int(salt[:16], 16) x 1000;
  - 1,128 admitted tasks;
  - 8,774 tasks traced, and 424,670 candidates skipped because their edit type had reached the cap;
  - 60 tasks for each of 17 edit types and for crop, and 48 for connect.
- An independent replay of the generator's candidate stream from that seed reproduced the first 1,051 of the 1,128
  held tasks exactly and in order: demonstrations, test input, test output, operation, family and source. The replay
  stopped at its 240-second limit.
- I recomputed every held task:
  - its family, rebuilt from the stored operation, is a held family (1,128 of 1,128);
  - its source task is in the held pool (1,128);
  - its four input grids are inputs of that source task (1,128).
- The set has 751 distinct families and 181 source tasks.
- 49 held tasks use an input grid that also occurs, identically, in a development-pool task. Excluding them changes
  no decision (section 2).

**The seal came before any solution was read.**
- `SEALED_PREDICTIONS` (11:13:15Z) names `predictions.0.jsonl` with sha256 918f2914. That digest equals the current
  file and the file at 8753d21c, and gives the joint digest f0a05e1e.
- `runs/SCORED` (mode 0444, 11:14:43Z) contains that joint digest.
- RESULTS.json was written at 11:14:46Z.
- The scorer's code checks the GO, git and the frozen hashes first, then compares the seal, then creates the marker
  exclusively, and only then opens solutions. My pre-run harness confirmed that order.
- The held run's code never opens solutions.
- **A disclosure, not a breach.** As the pre-run review anticipated, the half-hourly autosave stored the growing
  `tasks.0.jsonl` and `solutions.0.jsonl` in the private repository during generation, first in 18ffb0ee at 08:26Z.
  This is storage by git, not a read by any analysis.

**A single scoring.**
- One `sg_score` job: START 11:14:30Z, EXIT 0 at 11:14:46Z.
- No other scoring job for this study.
- One marker.
- RESULTS.json records the salt, freeze commit 4ba64f0c, the seal f0a05e1e and rehearsal false.

**The frozen hashes are unchanged.** At HEAD 565abff8:
- all 114 files match FREEZE.json, and the 107 tracked ones also match their HEAD blobs;
- FREEZE.json is still f397e0bb;
- the last commit that changed it is still 4ba64f0c.

The only study commit between the GO and the outputs that a person wrote is f11e3971, which changes PROGRESS.md
only. The others are autosaves of held outputs.

## 2. Recomputation (independent; everything matches RESULTS.json)

My own scorer read the sealed predictions and the solutions. Each of the 1,128 per-task correctness cells for 6
orders at 3 budgets equals RESULTS.json's: 0 differences.

**Correct test outputs, pass at 2, at each budget of counted operations.**

| order | 125 | 500 | 2,000 | share at 125, edit types weighted equally |
|---|---:|---:|---:|---:|
| hand-set | 953 | 1,008 | 1,087 | 0.844 |
| frequency table | 881 | 908 | 994 | 0.781 |
| linear model | 1,018 | 1,036 | 1,072 | 0.902 |
| small guide | 1,076 | 1,085 | 1,103 | 0.954 |
| specification-reading guide | 1,083 | 1,095 | 1,112 | 0.959 |
| shuffled-specification control | 1,050 | 1,058 | 1,088 | 0.931 |

**The primary at 125: met.** The test is the exact two-sided sign test. The interval is a 95% percentile interval
clustered by edit type, with 10,000 draws and `random.Random(20261105)`. Bootstrap seeds 1, 2 and 3 move each end of
the interval by at most 6 tasks.

| against | guide only | other only | difference | p | interval |
|---|---:|---:|---:|---|---|
| hand-set order | 147 | 17 | +130 | 5.2e-27 | 78 to 188 |
| frequency table | 207 | 5 | +202 | 1.1e-54 | 99 to 316 |
| linear model | 68 | 3 | +65 | 5.1e-17 | 25 to 109 |

**The second budget point, 500 operations:** the guide beats all three again.
- Hand-set order: 100 against 13, interval 55 to 122.
- Frequency table: 191 against 4, interval 85 to 300.
- Linear model: 62 against 3, interval 19 to 103.

**The secondaries at 125, Holm over three.**
- **Against the small guide:** 22 against 15, p 0.324, Holm p 0.324, interval -12 to 27. Inconclusive; this is the
  expected tie.
- **Against the shuffled control:** 52 against 19, p 0.00011, Holm p 0.00022, interval -6 to 81. Inconclusive,
  because the interval crosses 0.
  - The margin comes from a few edit types: outline +18, mirror_copy +10, duplicate +7, gravitate and scale +4 each.
  - It is negative for fill_box (-5), connect (-4), outbox (-2), move (-1) and extend (-1).
- **The linear probe:** a trained-encoder accuracy of 0.6463 against 0.461 with random weights (the most common edit
  type alone gives 0.0532). Tasks only the trained encoder gets right: 295; only the random one: 86. Holm p 2e-27,
  interval 134 to 291: the trained encoder beats random weights.
- Not pre-registered: at 500 the guide beats its shuffled control (49 against 12, interval 1 to 84). This is
  descriptive and does not change the 125 decision.

**Robustness.** Without the 49 held tasks that use a grid shared with the development pool, every decision stands:
- primary, against the hand-set order: 145 against 17, interval 77 to 184;
- primary, against the frequency table: 199 against 5, interval 94 to 306;
- primary, against the linear model: 64 against 3, interval 24 to 103;
- small guide: 18 against 15, interval -14 to 20;
- shuffled control: 48 against 19, interval -8 to 75.

**Work.**

| order at 125 | counted operations | edit applications | CPU-s |
|---|---:|---:|---:|
| hand-set | 101,878 | 2,293,406 | 131.8 |
| guide | 106,010 | 2,411,280 | 22.6 |

- 582 tasks reach the 125 budget under every order.
- Hole setup: 365.4 CPU-s. The total over task rows is 1,501.5 CPU-s, of which about 195 s falls in no arm: the
  encoder passes and the other models' scoring.
- The hand-set order's CPU at 125 (131.8 s) is larger than at 2,000 (68.0 s) although it applies about 10 times fewer
  operations. The arms run in a fixed order on each task, the hand-set order first, so per-arm CPU is order-dependent
  and is not comparable across arms (pre-run review, note 2). Counted operations are comparable.

**Descriptive item missing from RESULT.md.** The guide's own edit-type head ranks the generating edit type first for
600 of 1,128 held tasks (0.532), and in its top three for 998 (0.885).

## 3. RESULT.md: what it gets right, and the required corrections

**Correct as written:**
- the custody paragraph;
- the result table;
- the primary and 500-operation figures;
- the secondaries table's numbers;
- the erratum: 985 without the summary and 979 with it, 5 gained and 11 lost, p 0.21;
- the oracle paragraph, which is development only, with no held oracle comparison;
- the secondaries, named and not numbered;
- "It is not new reach";
- the by-edit table, and the statement that the guide and the small guide differ by at most 5 tasks in any edit
  type;
- the label and the precedents;
- lesson 2's main point, that the gain is learned guidance on the step's own analysis and not raw-specification
  reading;
- lesson 4.

**Required corrections.** Each item gives the current text, followed by the exact replacement. Line numbers refer to
9a68c6c2. Current text that runs over several lines of the file is quoted with its line breaks and indentation
collapsed to single spaces.

1. **The count (line 12).** "60 for each of 18 edit types and crop" would make 1,188.
   - Current: `- 1,128 tasks in all, 60 for each of 18 edit types and crop, and 48 for connect;`
   - Replace with: `- 1,128 tasks in all: 60 for each of 17 edit types and for crop, and 48 for connect, the 18th edit type, which was still short of 60 when the 10,800-second generation limit ended;`
2. **Where the rule comes from (lines 47, 52 and 58).** The frozen protocol says "Holm over three". The interval
   requirement for secondaries was fixed in the pre-run review's condition 5, which the GO accepted.
   - Line 47:
     - Current: `as frozen):`
     - Replace with: `as fixed before the run in the pre-run review's condition 5, accepted in the GO):`
   - Line 52:
     - Current: `so the frozen rule is not met`
     - Replace with: `so the pre-registered rule is not met`
   - Line 58:
     - Current: `**refuted** under the frozen rule.`
     - Replace with: `**not met** under the pre-registered rule.`
     - "Refuted" overstates the evidence against: the sign test favours the guide 52 to 19.
3. **The Work paragraph (lines 62 to 64).** The CPU comparison is a run-order artifact.
   - Current: `**Work.** The guide's 1,083 at 125 operations used 106,010 counted operations and 22.6 CPU-s of search. The hand-set order's 953 used 101,878 operations and 131.8 CPU-s.`
   - Replace with: `**Work.** At the same budget of 125 counted operations per task, the guide used 106,010 counted operations in all and the hand-set order 101,878; 582 of the 1,128 tasks reach the budget under every order. Per-arm CPU is not comparable in this run: the arms ran in a fixed order on each task, the hand-set order first on cold caches (its 125-operation run took 131.8 CPU-s, more than its 2,000-operation run's 68.0), and the guide's encoder time is counted in the task total, not in its arm.`
   - Keep the following sentence on the 365 CPU-s setup.
4. **Lesson 1 (lines 91 and 94 to 95).** Only three simple orders were tested, and the CPU artifact repeats here.
   - Heading:
     - Current: `**A learned order beats every fixed or simple order by a wide margin at a binding budget.**`
     - Replace with: `**A learned order clearly beats each of the three simple orders tested (the hand-set order, the frequency table and the linear model) at a binding budget.**`
   - Sub-bullet:
     - Current: `- Its 1,083 against the hand-set order's 953 is +130, with a search that cost 106,010 counted operations and 22.6 CPU-s against 101,878 and 131.8 CPU-s.`
     - Replace with: `- Its 1,083 against the hand-set order's 953 is +130 at the same budget (106,010 against 101,878 counted operations in all).`
5. **Lesson 2 (lines 100 and 102).** The mechanism was not tested, and a null difference agrees with a prediction;
   it does not confirm it.
   - Line 100:
     - Current: `- The step's pair analysis already reduces`
     - Replace with: `- A likely reason, not tested here, is that the step's pair analysis already reduces`
   - Line 102:
     - Current: `- This confirms the development finding, stated before the run.`
     - Replace with: `- This agrees with the development finding, stated before the run.`
6. **Lesson 3 (lines 103 to 105).** The probe's label is the edit type, and a "family" in this study is the full
   edit, parameters, predicate and view string. The probe is a separate regression, not the encoder naming anything.
   - Current: `**The encoder does learn the operation families.** It names the generating edit type with 64.6% cross-validated accuracy from its summary alone, against 46.1% for random weights and 5.3% for the most common type. The knowledge is there, but the block-ordering decision does not need it, because the deduction has already settled it.`
   - Replace with: `**The encoder does learn the edit type.** A linear probe on its summary recovers the generating edit type with 64.6% cross-validated accuracy, against 46.1% for the same architecture with random weights and 5.3% for the most common type. The information is there, but it did not make the block order measurably better than the step's own features; a likely reason is that the step's deduction has already settled the choice.`
7. **Lesson 5 (lines 109 to 111).** The cause is not established. On validation the frequency table and the hand-set
   order were level: 879 and 877, and 494 and 496 on the view capped at 60 per edit type.
   - Current: `**Static priors break when the operation mix shifts.** The frequency table, learned on the unbalanced training mix, falls below the hand-set order on the balanced held set (881 against 953). Learned orders that condition on each task's own features do not.`
   - Replace with: `**A static prior did not carry over to the held set.** The frequency table, learned on the unbalanced training mix, falls below the hand-set order on the held set (881 against 953), although the two were level on validation (879 and 877). This comparison was not pre-registered and its cause is not established. The learned orders that condition on each task's own features stay above the hand-set order.`
8. **Lesson 6 (line 113).** The term "ceiling" was undefined, and these are development data.
   - Current: `fits 102 or 103 of 134 at 125 operations, against a ceiling of 104.`
   - Replace with: `fits 102 or 103 of 134 at 125 operations (development data), against 104, the most any order reaches at 2,000 operations; in the earlier held run the guide, the linear model and the frequency table scored 318 to 323 against the 329 that the step reaches at 20,000 operations.`
9. **Section 3, item 2 (line 123).**
   - Current: `represents operation families from raw pairs.`
   - Replace with: `represents the edit type from raw pairs.`

**Recommended additions, not required.**
- **Custody:** "During the run, the half-hourly autosave stored the growing tasks and solutions files in the private
  repository (from 08:26Z). The run's code never opens solutions, and the scorer opened them only after the seal
  check and the marker. An independent replay from the seed reproduced the first 1,051 held tasks exactly."
- **Descriptive:**
  - the edit-head figures (0.532 top-1, 0.885 top-3);
  - the shuffled-control margin by edit type (section 2);
  - the 49 shared-grid tasks, with the unchanged decisions.

## 4. Sentences the papers may use

Use them as written, or shortened without changing a number or qualifier. Before use, define "counted operation"
once: one application of a candidate program to a grid.

1. "We tested a learned, specification-reading guide: a small transformer encoder over a task's input and target grid
   pairs, joined to a head that also reads the object-level step's own analysis of each search block, used to order
   those blocks."
2. "Code, weights and protocol were frozen and independently reviewed before any held task existed. The 1,128 held
   tasks were then generated from a seed derived from the hash of a committed authorisation file, using operation
   families and input grids reserved before development. The predictions were sealed before a single scoring."
3. "At 125 counted operations per task, the guide answered 1,083 of the 1,128 held tasks, against 953 for the
   hand-set order, 881 for a frequency table and 1,018 for a linear model. It beat each of the three: 147 tasks
   against 17, 207 against 5, and 68 against 3, with 95% intervals clustered by edit type of +78 to +188, +99 to
   +316 and +25 to +109 tasks."
4. "The held tasks are generated from ARC-AGI-2 public training input grids, and each was admitted only if the same
   frozen step solves it in its hand-set order within 20,000 counted operations. The gain is therefore search
   efficiency at a binding budget, not new reach."
5. "A guide that reads only the step's own block features, without the raw specification, answered 1,076. The
   difference of 7 tasks (22 against 15) is not significant. The held data thus give no evidence that reading the
   raw specification adds to what a learned order already gets from the step's own analysis."
6. "Feeding the guide another task's specification cost 33 tasks (52 against 19). The loss was concentrated in a few
   edit types, and the interval clustered by edit type included zero (-6 to +81), so the pre-registered test that
   the guide uses the specification's content was not met."
7. "A linear probe on the encoder's summary recovered the generating edit type for 64.6% of held tasks, against 46.1%
   for the same architecture with random weights. The encoder learned edit-type information, but that did not make
   the block order measurably better than the step's own features."
8. "Development had shown the same before the run: on validation, the same small learner scored 985 of 1,000 without
   the specification summary and 979 with it."
9. "An earlier tie between a learned guide and a frequency table on natural tasks (320 against 318 at 500
   operations) is consistent with a ceiling effect: the guide, the frequency table and a linear model (323) were all
   within 11 tasks of the 329 that the step reaches at 20,000 operations."
10. "What failed is informative. The step's own deduction already settles which block to try, so a specification
    reader is better aimed at choices that the deduction leaves open, such as predicates and parameters; this is a
    hypothesis for the next test."
11. "This is a step toward neural guidance for program synthesis, after DeepCoder, RobustFill, BUSTLE, CrossBeam,
    LambdaBeam and neural-guided deductive search. It is not a transformer that synthesises programs."

## 5. Do not write

- "the transformer for program synthesis", "a neural program synthesiser", or any wording that has the transformer
  synthesise programs.
- That reading the specification caused the gain, or that the guide beats the small guide.
- That the guide uses the specification's content as an established finding. Do not use the 500-operation shuffled
  result (49 against 12) to support it.
- The opposite overclaim: that the shuffled control shows the specification's content does not matter, or that spec-3
  "refutes" its use.
- Any held oracle figure, or "close to the oracle" on held tasks. The oracle (999 of 1,000 at 125) is development
  only.
- "beats every fixed (or simple) order". Only three were tested.
- "solves more tasks" or "new reach" without the budget. At 20,000 operations the step solves every held task.
- Any CPU ratio between orders, including 22.6 against 131.8 CPU-s, or "cheaper" or "faster" in CPU. That comparison
  is a run-order artifact.
- "static priors break when the mix shifts", or any other causal reason for the frequency table's drop.
- "generalises to unseen operations" or "unseen edit types". The held families are unseen combinations of known edit
  types, views and predicate kinds.
- "the encoder learned the operation families". The probe's label is the edit type.
- "held ARC tasks" or "ARC-AGI-2 tasks". These are tasks generated from ARC-AGI-2 public training input grids.
- "p = 0". Write the exact value, or p < 10^-16.
- "96% of tasks" without "of held tasks, all solvable by the step at 20,000 operations".
- Internal labels without definition: spec-1 to spec-4, v2, "block head", "Holm p" with no explanation.
