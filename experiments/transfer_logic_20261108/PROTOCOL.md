# Protocol: T1, circuit and access-control logic recovery with sparse probing

Study folder: `experiments/transfer_logic_20261108/`.
Author: Chimdi Walter Ndubuisi.
Written on 8 November 2026, before any held item was chosen or scored. Amended once (Amendment 1, section 10), also
before any held item was chosen.

## 1. Question

Does CORA's reasoning loop transfer to logic recovery through an adapter? The loop is:
1. propose a program from the current building blocks;
2. check it on the observations;
3. on failure, describe what is missing;
4. build the missing piece;
5. check again;
6. keep the piece only if it helps on held checks.

The test asks whether the loop recovers more Boolean functions exactly from sparse probes than two controls do: the
static base language, and the same loop fed a shuffled failure description.

Labels:
- circuit results are **real** (published benchmark functions);
- policy results are **synthetic from real seeds**;
- every result is **reconstruction** of a known function, not discovery.

## 2. Items and the split

Sources and licences are in DATA_MANIFEST.md.

**Circuits (real).**
- Eligible items: outputs of the Espresso example PLA files (MCNC benchmarks) with 6 to 12 inputs, completely
  specified and not constant, with repeats removed. That gives 573 items in 44 files.
- Each item is presented over all inputs of its file, so the learner is not told which inputs matter.
- Development files: a file is a development file when `int(sha256("T1-dev|" + file name), 16) % 4 == 0`. That gives
  9 files and 84 items, the only circuit items used in development.
- **Held-item hash rule.** Every other file (35 files, 489 items) is a held-candidate file. Inside each one, the items
  are ranked by `sha256(salt + "|" + item id)`, and the first 8 are held.
- The salt is the sha256 (64 hex characters) of the GO file. The coordinator writes and commits GO after the pre-run
  review. GO names the freeze commit and the FREEZE.json sha256 and carries a fresh 256-bit random nonce, so the salt
  is fixed after the freeze and the review, by someone other than the designer. The first committed GO is final; it
  is never redrawn or replaced.
- This gives **217 held circuit items** in 35 files.

**Policies (synthetic from real seeds).**
- 12 ClassBench seeds.
- Development: 4 policies per seed from the stream named "development" (48 in all).
- Held: 10 policies per seed from the stream `"held|" + salt`, generated only in the scored run. Constant policies,
  repeated functions and any function equal to a development policy are skipped.
- This gives **120 held policy items**.

## 3. Task, probes and the exact check

Item and probes:
- An item is a function T of n inputs, with n from 6 to 12 for circuits and n = 12 for policies.
- Probes are the first B inputs of a seeded random order of all 2^n inputs (seed "T1-probes-v1" and the item id),
  with B = ceil(f · 2^n).
- Each probe reveals T at that input. The held inputs are all the other inputs.

Fractions f:
- primary: 25%;
- secondary, circuits only: 12.5% and 50%.

**Exact recovery:** the arm's program equals T on every input, which means every probe and every held input. An arm
that returns no program has not recovered the item.

## 4. Arms

| Arm | Circuits | Policies |
|---|---|---|
| static | the base language: constants, literals and every two-input gate. The smallest fitting block is chosen (fewest inputs, then the most witness evidence, then canonical order), or no program | first-match lists of single-field rules, learned greedily (the pure rule covering the most remaining probes); no program if it gets stuck |
| grown (the CORA loop) | as static. When no block fits a node, the failure description names the input implicated by the closest conflicting probe pairs: witness edges first, then pairs two or three inputs apart. The missing piece is a Shannon cofactor split on that input, with both halves solved by the same loop | as static. When stuck, the failure description names the field implicated by the closest conflicting probe pairs. The missing piece is the best pure rule over the fewest fields that include that field, and its field set joins the library as a new template |
| shuffled control | the grown loop, with the described input replaced by a seeded random permutation of the free inputs | the grown loop, with the described field replaced by a seeded random permutation of the fields |
| reference (not a gate) | two-level minimisation with every unprobed input as a don't-care (in the style of Espresso), and scikit-learn's decision tree (CART, default settings, random_state 0) | the standard greedy decision-list learner with every arity allowed, and CART |

Notes on the arms:
- Step 6 of the loop is realised as a **verify flag**. The arm is rebuilt without each of 4 probe folds and must
  predict every left-out probe. The flag is a secondary measure; it does not change the primary.
