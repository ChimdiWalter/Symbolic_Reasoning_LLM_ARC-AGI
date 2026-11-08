# Guided-construction test: independent pre-run review (exact bytes)

Reviewer: an independent session that did not build the test. Written 6 Nov 2026, 10:36Z to 11:10Z. No `runs/GO` was
written, no held task was run, no kernel was pushed, no held test output and no solution file was opened. Every rerun
used commits extracted with `git archive` into a scratch folder (never the live tree, which was being revised while
this review ran), one CPU process at a time at nice 19, the heavy jobs inside `scripts/with_cpu_slot.sh`.

## Verdict

**Version 2 (the bytes the GO must name): PASS WITH FIXES.** The one required fix is in the run instructions of
`PROGRESS.md`, which is not a frozen file: no frozen byte changes, no re-freeze, no new review round.

- Reviewed: commit fdf37ea2; `FREEZE.json` version 2 sha256
  32c1652b58598eff9cfb21b1d5beaba9d54561a3a61c23663169654285262b17 (95 files); `PROTOCOL.md` d5510c8f...
  (unchanged); `PROTOCOL_AMENDMENT_1.md` 27b2e084...; candidate package 034bec18bbfeead16759146eb3a0abfc57a9fed81e9f7c610c36ecea15305873.
- Required before the GO (Finding 1): correct steps 6 and 7 of the run instructions.
- Version 1 (`FREEZE_V1.json`, 55afe42c..., the bytes first sent for review) would have been PASS WITH FIXES, with the
  scorer's unbound receipt as the required fix. I found the same gap independently (Finding 2). Version 2 closes it, and
  version 1 is superseded.

## 1. Hashes from the committed bytes

| What | Result |
|---|---|
| `FREEZE.json` v2, `FREEZE_V1.json`, `PROTOCOL.md`, `PROTOCOL_AMENDMENT_1.md`, package, `DEV_REPORT.md` v2 (2fcd67ef...), `config/CONFIG.json` (3272b67f...), `models/full.json` (bb467dde...) | equal the claimed digests, as blobs of fdf37ea2 and in the working tree |
| `FREEZE_V1.json` against `FREEZE.json` at aaaa7943 | byte-identical (55afe42c...) |
| v1 claims: `FREEZE.json` 55afe42c, `PROTOCOL.md` at d5a07f71 and HEAD, `DEV_REPORT.md` v1 8c15e10e, CONFIG, weights, package 80af8104, all at their commits | all equal |
| every digest of `FREEZE.json` v2 (95 files) and v1 (91 files) | 0 mismatches against the git blobs and the working tree. Six files are pinned by digest only because they are git-ignored (the arc-dsl resources and `a2/out/corpus.json`); their digests also equal the object step's `FREEZE_V2.json` |
| data digests (six `real.json` and `meta.json` files), the ARC-AGI-2 challenges digest | equal |
| v2 bookkeeping | the `changed_since_version_1` list is exact (9 files, both digests right), 4 files added, none removed; the rules, budget rule, stop rule, data and challenges digest are unchanged from v1 |
| object step, `FREEZE_V2.json` f6218c3e... (115 files) | 0 mismatches against the blobs and the working tree; the 41 files both freezes pin agree |
| package 034bec18 | 70 regular files, equal to the manifest (781702a8...) and to `FREEZE.json` v2; every frozen file not marked Athe-only is inside; no Athe-only file, no solution file and no `runs/GO` is inside; the packaged `real.json` files hold `input` only under `test` |
| three notebooks (a599d57b..., adc48e8b..., b15b827e...) | each embeds exactly the 034bec18 archive and checks its digest; metadata private, no GPU, no TPU, internet off |

Development code and records (`engine`, `features`, `model`, `policy`, `units`, `sim`, `dev`, `devan` and every file
under `dev/`) are unchanged from the step 2 and step 3 commits through version 1. In version 2, `dev/`, `models/`,
`config/`, `model.py`, `policy.py`, `units.py`, `sim.py`, `env.py`, `gate.py`, `run.py`, `kernel_run.py`,
`kaggle_build.py` and `kaggle_fetch.py` are byte-identical to version 1.

## 2. The budget rule and the stop rule, recomputed

I wrote my own simulation from the engine's rules. It imports nothing from `gcon/` or `objgrow/`. I ran it on the
committed trace (`dev/pass1`), fold weights (`dev/models/fold*.json`, with my own forward pass) and retries
(`dev/retries.jsonl`), with my own fold assignment (sha256 of "guided-fold:" plus the id, rank mod 5 within each benchmark).

