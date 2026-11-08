# Guided-construction test: protocol amendment 1

Dated 6 Nov 2026, 11:00Z. Written after the companion study's independent review of the step 4 package (its notes
0514 and 0515) and before any GO. This study has run no held task and has opened no held test output and no solution
file. Version 1 of the freeze is kept byte-identical as `FREEZE_V1.json` (sha256
55afe42c68c69efbe712132b00ea70914d12134608af0062c84539d58288e4c5). `FREEZE.json` version 2 pins this amendment.
`PROTOCOL.md` is unchanged; where the two differ, this amendment governs.

## 1. The scorer checks the exact bytes it scores (the blocker)

**Finding.** Version 1 of `gcon/score.py` (sha256 0e888128...) checked only that `INVARIANTS.json` said PASS. It did
not check that this verdict belonged to the current rows, the current GO and the current freeze. It then took the
scoring marker and called the held-solution function. A stale, copied or invented PASS could therefore open
solutions for rows that were never checked. The review showed this with an invented record (PASS, an old GO, an old
freeze) next to a current GO and changed rows.

**Rule now** (`gcon/verify.py`, `gcon/score.py`):
- `verify.py` reads every row file once, as bytes, and checks the rows parsed from those bytes. It then writes a
  receipt (`INVARIANTS.json`). The receipt ties the verdict to:
  - the sha256 of every row file and their joint digest;
  - the digests of the GO, the freeze, the protocol and the configuration;
  - the mode (held run or rehearsal).
- The scorer does the following before it takes the marker and before it opens any solution, in this order:
  1. It checks the GO and every frozen digest.
  2. It reads the row files once.
  3. It runs the same checks again on those bytes, and they must PASS.
  4. It requires the receipt to say PASS and to carry the same row digest, GO, freeze, protocol, configuration and
     mode.
  5. It takes the GO, freeze, protocol and configuration digests again; they must be unchanged.
  Any mismatch refuses, and nothing is taken or opened. Only then does it take the marker and open the solution
  files. The rows it scores are the rows it checked; they are not read again.
- The two solution functions refuse unless the GO holds and the marker exists.
- **Checks added to `verify.py`.** PROTOCOL.md section 8 lists these, but version 1 did not test them:
  - invariant 1 also compares the stage: the reference's "construction" or "base" against the arm's "construction"
    or "construction_none";
  - every row's benchmark and family must be the split's (the family is the bootstrap cluster);
  - in the held run, the three final kernels' metadata files must carry the final manifest's digests and say
    private, CPU only, internet off.
- **Regression tests** (`launch/score_guard_test.py`, run by `launch/smoke_test.py`; record
  `checks/SCORE_GUARD_TESTS.json`). The cases:
  - the review's case: an invented receipt (PASS, OLD_GO, OLD_FREEZE) with the current GO and a mutated row file;
  - the same invented receipt over unchanged rows;
  - a stale receipt: the rows changed after a valid check;
  - a receipt copied from another run folder;
  - a forged receipt with every current digest, over rows that break invariant 1;
  - a missing receipt;
  - a positive control: a valid receipt passes the guard and reaches the marker, which refuses in rehearsal mode.

  All cases run in rehearsal mode, on source stand-in rows, inside an unpacked package that holds no solution file.
  The solution functions are replaced by raising sentinels. Every negative case must stop before the marker, with
  no solution function called.

## 2. Work outside the operation counter (accounting)

**Finding.** The features' whole-output flag compares the content of each object's bounding-box crop with each
target, not only its shape as PROTOCOL.md section 5 says. The frozen W block makes the same comparison as its crop
precondition. Like the pair analysis and the admissibility checks, this pixel work is outside the counted
operations.

**Decision: the counter stays as frozen.**
- "Operations" means the frozen step's own capped counter: applications of a candidate program to a grid.
- The budget rule and the stop rule were computed with this counter. The frozen step does the same uncounted work for
  every view at every budget.
- Counting the comparisons now would change the rules after their outcome was seen. Instead, the uncounted work is
  described and reported:
- **The feature, as it is:** for a W block, 1 when every pair has an input object whose bounding-box crop equals the
  target in shape and content, and 1 when every target is one colour. It is a demonstration-only precondition. A
  shared predicate must still select the object, and the candidate is still verified exactly.
