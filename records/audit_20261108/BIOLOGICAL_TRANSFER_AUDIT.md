# Biological transfer audit

Date: 8 November 2026 (UTC). Part of the independent audit of the companion study's completed results (inventory in
`COMPLETE_COMPANION_RESEARCH_AUDIT.md`; numbers and commands in `INDEPENDENT_REPRODUCTION_RESULTS.md`). Nothing was rerun or
rescored. Correctness labels are the producers' saved scores unless a section says otherwise.

## Terms

- **Target**: one gene of one published Boolean model whose update rule must be reconstructed.
- **Withheld input**: one of the four network states per target that are kept out of training and predicted at the end
  (the papers sometimes call it a held query).
- **Training label**: one requested simulated observation of a target's next value.
- **Exact rule**: the reconstructed rule equals the published rule on every input.
- **Lineage**: the group of models that come from one source publication. It is the independent unit in these studies.
- **One-input rule**: the gene copies or inverts one other gene. A two-input rule uses two other genes.
- **Inferred wiring**: the likely regulators of a target, inferred from its own ten demonstrations.
- **Supplied wiring**: the documented regulators, given to the method as a ceiling.

## 0. What "transfer" can mean, and what the evidence supports

The author's definition (8 November): transfer means applying the reasoning pipeline (build an executable rule, check
it, diagnose, revise or ask for evidence, abstain) to other domains through adapters. Transfer of rules or priors
learned on ARC to genes is a separate, secondary question. Measured against that definition:

| Pipeline step | Biological evidence | What actually ran | Status |
|---|---|---|---|
| Build an executable rule and accept it only if it fits (verify or abstain) | 99 of 333 and 101 of 595 exact rules with inferred wiring | A rule-reconstruction procedure written for biology. It reuses CORA's verify-or-abstain acceptance design but none of the competition entries' code and not the shared two-input truth-table executor | Demonstrated, for one-input rules only in the replication |
| Ask for evidence (choose informative observations) | 320 against 291 exact rules | Committee disagreement over a pool of up to 64 unseen states, after one shared first state | Demonstrated for exact identification; it lowered held-input accuracy until a completion rule was added |
| Diagnose and revise | Completion rule, +47 withheld inputs | Engineered by researchers after the overall result; specification and code frozen before the per-target diagnosis was decoded and before it ran | A researcher-made revision, not an automatic one |
| Grow the rule language when the small language fails | 433 of 595 against 321 (conditional construction) | Separate study, audited separately on our side (`records/SPARSE_COFACTOR_NATURAL_INDEPENDENT_AUDIT_20261108.md`, pending) | Not judged here |
| Shared core | One two-input truth-table executor, byte-identical in all 20 places it is copied (SHA-256 `03f1d918...`) | Not used in the 333-target or 595-target inferred-wiring results; later natural runs call it through their own code; its gene-state adapter has run only in authored unit tests | Real, but must not be credited with these results |
| Transfer of content learned on ARC | Ordering counted from ARC: 177 against 194 for a fixed simplicity order | Counts of 5 of 16 two-input truth tables from 22 of 1,000 ARC training tasks | Tested; did not help |
| Continuous data | Spatial: modest exploratory signal; Perturb-seq: null without sensitivity; cell images: no result | Hand-specified adapters | Exploratory |

The papers can therefore say that the pipeline's acceptance design and its evidence-request step were carried to
published gene-regulation models and helped there, and that a researcher-made revision recovered the prediction loss.
They cannot say that the same procedure, including diagnosis and revision, ran on genes, that CORA's competition code
ran there, or that the shared executor produced these results.

## 1. Inferred regulator wiring: the 333-target study and the 595-target replication

**Classification:** COMPLETE AND VERIFIED (333-target study: totals only, because per-target results were not saved).
**Verdict:** PASS, with corrections.

### Numbers (all reproduced exactly)

| Condition | 333 targets: exact / wrong accepts | 595 targets: exact / wrong / rejected |
|---|---|---|
| Inferred wiring | 99 / 58 | 101 / 124 / 370 |
| Inferred wiring, gene labels shuffled once | 87 / 57 | 66 / 114 / 415 |
| No wiring, full prior | 85 / 58 | 66 / 112 / 417 |
| No wiring, empty prior | 85 / 58 | 66 / 112 / 417 |
| Supplied wiring (ceiling) | 148 / 54 | 222 / 122 / 251 |

