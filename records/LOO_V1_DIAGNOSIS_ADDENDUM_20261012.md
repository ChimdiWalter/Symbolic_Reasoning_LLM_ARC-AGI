# Adaptive LOO stability v1: diagnosis addendum, representation eligibility (2026-10-12)

DEVELOPMENT and SYNTHETIC, observation only (summit addendum, sections B to
E). No engine file was changed and no repair was run. The reach v2 recheck
stays STOPPED with 0 rows, and pilot v2 stays FROZEN_NOT_RUN (c1906ee). The
development subsets examined here were chosen after the failure was seen.
That makes this causal debugging, not test evidence. This record extends
`records/LOO_V1_DIAGNOSIS_20261012.md` (c2b8cd4, sha256 `f022f287...`) and
leaves it unchanged. It is committed before any intervention is selected.

Sources (sha256):

| output | sha256 | probe commit | output commit |
|---|---|---|---|
| `outputs/loo_v1/probe_kf892487f1049.json` | `9bdff08a...` | | 955542c |
| `outputs/loo_v1/probe_variants.json` | `a4eb82d8...` | | |
| `outputs/loo_v1/probe_eligibility.json` | `922151e2...` | fa7f67c | 82251a4 |
| `outputs/loo_v1/probe_negative.json` | `2f100350...` | 1f03a1c | 70d3ed9 |
| `outputs/loo_v1/probe_exposure.json` | `794ad70b...` | | 3ba75e5 |

## 1. The exact predicate and the first rejection site

A variant is coherent when it is consistent and its pixel coverage is at
least 0.80 (`geocat_arc/object_reasoning/segmentation.py:47`, `:291`).

Consistency is any one of three clauses:
- the count relation (`_count_relation_consistent`, `:261`);
- copy-like growth on every pair;
- grow-explained outputs on every pair, with zero granularity mismatch and
  unchanged shapes.

The count relation works as follows:
- A single pair is always consistent.
- A pair with zero input objects is never consistent.
- Across several pairs it accepts one parameter on every pair: a constant
  difference, a constant output count, or n_out = f * n_in with an integer
  f >= 1.

kf892487f1049 has coverage 1.0 for every variant on every subset, so
coverage never rejects. Each row lists the (input, output) object counts in
the order demonstration 0, 1, 2, 3.

| subset | S1 to S5 counts | S1 to S5 | S6 counts | S6 | searched | fold winner |
|---|---|---|---|---|---|---|
| full; every 3-subset; (0,1), (0,3), (1,2), (2,3) | (2,1) and (4,2) mixed | not coherent: first rejection `count_relation_inconsistent_and_no_copy_or_grow_relaxation` (differences -1 and -2; outputs 1 and 2; the ratio clause fails because n_out < n_in) | (1,1) and (2,2) | coherent | S6, S7 | G (1 rule, worst parameter class FEATURE) |
| (0,2) | (2,1), (2,1) | coherent (constant difference -1) | (1,1), (1,1) | coherent, 4 objects against 6, cut | S1, S2, S3, S5 | 2 rules, CONSTANT class, wrong on the held-out demonstration |
| (1,3) | (4,2), (4,2) | coherent (constant difference -2) | (2,2), (2,2) | coherent, 8 objects against 12, cut | S1, S2, S3, S5 | 4 rules, CONSTANT class, wrong on the held-out demonstration |

On (0,2) and (1,3) all seven variants are coherent. The cap
(`inducer.py:166`, `MAX_SEG_VARIANTS_TRIED = 4`) keeps the first four in
the trial order (`types.py:52`). S6 is therefore eligible but never
searched. It is "cut by the cap", not "ineligible". This corrects the
earlier wording "4 rules" for both pairs: the (0,2) winner has 2 rules.

## 2. Example-count dependence: the predicate behaves as designed

Every consistency clause quantifies over pairs:
- the count relation needs the same parameter on every pair;
- copy-like and grow-explained are per-pair conditions;
- the mismatch is a sum of non-negative per-pair terms.

So a variant consistent on a set of demonstrations is consistent on every
non-empty subset. Only the pooled coverage ratio can move either way.

Static check (`probe_exposure.json`):
- A fold never lost a coherent variant: 0 of 72 synthetic and 0 of 50
  development parent-fold pairs.