- **Work recorded in the held rows:**
  - for every arm and hole: the counted operations, segmentations, edit applications, constructor CPU, and the
    crop-precondition content comparisons (now counted for reporting);
  - for every task, shared by every arm: the CPU of the sketches and of the pair analysis;
  - for every task, used only by the learned arms: the CPU and content comparisons of the features. The learned arms
    are the guide, the linear model, the leave-one-benchmark-out guide, and donor guidance through the donor's
    features. The frequency order needs only the block keys, and the hand rule only the pair analysis.
  - The scorer reports these totals beside the operation counts for every arm (`RESULTS.json`, "work").
- **Claim wording:**
  - write "fewer counted operations for the same exact answers", always with both arms' CPU and uncounted work
    beside it;
  - if the guided arm's total CPU, features included, is not lower than the hand-set order's, the paper says so;
  - "fewer operations" is never written as less work, and "new reach" is never claimed;
  - write "learned guidance" unless the network beats the linear model;
  - DEV_REPORT.md speaks of counted operations only.
- **Descriptive fact from development; no rule depends on it.** All 75 source units gained at 500 were fitted
  through a single-rule paint candidate. None came through a whole-output form, which is where the crop flag acts.

## 3. The model's loss, exactly

This is what `gcon/model.py` did. The code and the weights are unchanged, nothing is retrained, and every
development number came from this code.
- **Features:** standardised with the training rows' mean and standard deviation. A feature with no spread is set to
  0.
- **Success:** a 0 or 1 target on the logistic output, with mean cross-entropy over each mini-batch.
- **Operations:** the target c = log(1 + the block's operations) is standardised as z = (c - m) / s, with m and s the
  training rows' mean and standard deviation. For the full model, m = 2.590 and s = 2.716; each fold's model uses its
  own m and s. The linear output is trained on z by mean squared error. Predictions are mapped back as
  c_hat = output x s + m.
- **Loss over each mini-batch:** mean cross-entropy plus mean squared error on z. In the protocol's units this is the
  cross-entropy plus the squared error in log(1 + operations) divided by s squared (7.38 for the full model). The
  operations term therefore carries about one seventh of the weight it would carry unstandardised. PROTOCOL.md
  section 5 described the loss as "their sum", and read with this standardisation that is what was done.
- **Weight decay:** 0.0001 x weight is added to each weight's gradient before the Adam step. Biases are excluded,
  and the decay is not part of the loss.
- **Score of a block:** p x exp(-c_hat).

## 4. Custody wording

DEV_REPORT.md said that no held task was opened. The precise statement:
- Study A's benchmark loader (`ngrow.data.tasks`) reads each benchmark's `real.json` into memory. That file holds
  every task's demonstrations and test inputs, held tasks included, and no outputs.
- The development code then kept the source tasks only.
- No held task entered any record, feature, label, model, rule or count.
- No test output or solution file of any half was read.

DEV_REPORT.md now says this.

## 5. What did not change

- The rules: the budget rule, the stop rule, the test budget of 500, the arms, the primary, the secondaries and the
  predictions.
- The trained weights, the configuration, and the held run's tasks and kernel layout.
- The engine's results. The counters added to the W block and to the features change no value. On the seeded
  71-hole sample:
  - the hand-set order at 100 to 5,000 still equals the frozen function with its cap set;
  - direct execution still equals simulation;
  - the features equal the pass 1 records.

  That is 781 checks with 0 failures (`checks/REVISION1_SAMPLE.json`).

## 6. Files changed

FREEZE.json version 2 lists each changed file's digest under both versions.
- **The guard and the receipt:** `gcon/score.py`, `gcon/verify.py`.
- **Work accounting:** `gcon/engine.py`, `gcon/features.py`, `gcon/held.py`.
- **The sample check's output path and feature check:** `gcon/devan.py`.
- **Version 2 freeze:** `gcon/freeze.py`.
- **The guard tests and scrubbing of local paths:** `launch/smoke_test.py`.
- **New files:** `launch/score_guard_test.py`, this file, `FREEZE_V1.json`, and the check records.
- **Wording:** `DEV_REPORT.md` (custody, accounting, notes).