- Replication: 595 targets, 75 models, 50 lineages. Inferred wiring against each control: 35 gains, 0 losses. The three
  controls succeed on exactly the same 66 targets, so their lineage contrasts are identical: they are one comparison,
  not three confirmations.
- Lineage sign-permutation test with the frozen seed: p = 0.0000200 one-sided (1 extreme draw in 100,000), Holm-adjusted
  0.0000600. The exact sign-flip value is 2^-20 = 0.00000095 (20 lineages differ, all in favour); the reported value is
  conservative. Lineage bootstrap interval for the gain: +3.42 to +8.32 points. Task-level McNemar test 35 against 0,
  nominal p = 2.9e-11 (tasks are not independent).
- Withheld inputs correct: inferred 807 of 900 answered; no wiring 624 of 687; shuffled 629 of 692; supplied 1,305 of
  1,372.
- **Rule size.** Every exact recovery without supplied wiring is a one-input rule (101 of 101; controls 66 of 66).
  Supplied wiring recovered 162 one-input and 60 two-input rules. In the 333-target study, inferred wiring accepted 43
  constant, 112 one-input and 2 two-input rules; targets exclude constants, so at least 97 of the 99 exact recoveries
  are one-input rules.
- **Where the gain is (after-the-fact split).** Networks of 30 genes or fewer: 15 against 14 of 147 targets. Networks of
  more than 30 genes: 86 against 52 of 448 targets, 34 of the 35 gains. The 333-target study admitted only networks of 2
  to 30 genes (its protocol, item 2), so these networks are larger than any in the original study.
- **Concentration.** The 35 gains sit in 20 lineages and 26 models; one lineage holds 9. Leaving out any one lineage
  gives a gain of 5.04 to 6.40 points. The four largest lineages (all readmitted) supply 191 of 595 targets; all nine
  readmitted lineages (33 models) supply 259 targets and 11 of the 35 gains. Without them: 64 against 40 of 336 targets.
- **333-target study units.** 44 models in 30 lineages; the largest lineage holds 70 targets; no model or lineage is
  shared with the replication. Its interval (+1.91 to +6.78 points) and Holm p = 0.0003 resample models, not lineages,
  and cannot be recomputed by lineage because per-model counts were not saved.
- **Protocol.** Code freeze, two reviewer receipts bound to it, the go decision and the single run all came before any
  outcome; every failure stayed in the 595-target denominator. The prediction stage never opened model files, supplied
  wiring or withheld answers.

### Corrections

1. Rule size: add "Every exact recovery in the replication was a one-input rule; only supplied wiring recovered two-input
   rules (60 of 222)."
2. Attribution: "CORA reconstructed", "CORA inferred which variables regulate a gene" (reviewed Writeup, line 47; master
   lines with "CORA inferred") and "Transfer of the pipeline: the same procedure (... diagnose, revise or ask for
   evidence ...)" describe steps and code the replication did not have. Replace with "a rule-reconstruction procedure
   written for biology, which reuses CORA's verify-or-abstain acceptance design but none of the entries' code".
3. 333-target statistics: replace "95% model-clustered CI +1.91 to +6.78, Holm-corrected p = 0.0003" with "(+4.20
   points; that study's bootstrap resampled models rather than the 30 publication lineages, so we rely on the
   replication for inference)".
4. Add "the three controls succeeded on exactly the same 66 targets".
5. Add "and accepted more wrong rules (124 against 112)".
6. Add "34 of the 35 gains came from networks with more than 30 genes, larger than any in the original study (within
   that original range, 15 against 14 of 147; split made after the fact)."
7. Cohort label: "reused biology cohort, replication" should read "first scored here; parsed earlier for an inventory;
   33 readmitted models; replication". The reviewed fallback's "readmitted lineages supply 191 of the 595 targets"
   should read "the four largest lineages, all readmitted, supply 191 of the 595 targets (all nine readmitted lineages
   supply 259)".
8. p-value: "p = 0.00002" should read "one-sided lineage sign-permutation p = 0.00002 (Holm-adjusted 0.00006), assuming
   independent lineages".
9. Shared executor: "A small shared Boolean interpreter serves grid-panel and gene-state adapters" placed next to 101 of
   595 implies it produced the result. Replace with "A small two-input truth-table executor, identical byte for byte
   wherever it is used, runs on ARC grid panels and in later gene-state experiments; it was not used in these results."
   The file is not tracked in the main repository: include it in the release or cite it as companion code.
