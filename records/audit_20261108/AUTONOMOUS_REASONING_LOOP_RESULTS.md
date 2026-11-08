# Autonomous reasoning loop results

Date: 8 November 2026 (UTC). Part of the independent audit of the companion study's completed results (inventory in
`COMPLETE_COMPANION_RESEARCH_AUDIT.md`). Nothing was rerun or rescored; correctness labels are the producers' saved scores.

## Terms

- **Authored functions**: Boolean functions written for the test, not natural data.
- **Two-input language**: every rule that uses at most two inputs (the source code calls it TT2).
- **Label**: one answered query, meaning the hidden function's value at one chosen input. A **paid label** is charged
  to the method's budget.
- **Exact recovery**: the predicted function is right on every input.
- **Fixed controller** or **router**: hand-written if-then rules. Nothing in this file was trained.
- **Fixed schedule**: the same sequence of actions for every case, with no diagnosis.
- **Conditional rule** (cofactor split): a rule that branches on one input and uses a smaller rule in each branch.

"Autonomous" in the papers can only mean: fixed hand-written decision rules executed without a human choice per case.
No result here involves a trained controller or a learned choice of which change to make.

## 1. Summary

| Result | Classification | Verdict | Reading |
|---|---|---|---|
| Authored diagnosis-and-revision loop, 219 of 256 | COMPLETE AND VERIFIED | PASS for the numbers; FAIL for "219 constructed" and for any reading that diagnosis helped | The gain over 38 comes from the supplied larger language plus one paid label per built function; a fixed schedule ties function by function |
| Saved traces of the existing construction loop | COMPLETE AND VERIFIED | PASS, with corrections | The loop runs end to end under fixed rules; its typed holes come from the demonstrations, not from the failed program |
| Construction at scale, 64 against 38 of 95 | Audited separately by our construction owner (inbox 0203) | Verified there, with three corrections | Our observations agree and are forwarded as observations only |
| Cofactor query-policy revision, +310 | COMPLETE AND VERIFIED | PASS for the narrow count; FAIL for any claim of a policy advantage | A researcher-made revision; a fixed expressive policy is at least as good on every unit |
| Sparse learner over 60 coordinates | COMPLETE AND VERIFIED | PASS, with corrections | Higher-arity coverage from a known method; its "tie" with the classical table holds by construction |
| Learned choice of which change to make | NOT STARTED as a completed study | INCONCLUSIVE | The decisive tests are still being built (section 6) |

## 2. Authored diagnosis-and-revision loop (219 of 256)

Design: all 256 Boolean functions of three inputs, each hidden among eight inputs; seven of each function's eight
truth-table rows are shown (other inputs at zero); four random held inputs per function. Two work tiers (10,000 and
40,000 units). Frozen sources at 22:48:46 UTC came before the single run at 22:56:57 UTC.

| Policy | Held bits correct of 1,024 | Exact of 256 | Answered of 256 | Paid labels |
|---|---|---|---|---|
| Two-input language alone | 279 | 38 | 75 | 0 |
| Fixed controller (search fails, ask for the missing row, build) | 1,003 | 219 | 256 | 181 |
| Fixed build-then-ask schedule | 1,003 | 219 | 256 | 181 |
| Fixed random action order | 1,003 | 219 | 256 | 362 |
| Strict abort when evidence is exhausted | 1,003 | 219 | 256 | 181 |
| Shuffled routing features | 819 | 173 | 210 | 2,160 |

- Decomposition: 219 = 38 two-input rules accepted at once + 181 three-input tables built; 1,003 = 279 + 4 x 181.
  Exactly 38 of the 256 functions depend on at most two inputs, so 38 is the two-input language's ceiling.
- Paired, function by function: controller against schedule, random order and strict abort: 0 gains, 0 losses (219
  both, 37 neither). Against the two-input language: 181 gains, 0 losses. Against shuffled features: 46 gains, 0 losses.
