# Paper Track review of the CORA draft, as a skeptical judge (1 Nov 2026)

**Read:**
- the Kaggle Writeup (`paper/writeup/WRITEUP.md`, without the editor's note);
- the manuscript (`paper/v2_neural_cora/main.tex`);
- the criteria page (arcprize.org/competitions/2026/paper);
- the records the paper cites, opened only to check numbers. Two of them are reviews:
  `records/CORA_SYNTHESIS_REVIEW_20261027.md` and `records/NOV1_INDEPENDENT_RESEARCH_REVIEW.md`.

**Not read:**
- the authors' review and claims notes in `paper/writeup/`;
- RESUME or PROGRESS files;
- Step B, VDCG, other projects' job folders, reserved private data and sealed partitions.

PENDING placeholders are not penalized. Word counts are whitespace counts. By that count the Writeup now has 1,455
words without the editor's note.

**The criteria page has three more requirements:**
- required sections: Abstract, Intro, Prior work, Approach "with an algorithm-level description", Results and
  Conclusion;
- "No filler, no unnecessary equations";
- Outstanding Papers need a score above 4.5.

## 1. Scores

| criterion | score | justification |
|---|---|---|
| Accuracy | **0** if O is linked; **2** if H is linked | **O:** the paper's own estimate is 0 to 2% on the hidden set. On 207 sealed training puzzles the same core answered 11 and got 8 right, and on Kaggle's CPUs the O+ rehearsal answered 1 of 172 public-evaluation outputs. **H:** it should score near NVARC's level, but its CORA part changed 0 of 172 public-evaluation outputs, so its number measures NVARC's method. H's eligibility is unconfirmed. |
| Universality | **1** | The paper says the submitted component "has run only on ARC". The biology studies use code written separately, and failure-blind, shuffled, generic and try-all arms matched every gain. In the StarDist study all 13 arms chose the same single intensity filter. This shows a portable design, not a method that generalizes. |
| Progress | **1** | The negative results are useful: learned pruning loses to static search; given an operation's exact behaviour, a 4B proposer implements 1 of 11; verified symbolic second attempts add nothing beside a strong neural model. None opens a path to higher accuracy. The one positive mechanism result rests on 4 tasks, inside a 211-structure language built to contain the answers. |
| Theory | **2** | Better than most papers: falsifiable predictions with named controls, the nesting identity, and a clear account of spurious fits. But the propositions are accounting identities, and the guard mechanism of the submitted component was not confirmed (sealed p = 0.5). The main evidence for "why" (Test S1) is weaker than reported once duplicate seeds are collapsed (objection 2). |
| Completeness | **3** | The manuscript documents caps, fallbacks, the merge rule, neural settings, engineering and eligibility. The Writeup falls short in four ways: it gives no algorithm-level description of CORA-CAST; it does not say that O and H run different CORA-CAST versions; it does not say that H's version timed out on the one puzzle only CORA-CAST answered; and it does not describe O+ if O+ is linked. The entry code is private until release. |
| Novelty | **2** | The paper says no ingredient is new, and its "what differs" column lists controls rather than mechanisms. The mechanism that worked (a sketch with one hole and the hole's required inputs and outputs, filled from a fixed structure language) is deductive synthesis: Sketch, λ², FlashMeta. None of these is in the Writeup's table. The submitted component is close to ARGA plus selective prediction. |

**Total:** 9 of 30 with O linked, 11 of 30 with H linked (mean 1.5 to 1.8).

**What a judge would credit:**
- unusual candour: labels for exposure and contamination, NVARC credited, negative results kept;
- pre-registration with frozen hashes, and one sealed run;
- blind, shuffled and matched-compute controls on every positive claim.

## 2. Objections, ranked by impact on the score

Fixes are given as Writeup text. Word changes are in brackets.

### 1. The approach described is not the approach submitted (Completeness, Novelty, Theory; possible gate)

**The text:**
- Title: "CORA: Failure-Grounded Construction and Verification of Executable Reasoning Capabilities".
- Abstract: "We test one hypothesis: a reasoning system can generalize better by using execution failures to decide which
  representation, program structure or executable capability to revise."
- Section 3: "**Capability growth** (research only, in no entry)."

**Why it costs points:**
- The rules require the code submission to "demonstrate the approach the paper describes".
- The title, the stated hypothesis and the Theory paragraph are about failure-grounded construction, which no entry
  runs.
- What the entries run is a hand-written verify-or-abstain module. It added 0 outputs to H, and the paper expects O to
  score about 0 to 2%.
- A judge can therefore score Completeness and Novelty only on the submitted part, and treat the capability-growth
  results as outside the submission.

**Fix [about -2]:**
- Keep the title. Change the subtitle to "Verify-or-abstain program answers on ARC-AGI-2, and a controlled test of
  failure-derived construction".
- Replace the first two abstract sentences (51 words) with: "We ask whether execution failures can tell a reasoning
  system what to change. Our entries use the last step of that loop: they answer with a hand-written, typed object
  program (CORA-CAST) only when it reproduces every demonstration and is re-derived with each demonstration held
  out."
- In Section 3, put the CORA-CAST algorithm (objection 5) first, and capability growth under "Research study (no
  entry runs it)".

### 2. The central positive result counts each task three times (Theory, Progress, trust)

**The text:**
- Abstract: "(24 against 12 of 33, p = 0.0005)".
- Section 5: "the symbolic constructor recovered 24 of 33 units with CORA's specification, 12 from the demonstrations alone
  (p = 0.0005; clustered interval 0.33 to 0.44) and 0 with shuffled specifications."

**Why it costs points:**
- The 33 units are 11 motivating tasks times 3 seeds.
- In `experiments/capability_growth_20261027/runs/s1_eval/results.json`, four arms give the same outcome on all three
  seeds of every task: the specification arm, the demonstrations-only arm, the primary arm and matched search. Blind
  enumeration is the only arm that varies (on 7 tasks).
- So the evidence is 8 tasks against 4: 4 discordant, one gained task per family, exact McNemar p = 0.125.
- Against matched search it is 8 against 5 (4 to 1, p = 0.375).
- Blind enumeration recovers 10 of the 11 tasks in at least one seed.
- The interval 0.33 to 0.44 comes from bootstrapping over 4 families, each of which gained exactly one task.
- The Writeup never defines "units", and "(11 tasks each)" suggests 44 tasks.
- Every count from a deterministic arm in the manuscript's Test S1 table is a multiple of 3. A judge who notices will
  discount this result and doubt the other statistics.

**Fix [about +25]:**
- **Abstract**, the last sentence (52 words), replaced by: "In controlled studies on tasks built from training
  grids, when CORA's failure analysis stated what a missing operation must compute, a symbolic constructor rebuilt
  it on 8 of 11 tasks against 4 from the demonstrations alone (p = 0.125; three seeds agreed on every task), and
  matched blind enumeration at a fifth of its compute." The learned-controller clause stays in Section 5.
- **Section 5**, the result: "In the pre-registered test the constructor recovered 8 of the 11 motivating tasks with
  CORA's specification, 4 from the demonstrations alone and none with shuffled specifications; three seeds per task
  agreed every time, so the evidence is 4 tasks, one per family (p = 0.125, not the 0.0005 computed over 33 runs)."
- **Section 5**, the comparison: "Against search in the starting grammar it recovered 8 tasks against 5 at a fifteenth
  of the compute (inconclusive by the frozen rule), and blind enumeration of the same 211 structures matched it at
  five times the compute".
- Elsewhere, "show why" becomes "suggest why" and "confirmed that the content matters" becomes "found that the
  content matters".

### 3. The entry descriptions do not match the records (Completeness, trust)

**The text:**
- "with CORA-CAST on attempt 2 (H) it still answers 43, 0 gained and 0 lost, because CORA-CAST's one accepted answer
  was already the neural model's."
- "O: the CORA-CAST core alone on CPU; attempt 2 is the test input."

**Why it costs points:**
- **(a) H's zero is partly a time-cap loss, not only redundancy.**
  - H's package hit its 15 CPU-second cap on 62593bfd, in the local rehearsal and on Kaggle:
    `outputs/score_first/runs/h_rehearsal_v1/cora_side/0_cast_selective_v2/62593bfd.json` reads TIMEOUT at 15.004
    s.
  - The neural model has only the second output of 62593bfd
    (`kaggle/score_first_2026/configs/results/h_rehearsal_v1/score.json`).
  - On the author's machine, O's version answers 62593bfd within the cap, so there H would have gained one output.
  - The same package accepted 62593bfd in an earlier run (`records/CAST_CANDIDATE_RISK_COVERAGE.md`, 3 accepted on
    the 120), so acceptance near the cap depends on machine speed.
- **(b) The two entries run different CORA-CAST versions.**
  - O runs the first version, whose folds pass when the held-out output is among a fold's two attempts.
  - H runs the stricter second version, which adds agreement across modules and restart stability.
  - The Writeup gives both one name and one acceptance rule.
- **(c) O+ is not described.** `records/NOV1_COMPETITION_COMMAND_DECISION.md` makes O+ the CORA-only entry for 2 Nov:
  CORA-CAST, then a second reviewed constructor package that supplies the next distinct answer. That package
  appears nowhere in the paper. If O+ is linked, the paper misdescribes the code.
- **(d) On Kaggle's CPUs, O's version also loses 62593bfd.** This finding comes from the entries' own run records,
  which are newer than the paper.
  - The O+ Kaggle rehearsal answers 1 of 172 (981571dc only), against 3 locally: per output 0.58%, task mean 0.83%
    (`kaggle/score_first_2026/configs/results/op_rehearsal_v1b/score.json`).
  - The first CORA-CAST version timed out on 5 tasks, 62593bfd among them, at 14.986 CPU s
    (`outputs/score_first/runs/op_rehearsal_v1b/run/pkg0_cast_v1/shard_2/62593bfd.json`).
  - So on Kaggle hardware neither entry produces CORA-CAST's one unique answer, and the Writeup's "O answers 3 of 172"
    describes the author's machine, not the entry as Kaggle runs it.

**Fix [about +24; +16 more if O+ is linked]:**
- O's public-evaluation result: report the Kaggle run ("on Kaggle's CPUs it answers 1 of 172, because the 15-second
  cap stops 62593bfd; on our machine, 3").
- Engineering, the author's call: O+ is not pushed yet, and its 11-hour budget leaves room for a cap scaled to
  Kaggle's CPU speed.
- The two text changes:
- H: "The neural entry alone (NVARC's method) answers 43 of 172, and H also 43 (0 gained, 0 lost): H's stricter
  CORA-CAST version hit its 15-second cap on 62593bfd, where the neural model has one of two outputs, and accepted
  only 981571dc, which the neural model already had."
- O: "O: the first CORA-CAST version alone on CPU (its held-out folds accept an output among a fold's two attempts);
  attempt 2 is the test input."
- If O+ is linked: one sentence that names the second package, describes it from its review, and says that attempt 2
  is its next distinct answer.

### 4. "Every answer right" rests on three answers to puzzles the authors had inspected (trust, Progress)

**The text:**
- Abstract: "CORA-CAST alone answers 3 of 172 test outputs, every answer right".
- Section 6: "and answer only when verified (CORA-CAST's public-evaluation answers were all right)".
- Section 5: "when a rule is inexpressible every fitting program is spurious, which is why CORA answers only after
  leave-one-out re-derivation."

**Why it costs points:**
- The claim rests on three outputs from two exposed puzzles. One of them shaped the design; the neural model already
  solves the other.
- The only run of O's core on unexposed puzzles was the 207 sealed puzzles
  (`experiments/cora_cast_20261026/results/confirm/CONFIRMATION_REPORT.md`). It answered 11: 8 right and 3 fitting
  but wrong. Whether the filter would have caught those 3 is unmeasured.
- Leave-one-out tests stability, not truth (the manuscript says so). It cannot catch a spurious rule that every subset
  of the demonstrations supports.
- The Progress paragraph cites the exposed 3 of 3 as support, which reads as selective.

**Fix [about +4]:**
- Abstract: "CORA-CAST alone answers 3 of 172 test outputs, all right but on puzzles we had inspected;"
- Section 4: "O answers 3 of 172 (2 puzzles), all right."
- Section 6 parenthesis: "(precision on unseen puzzles is not yet measured)".
- Section 5: "...every fitting program is spurious, and leave-one-out re-derivation removes only the unstable ones."

### 5. There is no algorithm-level description, which is a required section (Completeness, Theory)

**The text:** "Programs (up to two rules and a default) are built from the demonstrations and kept only if they reproduce all
exactly."

**Why it costs points:**
- The criteria page requires "Approach (with an algorithm-level description)".
- Neither document says how guards and actions are built from the demonstrations: what is enumerated, in what order,
  and how ties break.
- So a reader cannot reimplement the submitted component.

**Fix [about +68, paid for by objections 6, 7 and 10]:** replace the quoted sentence with the five steps below. Step
3's construction rule must be written from `experiments/cora_cast_20261026/cast/rewrite.py`, since neither document
states it.

"Per puzzle, within 15 CPU seconds:
1. take each grid's majority colour as background;
2. try symmetry completion, guarded rewriting, then a depth-2 typed search;
3. in rewriting, build a first-match list of at most two guard and action rules plus a default from the
   demonstrations [construction rule];
4. keep it only if it reproduces every demonstration and its answer is complete and changes the input;
5. answer only if rebuilding it without each demonstration predicts that demonstration (H also requires agreement
   across modules and restart stability); otherwise abstain."

### 6. The universality paragraph shows nothing about the submitted method, and omits two caveats (Universality, trust)

**The text:**
- "The entries' verified-or-abstain component has run only on ARC."
- "deleting dim objects, one of its own candidate edits, raised StarDist's object F1 on 50 fresh images from 0.692 to
  0.705 (38 better, 0 worse)".
- "a single-cell lung atlas's predicted displacement direction held in 41 independent donors (p = 0.0016;
  retrospective framework applicability)".