10. Two different controls both scored 87 of 333: label "shuffled documented wiring" (earlier study, 146 accepted, 59
    wrong) and "shuffled inferred wiring" (this study, 144 accepted, 57 wrong) separately.
11. Companion note 0532 calls "the entries' code ran unchanged on Boolean networks" unsupported. It did run unchanged in
    the earlier portability study (1,519 tasks, 0 errors, 0 of 42 answered tasks consistent with the true rule). The fix
    is attribution: "ran unchanged but recovered no rule; the results come from separate biology code."
12. Note 0534's "no learned biological transfer was run from it" is out of date: the ARC-ordering test ran (section 2).

### Sentences the papers may use

Full paper: "On published Boolean gene-regulation models, a rule-reconstruction procedure written for biology, which
reuses CORA's verify-or-abstain acceptance design but none of the entries' code, inferred each target gene's likely
regulators from its ten simulated transitions and recovered the exact published update rule for 99 of 333 targets,
against 85 without inferred regulators and 87 with them shuffled. A frozen, single-run replication on 595 targets from
75 further models in 50 publication lineages (all parsed earlier for an inventory; 33 previously excluded models
readmitted) recovered 101 against 66 for each of three controls, which succeeded on the same 66 targets (35 gains, 0
losses; one-sided lineage sign-permutation p = 0.00002, Holm-adjusted 0.00006, assuming independent lineages), and
accepted more wrong rules (124 against 112). Every exact recovery in the replication was a one-input rule, in which the
gene copies or inverts one other gene, and 34 of the 35 gains came from networks with more than 30 genes, larger than
any in the original study; neither result used the shared two-input truth-table executor or anything learned on ARC."

Writeup: "Within biology, a separately written procedure that infers each gene's likely regulators from ten simulated
transitions raised exact recovery of published update rules, almost all of them one-input rules, from 85 to 99 of 333
targets and, in a frozen replication on 75 further models in 50 lineages, from 66 to 101 of 595 (35 gains, 0 losses;
Holm-adjusted lineage p = 0.00006), with more wrong accepted rules (124 against 112) and nothing learned on ARC."

## 2. Truth-table ordering counted from ARC (595 targets)

**Classification:** COMPLETE AND VERIFIED. **Verdict:** PASS. This is the first independent recomputation of this
result; earlier reports copied its final numbers.

### Numbers (all reproduced exactly; arm names given explicitly)

| | Order counted from ARC | Plain index order | Same counts, randomly reassigned (one draw) | Hand-set simplicity order |
|---|---|---|---|---|
| Exact rules of 595 | 177 | 168 | 182 | 194 |
| One-input targets exact, of 165 | 155 | 155 | 155 | 159 |
| Two-input targets exact, of 156 | 22 | 13 | 27 | 35 |
| Three-or-more-input targets exact, of 274 | 0 | 0 | 0 | 0 |
| Withheld inputs correct, of 2,380 (2,348 answered) | 1,910 | 1,837 | 1,919 | 1,916 |
| Targets won / lost by the ARC order against this arm | | 13 / 4 | 0 / 5 | 3 / 20 |
| Lineages favouring ARC order / this arm / tied | | 9 / 3 / 38 | 0 / 4 / 46 | 3 / 12 / 35 |

- Note on the audit draft: one sub-audit table listed the one-input, two-input and withheld-input rows in a different
  arm order from its header. The row values above are re-read from the saved output with arm names attached.
- Statistics: one-sided sampled p 0.045 / 0.998 / 1.0 against index, simplicity and permuted orders; Holm-adjusted
  0.136 / 1.0 / 1.0; lineage-resampling intervals for the rate difference +0.15 to +3.09, -4.81 to -0.81 and -1.57 to
  -0.17 points. Full enumeration of sign patterns agrees (one-sided 0.046 / 0.998 / 1.0).
- The 274 targets needing three or more inputs are out of reach of the two-input language under every order. The order
  changed the outcome on 39 of 595 targets.
- Source counts: 22 witnesses from 1,000 ARC training tasks (978 excluded: 799 no matching layout, 176 no zero
  background, 2 no exact operator, 1 incomplete truth table).
- Equal resources: identical work counters, allowances and inputs in all four arms; inference CPU 57.45 to 57.66 s per
  arm. The three scoring attempts used 240.788 + 3,011.047 + 8.915 CPU s (about 3,260.75 CPU s in all). Two attempts
  failed (recursion limit; CPU limit) and are kept.