- What the controller did: in all 181 built cases, one pass. The two-input search failed, it bought the one unseen row
  (181 of 181 paid labels were that row), built the table, replayed and predicted. Its paid search for hidden relevant
  inputs never ran, because the shown rows vary only the three relevant inputs. The router uses three of its five
  features; the conflict flag and the observed count are recorded but unused.
- Wrong fits: 37 two-input rules fitted all seven shown rows but were wrong; they are the same 37 functions in all six
  policies and were accepted before any revision. 19 of them still got all four held bits right, 15 got three, 3 got
  two, so the 98% held-bit score hides most of these errors (85.5% of functions are exact). The design itself produces
  about 38 such wrong fits (standard deviation 4.9).
- The controller used 12.89% less native work than the schedule (53,757 units); all of it is the schedule's one failed
  build attempt before asking. The shuffled arm's 46 losses are cases whose donor had a two-input fit: the router then
  repeated the two-input search for 16 steps and never asked for the unseen row. Its donor work charge changed no
  answer (answers are identical at both work tiers).
- The "classical" readout is the same table, not compiled into conditionals, and the code refuses any case where the two
  disagree, so that tie holds by construction.
- Custody: all 6,336 prediction slots, including the nulls, stayed in the denominators; no paid or kept state equals a
  held input; 13 of 13 frozen files and 14 of 14 pins match; cost 5.263553 CPU s. One custody label is wrong:
  `cage/unified_failure_loop_source_review_20261107_v1/PRELIMINARY_FINDINGS.json` pins the amended freeze, but its four
  findings concern the predecessor freeze `ff0e59d0...` and it was written 22 s after the amended freeze. Relabel it
  "findings against freeze ff0e59d0, recorded after repair". The result is unaffected; the source diff shows the repairs
  came before any task was generated.

### Corrections