- For 16 arm and budget pairs, every unit's fit and retried operation, the fitted totals, the operation totals and the
  capped-hole counts equal `dev/curves.json` exactly. The pairs: hand-set order at 100, 125, 200, 500, 1,000, 2,000,
  5,000 and 20,000; cross-fitted guide at 100, 500, 2,000 and 20,000; linear model, frequency order, hand rule and
  leave-one-benchmark-out guide at 500.
- **Budget rule:** F = 177, 188, 213, 249, 264, 281 at 100 to 5,000 and 298 at 20,000. The threshold is 223.5, so 100,
  200 and 500 qualify, and **the test budget is 500**. The held budgets are 125, 500, 2,000 and 20,000, as in
  `CONFIG.json`.
- **Stop rule:** the cross-fitted guide fits 284 units and the hand-set order 213. There are 75 gains (all 1D-ARC) and
  4 losses (3 ConceptARC, 1 Mini-ARC), net +71. **GO.** The gain and loss unit lists equal the frozen record. The rule
  is applied exactly as `PROTOCOL.md` lines 157 to 159 state (net at least 10, gains at least 3 times the losses,
  pooled).
- Equivalence at 20,000 from the records: on all 1,275 holes, 0 differences between the engine and the frozen
  `hole_candidates` live, 0 between that function and the stored records, and 0 between my simulation and the
  frozen function (candidates, order, fields, operation count).
- The descriptive claims of `DEV_REPORT.md` section 5 all check out:
  - 342 units with no capped hole agree at 20,000; of the 83 with a capped hole, 8 retried a different candidate and 3
    lost their fit;
  - linear model +2/-0 and frequency order +1/-0 against the guide;
  - the guide against donor guidance +19/-3, against the hand rule +35/-4;
  - the leave-one-benchmark-out guide fits 245 of 283 1D-ARC units;
  - the hand-set order needs 20,000 operations to reach 284 fits.
- **Extra direct-execution sample**, at budgets the development sample did not use: 56 source holes (fresh seed 4242;
  14 capped at 20,000), on the version 2 engine.
  - Hand-set order at 125, 200, 500 and 1,000: the frozen function with its cap set, direct execution and my
    simulation agree.
  - Cross-fitted guide and hand rule at 125 and 500: direct execution and my simulation agree, the capped flag
    included.
  - 448 checks, 0 failures.
  - A first attempt reported failures. The cause was my own comparison: live tuples against recorded lists. After the
    same JSON normalisation as `devan.sample`, 0 failures.

## 3. No test output in features, labels or rules; training data

- **Features** (`gcon/features.py`) use the hole's demonstration pairs, the frozen pair analysis and the block's edit.
  They never use a test input, a test output or a benchmark name.