### Corrections

1. "No Holm-adjusted learned-transfer advantage" is true but incomplete. Add "and it was worse than the permuted order
   (0 gained, 5 lost) and the simplicity order (3 gained, 20 lost; lineage interval -4.8 to -0.8 points); its +9 over
   index order is not specific to the ARC counts".
2. "Uniform" is a fixed order: write "plain index order (no counts)".
3. Define "strong static": "a hand-set simplicity order (constants, single inputs, negations, then AND and OR), fixed
   before the run".
4. Reviewed fallback abstract, line 81: "ARC-derived ordering did not beat strong biological controls" is wrong (the
   controls are not biological). Write "An ordering counted from ARC training tasks did not beat simple fixed orderings
   on biological targets."
5. "Exact recoveries were unary or binary, with none requiring three or more essential inputs" is true by construction.
   Add "the 274 targets needing three or more inputs were out of reach of the supplied two-input language under every
   order".
6. Units: write "595 targets from 75 models in 50 lineages".
7. Costs have two scopes (outer receipt 8.915 CPU s / 10.517 wall s; inner 8.847 / 10.355). Name one scope and give the
   3,260.75 CPU s total for the three attempts.

### Sentence the papers may use

"On 595 previously scored targets from 75 published models in 50 lineages, the order counted from 22 of 1,000 ARC
training tasks recovered 177 rules exactly, against 168 for plain index order, 182 for one random reassignment of the
same counts and 194 for a hand-set simplicity order; its gain over index order did not survive Holm correction
(adjusted p = 0.14) and was not specific to the ARC counts, and it lost 5 targets and gained none against the permuted
order, and lost 20 and gained 3 against the simplicity order."

## 3. Grammar-growth stages: the empty learned library and the three-input OR form

**Classification:** COMPLETE AND VERIFIED (both stages). **Verdict:** PASS, with corrections.

- **First stage.** Only 1 of 182 source tasks failed the base fit, so the learned, tuned, permuted and all 20 random
  libraries were empty; only the supplied full library was non-empty. Every library gave 30 of 151 held tasks without
  wiring and 61 of 151 with correct wiring; all contrasts 0, Holm p = 1. The base language allowed up to three literals
  and was not empty.
- **Second stage.** A smaller base language (at most two literals) failed on 14 source tasks in 8 lineages (10 models).
  Of eight supplied three-input forms, the three-input OR form (an OR of three possibly negated inputs) was selected;
  seven of the eight forms tie on lineages, models and tasks, and it won on the fourth tie-break (residual-only
  witnesses, 14 against 11). It recovered 60 of 151 held rules in 19 models (55 on the first attempt, 5 on the
  second). The selected arm reuses the fixed form's library, so the two agree on all 151 tasks by design. Base language
  59; full eight-form language 60; source-tuned choice 60; shuffled-label choice 59; random mean 58.85. Fixed single
  forms: AND, OR and two others 60; two forms 59; two forms 58. The 151 held targets had already been scored in the
  first stage. No source and held task share a model or lineage.

### Corrections

1. Source for the first stage: cite `M/experiments/bbm_wiring_grammar_20261104/results_G/RESULTS_G.json` (SHA-256
   `332f3183...`) and its audit `B/cage/biology_transfer_20261102/INDEPENDENT_U6B_D_G_POSTSCORE_AUDIT_20261103.md`
   (`8f277bab...`), not the later stage's folder that coordination note 0565 names.
2. "Empty-grammar stage" should read "stage with an empty learned library".
3. Provenance: the three-input OR form was chosen from biological source models (development and differentiation
   family), not from ARC. Under any ARC-to-biology heading add "selected from biological source models, not from ARC".
4. "Fixed OR3 identical on every row" should read "because the selected arm reuses the fixed three-input OR library, the
   two agree on all 151 tasks", and add that three other fixed forms and the full language also reach 60.

### Sentence the papers may use

"The first Boolean grammar-growth stage was uninformative: only 1 of 182 source tasks failed its base fit, so every
learned library was empty. A second stage with a smaller base language found 14 failures in 8 source lineages and chose
a supplied three-input OR form, which recovered 60 of 151 held rules from 19 other, previously scored models; because the
chosen arm reuses that fixed form, the two agree on all 151 tasks, and the base language (59), the full eight-form
language (60) and the source-tuned and shuffled choices (60 and 59) did as well or within one task. Both stages learned
from biological source models, not from ARC."