- Grown contains static by construction: when the base language fits, grown returns the same program. So grown
  cannot lose to static on any item. What the primary measures is the size of the gain; the comparison with the
  shuffled control tests whether the failure description matters.

**Active probing (pre-registered secondary, grown arm).**
- The first B − 3c probes are the random ones, where c = floor(B / 4).
- In each of 3 rounds, a committee labels the unprobed inputs, and the c inputs where it is most split are probed.
  Ties go by random-order position.
- The committee is the grown program and 3 shuffled-route programs, all fitting every probe so far.
- This is compared with random probes at the same budget B.

## 5. Pre-registered primary

**Primary:** circuits (real) at f = 25%, exact held recoveries, grown against static.

**The same family also holds** grown against shuffled, with the same data and statistics.

Statistics for each comparison:
- the exact McNemar test (two-sided binomial test on the discordant items);
- the difference in exact-recovery rates, with a 95% paired cluster-bootstrap interval. Clusters are PLA files, and
  the bootstrap reuses the CORA U6 statistics module: 10,000 resamples from numpy default_rng(0);
- Holm's procedure over the two McNemar p-values.

A comparison is **supported** only when both hold:
- its Holm-adjusted test rejects at 0.05;
- its interval's lower bound is above 0.

## 6. Pre-registered secondaries

These are reported with Holm's procedure across the whole family:
- circuits at 12.5% and at 50%: grown against static, and grown against shuffled;
- circuits at 25%: active against random probes (grown arm);
- policies at 25%: grown against static, and grown against shuffled;
- policies at 25%: active against random probes.

Descriptive measures, with no test:
- the references against grown;
- the verify flag (verified items, and exact recoveries among them);
- held-input error counts;
- per-file and per-seed counts;
- CPU time.

## 7. Custody and stop rules

**Freeze.** FREEZE.json records the sha256 of two groups of files:
- every file the scored run uses: score_held.py, `tlogic/`, the reused U6 statistics module, config.json and the data
  archives;
- the documents and checks that define the run: DATA_MANIFEST.md, this protocol, ADAPTER_CARD.md, the unit tests and
  fetch_data.sh.

The development and helper scripts (run_dev.py, run_dev_budget.py, dev_summary.py and make_freeze.py) are not used by
the run and are not hashed. The freeze commit contains FREEZE.json.

**Before scoring.**
1. Report to the coordinator.
2. An independent pre-run review.
3. After Amendment 1, a delta check of the changed lines by the same reviewer.
4. The coordinator writes the file `GO` in this folder and commits it alone. GO holds:
   - the line `GO`;
   - `study: transfer_logic_20261108`;
   - `freeze_commit:` the 40-character hash of the amended freeze commit;
   - `freeze_json_sha256:` the sha256 of FREEZE.json at that commit;
   - `pre_run_review:` the commit hash of the check that clears the amendment;
   - `nonce:` a fresh 64-hex random value (256 bits), drawn once after the review;
   - `written_utc:` the time, as YYYY-MM-DDTHH:MM:SSZ.
5. Then one detached scoring run, launched from this folder:
   `sh ../../scripts/run_detached.sh transfer_logic_held --slot python3 -I score_held.py`.
   The run derives the salt itself; there is no salt argument.

**The run refuses** when:
- there is no committed GO whose first line is exactly GO. An uncommitted GO, an edited GO and a GO reading NO-GO all
  fail;
- GO was changed after its first commit;
- GO's freeze commit is not the last commit on HEAD that changed FREEZE.json;
- GO's FREEZE.json sha256 differs;
- GO's nonce is not 64 hex characters;
- any hash differs from FREEZE.json;
- the Python, numpy or scikit-learn version differs from FREEZE.json;
- results already exist.

**During the run.**
- The run creates `results/` and writes `results/run.status`, `results/held.jsonl` and `results/summary.json`. The
  status file and `summary.json` record the salt and the freeze commit.
- The launcher writes its command, logs, and START and EXIT lines to `outputs/detached/transfer_logic_held/`.

**Stop rules.**
- There is one scored run.
  - If it crashes before `summary.json` is written, it may be rerun once:
    1. rename `results/` to `results_attempt1/`, and keep and commit it;
    2. rerun with identical files and the same GO;
    3. say so in RESULT.md.
  - No other rerun is allowed.