- **Labels** (`gcon/devan.py` `dataset`):
  - success is "the trace block yields a multi-pair candidate";
  - the cost label is log(1 + the block's counted operations).
- **Fits** for the rules are demonstration fits of retries (G0 plus the candidate). Agreement groups use test inputs
  only, as in the frozen step.
- The controller records hold no correctness field.
- The packaged data hold no test output.
- **Retraining check:** I rebuilt three training sets from the trace alone, independently of `devan.py`: fold 0 held
  out (50,880 blocks), without 1D-ARC (19,216) and the full set (62,109 blocks, 11,820 successes). I fitted them with
  the frozen `gcon/model.py`. Each result is **bit-identical** to the committed weights: guide, linear model and
  frequency table. `models/full.json` equals `dev/models/full.json`. So the committed models were trained on exactly
  the source-half trace blocks and these labels, and on nothing else.
- The file times show a single pass: pass 1, then the step 2 summary, training (47 s), the sample, then the curves.
  Nothing indicates tuning. The cost target's standardisation is what the code did. Amendment section 3 now states it,
  and the retraining check confirms it.

## 4. Invariants, re-sort and gate

These are as declared (version 2 line numbers):
- Hand-set re-sort before the frozen de-duplication, grouping, sort and cut at 8: `gcon/engine.py` lines 391 to 413.
- Cap checks at the frozen places: lines 40, 142, 211, 357 and 380.
- A two-rule block runs only after all of its view's single-rule blocks, with none verified: line 363.
- Policies cap a two-rule block's score at its view's lowest single-rule score and break ties by hand-set place:
  `gcon/policy.py` lines 16 to 26. So a two-rule block is always placed after its single-rule blocks.
- I compared `run_W` and `run_T` with the frozen `whole_candidates` and two-rule code line by line. The only
  differences are the passed-in cap and the marks.
- Invariant 1, now with the stage (`gcon/verify.py` lines 64 to 79 and 130 to 134), and invariant 2 (lines 135 to 144)
  are implemented as `PROTOCOL.md` section 8 states. Invariant 2 is sound: when no cap binds, the set of blocks that
  run, and their counts, do not depend on the order.

Reruns in a scratch copy of fdf37ea2 (one process, nice 19, CPU slot):
- **Gate refusal check:** 6 of 6 refused.
  - No GO: held run, checks and scorer.
  - A GO naming another protocol.
  - One frozen file changed.
  - The scorer in rehearsal mode. Version 2 now stops this case even earlier, at the re-run checks. The marker's own
    rehearsal refusal is exercised by the guard's positive control.
- **Smoke test:** 12 source stand-in rows, 0 errors, receipt PASS. Per-task fits, capped counts, stages and the
  invariant summary are identical to the committed `checks/SMOKE_TEST.json`.
- **Scorer guard tests:** 7 of 7 behave as committed.
  - Invented receipt over mutated rows: refused at the re-run checks.
  - Invented receipt over current rows, stale receipt, copied receipt: refused at the binding.
  - Forged receipt over rows breaking invariant 1: refused at the re-run checks.
  - Missing receipt: refused.
  - In all six, the marker call is never reached and no solution function is called.
  - Positive control: it reaches the marker, which refuses in rehearsal mode.
- **Import audit** inside the unpacked package: every module comes from the package, the standard library or
  site-packages. The arc-dsl path and every root point into the package.
- **Path after the marker** (my addition): with the marker and both solution functions replaced by stand-ins and fake
  one-cell outputs, version 2's `score()` runs to the end on the smoke rows. It writes the primary, the 7 secondaries,
  the work tables and the predictions. So the code after the marker, new in version 2 (`work`), cannot crash after a
  real marker is taken. No file holding outputs exists in that package.

## 5. The three places where the code is more specific than the protocol

None of them can bias the primary (guide against hand-set order at 500):
- **Holes computed twice** (the reference inside the frozen function, then once for all arms).
  - `CT.sketches` is deterministic: no search, no time limit, the same builder, the same process.
  - Both primary arms use the same second computation.
  - A divergence would break invariant 1. That makes the run INVALID; it cannot move one arm.
- **A donor with fewer holes uses its last hole.** This touches only the donor arm (secondary 1), and development did
  the same (`devan.py` `donor_hole`).
- **One shared retry cache, seeded with the reference's retries.**
  - A retry is keyed by (task, candidate identifier). `ObjOp` normalises its specification, so equal identifiers mean
    the same operation.
  - Every arm reads the same cached result.
  - In development, retries took at most 1.5 CPU-s against the 20 CPU-s cap, so the order in which arms first
    request a retry cannot change its outcome.

## 6. Custody

- Solution files open only in `gcon/score.py`. In version 2:
  - `after_marker`, lines 31 to 35, guards both solution functions at lines 38 to 54;
  - they run only after the five-step guard (lines 81 to 98) and the O_EXCL marker (`gcon/gate.py` lines 62 to 72).
- Held tasks load only behind `require_go`. Rehearsal mode lists source stand-ins only.
- The package carries no solution file.
- The kernels are private, CPU only, internet off (4 workers, 7.5 h of wall time, which is 30 CPU-h at most).
- The version 2 check binds the final kernels' metadata to the final manifest's digests (`gcon/verify.py` lines 86 to
  90 and 149 to 156).
- Study B's scorer had not run when this protocol was committed: its log shows rehearsals still in progress at 08:15Z
  and 09:20Z.
- The amendment's custody wording (section 4) is correct: `real.json` loads whole, held demonstrations and test inputs
  included, no outputs. Development kept the source tasks only.

## 7. Wording

- `PROTOCOL.md` section 11 and `PROTOCOL_AMENDMENT_1.md` lines 78 to 82 carry the rules:
  - "learned guidance" unless the network beats the linear model (secondary 4, Holm-adjusted; the scorer sets
    `neural_wording` from it);
  - "fewer counted operations for the same exact answers", always with both arms' CPU and uncounted work;
  - never "less work", never "new reach".
- Development already shows the linear model and the frequency order at least equal to the network. On one smoke hole
  the guide spent about four times the hand-set order's edit applications and CPU at the same 501 operations. So CPU
  must stand beside every operation count.

## 8. Findings and exact fixes

**Finding 1 (required, run instructions only).** In `PROGRESS.md` (lines 42 to 48 of version 2, unchanged since
version 1), steps 6 and 7 must change for version 2. There are two problems.
- (a) Step 6 passes three kernel-metadata paths to `run.py verify`. Version 2's `gcon/verify.py` `main(run_dir)`
  (line 193) takes only the run folder; it reads the final kernels' metadata through `PACKAGE_MANIFEST_final.json`
  itself. As written, the command stops with a TypeError before any check.
- (b) `python3 -I` implies `-E`, so the interpreter ignores PYTHONHASHSEED. But `run.py` line 13 checks only the
  environment variable, so its guard passes while hashing stays random. Verify and score do not depend on hash order,
  so no number would change, but the guard gives false assurance. I showed this: `PYTHONHASHSEED=0 python3 -I` prints
  a different `hash("abc")` on each run, and `-s -B` prints a stable one.

Exact fix: replace steps 6 and 7 with the following, run in a shell where GC_REHEARSAL and NGB_REHEARSAL are unset
(Finding 3):

```
PYTHONHASHSEED=0 python3 -s -B run.py verify runs/held_run
PYTHONHASHSEED=0 python3 -s -B run.py score runs/held_run      (once, only on PASS)
```

**Finding 2 (version 1 only; fixed in version 2).** Version 1's `gcon/score.py` (lines 64 to 70 of 0e888128...)
trusted the PASS in `INVARIANTS.json` without binding it to the rows, the GO or the freeze. Version 2 fixes this: it
re-runs the checks on the exact row bytes, binds the receipt (verdict, row digest, GO, freeze, protocol,
configuration, mode), re-takes the digests, and only then takes the marker. The guard tests above confirm it.

**Finding 3 (advisory).** `ngb/env.py` lines 30 to 39 replace `ngrow.data.half("held")` with the source half whenever
NGB_REHEARSAL=1. Kaggle never sets this variable, and on Athe verify would fail safe (it would expect source tasks).
But in a shell that had it set, the donor arm's donors would silently come from the source half. Keep it unset (see
Finding 1).