## 4. Active selection of training labels and the completion rule (595 targets)

**Classification:** COMPLETE AND VERIFIED. **Verdict:** PASS, with corrections.

### What was checked

- An independent re-implementation, using only the 20 labelled training states and the 4 unlabelled withheld states
  per target, reproduced all 8,925 sealed predictions (1,785 target-arms times 5 readouts) and every "no rule fits"
  status. No withheld state appears in any training set; each arm has 20 distinct labelled states.
- Predictions were sealed at 18:26:37 UTC; scoring started at 18:26:40 UTC. Completion rule written 17:39:56; its code
  frozen 17:42:43; the per-target diagnosis decoded rows 17:43 to 17:45; active against uniform under the vote named
  primary 17:57:03; completion run started 18:16:02.
- The synthesis pass recounted every total and paired count below from the recovery's scored rows (SHA-256
  `cd35aebb...`, pin matches) with its own script: all match.
- Not checked: true outputs and exact-rule labels came from the producer's evaluator and were not regenerated (the
  audit rules forbid rescoring). They agree with the earlier scoring on 526 of 595 targets where that was checkable.

### Numbers

| Readout, withheld inputs correct of 2,380 | Active | Uniform | Permuted-variable control |
|---|---|---|---|
| Original (unanswered counted as incorrect; answered in brackets) | 1,586 (1,616) | 1,747 (1,876) | 1,643 (1,740) |
| Fill with zero | 2,002 | 2,028 | 2,004 |
| Training-label majority | 2,178 | 2,112 | 2,122 |
| One minimum-error rule | 2,194 | 2,149 | 2,146 |
| Vote of distinct minimum-error rules (primary) | 2,200 | 2,153 | 2,156 |
| Exact rules of 595 | 320 | 291 | 297 |

- Exact rules by size: one-input 165 of 165 in every arm; two-input 155 / 126 / 132 of 156; three or more 0 of 274.
  Exact active against uniform: 30 gains, 1 loss; 21 lineages positive, 0 negative.
- Primary, active minus uniform under the vote: +47 inputs (+1.97 points; 92.44% against 90.46%).
  - By target: 94 better, 62 worse, 439 tied. By model: 38 / 21 / 16. By lineage: 28 / 14 / 8. Dropping any one
    lineage leaves +39 to +51.
  - Descriptive bootstrap intervals: by target +0.50 to +3.49 points; by model +0.50 to +3.48; by lineage +0.61 to
    +3.46.
  - By target size: one-input 0; two-input +30 (623 against 593 of 624; completion never touches these, since every
    abstention is on a target with three or more inputs); three or more inputs +17 (917 against 900 of 1,096).
  - By which arm originally fitted: both fitted +32 (1,490 against 1,458); only uniform fitted +12 (301 against 289);
    only active fitted +5 (96 against 91); both abstained -2 (313 against 315 of 400).
- Active minus uniform under the other fills: zero -26; majority +66; one minimum-error rule +45. Active against the
  permuted-variable control under the vote: +44 (lineages 24 better, 12 worse, 14 tied).
- 168 vote positions were exact ties, set to zero by the fixed rule (active 77, uniform 29, permuted 62).
- Costs: completion used 0 new labels and reused 35,700. Recovery attempts 296.569265 + 19.839388 = 316.408653 CPU s;
  with monitors 329.157130927 CPU s. About 25 of the recovery's 32.6 CPU s were monitoring; the scoring worker used 7.1.
  Acquisition run: 35,700 label requests, 400.536959 CPU s.

### The first scoring attempt

The first scoring attempt stopped at its fixed 120-second limit. Its journal files are fsynced on every row, and their
newline counts give 235 cost records and 3,515 scored rows (234 targets times 15 rows plus 5). The scoring code
(`host.py`, function `score`) evaluates a target's four true outputs, then writes its cost record, then its 15 rows, so
true outputs were evaluated for exactly 235 of 595 targets (940 of 2,380 withheld inputs). Before that loop the code
also loaded, for all 595 targets, the acquisition run's saved scores (exactness labels and counts of correct withheld
inputs), which that run's own scoring had already produced. The rows were not used. Coordination note 0565, the
companion's summary files, the reviewed fallback ("possible partial truth access", line 1292) and the Writeup call the
count unknown; it is known.