1. "219/256 constructed Boolean cases" (master, five places, for example "solved 219 of 256 constructed Boolean tasks
   but tied a strong fixed search"; ARC paper, two places; Writeup, one) should read "219 of 256 authored Boolean
   functions recovered exactly (38 two-input rules accepted at once, 181 three-input tables built by the loop)". The
   master's "219 against 219 constructed Boolean tasks" should read "219 against 219 authored Boolean functions".
2. "38/256 for the restricted language": add that 38 is that language's ceiling and that the baseline bought no labels
   against 181 for the loop, so the gap measures the supplied language, not diagnosis.
3. "A strong fixed search also 219/256": it is a fixed schedule, not a search. Write "a fixed build-then-ask schedule
   with the same language and evidence rule recovered the same 219 functions".
4. "37 wrong rules fitted the visible examples": write "37 two-input rules fitted all seven shown rows but were wrong;
   they were accepted before any revision in all six policies", and add that 19 of them still got all four held bits
   right and that the design produces about 38 such fits.
5. "Repeated paid-evidence, then two-input no-fit, then construction loop" (note 0575, `REPORT_OUTCOME.md`) reverses the
   order and nothing repeated. Write "in every built case, one pass: the two-input search failed, one paid label for the
   unseen row, construction, replay, prediction; the paid search for hidden relevant inputs never ran".
6. "Classical same-transcript programs tied": a consistency check by construction, not a comparator.
7. Shuffled control, "donor debit prevents a clean causal interpretation": write "misleading features cost 46 functions;
   since a feature-blind schedule tied, the test cannot show that authentic features help".
8. "Fewer queries than random routing": the comparison is with one fixed action order that asks one extra label. The
   12.89% work saving over the schedule comes entirely from the schedule's failed build attempt.
9. "Independent" reviews: the source, host and outcome reviews were separate agents in the same companion workstream;
   the outcome review used aggregates only. Write "separate-agent review of saved aggregates; row-level recount by this
   audit".
10. Relabel the preliminary-findings file as above.

### Sentence the papers may use

"On an authored test of all 256 Boolean functions of three inputs, each hidden among eight inputs with seven of its
eight truth-table rows shown, a fixed hand-written controller that detects that no two-input rule fits, buys the one
unseen row and builds a three-input table recovered 219 functions exactly (38 two-input rules accepted at once plus 181
built; 1,003 of 1,024 held-out bits), against 38 for the two-input language alone, which is all that language can
express. A fixed build-then-ask schedule with the same language and evidence rule recovered the same 219 functions, so
the gain comes from the supplied larger language and one bought label per built function rather than from diagnosis,
and 37 two-input rules that fitted all seven shown rows but were wrong were accepted unchanged by every policy."

## 3. The existing construction loop and its saved traces

The construction closeout (95 generated tasks) is audited separately by our construction owner (inbox 0203: every
number matches in bound mode; corrections on compute direction, the 857 digest mismatches and reuse). Our diagnosis-loop
audit read the same code and saved traces. What it found agrees with 0203; the points below are observations for the
owner and the paper agent, not a second verdict on the closeout.

**Numbers that reproduce** (from the saved analysis): construction from typed holes 64 against 38 for static search in
the starting language (33 both, 31 construction only, 5 static only, 26 neither); exact paired p = 1.29e-5 (assumes
independent tasks); intervals +5.1 to +40.6 (8 groups), +16.8 to +38.9 (per task), +11.6 to +41.4 (11 families) points;
by world 23 against 15, 20 against 7, 21 against 16, and leaving out either of two worlds makes the interval include
zero; holes taken from another task 64 against 16 (51 gains, 3 losses); blind enumeration of the 211 structures,
success in all three seeds, 64 against 3; reuse in the same family 51 against 28 of 60, in other families 23 against 28
(Holm p 0.47).

**Controls the handoffs omit** (computed from the saved analysis):
- Demonstrations alone as the hole (same 211 structures): 48; 64 against 48 is 16 gains, 0 losses (p 3.1e-5; +6.5 to
  +34.8 points; all 7 non-tied groups favour the typed holes, sign p 0.016). This is the best evidence that the typed
  holes help, and it is a same-language control.
- Blind enumeration: success in most seeds 32; in any seed 74, including 18 tasks construction never recovered.
- Demonstrations alone against static search: 48 against 38 (23 / 13; p 0.13).
- Group-level sensitivity (not predeclared): 6 of 8 groups favour construction; sign p 0.29; signed-rank p 0.15.

**What the code does** (`cgrow/controller.py`, `cgrow/s1.py`, `cas/run_world.py`, `cas/analysis.py`):
- Typed holes are computed by `controller.sketches(train, g)` from the demonstrations, directly or after undoing one
  invertible starting-language operation. The closest failed program, its residue and the shape relation are recorded
  but no later step uses them; the failure only triggers construction. The producer's own lineage report already calls
  them "demonstration-derived hole pairs".
- The controller chose "invent an operation" in all 285 units, because that decision is how tasks were included; the
  action choice was never varied. Static search found a correct starting-language program for 38 of the 95 tasks, so
  "an operation is missing" is a budget-limited hypothesis.
- On held tasks, `run_world.commit` gives each task its family's capabilities by the generator's family label. No grammar
  holding all learned capabilities, used without the label, was tested; the other-family grammar did worse than static
  search (23 against 28).
- Compute favours the static comparator: 212 to 377 CPU s per task for static search (world means) against 27 to 44
  charged s per construction repeat (82 to 131 for all three); 0203 gives 8.47 against 2.61 CPU hours in all. 23 static
  searches stopped near their memory limit and 2 failed (0203 records the two memory errors as a deviation).

**Saved traces (lineage join)**: 1,140 unit records (285 per arm); unit end states 180 promoted, 12 quarantined, 93 none;
196 candidate rows (180 promotions, 13 quarantines with one later promoted, 3 no-fits); task routes 60 admitted, 4
fallback, 31 none. Of 16,139 checks, 15,282 passed and 857 failed originally (834 reuse and 23 other-family digests,
from raw-byte hashing of files written with different spacing); 1,023 rechecks (the 857 plus 166 that had passed) all
pass after the whitespace repair. The 722 "same-capability links" are 722 of 903 link records and cover only 11
capabilities, 51 held tasks, 73 task-capability pairs and 10 families. The rejected example kept 13 regression tasks and
failed 36 validation retries, each stopping at the search budget (about 150,000 calls); its answer was still committed
as a fallback, and its saved label is correct.

### Corrections (for the owner and the paper agent)

1. "Failure-derived typed holes", "CORA's own failed-program analysis", "typed residue/shape/hole diagnosis" (note 0565
   section 2; `CORRECTED_PAPER_PARAGRAPH_V2.md`; the master in several places): write "typed holes computed from the
   demonstrations once search fails".
2. "Strong static search": write "static search in the starting language, which received more processor time", and add
   the same-language controls (demonstrations alone 48, 16 gains and 0 losses; blind enumeration 32 in most seeds, 3 in
   all seeds, 74 in any seed).
3. "Makes operations available that matched static search did not reach": it is the supplied space that makes them
   available. Write "finds missing operations reliably inside a supplied space (64 in all three seeds, against 48 from
   the demonstrations alone and 3 for blind enumeration)".
