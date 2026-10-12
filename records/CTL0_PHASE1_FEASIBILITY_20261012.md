# Failure-typed controller v0, phase 1: candidate audit and feasibility (2026-10-12)

**Scope.** READ-ONLY audit, schema design and static feasibility (user
directive "FAILURE-TYPED REASONING CONTROLLER v0, PHASE 1", 2026-10-12). No
intervention was run, and no engine or measurement package was changed.

**Start.** HEAD 106a911, tree clean, nothing running, all 7 freezes 0
problems. P3 is closed as P3_REJECTED; it was not rerun or tuned. P2 and
reach v2 remain unexecuted.

**Evidence labels.** DIRECT = read from a sealed record or recomputed from
recorded grids. FORENSIC = inferred from records, examined after the failure
was seen. UNKNOWN = not determinable from what was recorded.

**Sources.**

| source | identity |
|---|---|
| reach v1 rows | `outputs/reach_v1/measure_rows.jsonl` (60ddd04) |
| diagnosis rows | `outputs/loo_v1/diagnose_rows.jsonl` (4c14f9d) |
| P3 rows | `outputs/p3/preflight_rows.jsonl` (98c9bed) |
| this audit | `scripts/ctl0_audit.py` (83eba55) -> `outputs/ctl0/audit.json` (ecfa842, sha256 `cc723317...`) |

## 1. Candidates on the four real tasks (full data; DIRECT)

| task | proposals generated | distinct | fit the failure evidence | compiled and installed | engine result with e | resource limit | pool predicting test |
|---|---|---|---|---|---|---|---|
| kf892487f1049 | 1 (bbox_fill, S6) | 1 | 1 (6 instances) | 1 | ACCEPTED and used; fails adaptive LOO | no | 1 |
| k5a49896251a2 | 1 (connect, S6) | 1 | 1 | 1 | rejected at the engine's own leave-one-out | no | 1 |
| k017955a77fc5 | 1 (window_fill, S2) | 1 | 1 | 1 | no result | 450 s hard cap, twice | 1 |
| k5991e227189e | 1 (connect, S6) | 1 | 1 | 1 | no result | 450 s hard cap, twice | 1 |

Notes:
- "Fit the failure evidence" means reproducing every memorized instance of
  one view. That is the proposer's acceptance rule (`construct.py:48`).
- Demonstrations-only construction proposes nothing on these four tasks. The
  shuffled-failure control proposes only on k5991e227189e, and only the
  task's own connect.
- At full data, no task has competing candidates.

## 2. Candidates in every outer adaptive-LOO fold (DIRECT)

| task | fold | proposals | selected | engine | first failure |
|---|---|---|---|---|---|
| kf892487f1049 | f0 | 1 | bbox_fill (= full) | rejected at its own LOO | inner pair (1,3) cuts S6 |
| kf892487f1049 | **f1** | **2: window_fill(k=2), bbox_fill** | window_fill | rejected at its own LOO | see section 3 |
| kf892487f1049 | f2 | 1 | bbox_fill | rejected at its own LOO | inner pair (1,3) cuts S6 |
| kf892487f1049 | f3 | 1 | bbox_fill | rejected at its own LOO | inner pair (0,2) cuts S6 |
| k5a49896251a2 | f0 | 0 | none | | the extraction cuts S6 (NO_PROPOSAL) |
| k5a49896251a2 | f1 | 1 | connect | rejected at its own LOO | single-demonstration inner folds cut S6 |
| k5a49896251a2 | f2 | 0 | none | | the extraction cuts S6 |
| k017955a77fc5 | f0, f1 | 0 | none | | the support needs demonstrations 0 and 1 together |
| k017955a77fc5 | f2 | 1 | window_fill | 450 s cap | identifiability from one demonstration |
| k5991e227189e | f0 | 1 | connect | rejected at its own LOO | S6 dropped in inner subsets |
| k5991e227189e | f1 | 0 | none | | the outer subset drops S6 |
| k5991e227189e | f2, f3 | 1 | connect | 450 s cap | S6 dropped in inner subsets |

Totals:
- 13 of 14 folds have at most one candidate.
- Only kf892487f1049 f1 has two.
- No fold produced a false acceptance; every failure is a rejection or a
  non-proposal.

## 3. kf892487f1049 fold f1 (demonstration 1 removed)

- **A. Was bbox_fill generated?** Yes (DIRECT). It is proposal 2, identical
  to the full-data extension `gx_9948b01172bd12a8`.
- **B. Why was window_fill first?** By the fixed grammar order (DIRECT, code
  plus record). Both settings reproduce all 4 of the fold's memorized S6
  instances; within one view, settings are proposed in GRAMMAR order, where
  window_fill precedes bbox_fill (`construct.py:26`); and the measurement
  installs `proposals[0]` (`measure.py:384`). No evidence ranked them.
- **C. Did both fit every available demonstration?** Yes (DIRECT):
  - applied in S6, each reproduces all 3 fold training outputs exactly
    (`ctl0_audit`);
  - installed, each yields a train-exact top-level program: G* with
    window_fill (B arm) and exactly G (sha `f22944438323`) with bbox_fill
    (the forensic C arm).
- **D. Did they differ on training-derived validation evidence?** No
  (DIRECT). Both have the same fit, the same instance support (4 instances, 3
  demonstrations), and both fail the engine's leave-one-out the same way. They
  differ on the permitted UNLABELLED inputs: 4 cells on demonstration 1's
  input and 4 cells on the test input.