- Folds added coherent variants in 12 of 72 synthetic and 24 of 50
  development pairs.
- On kf892487f1049 the only additions are S1 to S5, on exactly (0,2) and
  (1,3).

The predicate does what its docstring says. The defect is its interaction
with the cap. The engine's own cross-variant canonicalization
(`_induce_candidate`, round 3) states the intended invariant: after a
train-perfect winner, "the remaining STRICTLY-COARSER variants ... are still
tried ... so an N-1-pair reinduction fold converges on the same variant the
full train set picks even when the fold's smaller pair set lets a finer
variant fit spuriously". But the cap is applied before that loop, in fixed
order, to the fold's larger coherent set. On (0,2) and (1,3) it cuts the
strictly coarser S6. The invariant fails in exactly the case it was written
for.

## 3. Hypotheses about the 02/13 exclusion

- **H_rep (representation): TRUE.** The searched set changes with the
  demonstration subset, and S6 is cut.
- **H_search: TRUE at variant level only (the cap).** Exploring every
  candidate of the searched variants (`explore_all`) does not recover G: 4
  programs on (0,2), 8 on (1,3), none of them G.
- **H_rank: FALSE.** G is never enumerated on these pairs. The engine's
  winner key puts the worst parameter class first, and G's class (FEATURE,
  rank 1) beats CONSTANT (rank 3). S6 is strictly coarser, so the parsimony
  skip would not prune it.
- **H_evid: WEAK ONLY.** G and the constant-class programs are both
  train-exact on each of these pairs, so two demonstrations do not exclude
  the wrong programs. The engine's own preference would still choose G.
  Evidence is binding elsewhere: k017955a77fc5's support and its
  identifiability from one demonstration.
- **H_budget: FALSE.**
  - WALL = CPU1 in 23 of 23 arms.
  - The pair searches complete: 0.25 s of CPU on (0,1), 1.6 s on (0,2) and
    23 s on (1,3); explore_all takes 5.4 s and 73 s on (0,2) and (1,3).
  - Outer fold f3 hit no deadline at all.

## 4. Falsified hypotheses (recorded before any intervention is selected)

1. "S6/S7 are ineligible on (0,2) and (1,3)": false. They are eligible and
   cut by the cap.
2. "The cross-variant parsimony skip pruned S6": false (955542c). S6 never
   entered the candidate list.
3. "A ranking error": false (section 3).
4. "Budget or host contention": false (section 3).
5. "Searching an extension's variant first and admitting it is a safe
   generic repair" (the reach v2 variant-carrying installation, 568af22):
   falsified on synthetic controls. In the ADMIT condition (section 5) it
   produced 1 false acceptance and 2 rejections of natively correct tasks,
   and gained nothing.
6. "Promoting an already eligible variant first is safe": falsified the same
   way (PROMOTE, section 5).
7. "Letting the coarser completion reach every cut variant is narrow" (P1):
   falsified statically (section 6). It would be exposed on 73 of 96
   synthetic subsets, almost always through S7. S7 is the proximity variant
   that the engine consults only when the connectivity variants are
   incoherent (`types.py`).

## 5. Negative synthetic probes

Design (1f03a1c):
- 24 seeded tasks in 6 rule families, each with 3 training and 2 held-out
  demonstrations from the same rule.
- Each run is the engine's own induction (train-exact plus its own
  leave-one-out, 20 s).
- BASE: no overlay.
- PROMOTE: each eligible variant searched first.
- ADMIT: each ineligible variant searched first and admitted.
- Both overlays are local to the probe.

BASE: 7 correct, 2 false acceptances, 15 rejected. All 15 rejections are at
the engine's own leave-one-out, which re-induces from 2 demonstrations.

Each overlay run is paired with the same task's BASE outcome:

| condition | runs (tasks) | unchanged | correct to rejected | correct to false acceptance | rejected to false acceptance | gains |
|---|---|---|---|---|---|---|
| PROMOTE | 131 (23) | 128 | 2 (translate_down_0 S6, translate_down_1 S7) | 0 | 1 (translate_down_2 S7) | 0 |
| ADMIT | 37 (10) | 34 | 2 (multicolor_majority_3 S1, S5) | 1 (halo_0 S4) | 0 | 0 |