**Why it costs points:**
- **StarDist:** all 13 arms, try-all included, made the same single edit
  (`cross_domain/universality_v2/neural_repair/summary.json`). The gain belongs to a hand-written filter, not to
  diagnosis and not to CORA-CAST.
- **Single cell:** in the second cohort, the predicted size was worse than "no effect" for all 19 COVID-19 donors
  (better/worse 0/19, `records/CROSS_DOMAIN_SCRNA_CASE_STUDY_20261025.md`). Every arm's final p lay between 0.0006
  and 0.0016; the 0.0016 that the Writeup reports is the weakest of them.
- **BBBC039:** the auditor's status is BLOCKED, on 54 against 60 executions. The manuscript says so; the Writeup does
  not.
- So the paragraph spends 109 words, earns about nothing on Universality, and invites questions of trust.

**Fix:**
- **(a)** Replace the paragraph with the pending fresh-nuclei run of the hashed entry package, unchanged and with its
  blind and shuffled controls. It is the only test here that could raise this score.
- **(b)** Otherwise, cut the paragraph to: "Universality is untested for the submitted component, which has run only on
  ARC. A separately written repair procedure with the same verify-or-abstain design ran on three public biological
  data sets; failure-blind controls matched every gain, so we claim a portable design, not transfer." [about -66]