- The run aborts at 30 CPU-minutes. An aborted run makes no primary claim and is reported as incomplete.
- Allowances:
  - each circuit fit has a 4,096-node allowance. It cannot bind at 6 to 12 inputs, because a tree has at most 2,047
    nodes;
  - each policy fit is capped at 512 rules.

  A fit that runs out returns no program, which counts as not recovered.
- No code, configuration or data changes after the freeze.
- Any deviation is written in RESULT.md, before the results.

**After the run.** RESULT.md reports:
- every number with its denominator, labelled held, real or synthetic, and reconstruction;
- every negative written as result → lesson → direction.

An independent post-score audit follows.

## 8. Expected cost

Development runs at the frozen settings took:
- 84 circuit items at one fraction: about 4 CPU-seconds;
- 48 policy items: about 61 CPU-seconds. Most of that is active probing.

The scored run has 217 circuit items at three fractions and 120 policy items at one fraction, so about 3 CPU-minutes
are expected. The cap is 30.

## 9. Development history that shaped this protocol

Development used only the 84 development circuit items and the 48 development policies; PROGRESS.md has the full
history. These points matter here:
- The primary fraction (25%), the file cap (8) and the circuit arms were set before the first development run.
- The policy budget was first 256 probes. A timing check showed that policy rules were too specific to be hit at that
  density, so the budget was changed to 25% before the first full development run. That check covered 3
  development policies and 6 development circuits.
- The policy growth rule was revised once, after a mechanistic diagnosis:
  - version 1 unlocked every rule of the new arity, so after the first grown rule the shuffled control searched the
    same language, and it tied grown 17 to 17 of 48;
  - version 2, the frozen one, adds only the described field set as a template.

Development caveats, stated before the run:
- **Grown only tied the decision tree.** At 25% on the 84 development circuit items, grown and CART both recovered 12,
  and the Espresso-style minimiser recovered 10. The loop matched the classical learners; it did not beat them.
- **The circuit gain was concentrated in one file.** alu1 gave 8 of grown's 12 development recoveries at 25%. Without
  alu1, grown recovered 4 of 76 items, static 1 and shuffled 1. No alu file is in the held pool.
- **Version 2 policy growth fell short.** It recovered 15 of 48 development policies. Version 1 and the full
  decision-list learner each recovered 17.
- **Shuffled also contains static.** When the base language fits, the shuffled loop returns the same program as
  static, so neither grown nor shuffled can lose to static on any item. A supported grown-against-static result
  therefore shows only that growth adds recoveries. The claim that the failure description matters, which is the
  transfer claim, rests on grown against shuffled, and RESULT.md's headline follows that comparison.

## 10. Amendment 1, 8 November 2026, made before any held item was chosen

**Reason.** The independent pre-run review (`reviews/PRE_RUN_REVIEW.md`, commit 99ec4245) failed the first freeze
(commit cb4369883501797581ff201a102923cefc2f43ef) on two custody defects:
- **The salt.** The salt was the freeze commit hash, which the designer chose and could have ground. The frozen check
  also accepted any commit that had the frozen tree, parentless copies included.
- **The launch line.** It redirected output into `results/` before that folder existed, so Python never started, and
  it bypassed the program's detached launcher.

The review passed the design.

**Changes.**
- **The salt.** It is now the sha256 of the committed GO file (section 2). `tlogic/data.py` accepts only a
  64-character salt.
- **The run's checks.** `score_held.py` derives the salt in its checks, which are the review's text plus two
  additions: the first-commit rule for GO and the version check. It records the salt and the freeze commit, creates
  `results/` itself, and has no salt argument.
- **The GO check is exact,** so "NO-GO" cannot pass.
- **The launcher** is `scripts/run_detached.sh` with a CPU slot (section 7).
- **The crash-rerun rule** is now explicit (section 7).
- **Section 9** states the four development caveats.
- **DATA_MANIFEST.md** adds the Berkeley copyright notice and the salt rule. It also says that `index.html` is
  provenance only.
- **ADAPTER_CARD.md** updates its line counts.
- **Wording.** Section 7 now lists exactly what FREEZE.json covers and gives the allowance for each domain.

No arm, item rule, fraction, statistic or data file changed. The held-candidate pool, the cap and the held counts
(217 circuits, 120 policies) are unchanged.