In total, 6 of 168 runs changed outcome, and all 6 changes were harmful.
`docs/summit_poster/figures/fig_negative_controls.png` shows them. The
code path accounts for three harm mechanisms:

- **M1, parsimony pruning.** A coarser variant searched first wins. The skip
  `_seg_count(seg) >= min(winner counts)` then prunes every finer native
  variant before it is tried.
  - translate_down_0: S6 (10 objects) prunes S1 to S3 (14 objects).
  - translate_down_1: S7 (8 objects) does the same.
  - In both cases the forced program then fails the engine's leave-one-out.
- **M2, false acceptance.** The forced variant's program passes train-exact
  and the engine's leave-one-out, but it is wrong on held-out
  demonstrations: translate_down_2 with S7, and halo_0 with S4 (an
  incoherent view).
- **M3, budget displacement.** Admitting incoherent S1 or S5 first on
  multicolor_majority_3 took 38.3 s and 36.8 s, against 10.5 s natively,
  and the run was rejected at the leave-one-out. This is consistent with
  budget displacement, but the probe does not separate it from a wrong fold
  program.

Limits:
- Only 7 tasks are natively correct, so regressions are measurable on 7
  tasks only.
- The families are synthetic, not ARC.
- 3 demonstrations put every task under the same nested reduction as the
  real folds.

Consequence: the reach v2 repair (568af22) belongs to the
PROMOTE/ADMIT class, because it searches V first and admits it. It is NOT
recommended to run, and its recheck stays STOPPED. Retiring it is the
user's decision.

## 6. Static exposure of two cap corrections (3ba75e5; no induction run)

- **P1, global coarser completion.** Search any cut coherent variant that is
  coarser than a kept one.
  - The cap binds on 74 of 96 synthetic subsets.
  - P1's necessary condition holds on 73 of them, almost always through S7.
  - Verdict: broad. Rejected before any run.
- **P2, anchored completion inside the engine's own leave-one-out.** The
  upper bound counts every kept parent variant that a fold cuts.
  - Synthetic: 3 of 72 folds: bbox_fill_L_0 (fold 12, S6),
    multicolor_majority_1 (fold 02, S4 and S7) and multicolor_majority_3
    (fold 01, S4, S6 and S7). multicolor_majority_3's native winner is S3,
    which is never cut. So at most two tasks can change, and both are
    natively rejected.
  - Development: 15 of 50 folds of the four failure-conditioned (FC) tasks.
    On kf892487f1049 they are exactly the failing inner folds of all four
    outer folds: (0,2) in f1 and f3, (1,3) in f0 and f2.

## 7. Intervention proposal P2: LOO-ANCHORED VARIANT COMPLETION

Status: NOT AUTHORIZED. Nothing is implemented or run.

Class: representation-admission correction, not semantic invention.

**Rule.** P2 acts only inside the engine's own leave-one-out (the fold
inductions of `loo_validate`, `inducer.py:2749`). Let v* be the
segmentation variant of the program under validation. If the unchanged
predicate finds v* coherent on the fold's pairs, but the cap cuts it,
append v* after the kept variants.

Nothing else changes:
- the predicate, its threshold and the trial order;
- the cap for the kept variants;
- the cheap-first probe;
- the parsimony skip: v* is searched only if no winner exists yet, or if v*
  is strictly coarser than the fold's winner;
- the winner key;
- the top-level induction;
- the CORA proposer and its selection;
- the outer adaptive leave-one-out;
- every budget.

**Why it is generic.** It restores the engine's own documented invariant
(section 2), which the cap breaks whenever a smaller pair set admits extra,
finer variants. v* comes from the program under validation, never from a
task id or an answer.

**Constraints learned from section 5.**
- No reordering, which avoids M1 and M3.
- No admission of an incoherent variant, which avoids the M2 route through
  incoherent views.
- At most one variant, appended last.

**Disclosed costs.**
1. P2 changes the engine's internal leave-one-out gate. In exposed folds the
   gate can pass where it now fails. The protocol's acceptance criteria are
   unchanged: the outer adaptive leave-one-out rebuilt per fold, replay,
   attribution, support and unanimity. But this is still a change to the
   reasoner's acceptance procedure. Whether it counts as weakening the
   acceptance criteria is the author's decision.