### 7. Training-set performance is reported (rules)

**The text:** "**CORA-CAST on held-out training puzzles.** Guards lifted solves from 3 to 10 of 176 (p = 0.016); the
acceptance rule accepted 13 answers, all correct, rejecting exactly the two wrong; a one-time sealed test on 207 was
inconclusive (8 against 6 without guards and 7 for matched search; p = 0.5), with 3 fitting but wrong attempt-1
predictions."

**Why it costs points:**
- The rules say "Don't report train set performance."
- These are solve counts on ARC-AGI-2 training puzzles. The italic label does not change that.
- The manuscript's abstract repeats them.
- The Test S1 tasks are constructed tasks, which are easier to defend as a mechanism study.

**Fix [about -45]:**
- Delete the paragraph.
- Add to Limitation: "On unexposed training puzzles, the same core also produced fitting but wrong answers."
- Keep the counts in the manuscript, outside the abstract.

### 8. The novelty argument rests on controls and misses the closest predecessors (Novelty)

**The text:**
- "No ingredient is new by itself; the difference is how failure evidence is used, and the controls."
- Row 1 of the table: "growth from unsolved tasks; demonstrations-only, shuffled and matched-search controls".

**Why it costs points:**
- Controls are evidence, not novelty.
- The mechanism that worked takes a hole's required inputs and outputs, derived from a sketch, and fills the hole from
  a fixed language. That is the core of deductive synthesis:
  - Sketch;
  - λ² (Feser et al. 2015);
  - FlashMeta's witness functions (Polozov and Gulwani 2015).