4. "Unequal pooled three-repeat compute": write that the inequality favours the static comparator (0203).
5. p = 1.29e-5 treats the 95 tasks as independent: report it beside the 8-group interval, with 6 of 8 groups favouring
   construction and the leave-one-world-out result.
6. "16 failure-shuffled": write "16 with holes taken from another task's demonstrations". This shows the task's own data
   matters, not that failure analysis does.
7. "722 same-capability links": add "these cover 11 capabilities reaching 51 held tasks (73 task-capability pairs, 10
   families)".
8. Reuse 51 against 28: state that the family label routed the capabilities, that it is descriptive (0203: its
   pre-registered condition fails), and that other-family reuse did worse than static search.
9. "Declared action": the action was never varied.
10. Rejected trace: add that its answer was still committed as a fallback and was correct, and that "no validation fit"
    means no other task fitted within the search budget.

## 4. Cofactor query-policy revision on authored functions (+310)

Design: all 256 Boolean functions of three inputs, hidden among five coordinates, 4 of 32 inputs withheld from
querying; three embeddings (pool seed 732 on coordinates 0, 2, 4; seed 1701 on 1, 2, 3; seed 2903 on 0, 1, 3); 20, 40
and 60 labels; six hand-picked four-input functions. Freeze 20:40:33 UTC, launch 20:44:14, outputs 20:46:09.

| Exact at 20 labels (seed 732 / 1701 / 2903) | Exact of 256 |
|---|---|
| Revised policy | 254 / 248 / 188 |
| Earlier policy, rerun unchanged inside the frozen comparison | 148 / 138 / 94 |
| Fixed policy comparing the full one-split conditional language from the first query | 256 / 256 / 256 |
| Fixed conditional inference on the revised policy's labels | 256 / 252 / 196 |
| Uniform (random-order) querying | 256 / 190 / 128 |
| Shuffled routing | 254 / 248 / 38 |
| Two-input language | 38 / 38 / 38 |

- Paired, revised against earlier (recounted by the synthesis pass): 106 / 110 / 94 gains and 0 losses at 20 labels,
  310 in all. Across all 1,572 units: 310 gains and 1 loss (four-input functions, 40 labels, two-level splits: 2 of 6
  against 3 of 6).
- Fixed policy against revised: revised-only wins 0 / 0 / 0; fixed-only wins 2 / 8 / 68. Uniform against revised:
  revised-only 0 / 64 / 68; uniform-only 2 / 6 / 8. Held inputs correct of 3,072: revised 2,864; earlier 2,550; fixed
  3,072; uniform 2,742.