- **E. Could a rule prefer bbox_fill without the removed demonstration?**
  - Not from the fold's evidence.
  - A parsimony prior would (bbox_fill has no parameter, window_fill has
    k = 2). But that is a post hoc observation on one fold, chosen after the
    failure was seen, and not a validated rule (FORENSIC).
  - Only the removed demonstration separates them (window_fill reproduces 0
    of its 2 instances, bbox_fill 2 of 2), and a selector may not use it.
- **F. Should the reasoner have abstained?** On fold-local evidence, yes:
  two plausible repairs fit every demonstration and disagree on the inputs to
  be predicted. But abstention would not have produced a solve. With bbox_fill
  installed, the fold still fails the engine's leave-one-out (C arm, DIRECT),
  because inner pair (0,2) cuts S6 (the representation-cap mechanism).
- **G. Construction failure?** No. bbox_fill was generated. f1 is
  MULTIPLE_PLAUSIBLE_REPAIRS on top of a VERIFICATION_BLOCKER.

## 4. The two P3 false acceptances (FORENSIC; truth reported separately)

| | translate_down_2 | ADV:translate_down_505 |
|---|---|---|
| native (BASE) | rejected at its own LOO, 2 of 3 folds | same, after budget exhaustion |
| P3 | S7 program accepted, 3 of 3 folds, in 3 s | same, in 6 s |
| unseen S7 composition on a held-out input | a single-component group | a three-colour group |

- **Which evidence supported the wrong program.** Exact fit on 3
  demonstrations, plus an inner leave-one-out in which every 2-pair fold also
  had S7 admitted and converged on the same S7 program.
- **Competing candidates.** Yes. The native S1-based train-exact candidate
  existed (it is what BASE validated and rejected). Its predictions were not
  recorded (UNKNOWN).
- **Did the engine detect disagreement?** No. One winner is chosen by key,
  with ties broken toward fewer objects. No cross-candidate check runs on
  unlabelled inputs.
- **Why inner LOO passed.** The training demonstrations never contain the
  configuration that breaks the proximity grouping. Every fold sees the same
  kind of groups.
- **Missing information.** The held-out inputs contain S7 groups whose
  composition never occurs in the training inputs (DIRECT, input-only;
  `ctl0_audit`).
- **Could a no-oracle diagnostic have seen the risk?** An input-only
  out-of-support check flags both P3 false acceptances. Across all 37 accepted
  synthetic programs, it flags 4 of 8 false acceptances and 1 of 29 correct
  programs (the one P3 gain).
- **Caveats.** It misses the 4 rule-level false acceptances (S3 and S1
  views). It is post hoc, the 37 programs are correlated BASE/P3 pairs, and
  it is synthetic. It is NOT validated.

## 5. Ambiguity indicators studied (none assumed valid)

| indicator | computable without answers | genuine or just count | stable under harmless changes | rejects correct | misses wrong |
|---|---|---|---|---|---|
| several distinct exact-fit candidates | yes | count only: 13 of 14 folds have at most 1 | yes | unknown | yes (single-candidate false acceptances) |
| disagreement on permitted unlabelled inputs | yes | genuine where it fires: kf892487f1049 f1 | expected yes, untested | unknown (needs candidate pools) | unknown |
| disagreement across folds | NO for selection: other folds contain the fold's held-out demonstration | | | | |
| ranking by a fixed prior (grammar order) | yes | identifies an evidence-free ranking | yes | | |
| demonstration support (existing support gate) | yes | genuine | yes | known cost: 3 of 4 synthetic abstained correctly-predicted (pilot v1) | |
| representation out of support (post hoc) | yes | partly | untested | 1 of 29 | 4 of 8 |
| top-level accept but inner-LOO fail | yes | genuine | yes | already blocks | |

## 6. Failure categories, against the evidence

**Supported (established):**
- REPRESENTATION_EXCLUDED: the cap cuts the view in inner folds (11 of 14
  folds, the earlier diagnosis).
- REPAIR_NOT_GENERATED: 5 folds with no proposal.
- MULTIPLE_PLAUSIBLE_REPAIRS: kf892487f1049 f1.
- RESOURCE_EXHAUSTED: 450 s caps in 3 folds and 2 full-data runs.
- ENGINE_REJECTED: k5a49896251a2 at full data.
- CERTIFICATION_UNSTABLE: train-exact at the top level, failing at the
  engine's leave-one-out.

**Suspected only:**
- INSUFFICIENT_EVIDENCE: k017955a77fc5 support and single-demonstration
  identifiability.

**Not identifiable here:**
- SEARCH_TRUNCATED: deadlines confound it with resources.
- CAPABILITY_GAP_SUSPECTED: no complete bounded absence check exists.
- UNKNOWN: kept.

## 7. Verdict: MIXED_OR_UNRESOLVED

- **Selection is not the limiting factor for any real verified
  reconstruction.** Only 1 of 14 folds has competing candidates, and there
  the correct one also fails verification.
- **Per fold:**
  - kf892487f1049 f1 is ABSTENTION_ONLY_FEASIBLE over a VERIFICATION_BLOCKER.
  - 8 folds are VERIFICATION_BLOCKER (representation excluded in inner folds),
    3 of them with resource exhaustion.
  - 5 folds are CONSTRUCTION_BLOCKER.
- **On real tasks, a selector or an abstention rule can neither add a
  verified reconstruction nor remove a false acceptance:** reach v1 had none.
- **On synthetic tasks, the native verifier does false-accept:** 3 of 41
  native runs here; 5 of 5 and 28 of 28 wrong extensions in v1.9. That is
  the one place a generic unsupported-confidence check has evidence behind it.

## 8. Claim ceiling

Diagnostic labels only. No new scientific result, no selector or controller,
no ARC result. The certified score is still 185 of 1,000, and pilot v2 is
FROZEN_NOT_RUN.