- The guarded object rewriting of the submitted component has ARGA as its nearest neighbour, and ARGA is missing from
  the Writeup.
- Row 4's difference ("only on attempt 2, only when accepted") is a policy, not a method.

**Fix [about +24]:**
- Intro sentence: "No ingredient is new by itself; the difference is that a failed search's hole specification decides whether the
  language grows."
- Row 1:
  - add the deductive-synthesis predecessors;
  - put in its third cell: "the hole specification comes from a failed search and decides whether to add an
    operation, admitted only after held-out validation".
- Add ARGA to row 3, together with selective prediction.

### 9. "Never prune" contradicts the submitted system, and the controller result follows from its design (Progress, Theory)

**The text:**
- "keep strong static search, never prune, and answer only when verified".
- "(a failure-conditioned controller 33 of 128 against 87; ...)".
- Abstract: "while learned controllers that pruned search never beat strong static baselines."

**Why it costs points:**
- CORA-CAST's own typed search prunes: it drops a partial program when a contract proves it cannot fit.
- The 33-of-128 controller could only remove branches from the static search, so it could not win. The cited review
  calls that result "mostly a design artifact".

**Fix [about +10]:**
- "keep strong static search, prune only with sound checks, and answer only when verified".
- "a controller that could only prune lost to static search (33 against 87 of 128)".