### Corrections

1. Partial access: replace "unknown" with "The first scoring attempt evaluated true outputs for 235 of the 595 targets
   (940 of 2,380 withheld inputs) and wrote 3,515 of 8,925 scored rows before it stopped at its 120-second limit; these
   rows were not used." The current master no longer mentions the failed attempt at all; it must ("Do not claim
   single-ever scoring", note 0565).
2. "Original scoring stage FAILED_NO_RETRY" is ambiguous. Write "The completion study's first scoring attempt stopped at
   its fixed 120-second limit and was not retried under its own protocol. A separately frozen score-only protocol,
   checked by a separate automated review process within the project, then scored the identical sealed predictions
   once, with a 600-second limit and local storage, without new inference or new labels."
3. "1,586 / 1,747 / 1,643 of 2,380" should read "withheld inputs predicted correctly, counting unanswered inputs as
   incorrect (answered 1,616 / 1,876 / 1,740)".
4. Method: the reviewed fallback (line 1221) says "Active selection uses classical bisection ...". That was not
   implemented. Write "After a first state shared with uniform selection, active selection labels, from a random pool of
   up to 64 unseen non-withheld states, the state that splits the still-consistent one- and two-input rules most evenly;
   random states fill in when fewer than two rules remain or a fixed computation cap is reached." (The current master
   already says committee disagreement, not bisection.)
5. Control name: "shuffled active sequence" (fallback table line 1233; master) and "shuffled selection" (Writeup) should
   read "permuted-variable control: the actively chosen states with their variable positions randomly permuted, then
   newly labelled (standalone cost 40 labels per target)".
6. Order of events: "Saved predictions showed ... We therefore tested ..." (master) and "The diagnosis led to ..." (note
   0563) reverse what happened. Write "The overall outcome (more no-fit abstentions under active selection) motivated a
   completion rule whose specification and code were frozen before the per-target diagnosis was decoded."
7. "Fixed before the new predictions were scored" can be strengthened to "fixed before the completion predictions were
   computed".
8. Add the target and lineage paired results the frozen plan required (94 / 62 / 439 targets; 28 / 14 / 8 lineages).
9. Add the source of the +47: "Thirty of the 47 come from two-input targets that completion does not touch. On the 100
   targets where both methods abstained, completion scored 313 against 315 of 400. With a fill of zero, active
   selection is below uniform (2,002 against 2,028)."
10. Do not present 1,586 to 2,200 as the method's gain: a fill of zero alone reaches 2,002 and the training-label
    majority 2,178; the vote adds 22 over the majority in the active arm and 41 in the uniform arm.
11. Disclose the tie rule: "168 vote positions were exact ties, set to zero by the fixed rule."
12. "Independently reviewed" should read "reviewed by a separate automated process in the same project". The outcome
    review (290 checks, 0 failures) checked arithmetic and receipts, not rows; true values and exact labels were not
    regenerated.
13. Words: "no three-or-more-input exact rule was learned" should say "recovered". Define "query" where used, or say
    "withheld input".
14. Costs exclude development, fixtures, reviews, the 3.80 CPU s diagnosis and the acquisition run; say so.

### Sentence the papers may use (both sentences together)

"On 595 previously studied target rules from 75 published Boolean models (50 publication lineages), with 20 simulated
training labels per target for each method, active example selection recovered 320 rules exactly against 291 for uniform
selection and 297 for a control that permutes the variables of the actively chosen states, but it abstained more often
on rules with three or more inputs, so it predicted 1,586 of 2,380 withheld inputs correctly against 1,747 and 1,643
(unanswered inputs counted as incorrect); a completion rule fixed before it was run, which answers each abstained target
by majority vote of the distinct one- and two-input rules that best fit the same 20 labels, gave 2,200 against 2,153
and 2,156 correct, a prespecified active-versus-uniform difference of 47 inputs (1.97 percentage points; 28 of 50
lineages favoured active selection and 14 favoured uniform), of which 30 come from two-input rules that active selection
recovered exactly more often. This is exploratory evidence on a reused cohort, with no new training labels and no new
significance test: completion recovers no additional exact rule, a fill of zero leaves active selection below uniform
(2,002 against 2,028), and because the first scoring attempt stopped at its 120-second limit after evaluating 235 of
the 595 targets, the identical sealed predictions were scored once more under a separately frozen and reviewed
protocol."

