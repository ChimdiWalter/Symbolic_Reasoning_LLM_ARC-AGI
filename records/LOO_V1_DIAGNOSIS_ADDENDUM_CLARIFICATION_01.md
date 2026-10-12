# Clarification 01 to the representation-eligibility addendum (2026-10-12)

This note is appended to `records/LOO_V1_DIAGNOSIS_ADDENDUM_20261012.md`
(a719383, sha256 `dded91aa...`). That addendum, the diagnosis record
(c2b8cd4, `f022f287...`) and every frozen experiment record are unchanged.
The note follows the post-diagnosis scientific addendum of 2026-10-12, which
authorizes diagnosis and design only. Nothing here was run as a repair.

## 1. Monotonicity: observed, not a theorem; and not observed everywhere

**What was overstated.** The addendum's section 2 is titled "the predicate
behaves as designed". Its own text is correct: consistency survives removing
a demonstration, and "only the pooled coverage ratio can move either way".
The summaries derived from it went further and called the whole eligibility
test monotone:
- the addendum commit message: "the predicate is monotone in the
  demonstrations (a fold never loses a coherent variant)";
- RESUME and the stage ledger: "eligibility is MONOTONE";
- the summit evidence index: "The eligibility predicate is monotone in the
  demonstrations";
- paper section 8.17: "removing demonstrations can only add coherent
  variants";
- the poster: "removing demonstrations never removes an eligible view".

**The correct statement.**

1. **Deletion-stable, from the code.** If the consistency part of the test
   holds on a set of demonstrations, it holds on every non-empty subset.
   - The three clauses are the count relation, copy-like growth on every
     pair, and grow-explained outputs on every pair with zero granularity
     mismatch.
   - Each clause is either a per-pair condition or one parameter shared by
     all pairs.
   - This rests on three assumptions:
     - the per-pair background, segmentation and matching are computed from
       that pair alone (`segmentation.py:337-351`);
     - `ARC_CREATE_COHERENCE` is off, as in every run here;
     - the subset is non-empty.
2. **Not deletion-stable.** The coverage clause pools pixels over the pairs
   and must reach at least 0.80. Removing a well-covered demonstration can
   pull it below the threshold. So the complete coherence test is not
   guaranteed to be monotone.
3. **Observed.** The census (`outputs/loo_v1/probe_equivalence.json`,
   7d11993, sha256 `90c2a325...`; script 4882e22) found:
   - No losses where the addendum looked:
     - the 4 failure-conditioned (FC) tasks: 0 losses in 50 parent-fold
       pairs;
     - the 24 synthetic fixtures: 0 losses in 72 pairs.
   - Losses on the full development set:
     - across all 60 development tasks, 7 of 724 parent-fold pairs, in 5
       tasks, lose a coherent view;
     - every loss comes from coverage falling below 0.80 (parent 0.800 to
       0.880, fold 0.667 to 0.796), with consistency intact;
     - consistency never broke: 0 of 3,886 development and 0 of 405
       synthetic consistent (view, parent-fold) cases.
   - A constructed TOY pair (labelled as such) shows the mechanism directly:
     - pooled coverage is 0.886 and the view is coherent;
     - after removing the well-covered demonstration, coverage is 0.200 and
       the view is incoherent.
4. **The kf892487f1049 mechanism is unaffected.** Coverage is 1.0 on every
   subset of that task. The 02/13 exclusion is the cap acting on views that
   the smaller pair set admits through consistency.

**Wording to use.** "Count consistency (all three consistency clauses) is
deletion-stable under the stated assumptions. The complete eligibility test
is not: pooled coverage can fall below 0.80 when a demonstration is removed,
and on the development set it did so in 7 of 724 parent-fold comparisons."

## 2. P2 is a FORENSIC proposal only

P2 (addendum section 7) would append v*, the variant of the program under
validation, inside the engine's own leave-one-out. The parent induction
chose v* using all of its pairs, including the inner held-out demonstration.

Injecting v* into the fold's induction therefore lets that demonstration
influence which representation the fold receives. The amended inner
leave-one-out would test whether the program is stable given a
representation selected with that extra information. That is not
independent fold re-induction. **P2 cannot satisfy the original inner
leave-one-out certificate.**

The outer held-out demonstration stays protected, so this is not leakage of
an answer. It is still a weaker internal validation.

Decision recorded (user, 2026-10-12): P2 is not executed. If it were ever
run, it would be a labelled forensic diagnostic that counts toward no
certificate. Its pre-registered predictions are preserved as written:
- at most 3 of 4 outer folds pass on kf892487f1049;
- f1 is still refuted after window_fill;
- the screen is predicted to fail.

The reach v2 variant-first recheck stays STOPPED and is not to be resumed.

## 3. Validation boundary, binding on every future candidate

- **What a fold may use.** A fold's programs, representation choices,
  extension parameters, ranking decisions and priors are selected using only
  that fold's training subset. Nothing derived from the fold's held-out
  output is injected into it.
- **Where this applies.** It holds for the engine's inner leave-one-out and
  for the outer adaptive leave-one-out, each with its own held-out boundary.
- **What stays as it is.** The original independent re-induction standard
  and the engine's acceptance requirements remain intact.
- **What any future repair needs:**
  - a separately versioned implementation;
  - pre-registered tests and a failure policy;
  - synthetic adversarial controls;
  - no regression on native successes;
  - no new false acceptance under the stated controls;
  - matched resource accounting;
  - an unchanged independent evaluator.

## 4. Derived documents corrected with this note

The following were corrected; the addendum and the frozen records were not
edited:
- `docs/PAPER_SKELETON.md`
- `records/CORA_SUMMIT_POSTER_EVIDENCE_20261012.md`
- `docs/summit_poster/poster.tex` and `poster.pdf`
- `docs/summit_poster/abstract.tex` and `abstract.pdf`
- `RESUME.md`
- `records/STAGE_LEDGER.json`