### 10. The text is dense, uses undefined terms, and contains filler (all criteria; "Shorter and clearer")

**The text:**
- Section 1: "CORA follows the hypothesis: observations, candidate representations, program construction, execution,
  failure evidence, candidate revisions, verification, a capability library, reuse. Each Paper Track criterion has a
  labelled paragraph below."
- "Five further architectures gave no gain."
- "Against matched search the primary comparison was inconclusive (24 against 15, p = 0.035)".
- "design-exposed lead".

**Why it costs points:**
- The list in Section 1 carries no content, and the sentence about labelled paragraphs is meta-text.
- No reader can check five unnamed architectures.
- A p of 0.035 labelled "inconclusive", without the rule behind the label, confuses the reader.

**Fix [about -32]:**
- Delete the two Section 1 sentences and the architecture sentence.
- Objection 2 resolves the p-value issue.
- "design-exposed lead" becomes "a puzzle that shaped the design".

### 11. The linked entry, its eligibility and the code (Accuracy, Completeness)

**The text:**
- "H's prize eligibility is unconfirmed (undeclared checkpoint training data); O uses no pretrained model."
- "Reproduction. Notebook **[PENDING: entry notebook]**; code and frozen protocols: GitHub **[PENDING: release
  revision]**."

**Why it costs points:**
- Linking H ties the paper to an entry whose eligibility the paper itself doubts.
- The manuscript says the entry and the CORA-CAST code stay private until the author publishes them. A judge has to
  be able to read the linked code.

**Fix:**
- Link H only after the host confirms in writing; otherwise link O or O+.
- Before submitting, publish a revision that contains the entry notebook, CORA-CAST and the Test S1 code.
- H's submission id is already recorded: 57867631 (`records/NOV2_FINAL_SUBMISSION_STATUS.md`).

### 12. Small precision fixes (0 to 8 words each)

- **"NVARC's notebook, rerun unchanged (57160429)":** the originality audit records patches for compatibility and
  deployment. Say "rerun with compatibility patches only".
- **"in our own clean-room code":** the claim cannot be checked, and the repository holds a copy of NVARC's notebook,
  pulled to build 57160429. Say "re-implemented from its public description".
- **"wrong for 96 of the 120 puzzles":** say "wrong for some grid in 96 of the 120 puzzles; the fix, in CORA-CAST,
  added no fit by itself". This pre-empts the reading that the zero results are a bug.
- **"in all 113 audited puzzles no correct program lay within one revision step":** CORA held no fitting program on any
  of the 113 (`n_vs` = 0 in the audit file). Say so.
- **"what a program language can express and reach, not ranking":** say "what CORA's program languages can express".
  In the manuscript's neural-pool table, likelihood selection keeps 22 outputs of the pool's 27, so for a neural pool
  ranking does matter.
- **Public evaluation:** also give it in the leaderboard's task-averaged metric: 26.7% (Kaggle rehearsal) or 27.1% for
  the neural entry, and 1.7% for O.