- Mechanism: the two policies query identically until the third witness (a witness is two inputs that differ in one
  coordinate and give different answers); after it, the revised policy compares conditional rules split on the
  lowest-numbered certified coordinate (`min(cert)`). Abstentions are unchanged (2 / 8 / 16); the whole gain is wrong
  complete functions (106 / 110 / 146 under the earlier policy) becoming exact.
- Units are not independent: the 310 gains come from 158 distinct functions (49 gain in all three embeddings, 54 in
  two, 55 in one). The only replicate is the embedding; 3 of 3 favour the revision (sign test one-sided p = 0.125).
- The first embedding is the one on which the earlier policy's failure was diagnosed; only seeds 1701 and 2903 are
  prospective (204 gains, 0 losses over 512 units).
- Compute: the fixed policy used 16.3 times the revised policy's work and 14.2 times its CPU; the revised policy 2.15
  times the earlier policy's work and 1.51 times its CPU. All arms used 20 of 28 allowed inputs; no cap was approached.
- The frozen protocol says "a policy benefit must survive the supplied expressive acquisition and all fixed nuisance
  controls". It did not: the fixed expressive policy is at least as good on every unit and uniform querying still wins
  on the first embedding (256 against 254). Judged as a test of policy advantage, the experiment failed by its own
  criterion.

### Corrections

1. "0 losses" needs a scope: "310 gains and 0 losses at the 20-label endpoint on the three-input functions (768 units);
   across all 1,572 units, 310 gains and 1 loss (six hand-picked four-input functions, 40 labels, two-level splits: 2 of
   6 against 3 of 6)."
2. Units: "The 310 gains come from 158 distinct functions. The only replicate unit is the embedding, and 3 of 3 favour
   the revision. No significance is claimed."
3. "Three predeclared embeddings" (PAPER_DELTA) should read "one diagnosis embedding and two embeddings fixed before the
   rerun".
4. "Repaired a diagnosed query-policy weakness" (note 0570; the master uses "repaired" in several places) should read
   "improved the earlier query policy", adding that the fixed policy is at least as good on every unit and that the
   protocol's policy-benefit criterion was not met.
5. "895 checks, zero issues" should read "895 automated checks on saved aggregates, source hashes and custody records,
   840 of which repeat ten bookkeeping checks; zero failed checks, status pass with qualifications; it opened no rows,
   did not rehash the predictions and did not check the 310 / 0 pairing".
6. OPTIONAL_PAPER_FOLLOWUP's "In the first version ... it recovered 148, 138 and 94" should read "The original query
   policy, rerun unchanged inside the frozen comparison, recovered 148, 138 and 94" (the first version ran only on the
   first embedding).
7. Table row "Earlier TT2-oriented queries and constructor" should read "Earlier two-input query rule, same conditional
   constructor".
8. "Executable diagnosis-driven revision" and "closes one local diagnosis-to-change loop" should read "a researcher-made,
   diagnosis-driven query-policy revision, frozen and tested prospectively; the only automatic step is switching to
   conditional hypotheses after three witnesses".
9. REPORT_V3's shuffled-routing explanation is wrong for seed 1701. The fixed permutation is 0 to 2, 1 to 1, 2 to 3, 3
   to 4, 4 to 0: at seed 732 the split moves to coordinate 2, which is relevant (a tie); at seed 1701 coordinate 1 maps
   to itself, so the shuffled arm equals the revised policy and is not a control there; at seed 2903 the split moves to
   coordinate 2, which is irrelevant (38 against 188).
10. "First certified variable" should read "lowest-numbered certified coordinate".
11. Equal resources: "identical label caps (all used 20 of 28 allowed inputs) and identical compute ceilings, but not
    equal compute: the fixed policy used about 16 times the revised policy's work, and the revised policy about 2.2
    times the original's."