**Finding 4 (advisory).** In `gcon/held.py`, the hole and donor computations (lines 187 and 193) sit outside the
per-arm `try`. An exception there ends the worker and loses the rest of its shard. That fails safe: missing rows make
the run INVALID, just as an error row does. These paths ran on all 1,275 source holes and on 12 stand-ins, but never
on an ARC-AGI-2 evaluation task before the run, because rehearsal uses source stand-ins. Accept as is.

**Finding 5 (advisory: what "fitted" meant in development).** Development counts a unit as fitted through a retry on
the controller's stored holes (`gcon/dev.py` line 70, `gcon/devan.py` line 299). The held run re-runs the base search
and recomputes the holes with the seed-independent builder. This is a narrower reading of `PROTOCOL.md` line 53 than
the held run uses. It cannot bring in a test output, and it cannot bias the primary. Its reach is bounded:
- the stop rule would flip only if more than 61 of the 75 gains were base-search fits;
- the budget cannot rise above 500, because F(1,000) = 249 exceeds 0.75 F(20,000) whatever is added;
- it could fall below 500 only if at least 11 units were base-search fits that no retry fits at 500.

Fix: state this reading in the paper's methods. No byte change.

**Finding 6 (advisory, write-up).** The positive outcome paragraph (`PROTOCOL.md` lines 235 to 240) needs three changes
when it is filled. The amendment governs where the two differ.
- "keeps three quarters of its answers" becomes "keeps at most three quarters of the source units it fits at 20,000
  operations".
- "operations" becomes "counted operations", with both arms' CPU beside it.
- "Learning bought efficiency, not reach" must not read as less work. For example: "Learning bought fewer counted
  operations, not reach", followed by the CPU figures.

**Finding 7 (trivial).**
- `DEV_REPORT.md` section 2 (line 36 of version 2) says "71 (12 capped)". In fact 19 of the 71 sampled holes are
  capped at 20,000: 12 drawn from the capped list and 7 among the 60 random ones.
- The scorer's shared-work summary omits the sketches' CPU. Each row records it, and it is the same for every arm.