**Word budget:**
- **Cuts:** objection 6(b) (-66), 7 (-45), 10 (-32) and the "What did not work" paragraph (about -20).
- **Additions:** objections 1 (-2), 2 (+25), 3 (+24), 4 (+4), 5 (+68), 8 (+24), 9 (+10) and 12 (about +25).
- **Net:** about +17, which ends near 1,472 words, or about 1,488 if the O+ sentence is added.
- **If Kaggle's counter runs higher:** shorten the novelty rows first.
- Run `paper/writeup/wordcount.py` after editing.

## 3. Spot-checks against the cited records

| # | claim | record | result |
|---|---|---|---|
| 1 | 57144804 scored 0.00% | `records/KAGGLE_NATIVE_V1_OFFICIAL_RESULT_20261013.md` | verified |
| 2 | 57354496 scored 0.00% | `records/KAGGLE_CORA_FHR_V1_LOG_20261015.md`, section 5 | verified |
| 3 | 57160429 (NVARC's notebook) scored 27.64% | `records/KAGGLE_NEURAL_V1_LOG_20261013.md`, section 11.2 | verified. "Unchanged" is imprecise: the originality audit lists compatibility and deployment patches |
| 4 | every CORA-only configuration solved 0 of 120; 273 of 344 attempts were the fallback | `records/RESULTS_SYNV4_REALCHECK_KAGGLE_DEV_20261022.md`, section 3 | verified (8 configurations, all 0.0%) |
| 5 | in 113 audited puzzles, no correct program within one step | `experiments/architecture_sweep_20261026/runs/episodes_v1/reach_eval_dev.json` | verified: 113 no_reach, 0 with any correct behaviour. The version space was empty on all 113 |
| 6 | six of seven views assumed background 0, wrong for 96 of 120 puzzles | `records/CORA_SYNTHESIS_REVIEW_20261027.md` | verified, with one wording change: the record says "non-zero majority colour in some grid" (67 in every input grid) |
| 7 | first break at expressivity 29, canvas 13, representation 4 (of 46) (manuscript) | same | verified |
| 8 | O answers 3 of 172 (2 puzzles), all right, in 262 s | `records/NOV1_COMPETITION_COMMAND_DECISION.md`; `kaggle/score_first_2026/configs/results/op_rehearsal_v1b/score.json` | verified for the local run only. O runs the CAST v1 core. On Kaggle's CPUs the O+ rehearsal answered 1 of 172, because 62593bfd timed out |
| 9 | H: 43 of 172, 0 gained, 0 lost; only 981571dc accepted | `records/NOV2_FINAL_SUBMISSION_STATUS.md`; `kaggle/score_first_2026/configs/results/h_rehearsal_v1/score.json` | numbers verified; the "because" is incomplete. 62593bfd timed out at 15.004 CPU s, and the neural model has only 62593bfd:1 |
| 10 | Test S1: 24, 12, 0, 22 and 15 of 33; p = 0.0005; interval 0.33 to 0.44; p = 0.035; 9.6, 141.1 and 48.7 CPU s | `experiments/capability_growth_20261027/reports/TEST_S1_REPORT.md`; `runs/s1_eval/results.json` | numbers verified; the inference is not. In the deterministic arms, 0 of 11 tasks vary by seed. At task level: 8 against 4 (p = 0.125); against matched search, 8 against 5 (p = 0.375) |
| 11 | all four operations rebuilt exactly, 6 of 6 reuse, contract check passed | `TEST_S1_REPORT.md` | verified. Trim's structures are starting-grammar macros, and the report calls upscale "a deep G0 macro", where the manuscript says "expansion" |
| 12 | Test I-b: 5 against 3 of 33 (p = 0.625); matched search 15 | `experiments/capability_growth_20261027/reports/TEST_IB_REPORT.md` | verified. Matched search found 5 of 11 tasks and is deterministic |
| 13 | Test I: 2 of 4 operations recovered with fixed parameters; ceiling probe 1 of 11 | `experiments/capability_growth_20261027/reports/TEST_I_REPORT.md` | verified |
| 14 | pilots: 33 of 128 against 87; 32 of 64 against 64 | `records/NOV1_INDEPENDENT_RESEARCH_REVIEW.md` | verified. The review calls the first "mostly a design artifact" |
| 15 | guards: 3 to 10 of 176, p = 0.016 | `experiments/cora_cast_20261026/M2_REWRITE_REPORT.md` | verified (7 gained, 0 lost) |
| 16 | 13 accepted, all correct (lower bound 0.77); the 2 rejected were the 2 wrong | `records/CAST_CANDIDATE_RISK_COVERAGE.md` | verified |
| 17 | sealed 207: 8, 6 and 7 (p = 0.5); 3 fitting but wrong among 11 attempted | `experiments/cora_cast_20261026/results/confirm/CONFIRMATION_REPORT.md` | verified. The core is "CAST v1 core", O's package, run without its acceptance filter |
| 18 | StarDist: 0.692 to 0.705, 38 better, 0 worse | `cross_domain/universality_v2/neural_repair/summary.json` | verified. False positives fell from 995 to 902 and misses rose from 163 to 170; all 13 arms are identical |
| 19 | BBBC039: 0.883 to 0.923 | `cross_domain/bbbc039_repair_20261026/REPORT.md` | verified. A failure-blind seed reached 0.9234; the auditor status is BLOCKED |
| 20 | single cell: direction held in 41 donors, p = 0.0016 | `records/CROSS_DOMAIN_SCRNA_CASE_STUDY_20261025.md` | verified. Predicted size was worse than no effect for 19 of 19 COVID-19 donors; every arm's p was 0.0006 to 0.0016 |
| 21 | five further architectures gave no gain | `experiments/architecture_sweep_20261026/ALL_FIVE_RESULTS.md` | verified (0 on the public evaluation) |
| 22 | neural settings: rank 64, alpha 64, learning rate 1e-4, 48 steps, 8,192 tokens, 8 + 8 augmentations | `records/KAGGLE_SCORE_FIRST_SUBMISSION_READY_20261026.md` | verified for entry A |
| 23 | "An independent code review returned GO" (manuscript, H's neural method) | `records/NOV2_FINAL_SUBMISSION_STATUS.md`, risk 4 | **not verified as stated.** The GO was for entry A; H's neural code (C4) "was reviewed only by the sprint's own reviewers" |
| 24 | 14 solved tasks; 4x probe; Qwen3-4B-Instruct-2507 | `TEST_I_REPORT.md` | verified |

## 4. Issues in the manuscript only

1. **Abstract:** it reports solve counts on training puzzles (176 and 207). Move them out.
2. **Code review:** "An independent code review returned GO" is attributed to the wrong code (check 23).
3. **Upscale:** "compress, downscale and upscale as expansions" conflicts with the Test S1 report's "upscale is a deep
   G0 macro".
4. **Test S1 table:** add a task-level column, and state that the deterministic arms repeat across seeds.
5. **Engineering:** "capped at 900 s" is a soft cap. H's rehearsal had 2 tasks over 900 s, the longest 1,099.5 s.
6. **Acceptance rule:** the paragraph describes the second version, but entry O runs the first. Give the rule entry by
   entry.
7. **Length:** 24 dense pages in the PDF. Moving the generated-puzzle, five-architecture, drug-response and grammar-induction
   material to appendices would make it shorter and clearer.

## 5. The three changes that would raise the total most

1. **Make the paper describe exactly the linked entry, and make that entry its subject.**
   - **Text:**
     - the subtitle and the abstract reframe (objection 1);
     - the five-step algorithm;
     - each entry's CORA-CAST version;
     - the 62593bfd timeout, in H and on Kaggle's CPUs (where O answers 1 of 172, not 3);
     - the second package, if O+ is linked.
   - **Link:** choose by eligibility. H only with the host's written confirmation; that is worth about +2 on Accuracy.
     Otherwise link O or O+.
   - **Expected gain:** Completeness 3 to 4, and the paper no longer risks failing the rule that the code must
     demonstrate the approach.
2. **State the evidence at its real strength.**
   - **Edits:**
     - Test S1 at task level (8 against 4 of 11, p = 0.125);
     - "all right, on inspected puzzles; unseen precision not yet measured";
     - "prune only with sound checks";
     - the training-set paragraph deleted.
   - **Expected gain:** this protects Theory and Progress. A judge who finds the seed duplication will otherwise doubt
     every number. It also removes a breach of the rules.
3. **Give universality one result for the submitted code.**
   - **The result:** the approved fresh-nuclei run of the hashed package, unchanged, with blind and shuffled controls,
     replacing the biology paragraph.
   - **If the run is null:** cut the paragraph to two sentences and spend the words on changes 1 and 2.
   - **Expected gain:** Universality 1 to 2, if the run beats its controls.