12. "Prior independent source review" should read "source review reported before launch, saved 41 seconds after".
13. Held-input counts are correlated (at seed 2903 the four withheld inputs cover only two distinct patterns of the
    relevant coordinates).
14. State the mechanism: the revision changes only the queries asked after the certificate.

### Sentence the papers may use

"On authored test functions (all 256 Boolean functions of three inputs, each hidden among five input coordinates with
four inputs withheld from querying), a researcher-made revision of the query policy, prompted by the first version
losing to random querying, raised exact recovery (the whole function correct on all 32 inputs) after 20 answered
queries from 148, 138 and 94 to 254, 248 and 188 functions in three fixed embeddings (310 gains and no losses on the
same functions; the first embedding is the one that exposed the failure), but a fixed policy that compared the full
one-split conditional rule language from the first query recovered all 256 in every embedding, so the result shows that
query selection must keep pace with a growing rule language, not that adaptive growth beats a strong fixed learner."

## 5. Sparse learner over 60 coordinates

Design: all 256 three-input functions and six chosen four-input functions placed on random coordinates among 60; 20,
40 and 60 exact labels; seeds 731 and 1701; four held inputs per unit. Frozen 21:00:03 UTC, launched 21:01:57 UTC.

- Exact recovery of the 256 three-input functions at 20 / 40 / 60 labels: 36 / 248 / 256 (seed 731) and 38 / 249 / 256
  (seed 1701). Of the 218 functions that truly use all three inputs: 1 / 210 / 218 and 1 / 211 / 218.
- Two-input table learner on the same labels: 35 / 38 / 38 and 37 / 38 / 38. It can express only 38 of the 256
  functions. The only arm with random queries is also limited to two-input tables (30 / 38 / 38 and 32 / 38 / 38).
- At 20 labels: wrong fits 80 and 65, no fit 140 and 153. Four-input functions at 60 labels: 5 of 6 and 6 of 6. At least
  62 of 158 wrong fitted rules across all budgets still predicted all four held inputs correctly.
- Implementation: never builds the 2^60 input space; every bisection midpoint costs a label; 0 held inputs among the
  training inputs of 3,144 transcripts; neither the target's support nor its arity reaches the learner. Inference rerun
  from saved transcripts with the frozen engine reproduced all 6,288 readouts; seal hashes match (rehashed for the first
  time by this audit).
- The conditional (Shannon decomposition) program and the classical answer table compute the same function in 1,572 of
  1,572 units by construction: the conditional arm re-encodes the same table without loss.
- Exact 95% intervals (descriptive only): 36/256, 0.101 to 0.189; 248/256, 0.939 to 0.986; 1/218, 0.0001 to 0.025; 5/6,
  0.36 to 0.996; 6/6, 0.54 to 1. Functions within a seed share one query stream and the budgets share placements, so
  the two seeds are the only real replications.

### Corrections

1. "Ties the classical same-transcript support-table comparator": write "The nested if-then (Shannon decomposition)
   program is a lossless rewrite of the classical answer table built from the same labels, so the two match in every
   unit by construction. This is a consistency check, not a comparison of methods."
2. "vs 35/38/38 and 37/38/38 for two-input tables": write "A two-input table learner on the same labels, which can
   express only 38 of the 256 functions, recovered 35/38/38 and 37/38/38. The gap reflects what each learner can
   express, not query efficiency."
3. "Independent review 451 checks": write "A separate script review of source hashes and saved summary arithmetic found
   no inconsistency. A later audit reproduced all 6,288 sealed readouts from the saved label transcripts and confirmed
   the seal hashes." Do not cite 451 as strength (96 checks test the by-construction tie; 8 compare saved numbers with
   hard-coded headline numbers).
4. "Root independently reviewed the exact source, then launched it once": the review file was written by the launcher 3
   ms before launch. Write "A pre-launch checklist confirmed the frozen file hashes before the single launch."
5. Low budgets: state that only 1 of the 218 three-input functions was recovered per seed at 20 labels, with 80 and 65
   wrong fits and 140 and 153 no-fits.