**Finding 8 (governance, the coordinator's call).** The protocol was committed at 09:55Z. The program's milestone was
04:30Z (`records/NOV6_TAILORED_RESEARCH_PROGRAM.md` section 2.11), and the slip exceeds that program's two-hour rule.
- `PROTOCOL.md` section 10 re-timed its own milestones, and where it is more specific it governs.
- Every later milestone of the program has been met or beaten.
- Please confirm the re-timed schedule when writing the GO.

## 9. Compute used by this review

About 3 CPU-minutes on Athe:
- recomputation 4 s, retraining 10 s;
- extra sample 37 s, plus 39 s for the first attempt;
- smoke test, refusals and guard tests 66 s;
- post-marker exercise and hash checks a few seconds.

The heavy jobs ran in one shared CPU slot. The light checks ran at nice 19. Step B and GPU 1 were never touched, and
nothing was made public.

## Version 3 re-check (commit 2edba81c), appended 6 Nov 2026, 11:30Z to 11:45Z

This was a bounded re-check of the change from version 2 to version 3. I used the same rules as above: the commit was
extracted with `git archive` into a scratch folder, one CPU slot was used at nice 19, and no GO, held task, kernel push
or solution file was touched.

**Verdict for version 3: PASS.** No required fix. The GO lines name version 3:
- line 1: `protocol_sha256 d5510c8f0c2d1ded6d1b5fc1fae145e5a4050da9a56af8276ed41f952c9dfd53`;
- line 2: `freeze_sha256 29ca65634f03e58673b2d93c92ef84366d0a1191152731c1ea30e97f2fca376b`.

These are `PROGRESS.md` lines 75 and 76. The gate (`gcon/gate.py` line 50) and `kaggle_build.py final` both require
exactly these two lines.

### Digests (from the committed bytes)

| What | Result |
|---|---|
| `FREEZE.json` v3 29ca6563... (97 files) | 0 mismatches against the git blobs of 2edba81c and the working tree. Six git-ignored files are pinned by digest only, as before |
| `FREEZE_V2.json` | 32c1652b..., byte-identical to `FREEZE.json` at fdf37ea2. `FREEZE_V1.json` is unchanged (55afe42c...) |
| `PROTOCOL.md`, `PROTOCOL_AMENDMENT_1.md` | unchanged (d5510c8f..., 27b2e084...) |
| `PROTOCOL_AMENDMENT_2.md` | 0ee320567941c3fabf6ee22624eaf81d47f4727cdb39d94f2f5eefe7b2d46527 |
| change bookkeeping | `changed_since_version_2` is exact (8 files: `DEV_REPORT.md`, `freeze.py`, `held.py`, `kaggle_fetch.py`, `score.py`, `verify.py`, `score_guard_test.py`, `smoke_test.py`). Two files were added (`FREEZE_V2.json`, amendment 2, both Athe-only) and none removed. The rules, budget rule, stop rule, data digests and ARC-AGI-2 digest are unchanged |
| candidate package | 5fc01b635c6c196faaee010a5800904a9e71670ffe33bebf6d404f89e67e76bd (431,625 bytes). 70 regular files, equal to its manifest and to `FREEZE.json` v3. Only `gcon/held.py` and `FREEZE.json` differ from the version 2 package. No Athe-only file, solution file or GO is inside. Each of the three notebooks embeds exactly this archive; metadata private, no GPU, no TPU, internet off |
| configuration and weights | `CONFIG.json` 3272b67f..., `models/full.json` bb467dde..., leave-one-benchmark-out weights 5d48cceb..., c0743583..., 414ab812...: all unchanged |

### Nothing in the diff changes the primary, the budget, the weights or the arms

The following are byte-identical to version 2:
- the search code: `engine.py`, `features.py`, `model.py`, `policy.py`, `units.py`, `sim.py`;
- the support code: `env.py`, `gate.py`, `dev.py`, `devan.py`, `kaggle_build.py`, `run.py`, `launch/kernel_run.py`;
- `config/`, `models/`, every development record under `dev/`, `PROTOCOL.md` and amendment 1.

So the earlier recomputations carry over unchanged: the budget rule (500), the stop rule (GO, 75 gains and 4 losses),
the bit-identical retraining and the extra direct-execution sample (448 checks).

The changed code:
- **`gcon/held.py`** (the only changed file the kernels run) adds `n_demos` to each row (line 169). It writes a reference
  error as a record with type, message and traceback tail (line 174). No arm's sequence, budget, retry or answer is
  touched.
- **`gcon/score.py`.** The primary is still study A's `compare` of guide@500 against hand@500 on correct test
  outputs. The changes add two binding fields (line 28), per-task CPU (lines 75 and 134) and shared-work sums, and
  reword the note (line 209).
- **`gcon/verify.py`** adds checks only, so it can turn a run INVALID but never change an answer.

### Bounded read of the new checks (`gcon/verify.py` version 3)

- **Stage.**
  - `ref_view` and `arm_view` (lines 97 to 114) map only "construction", "base" and "construction_none". Any other
    stage becomes "unknown" and fails.
  - `branch_problems` (lines 125 to 183) requires every arm's stage to agree with its fit, and a fitting arm to carry
    an operation and attempts.
- **Identities.** `identities()` (lines 81 to 95) takes task, benchmark, family, demonstration count and test count
  from `held.task_list`, behind the GO. That means the split and the pinned benchmark files, plus the ARC-AGI-2
  challenges with their pinned digest. Each set must hold exactly its trusted ids. The digest is bound in the receipt
  (line 350) and in the scorer's binding.
- **Kernel receipts.** `kernel_receipts` (lines 186 to 263) requires all of the following:
  - the final manifest: mode final, the current GO, freeze and protocol, and exactly the three kernels with their
    identifiers and sets;
  - per kernel: metadata matching its digest (private, no internet, no GPU, no TPU), the notebook digest, a push
    receipt with return code 0, a fetch receipt with sets, archive path and per-file digests, and the archive's bytes;
  - a driver record with every worker at 0, none stopped at the limit, not a rehearsal;
  - row files that equal, byte for byte, the files the kernel returned: nothing missing, nothing extra.

  The joint digest is bound (line 351). In a held run nothing skips this; rehearsal skips it and never scores.
- **Branch evidence.** There are four permitted branches, each with its evidence, as amendment 2 section 4 states.
  Unknown shared stages, a `base_fit` without a base-stage fit, `under_two_demonstrations` against the trusted count,
  and empty, False or bare-string reference errors all fail.
- **Disclosure, loss and custody wording.** These are amendment 2 sections 5 to 7 and `DEV_REPORT.md`.
  - Per-task CPU and the shared hole setup are reported beside counted operations.
  - The cost loss is stated as the code does it. My bit-identical retraining confirms this is the form the frozen
    weights came from.
  - Development physically loaded held demonstrations and test inputs: this is what I saw in `objgrow.grow.setup`.
- **Run instructions** (`PROGRESS.md` lines 67 to 90): steps 6 and 7 use `python3 -s -B` with the
  run folder only, and step 0 unsets and checks GC_REHEARSAL and NGB_REHEARSAL. Version 2 Findings 1 and 3 are
  resolved.

### Reruns (scratch copy of 2edba81c, one CPU slot, nice 19)

Every result below is identical to the committed version 3 records (`checks/GATE_REFUSAL.json`,
`checks/SMOKE_TEST.json`, `checks/SCORE_GUARD_TESTS.json`).
- **Gate refusals: 6 of 6 refused.** No GO for the held run, the checks and the scorer; a GO naming another protocol;
  one frozen file changed; the scorer in rehearsal mode.
- **Smoke test.** 12 source stand-in rows, 0 errors, receipt PASS. The per-task fits, capped counts, stages and the
  invariant summary are identical to the committed record. The summary now also counts the branches: 12
  construction, 0 `base_fit`, 0 `under_two_demonstrations`, 0 reference errors.
- **Scorer boundary: 7 of 7.** Six cases are refused before the marker with no solution call: the invented receipt
  over mutated or over current rows, the stale and the copied receipt, the forged receipt, the missing receipt. The
  positive control reaches the marker, which refuses in rehearsal mode.
- **Verification sentinels: 17 of 17.**
  - All 15 negative cases give verify INVALID. They are:
    - the hand-set stage at 20,000, the reference stage, and an arm stage that contradicts its fit;
    - the family, the benchmark, the test count and the demonstration count;
    - `base_fit` without a base stage, and `base_fit` without a fit;
    - an empty, a False and an old-format string reference error;
    - a reference error next to an answer and arms;
    - `under_two_demonstrations` with two or more trusted demonstrations;
    - an unknown shared stage.
  - With a forged PASS receipt carrying every current digest, each of the 15 is refused before the marker, with no
    solution call.
  - The two positive controls (a consistent `base_fit` row and a consistent reference-error row) verify PASS and reach
    the marker.
- **Kernel-receipt cases: 17 of 17.**
  - The consistent invented tree passes.
  - Each of the 16 negatives fails, and each fails at the intended check. They are:
    - a missing tree, kernel, push receipt or fetch receipt;
    - a substituted role;
    - internet on, not private, a GPU;
    - metadata changed after the manifest;
    - a failed push, a failed worker, a rehearsal record;
    - a changed archive;
    - a package naming another GO;
    - a row file the kernel did not return, an extra row file.
- **Import audit** in the unpacked package: every module comes from the package, the standard library or
  site-packages.
- **Path after the marker.** Version 3's `score()` runs to the end on the smoke rows, with the marker and both
  solution functions replaced by stand-ins and fake outputs. It writes the primary, the 7 secondaries, the new
  per-task CPU, the shared-work sums (hole setup, reference and task totals) and the predictions.
- **Compute:** about 78 CPU-s, all in one shared CPU slot at nice 19.

### Advisory (no byte change, not needed for this run)

- `gcon/verify.py` line 288 reads the row's demonstration count with the trusted count as its default, so a row
  without `n_demos` passes that comparison. Version 3 rows always carry it, the branch decisions use the trusted
  count, and the kernel receipts bind the row bytes, so nothing depends on it.
- `kernel_receipts` checks the archive's digest and the fetch record's per-file digests. It does not reopen the
  archive to recompute those per-file digests. `kaggle_fetch.py` writes them from the checked extraction, so this
  matters only against a deliberately rewritten fetch record. A later version could compare the archive members
  directly.
- Amendment 2 section 7 says the ARC-AGI-2 challenges were "never parsed on Athe". That holds before the GO. After the
  GO, verify and the scorer's guard parse them (demonstrations and test inputs only) to build the trusted identities,
  as version 2 already did.

## Version 4 re-check (commit ecb9be10), appended 6 Nov 2026, 11:55Z to 12:05Z

This was a bounded re-check of the change from version 3 to version 4. I used the same rules: the commit was extracted
with `git archive` into a scratch folder, one CPU slot was used at nice 19, and no GO, held task, kernel push or
solution file was touched.

**Verdict for version 4: PASS.** No required fix. I would accept exactly these GO lines (`PROGRESS.md` lines 75 and
76; required by `gcon/gate.py` line 50 and by `kaggle_build.py final`):

```
protocol_sha256 d5510c8f0c2d1ded6d1b5fc1fae145e5a4050da9a56af8276ed41f952c9dfd53
freeze_sha256 d876eeded96c1c6f9672bc292bfe5a479d40c6175c0bf43cb51e628ac11b1cdf
```

How the three items match my earlier advisories:
- The first (a row without `n_demos` passed) is the one I recorded for version 3.
- The second, binding `kernel_run.json` to its returned digest, is next to my advisory but not the same point. Mine was
  that the fetch record's per-file digests are never recomputed from the archive. That advisory still stands, still
  optional.
- The third, the missing donor comparison total, I had not flagged; the companion found it.

### Digests (from the committed bytes)

| What | Result |
|---|---|
| `FREEZE.json` v4 d876eede... (99 files) | 0 mismatches against the git blobs of ecb9be10 and the working tree. Six git-ignored files are pinned by digest only, as before |
| `FREEZE_V3.json` | 29ca6563..., byte-identical to `FREEZE.json` at 2edba81c. `FREEZE_V2.json` (32c1652b...) and `FREEZE_V1.json` (55afe42c...) are unchanged |
| `PROTOCOL.md`, amendments 1 and 2 | unchanged (d5510c8f..., 27b2e084..., 0ee32056...) |
| `PROTOCOL_AMENDMENT_3.md` | 5c3e877951babbe860090a83c79edcf1edd01eb8f24099f50104c150df5e1f1f |
| change bookkeeping | `changed_since_version_3` is exact: `freeze.py`, `score.py`, `verify.py`, `score_guard_test.py`, `smoke_test.py`. Two files were added (`FREEZE_V3.json` and amendment 3, both Athe-only) and none removed. The rules, budget rule, stop rule, data digests and ARC-AGI-2 digest are unchanged |
| candidate package | e5d2d77c0cb751d52cdb74aa68d83595d6d05a3f119ce3ed4efba7ac1b06f6f8 (431,583 bytes). 70 regular files, equal to its manifest and to `FREEZE.json` v4. **Among the packaged files only `FREEZE.json` differs from version 3.** No Athe-only file, solution file or GO is inside. Each of the three notebooks embeds exactly this archive; metadata private, no GPU, no TPU, internet off |
| companion report | `cage/guided_construction_c_independent_review_20261106_v3/REPORT.md` has sha256 bba3a271..., as cited. Its note 0522 lists exactly the three items amendment 3 fixes |

### The three fixes, and nothing else

The following are byte-identical to version 3:
- the search code: `engine.py`, `features.py`, `model.py`, `policy.py`, `units.py`, `sim.py`;
- the support code: `env.py`, `gate.py`, `dev.py`, `devan.py`, `kaggle_build.py`, `kaggle_fetch.py`, `held.py`,
  `run.py`, `launch/kernel_run.py`;
- `config/` and `models/` (configuration 3272b67f..., weights bb467dde... and the three leave-one-benchmark-out
  files);
- every development record under `dev/`, `DEV_REPORT.md`, `PROTOCOL.md` and amendments 1 and 2.

So the primary, the budget (500), the stop rule (GO), the weights, the arms, the configuration, the engine and the
features are unchanged. My recomputations from the first review still hold.

The fixes:
1. **`n_demos` required.** `gcon/verify.py` lines 295 to 298 fail a row that lacks `n_demos` or carries a non-integer
   there (a boolean is rejected too, since its type is not `int`). Otherwise `n_demos` is compared with the trusted
   count, together with benchmark, family and test count. The trusted count still decides the branch.
2. **Driver record bound.** `gcon/verify.py` lines 254 to 259 compare the sha256 of the `kernel_run.json` copy used in
   verification with `files_sha256["kernel_run.json"]` of that kernel's fetch receipt. The key matches what
   `kaggle_fetch.py` writes: paths relative to the returned `run/` folder. A missing entry or a different digest fails.
   The earlier structural checks of the record still apply.
3. **Donor total.** `gcon/score.py` line 128 sums `donor_feature_comparisons` over the rows beside
   `donor_feature_cpu_s`. Lines 132 to 136 label both "cache delta", because a donor's setup is recorded only on the
   task that first computes it. This is reporting only.

The other diffs are bookkeeping and tests: `freeze.py` writes version 4, `smoke_test.py` prints the new case, and
`score_guard_test.py` adds the new cases.

### Reruns (scratch copy of ecb9be10, one CPU slot, nice 19)

Every result below is identical to the committed version 4 records (`checks/GATE_REFUSAL.json`,
`checks/SMOKE_TEST.json`, `checks/SCORE_GUARD_TESTS.json`).
- **Gate refusals: 6 of 6 refused.** No GO for the held run, the checks and the scorer; a GO naming another protocol;
  one frozen file changed; the scorer in rehearsal mode.
- **Smoke test.** 12 source stand-in rows, 0 errors, receipt PASS. Per-task fits, capped counts, stages, the
  invariant summary and the branch counts are identical to the committed record.
- **Scorer boundary: 7 of 7.** Six cases are refused before the marker with no solution call. The positive control
  reaches the marker, which refuses in rehearsal mode.
- **Verification sentinels: 18 of 18.**
  - All 16 negative cases give verify INVALID. With a forged PASS receipt carrying every current digest, each is
    refused before the marker, with no solution call.
  - The two positive controls verify PASS and reach the marker.
  - **New case `row_without_n_demos` fails at the intended check**, "row without its demonstration count (n_demos)".
    `demonstration_count_mutant` still fails at the identity check.
- **Kernel-receipt cases: 19 of 19.** The consistent tree passes, and every negative fails at its intended check.
  - **The two new cases each fail with exactly one failure, the intended one**, "kernel driver record differs from
    the returned file (fetch digest)". They are an edited `kernel_run.json` with a stale digest, and the entry
    removed from the fetch receipt.
  - Two older cases, the rehearsal record and the failed worker, also edit `kernel_run.json`. They still fail at their
    intended check ("kernel driver record"), and now the new digest check fires as well, as it should.
- **Donor total case.** The scorer, fed fake outputs with a scratch marker, reports `donor_feature_comparisons` = 134,
  equal to the sum over the held rows, with its "cache delta" scope label. The real marker was never created.
- **Import audit** in the unpacked package: every module comes from the package, the standard library or
  site-packages.
- **Path after the marker** (my own exercise, fake outputs): version 4's `score()` runs to the end. Its shared-work
  totals now include `donor_feature_comparisons` (116 on the unmodified smoke rows) and both scope labels.
- **Compute:** about 70 CPU-s, in one shared CPU slot at nice 19.

### Still open (advisory, no byte change, not needed for this run)

- `kernel_receipts` still does not reopen each returned archive to recompute the per-file digests it compares
  against. Those digests are written by `kaggle_fetch.py` from the checked extraction, so this matters only against a
  deliberately rewritten fetch record.
- Amendment 2 section 7 says the ARC-AGI-2 challenges were "never parsed on Athe". Read it as before the GO; after the
  GO, verify and the scorer's guard parse the challenges (demonstrations and test inputs only) to build the trusted
  identities.