## 5. Continuous-data follow-ups (spatial transcriptomics, Perturb-seq, cell images)

Each follow-up ran once from a frozen protocol (freeze hashes: spatial `324e85d6...`, Perturb-seq `08d549ca...`, images
`40ac5d2b...`), with every prediction written, flushed and hashed before any answer was opened. No source file changed
after the launch at 00:27 UTC. Total cost 145.63 CPU s (0.0405 CPU hours), no GPU.

### Spatial transcriptomics (one donor, four adjacent sections, 14,234 spots)

**Classification:** COMPLETE AND VERIFIED. **Verdict:** PASS. The primary criterion failed; a secondary ablation gave a
modest exploratory signal.

| Arm | Macro-F1 (mean of white-matter and cortex F1) | Changed | Corrected / harmed | Sections below native |
|---|---|---|---|---|
| Native (no repair) | 0.9315545 | 0 | 0 / 0 | 0 |
| Original marker rescue | 0.9320277 | 123 | 58 / 65 | 2 |
| Neighbour check only (secondary) | 0.9349975 | 48 | 36 / 12 | 0 |
| Marker-rank check only | 0.9312713 | 86 | 38 / 48 | 2 |
| Both checks (primary) | 0.9336119 | 32 | 23 / 9 | 1 (section 151676, -0.00017) |
| Both checks, graph shuffled | 0.9315545 | 0 | 0 / 0 | 0 |

- The shuffled control could almost never fire: 18.3% of spots are predicted white matter, so a random six-spot
  neighbourhood has at least five such spots with probability 0.00105 (about 0.09 expected changes among 86 eligible
  spots). It is equivalent to native and does not test spatial information.
- Inside the rescue's 123 changes, a random 48 would hold 22.6 corrections on average; the neighbour check had 36
  (P = 6.6e-7). A random 32 would hold 15.1; the primary had 23 (P = 0.0011). Spot-level tests treat correlated spots
  from one donor as independent and are descriptive only.

### Perturb-seq (64 readout genes, 255 held perturbations, 16,320 correlated predictions per method)

**Classification:** COMPLETE AND VERIFIED. **Verdict:** PASS, as a null without sensitivity.

- Truth: 16,288 similar, 26 higher, 6 lower. Native and all 16 program arms: 16,286 correct; mean, ridge and
  all-similar: 16,288. Directional F1 0 in all 20 arms; 0 rules admitted.
- The admission bar (log 20 + log 48 = 6.87) needs at least 4 net corrections; summed training gain was 0 for all 64
  genes in every authentic and shuffled fold-vote arm, and the best in-sample static arm reached +1 for one gene. The run
  could not distinguish scalar from pairwise representations.
- Inputs are pathway-neighbour averages of training perturbations' response changes, not measured pre-perturbation
  expression.

### Cell images (LIVECell, NuInsSeg, MoNuSAC; 78 evaluation parents)

**Classification:** BLOCKED BY IMPLEMENTATION. **Verdict:** INCONCLUSIVE (no result).

- 624 predictions were sealed and replayed. The worker then failed with an out-of-memory error while rasterizing a
  MoNuSAC reference: the inherited decoder allocates one full-image mask per annotated nucleus, under a 2 GiB
  address-space limit. Given the fixed dataset order, it had already decoded the 38 LIVECell and NuInsSeg evaluation
  references and scored them in memory, but wrote nothing; how many MoNuSAC references it reached is unknown.

### Corrections

1. Shuffled spatial control described as "matched" and as beaten: replace with "The graph-shuffled combined gate made no
   changes; by construction it was expected to make almost none, so it is equivalent to the native arm and does not test
   whether neighbour information beats a random filter of the same size."
2. "Useful exploratory positive" and "modest measured signal": replace with "a modest exploratory signal from a
   predeclared secondary ablation on one previously used donor; it has no matched shuffled control, was not compared with
   standard spatial smoothing, and its five-of-six rule was set by hand without a check on the source donors."
3. "Independent saved-aggregate audit passed 175 checks": write "a saved-aggregate arithmetic check written before the
   run passed 175 checks".
4. Perturb-seq "No repair gain": add "Even on training data no candidate gained more than one net correction over the
   baseline, against at least four required for admission, so this run could not distinguish scalar from pairwise
   representations."
5. Images, "reference access before allocation failed is unknown": replace with the precise statement above; any later
   score-only recovery must disclose it.
