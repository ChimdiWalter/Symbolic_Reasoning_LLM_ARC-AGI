# Failure-guided choice test, revision 1: independent pre-run review

Reviewer: our independent review session, which did not build this test. Written 8 Nov 2026.

What I reviewed:
- protocol sha256 ccaa3e7cc074739e8c5198d632e9212e54df858fa3784fa823fad3aa1f68d011;
- freeze sha256 a38f51ae42a80769d45a3646e1bc88f0eec17ce0e12c8739c31f927b2503d2c3;
- freeze commit ce069bd6, plus the progress commit 03d8aeb7.

What I did not do: create a GO, generate or open a held task, or push anything to Kaggle. I opened no file of the
companion study's version.

Every rerun below used a scratch copy extracted from ce069bd6 and touched only the source set.

## Verdict: PASS-WITH-NOTES

There is no blocking finding. One procedural step must be added to the run instructions before the measurement step
(note 1). It changes no frozen byte.

GO lines I would accept, in `GO_FGC` in the study folder (the gate's file):

```
protocol_sha256 ccaa3e7cc074739e8c5198d632e9212e54df858fa3784fa823fad3aa1f68d011
freeze_sha256 a38f51ae42a80769d45a3646e1bc88f0eec17ce0e12c8739c31f927b2503d2c3
```

Write `GO_FGC` once and never edit it. Its exact bytes set the held set's salt, and every later stage requires the
claim to name the same bytes.

## 1. The freeze

- **Every digest matches.**
  - `FREEZE.json` lists 78 study files, 40 dependencies and 1 data file.
  - Every digest matches the working tree. Every tracked file also matches its blob in ce069bd6.
  - Six dependencies are git-ignored and pinned by digest only: the arc-dsl resources and A2's `out/corpus.json`. So
    is the data file, which lives outside the repository at `<ARC data folder>/arc-agi_training_challenges.json`
    (see note 4).
- **What it binds.**
  - The protocol, all of `fgc/*.py` and the three configuration files.
  - In `config/STUDY_CONFIG.json`: the test families, quotas, size caps and salt rule.
  - In `config/ROUTERS.json`: K_S, T*, the static order, F's rule and G's weights.
  - `launch/*.sh` and `checks/CONTRACT_CHECKS.json`.
  - The world copies, the source set and its measurements.
  - Every imported dependency, including the construction test's `cas/generate.py` Builder, and the ARC training
    challenges file.
- **The held-generation rule is bound.** It is `fgc/generate.py` `test()` together with the configuration. It uses the
  held families, quota T1, T2, T3, T1, T2, T3 per family (at most 36 tasks) and 6 depth tasks per world with a crop
  outermost (at most 18). It excludes every source of every world-copy task and every source of the source set.
- **No held task exists.** There is no `GO_FGC`, no `runs/RUN_CLAIM.json` and no `runs/test/`, now or anywhere in git
  history.
- **The salt comes from the GO.** `gate.claim_and_salt()` returns "fgc-test-" plus the first 16 hex digits of the GO
  file's sha256, after the generate stage passes. That stage:
  - checks that the GO lines bind the live protocol and freeze;
  - checks every frozen digest;
  - refuses if a claim or `runs/test/` exists;
  - creates the claim exclusively (`open(..., "x")`).

  So no held task can exist before the GO.

## 2. The full-bank contract (`fgc/contract.py`, `fgc/pipeline.py`)

- **One bank, one function.** Every arm, the oracle included, runs through `run_arm`, with the current task's own
  measurement (`ms[t]`). `fgc/pipeline.py` calls `K.run_arm` exactly twice, at seal and at score, and both pass `ms[t]`.
  `execute` runs only the two interventions of BANK, from that task's own measured search and construction records.
- **One meter, one budget.** One `Meter` per arm and task charges the base attempt's calls, then each intervention's
  calls. Every arm gets the same budget at each multiple of T*.
  - Search inside the bank gets `min(K_S, remaining)` for every bank arm. Arm B is the named exception.
  - Construction needs its complete measured calls; when it is cut off it commits nothing.
- **Arms differ only in order.** At sealing:
  - A gets no intervention; B gets search only, with every remaining call;
  - C gets the frozen static order (construction, then search);
  - D gets an order from sha256("random:" + id);
  - F gets the frozen rule applied to this task's descriptor; G gets the frozen regressions on that descriptor;
  - E gets F's rule applied to the donor's descriptor;
  - H is computed only at scoring, from the generator's cause, so sealing never reads an evaluator-only file.
- **The shuffled diagnosis uses only the donor's descriptor.** The donor is the next task in sha256("donor:" + id)
  order, so no task is its own donor. It enters only as `feats[donor[t]]`. A descriptor holds scalar features (sketch
  scores, closest-cell share, sizes, colour counts, shape class) and no grid. `run_arm` always receives the current
  task's measurement, so the donor's demonstrations, measurement and budget are never used.
- **Contract checks.**
  - I reran `fgc/contract_checks.py` in a scratch copy. The output is identical to the committed
    `checks/CONTRACT_CHECKS.json`: all 10 replays and all 9 properties pass.
  - I recomputed every replay by hand. The expected (predictions, committing intervention, calls) triples are all
    correct, including the K_S cap, arm B's full remainder, a construction cut off, and a search that exhausts its
    fragment early.

## 3. The four unmatched items (protocol section 5): disclosed and acceptable

1. **Named controls.** Arms A and B and the oracle H are named controls or an upper bound, not competitors of C.
2. **Free descriptor.** F, G and E read a descriptor that costs no calls; C and D need none. Its CPU is negligible,
   and the failure record's CPU is recorded.
3. **Construction in every arm uses the failure record.** Construction is built from the current task's own typed holes
   in every arm, C included. So the test measures failure evidence for *ordering* the bank, not inside construction.
   This is the right scope statement and applies symmetrically to F and C.
4. **No interleaving.** No arm interleaves or splits an intervention. This holds for all arms alike.

None of the four favours F or C in the primary. Each is stated where the protocol defines the contract.

## 4. The primary, the ladder and the expectation are pre-registered and implemented

- **Primary.** F against C at T* = 3,500,000 calls on exact correct query outputs. It uses the exact two-sided McNemar
  test on discordant tasks (`arms.mcnemar_exact`). The interval is a family-clustered percentile bootstrap of the mean
  paired difference, with families resampled, 10,000 draws and seed 7 (`arms.cluster_boot`). Success needs p < 0.05
  and the lower end above 0 (`pipeline.score`).
- **Secondaries and curve.** G against C, F against E and F against D are Holm-adjusted together. The budget curve
  runs at 0.25, 0.5, 1, 2 and 4 times T*.
- **Decision ladder.** `pipeline.decide` implements section 8 in order:
  1. selection advantage;
  2. static bank better;
  3. efficiency (only-F at least only-C, and the calls interval entirely below -175,000);
  4. capability (C against B at T*);
  5. coverage (C against B only at 4T*);
  6. none.
- **Expectation.** Section 9 states, before any held task exists, that no selection advantage is expected and that
  the decision should be capability or coverage.
- **Source development reproduced.** I worked from the sealed source predictions (digest checked) and the source
  labels. Results at T*: C 45, F 45, G 45, E 39, D 33, B 33 of 71.
  - C against B gives 16 against 4 tasks at T* (p 0.0118) and 18 against 3 at 4T* (p 0.0015).
  - The source decision is "coverage". All of this matches `runs/dev/source/ANALYSIS.json`.
- **"The router and the static bank choose identically" holds in effect, not literally.**
  - F's order differs from C's on 12 source tasks, where it puts search first on the depth signature. G's order
    differs on 33.
  - At all five budgets, F's and G's committed predictions and committing interventions are identical to C's on all
    71 tasks. On the 12 depth tasks, C's construction is rejected after about 900 calls and search then commits the
    same answer.
  - F saves 139 calls per task on average (interval -274 to -37).
- **Constants recomputed** from the source measurements:
  - the 90th percentile of the 27 depth tasks' correct-first-fit calls is 2,454,294 (the protocol says 2,454,826);
  - the 75th percentile of the oracle's spent calls over its 54 solves is 3,293,681 (the protocol says 3,293,679).

  The small differences come from the interpolation detail. Both pairs round up to the frozen K_S = 2,500,000 and
  T* = 3,500,000. The static order also reproduces: construction first 45 against search first 25.

## 5. Leakage and exposure

- **Disjoint families.** Source and held families do not overlap:
  - operation families: W1 upscale and downscale, W2 dmirror and rot90, W3 vupscale (source) against W1 compress and
    trim, W2 cmirror and rot270, W3 hupscale and switch (held);
  - depth families: reflect or rotate outermost (source) against crop outermost (held).
- **Disjoint sources.** Held tasks exclude every source grid used by any world-copy task (all partitions) and by the
  source set. Sources used are carried across worlds within the held build.
- **Exposure is disclosed.**
  - Section 3 says the held families were part of the construction test's worlds, and that their general behaviour
    under construction and static search was seen there.
  - Those worlds' own tasks of the held families stay in the world copies, as context for construction's gates. That
    is the same for every arm and disclosed there.
  - The source missing-operation tasks are the construction test's own, with outcomes seen.
  - F was hand-written from source failure records only.
- **Packaging.** The measurement kernels carry the held tasks' system view only: demonstrations and query inputs. They
  also carry each world's `evaluator_only/REMOVED.json`, which defines the world's grammar and names no task's cause
  or family.

## 6. Detached execution

- **The launch rule.** `PROGRESS.md` line 35 says every post-GO step longer than five minutes, and every sealing and
  scoring run, is launched as `sh ../../scripts/run_detached.sh <name> sh launch/run_job.sh <job> <frozen command>`.
  - `run_detached.sh` writes `outputs/detached/<name>/`: `cmd.txt`, `cwd.txt`, `stdout.log`, `stderr.log`, and a
    `run.status` with start and exit lines. It refuses a second run under the same name while the first is active.
  - The frozen `launch/run_job.sh` takes a CPU slot at nice 19, with PYTHONHASHSEED=0 and PYTHONPATH=. It writes
    `runs/status/<job>.status` and `logs/<job>.log`, and appends start and end lines to `PROGRESS.md`. That file is
    deliberately not frozen.
- **Kaggle steps.** `launch/push_when_free.sh` pushes only while the kernel does not exist. It retries only on
  Kaggle's explicit session-limit refusal, judging by the push output text rather than the return code, the lesson
  from the guided-construction run. `fgc/fetch.py` checks each archive against the digest the notebook printed, and
  checks that every member is a safe path.

## 7. Notes (none blocking)

1. **Required procedural step: gate the measurement.** No frozen code calls the gate's "measure" stage:
   `fgc/kaggle_build.py` and `fgc/fetch.py` never call it, and protocol section 10 step 3 lists no gate step. That
   falls short of section 11's "the gate re-checks every digest before each stage". The seal stage re-checks every
   digest later, and each kernel's `PACKAGE.json` records the sha256 of every packaged file. Add to the run
   instructions:
   - run `python3 -I fgc/gate.py measure` before building the TEST kernels, and record its "ok measure" line (it checks
     the GO, every frozen digest, the claim and the committed held manifest);
   - after building, confirm that every packaged frozen file's digest in `runs/kaggle/TEST_k/PACKAGE.json` equals
     `FREEZE.json`;
   - the post-score audit repeats that comparison.
2. **The efficiency threshold was tightened after the preliminary source results.** It changed from "the calls
   interval below 0" to "below -5% of T*", in `pipeline.decide` between ec990218 and ce069bd6.
   - The original rule would have labelled the source set's trivial 139-call saving as "efficiency".
   - The change used source data only and makes the claim harder to reach, so it is legitimate development.
   - The write-up should say it was set after the preliminary source run.
3. **Expected power.** With at most 54 held tasks in 9 families, and no discordant source task, the primary is
   expected to be inconclusive. Section 9 pre-registers that; the informative rungs are capability and coverage. Report
   the decision label, "controlled generated tasks", and F and G separately.
4. **External data file.** It is pinned at `<ARC data folder>/arc-agi_training_challenges.json`, outside the
   repository. Every stage's gate refuses if it moves or changes, which fails safe. Leave it in place until the score
   stage.
5. **Run instructions and protocol text differ only in form.** `PROGRESS.md` wraps the protocol's frozen commands in
   `run_detached.sh`; the inner commands are the frozen ones. Keep it that way. Generation, sealing and scoring should
   go through `launch/run_job.sh`, which sets PYTHONHASHSEED=0 and PYTHONPATH=. for `python -m ...`. Only the
   standard-library tools (`fgc/gate.py`, `fgc/kaggle_build.py`, `fgc/fetch.py`) are meant for `python3 -I`.