6. Add "Across all budgets, at least 62 of 158 wrong fitted rules predicted all four held inputs correctly."
7. Add "The method assumes at most four relevant inputs and exact, noise-free answers to any input it chooses."
8. State that the seeds are the only replications.
9. "Cofactor engine" is an undefined internal label: write "Shannon decomposition (splitting a rule on one input into two
   smaller rules)".

### Sentence the papers may use

"In an authored test, a sparse classical query learner (binary search between two differently answered inputs to find
each relevant input, then a complete answer table written as nested if-then rules) recovered hidden rules that use three
of 60 binary inputs without enumerating all 2^60 inputs: with 20, 40 and 60 exact answers to inputs it chose, it
recovered 36, 248 and 256 of all 256 three-input rules in one random placement and 38, 249 and 256 in a second, that is
1, 210 and 218 and 1, 211 and 218 of the 218 rules that truly use all three inputs, with 80 and 65 wrong fitted rules at
20 answers; a two-input learner given the same answers, which cannot express those 218 rules, recovered 35, 38 and 38
and 37, 38 and 38, and the plain answer table built from the same answers made identical predictions by construction.
This shows higher-arity coverage from a known method, not a new learning advantage, a learned policy or a biological
result."

## 6. What these results show about learning what to change

- Every revision in this file was either made by researchers (the cofactor query policy; in biology, the completion
  rule) or executed by a fixed hand-written rule (the authored loop; the construction controller).
- The strongest comparisons are ties with strong fixed alternatives: the fixed build-then-ask schedule equals the
  controller; the fixed expressive query policy is at least as good as the revised policy on every unit; the classical
  table equals the conditional program by construction.
- So no completed result shows that choosing which change to make from failure evidence beats a strong fixed
  alternative. The decisive tests are the companion's selection experiment (note 0201: fixed evidence-based router and
  trained router reported separately, against full-bank or static access to every intervention, matched extra search,
  random, shuffled-failure and failure-blind controls) and our grid multi-cause routing test (construction owner). The
  companion's natural Boolean selection follow-up has no qualified result yet (note 0589).

## 7. Learned, supplied, constructed, transferred

| | Authored loop | Construction loop | Cofactor revision | Sparse learner |
|---|---|---|---|---|
| Supplied by people | Two-input language; tables over at most four inputs with a conditional compiler; three actions; the if-then router; evidence procedures; immediate acceptance of any fitting two-input rule; caps; the task design | Starting grammar; the 211-structure space (chosen so every removed operation is expressible); three hole forms ranked by a fixed score; controller rule; gates (novelty, at most 3 retries, regression, validation); promotion (2 of 3 seeds) and fallback rules; generator, families, worlds; the family label that routes reuse | Rule languages; the three-witness trigger; routing; all four query policies including the revision; caps, seeds, embeddings, withheld inputs; the 262 functions; scorer | All 262 functions and their placements; exact answers; the four-input cap; hypothesis languages; two-input-first order; query strategy (random screens then bisection, file byte-identical to the 6 November review); caps, seeds, held inputs |
| Chosen automatically per case | That two-input search fails; which row to ask; building, compiling, replaying, predicting; abstaining | Triggering construction; computing holes; structure and parameters; gate outcomes; admission or rejection; held-task answers | The certificate, candidate set, queries and fitted rule (discarded after each unit) | Certified inputs and one fitted program per unit |
| Learned | Nothing | 11 admitted capabilities (structure plus fitted parameters) selected by automatic gates; no trained model | Nothing; the revision was a human code change | Nothing |
| Transferred | Code only (interpreter, ledger and witness copied byte for byte) | Within-family reuse routed by the family label; other-family reuse did not help; none of this ran in the Kaggle entries | Nothing; the earlier policy was reused unchanged (verified unit by unit) | Nothing; reusing the bisection file is code reuse |