6. State the cause of the image failure (one full-image mask per nucleus under a 2 GiB limit).
7. The spatial pre-amendment source text was not archived (only hashes and test receipts); say so.
8. A receipt label is wrong: "Terminal receipt `6e1061f9...`" is the authoritative final receipt; the terminal receipt is
   `fe9f4d06...`.
9. Write "64 readout genes across 255 held perturbations (16,320 correlated predictions per method)".
10. Manuscripts: "real Perturb-seq expression profiles" (master and reviewed fallback, line 1186) should read "real
    Perturb-seq perturbation-response profiles (changes relative to control cells, not measured pre-perturbation
    expression)"; "on noisy data a uniform bar is either too strict or not selective" should read "in the imaging and
    Perturb-seq studies a uniform bar was either too strict or not selective; whether noise is the cause is an untested
    hypothesis"; the heading "Why strictness is selective on symbolic benchmarks and suppressive in noisy imagery" should
    read "Strictness was selective on symbolic benchmarks and suppressed corrections in an imaging calibration"; after
    "the needed change there is in representation, not search" add "A follow-up that added such relations, comparisons
    between training-imputed responses, also admitted no rule because even on training data no candidate neared the
    admission bar, so the limit there includes the evidence, not only the language." Stale lines saying a Perturb-seq
    pilot is "held behind pre-declared criteria" must be replaced by the sentence below.

### Sentence the papers may use

"Three exploratory follow-ups on previously used biological data were each run once from a reviewed, frozen protocol,
with every prediction fixed and hashed before any answer was opened: on four adjacent brain sections from one donor, the
predeclared primary rule, which accepts an earlier marker-based white-matter rescue only when at least five of a spot's
six nearest neighbours are already predicted white matter and a marker-rank check agrees, raised macro-F1 (the average
of the F1 scores for white matter and for the cortical layers) from 0.9316 to 0.9336 (23 corrections, 9 harms) but
failed its criterion because one section worsened slightly, while the neighbour check alone, a predeclared secondary
ablation, reached 0.9350 (36 corrections, 12 harms, all four sections better); on Perturb-seq, rules comparing response
changes imputed from training perturbations, not measured pre-perturbation expression, were admitted for none of 64
readout genes because even on training data no candidate gained more than one net correction over the baseline against
at least four required, and no method found any of the 32 directional responses among 16,320 held predictions; and the
cell-image follow-up stopped with an out-of-memory error while decoding reference masks, so it gave no result."

Do not write: "significant", "beat a matched shuffled control", "relational representations fail on Perturb-seq", "a
new imaging null", "adapter law", "learned transfer".

## 6. Learned, supplied, constructed, transferred (all biology results)

| Result | Supplied by people | Learned or inferred | Transferred |
|---|---|---|---|
| Inferred wiring (333, 595) | Rule language (constants, literals, AND/OR of up to 3 literals: 2,204,362 rules at 60 genes); smallest-fit selection; verify-or-abstain check; flip-score inference rule; task recipe; exactness checker; supplied wiring for the ceiling only | Per target only: the regulator set (recomputed in each leave-one-out fold) and the chosen rule; nothing across targets | The verify-or-abstain design idea; no ARC-learned artifact, no entry code, no shared executor |
| ARC-derived ordering | 16-function language and interpreter; the adapter; input pairs; fewest-input rule; budgets; three control orders; scorer | Counts of 5 of 16 truth tables from 22 ARC tasks (the only thing transferred) | Only the order of the 16 tables; it decided between equally simple fits and changed 39 outcomes |
| Three-input OR stage | 8 forms; the two-literal base language; search join; ranking; two-attempt readout | The choice of one form from 14 biological base failures | Between biological families, not from ARC |
| Active selection and completion | Cohort; simulator; 16 two-input truth tables over all variable pairs; tie order; the three selection rules and the 20-label budget; the four completion rules (engineered by the authors after the overall result); scorer | Per target only: which one- and two-input rules fit its 20 labels | Nothing learned from ARC; shared Boolean code is reused software |
| Continuous follow-ups | Neighbour graph, five-of-six bar, marker checks; Reactome relations, imputer, thresholds, error model, admission bar; image operators, features, priors | Nothing in the spatial run; per-gene choices among 48 replacements (none admitted); image operator choice from 51 calibration parents (never scored) | Nothing from ARC; "accept an edit only if a check passes" is a design idea |