2. Anchoring. The parent chose v* using the inner held-out pair. The inner
   leave-one-out then tests whether the rule is stable given the
   representation, not whether the representation is re-selected. The
   outer adaptive leave-one-out stays independent: the outer held-out
   demonstration never influences v*.
3. Cross-fold budget. The extra search spends the induction's shared
   deadline, so later folds can hit it earlier.

**Implementation, if authorized.**
- A new versioned package installs P2 as a context-manager overlay on a
  generated copy of `_induce_candidate`, with marked lines and a `--check`
  equality test (as `scripts/build_measure2.py` does).
- No engine file is edited, and the reach v1, pilot v2 and diagnosis
  freezes are unchanged.
- Mutant tests:
  - with the anchor off, results are byte-identical;
  - with v* already kept, results are identical;
  - the overlay restores the engine afterwards.

**Pre-registered predictions** (committed here, before any implementation):
1. P2 changes only the folds listed in section 6. Outside them, the program
   sha, failure stage and acceptance are byte-identical.
2. kf892487f1049:
   - In the inner folds (0,2) and (1,3), S6 is searched and G wins on the
     engine's own key.
   - Outer folds f0, f2 and f3 accept G and reproduce their held-out
     demonstration.
   - f1 still fails. The CORA reasoner installs only the first proposal
     (`cora_reach/measure.py:384`), which is window_fill on that fold, and
     the held-out demonstration refutes it.
   - Complete adaptive leave-one-out is therefore NOT predicted: 3 of 4
     folds at best.
3. k5a49896251a2:
   - The full-data run can become accepted, because its inner folds (0,1)
     and (1,2) are exposed.
   - Outer fold 1 can pass.
   - Outer folds 0 and 2 stay NO_PROPOSAL, because the cut happens in K's
     extraction.
   - Not complete.
4. k017955a77fc5 and k5991e227189e: unchanged at full data, because V is
   never coherent there.
5. The screen (at least one development task with invariant conditions 1 to
   5 together) is predicted to FAIL under P2. P2's value is diagnostic: it
   confirms or refutes the mechanism, and it removes one blocker if it is
   safe.

**Frozen assessment criteria.** All of them must hold for P2 to be kept:
- **S1, synthetic safety.**
  - The fixtures are the 24 tasks of section 5 (same seeds, 20 s) plus a
    new adversarial family of at least 12 tasks, generated and committed
    before P2 runs.
  - In every adversarial task, the parent's variant is cut in a fold.
  - In half of them the coarse rule is correct. In the other half a decoy
    coarse rule is train-exact but wrong on held-out demonstrations.
  - Required: 0 new false acceptances and 0 regressions against the same
    engine without P2.
- **S2, byte identity.** Every task or fold outside the exposure set is
  unchanged.
- **S3, development side effects.**
  - On the 60 tasks, no task that the original engine accepts changes its
    program or loses acceptance.
  - Both arms run under the same `budget_s` and the CPU1 clock, and the
    report gives CPU totals for both.
- **E1, mechanism.** Prediction 2's inner-fold claim holds. If it fails, the
  mechanism account is wrong: stop and re-diagnose.

**Kill rule.**
- Any S1, S2, S3 or E1 failure rejects P2, and the rejection is recorded.
- No tuning to make kf892487f1049 pass.
- Whatever the outcome, pilot v2 and the 488 untouched candidates stay
  untouched.
- A pass would license only a new, versioned, prospectively frozen blind
  pilot, and only on a new explicit authorization.

## 8. Claims after this addendum

Unchanged. Nothing is upgraded:
- no new ARC solve; the certified score is 185/1,000;
- reach v1 adaptive leave-one-out is 0 of 14 folds;
- BOUNDED_SEMANTIC_EXTENSION_CERTIFIED is not established;
- the biology lane is untested.

Newly established, forensic tier, development and synthetic only:
- the predicate-level mechanism of the 02/13 exclusion;
- the monotonicity of the eligibility predicate;
- the harmfulness of variant-first interventions on synthetic controls.

## 9. Next safe action

None is launched. P2 waits for an explicit decision:
- authorize its development experiment as specified;
- amend it;
- or keep the program at diagnosis.
