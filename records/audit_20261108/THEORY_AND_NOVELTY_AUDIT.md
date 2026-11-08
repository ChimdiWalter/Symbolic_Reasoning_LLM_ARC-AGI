# Theory and novelty audit

Date: 8 November 2026 (UTC). Documents audited: the full research paper ("Learning What to Change", the master,
`paper/v2_neural_cora/main.tex`) and the ARC paper (`paper/final_20261108/cora_final.tex`). Part of the independent audit
of the companion study's completed results (inventory in `COMPLETE_COMPANION_RESEARCH_AUDIT.md`).

**Versions.** The master was being edited during the audit. Line numbers below refer to a frozen copy taken at 22:44
local time (SHA-256 `953959dc...`, based on commit `956d70e9`); the master has since been revised (commit `36cdf3a1` and
later edits), so use the LaTeX labels and quoted phrases, not the line numbers. The ARC paper's related-work and theory
sections were word-for-word identical to the companion's reviewed source (`53b922cb...`), so every finding on them
applies to the reviewed fallback as well.

**Severity.** Major: a theory or novelty claim is false or rests on a mis-specified model. Moderate: a reviewer would
rightly object to an unsupported or wrongly scoped statement. Minor: wording, attribution or bibliography.

## Summary

- Most propositions are correct under their stated assumptions, and the master labels them "elementary". The ARC paper
  goes further and lists them as "a theory" contribution.
- Three formal statements have real gaps: the decision model with the proposition "A record does not identify its
  cause", the proposition on language growth under agreement of all fitting programs, and the contract-pruning
  proposition.
- Two of the five predictions (admission and reuse) leave out costs the literature already names.
- Most serious: the claimed difference from library learning misdescribes DreamCoder, and the paper's own construction
  results do not support it.
- The empirical audits sharpen three theory-facing claims: the knowledge-keyed acceptance bar was never tested apart
  from a support prior (`BIOLOGICAL_TRANSFER_AUDIT.md`, section 1); every learned or adaptive selection result is either
  a fixed hand-written rule or ties a strong fixed alternative (`AUTONOMOUS_REASONING_LOOP_RESULTS.md`, section 6; the
  view score in `NATURAL_ARC_CONSTRUCTION_REVIEW.md`, section 2); and transfer from ARC failed even with a shared
  binary alphabet (`BIOLOGICAL_TRANSFER_AUDIT.md`, section 2).

## Checked and correct

Arithmetic recomputed with `scripts/theory/checks.py`:
- "Demonstrations underdetermine programs" (`prop:under`): correct under its closure assumptions (Mitchell's point that a
  learner without inductive bias cannot classify unseen cases).
- "Verification establishes consistency, not intended correctness" (`prop:stability`): correct for a deterministic
  acceptance rule.
- "Selective acceptance trades coverage for precision" (`prop:selective`): a weighted-mean identity. All 82 strict
  answers are among the fit-only answers; precision 71/82 = 0.866 against 102/134 = 0.761; the 52 removed answers had
  precision 31/52 = 0.596.
- Nesting (`prop:nest`, solved at most generated at most expressible): a correct accounting identity.
- "An omitted essential input cannot be recovered by search" (`prop:essential`): correct.
- "Demonstrations carry a bounded amount of information" (`prop:information`): the decision-tree proof is correct,
  adaptive queries included. log2 C(20,3) = 10.155; rules with at most three inputs among 23 genes: 388,656, of which
  ten observations can single out at most 1,024 (0.263%); ten observations of a four-input rule leave at least 64
  completions. The design-simulation ceilings agree (10 variables, 10 transitions: at most 3.9% of three-input rules
  identifiable, at most 3% observed; 60 variables, 20 transitions: at most 14.1%, at most 13% observed).
- Akutsu, Miyano and Kuhara 1999, Theorem 3 gives the worst-case bound the paper cites (read in the paper's text).
- Exact sign-test p-values and the Wilson bound for 13 of 13 (0.772): correct.
- The 754-of-842 exclusion: a sound argument for a finite, frozen, one-step language.
- The companion's theory notes are correct and carry two scope precisions the master dropped: candidate programs are
  total (defined on every input), and failure hypotheses are joint, not exclusive. The master's "forthcoming packet"
  note is stale; the packet exists.

## Issues

1. **Major. The difference from library learning misstates DreamCoder and is contradicted by our own data.** Where: the
   section "What would distinguish it experimentally" (`sec:distinguish`); "Compressing the language does not extend
   search reach"; the companion novelty note's LILO row. The text says library learning "compresses what is already
   reachable" and "compression adds none". DreamCoder's held-out ablations show the opposite ("neither ablation ever
   solves more than 60% of held-out tasks while DreamCoder learns to solve nearly 100%", checked in the PLDI text).
   Compression leaves expressibility unchanged but raises budgeted reach. CORA's construction result is the same kind of
   effect: the 211-structure space contains the answers, blind enumeration recovered 10 of 11 construction-test tasks,
   and two of the four constructed operations (trim, upscale) are compositions of the base grammar. The 28-to-27-node
   result is one test of CORA's own compression (note 0568 already says it "is not a universal law"). **Fix:** state
   the contrast as expressibility against budgeted reach; say that both compression and CORA's construction act on
   budgeted reach; claim no difference from DreamCoder, LILO or Stitch until a natural held-task comparison at matched
   total compute exists (construction from failure, against compression of solved programs, against static search).
2. **Major. The decision model does not fit the paper's own example, and the records proposition proves nothing as
   written.** Where: equation `eq:gain`, proposition `prop:records`, figure `fig:samefailure`. The failure record is a
   deterministic function of the system and the demonstrations, so "the record has the same distribution under two
   hypotheses" is always true for a fixed task and the proposition is empty. Evidence acquisition changes the
   demonstrations, which rec(a(S), D) cannot express. The proposition reads a single cause from a distribution over
   mutually exclusive types, but the four-intervention worked example needed all four interventions together and the
   companion's note says hypotheses are joint. The figure shows four different systems, not one system under two
   hypotheses. **Fix:** put a distribution over tasks given the cause, P(demonstrations, test inputs, answer | cause),
   with the cause ranging over sets of failure types; state separation in terms of the observation after an action,
   including new evidence; call the figure an illustration; import the companion's formulation (every action may depend
   only on what has been observed so far).
3. **Moderate. Information value is claimed as the paper's own and is missing from its formula.** It is the core of
   Russell and Wefald's value of computation. `eq:gain` scores only the direct change in answers minus cost, so a pure
   diagnostic action scores below zero and the stated policy would never run one. **Fix:** add an expected
   value-of-information term or state that the myopic rule undervalues diagnostics; keep as the genuine difference that
   persistent changes need validation across tasks, and relate it to Minton's utility problem.
4. **Moderate. The growth proposition is false for programs that can fail on the test input** (`prop:unanimity`). The
   proof needs at least one prediction at the test input under the smaller language; if every fitting program there is
   undefined, the larger language can add an answer. CORA's search records undefined test predictions
   (`experiments/cora_cast_20261026/cast/search.py`, `_visit`). Its table entry cites the bioimage calibration, which
   changed acceptance within a fixed language using near-top fits, a rule the proposition itself calls non-monotone.
   **Fix:** assume every fitting program is defined at the test input, or count "undefined" as disagreement; relabel the
   bioimage case as an illustration of disagreement leading to abstention.
5. **Moderate. The contract proposition does not match the computation the code performs** (`prop:contracts`; ARC paper
   appendix). Soundness is defined on concrete grids, but the search prunes against summaries of all completions built
   from merged abstract states, which needs soundness for every grid an abstract state stands for (or monotone
   contracts). "Incompatible with the demonstration output" must range over all completions (a 3 x 3 prefix can still
   reach a 6 x 6 output by upscaling). Exactness holds only when both searches complete, and only up to
   observational-equivalence merging and a cap of 64 recorded fits. The code and `tests/test_contracts_exhaustive.py`
   (check c) already use the stronger notion. **Fix:** restate soundness for abstract inputs, define pruning by the
   completion summary and the backward predecessor check, add the completion and cap conditions.
6. **Moderate. The admission bound ignores that the constructor chooses among many candidates** (Prediction 4; ARC
   paper theory item 5). The bound eps^v holds for one pre-specified operation; choosing among up to 211 structures gives
   N times eps^v, which is 2.1 at eps = 0.1, v = 2: no bound. **Fix:** state it per candidate and over the family, or
   validate on tasks held out after selection.
7. **Moderate. The reuse bound ignores that new operations widen the search** (Prediction 5). Comparing b^k' with b^k
   omits the growth of the branching factor. The appendix records this cost: on the public evaluation the learned
   library raised execution-budget stops from 9 to 43. **Fix:** compare (b + delta b)^k' with b^k, cite Minton 1990,
   give the 9-to-43 result as the measured face.
8. **Moderate. The ARC paper calls a tautology an "empirical pattern"** (theory item 4, "converted budget into answers
   only within the language's reach", and the criteria table's theory row). If "reach" means expressibility it says
   nothing; if it means what static search finds, the data contradict it (the guide at 500 operations got 4 tasks the
   hand-set order missed at 20,000; at 20,000 the discordant tasks split 4 against 3). **Fix:** "guidance changed which
   answers a fixed budget found, and at 20,000 the counts tied (327 against 329)".
9. **Moderate. The knowledge-keyed acceptance bar is credited with evidence it never received** (`eq:bar`; ARC paper
   theory item 6). Inferred wiring is a prior built from the same demonstrations (a simplicity bias), not established
   knowledge; supplied wiring is the target's own published support (an oracle); the bar was never separated from the
   prior; for deterministic exact fits the likelihood ratio is 1 or infinite, so the bar reduces to a prior threshold.
   **Fix:** say the bar is untested; present 85 to 99 and 66 to 101 as a support-prior result; add a noise model if the
   bar is meant to weigh evidence.
10. **Moderate. The leave-one-out claim is credited to a mechanism the data do not isolate** (novelty claim i; table
    `tab:prior` row C; ARC paper novelty claim 2). The significant precision gain (+0.105) belongs to the whole strict
    policy; leave-one-out alone gave +0.087, Holm p = 0.176. Joffe and Eliasmith use leave-one-demonstration-out
    cross-validation on ARC to choose hypotheses (checked in their text; the paper calls it "held-out demonstrations").
    Jackknife+ goes uncited, and CORA's gate has no comparable guarantee. **Fix:** name the claim "stability-gated
    abstention (strict policy)", mark leave-one-out as not isolated, describe Joffe and Eliasmith exactly, cite
    jackknife+ and state that CORA gives no coverage or precision guarantee.
11. **Moderate. The construction claim overstates "growth" and its main p-value counts dependent tasks as independent**
    (master claim ii; `tab:prior` row A; the grammar-induction paragraph; ARC paper claim 1). "Growth" is selection from
    a pre-registered finite space; the outer language never changes. That is closer to DeepCoder's sort-and-add ("the
    next most probable function (or several) are added to the active set", checked) guided by deduced specifications
    (lambda-squared, FlashMeta). The ARC paper's precedent list misses Berwick 1980, Cussens and Pulman 2000, Neo, the
    full Popper record and Soar chunking at impasses (the master cites all but Soar; neither cites Soar). p = 0.0078
    treats 11 tasks from 4 removed-operation families as independent; at family level both the shuffled control and the
    demonstrations-only control lose in 4 of 4 families (exact two-sided p = 0.125 each), so "shuffled significant,
    demonstrations-only not" depends only on the unit. **Fix:** "specification-guided selection within a declared
    space"; report family-level counts beside task-level ones; bring the master's precedents into the ARC paper.
12. **Moderate. The introduction claims a gap that prior systems already fill** ("What none of these results requires is
    ... determining what its reasoning language is missing"). DreamCoder, LILO and Stitch learn abstractions;
    LEGO-Prover adds verified lemmas; LATM builds tools from 3 examples checked by unit tests on 3 validation samples
    (checked); the ABC repair system's reformation changes a theory's language; ARCANA conditions its prior on failure
    feedback. **Fix:** narrow the gap to choosing among kinds of revision from typed failure evidence, under matched
    controls.
13. **Moderate. The master title names an untested programme as the paper's result.** "Failure-Grounded Co-Induction of
    Representations ..." names a paradigm whose distinctive part has no positive evidence: the one researcher-diagnosed
    extension fitted 18 tasks against 17 for the base language and 17 for a random extension, and on nine authored cases
    a fixed hand-written view score solved 3 against 9 of 9 for the full view bank in a shuffled order. **Fix:** "Toward
    ...", or move co-induction to the subtitle as a research programme.
14. **Moderate. The ARC paper calls its elementary statements "a theory" that "predicts" results.** Two of the six
    "results" are not results (item 5 is an idealized bound, item 6 a proposed criterion). Selective acceptance and
    language growth were added on 6 November, after the measurements; predictions 2 to 5 predate the construction test
    (27 October against 1 November). **Fix:** "elementary conditional results that account for", citing protocol dates
    where a prediction was registered first.
15. **Moderate. The ARC paper omits the classical sources for its own propositions** (Mitchell 1997 for
    underdetermination; Padhi et al. 2019 for a larger language lowering accuracy; the must-cites in
    `records/NOV6_GRAMMAR_INDUCTION_LITERATURE.md`). **Fix:** add them from that record's verified entries.
16. **Minor to moderate. Two "measured face" entries in `tab:theorystatus` do not instantiate their propositions**
    (`prop:larger`). The cited puzzle had 0 correct in both language versions (inexpressibility, not loss caused by
    growth); the proof's one-task construction does not show "coverage rises" (that needs a second task); the two
    outranking programs must also predict two different wrong outputs. **Fix:** amend the construction and replace the
    measured face.
17. **Minor to moderate. Prediction 3 is false as stated.** "When no program in H or R_k(H) fits, only a new operation
    ... can raise coverage" (H the solver's hypothesis memory, R_k(H) the programs within k actions of it): more search
    could also raise coverage. **Fix:** condition on the whole language, or say "more search or a new capability".
18. **Minor to moderate. Expressibility is defined two ways.** expr(L) does not require fitting the demonstrations (with
    constants every answer is expressible), while the 754-of-842 analysis uses the fit-based notion. **Fix:** define it
    via the version-space predictions A_L(D, x*).
19. **Minor to moderate. Two precedents for Boolean experiment design and active selection are missing.** Ideker,
    Thorsson and Karp 2000 choose perturbations by entropy to discriminate consistent Boolean networks (checked): the
    nearest precedent for 320 against 291 and for the design simulation. Query by committee and Angluin are cited only
    later. **Fix:** cite Ideker et al. 2000 and query by committee or halving where acquisition is introduced.
20. **Minor to moderate. The transfer explanation is post hoc and misses a later result.** "No shared alphabet" explains
    the early zero-witness result, but a later adapter built a shared binary alphabet, found 22 witnesses, and the
    transferred ordering still lost (177 against 194 static and 182 permuted). **Fix:** report it as a negative with a
    shared alphabet in place.
21. **Minor. Smaller statement, citation and definition fixes.**
    - "A learned policy changes the order ... not the set of programs that can be reached" holds only for complete
      search at unlimited budget.
    - Padhi et al. is attached to the nesting; it belongs with "a larger language can lower accuracy". The contract
      proposition is cited for efficiency but is about exactness.
    - Pereira and Schabes' brackets were supplied supervision; inferred regulator sets add nothing beyond the
      demonstrations.
    - "Guidance moves only the left of the budget curve" follows from complete enumeration in any approach, and 20,000
      operations is not an asymptote.
    - "A missing operation (construction succeeds where matched search fails)" misidentifies trim and upscale, which are
      base-grammar compositions.
    - The reachability paragraph uses the decision model's menu, but the audit used the harness's edit menu.
    - Residual masks and "fits when B = R = 0" are undefined when output size changes (39 of 120 public-evaluation
      puzzles). "The record is a function of S and D only", yet acceptance reads the test inputs.
    - "Whatever the rule language" is misleading (a restricted language or prior can leave one rule); credit the counting
      bound to Angluin 1988 and Akutsu et al. 1999, Theorem 3.
    - The policy conjecture's "best fixed order" must be selected on source tasks; the co-induction conjecture should
      say whether researcher-diagnosed changes count, and if so record the 18 / 17 / 17 test as a failed instance.
    - ARC paper: "would need a search reaching programs of about 29 nodes" treats reference-program length, an upper
      bound, as a requirement.
    - Chollet's measure weights skill acquisition by priors, experience and generalization difficulty; "answers per
      unit of compute" is a different quantity, so say "inspired by".
    - Stitch: PACMPL 7 (POPL), Article 41, pp. 1182 to 1213, doi 10.1145/3571234 (checked). DeepCoder "widens its active
      set of existing functions", not "adds functions". The Murphy 2026 detail "expands the pool when error is too
      large" is not in its abstract.
    - The companion's leave-one-out characterization "accepts exactly when every observed assignment occurs twice"
      should add that the test input's assignment must also have been observed.

## Novelty: nearest precedent per claim

Citations were checked on Crossref, arXiv or in full text on 7 to 8 November. "(not cited)" means the papers omit it.

| Claim | Nearest precedent | What the executed experiments add | Verdict |
|---|---|---|---|
| Construction specified by failure, admission checks and reuse | LATM (arXiv 2305.17126); LEGO-Prover (arXiv 2310.00656); lambda-squared (doi 10.1145/2737924.2737977); FlashMeta (doi 10.1145/2814270.2814310); Alford et al. on ARC (doi 10.1007/978-3-030-93409-5_54); DeepCoder sort-and-add (arXiv 1611.01989); Berwick (doi 10.3115/981436.981453); Neo (doi 10.1145/3192366.3192382) | Construction test (11 tasks, 4 planted deletions, inside a 211-structure space that contains the answers): own specification 8, another task's 0 (family level 4 of 4, p = 0.125); matched search 5; blind enumeration 10 at about 5 times the CPU. At scale: 64 against 38 against 16 of 95, compute favouring the static arm, intervals crossing zero if either of two worlds is dropped; demonstrations alone 48 | Incremental; the new element is the shuffled-specification control |
| A failed search triggers growth | Soar chunking at impasses (doi 10.1007/BF00116249, not cited); DeepCoder sort-and-add | Search kept going on all 4 decoys; no control isolates the trigger | Not novel |
| Leave-one-out verify-or-abstain | Joffe and Eliasmith (arXiv 2511.08747); El-Yaniv and Wiener (JMLR 11:1605-1641); jackknife+ (doi 10.1214/20-AOS1965, not cited) | Strict policy +0.105 precision at 52 fewer answers on previously examined tasks; leave-one-out alone not significant; no guarantee | Incremental and small; not isolated |
| Contract-pruned typed search | Yoon, Lee and Yi (doi 10.1145/3591288); Absynthe (doi 10.1145/3591285) | 0 lost fits on a finite scope; 28 times fewer executions; no answer changed | A domain instance |
| Learned search order | DeepCoder; CrossBeam (arXiv 2203.10452) | 320 against 234 at 500 counted operations, but frequency (318) and linear (323) orders matched the guide; 327 against 329 at 20,000 | Nothing beyond a frequency prior |
| Library reuse against compression | DreamCoder (doi 10.1145/3453483.3454080); LILO (arXiv 2310.19791); Stitch (doi 10.1145/3571234) | CORA's own compression 28 to 27 nodes, no reach gain; same-family reuse 51 of 60 against 28 is descriptive and routed by the family label; other-family 23 against 28; none of these systems was run | Nothing established beyond them |
| Popper comparison | Cropper and Morel (doi 10.1007/s10994-020-05934-z) | 1 of 5 against 3 of 5 with unequal budgets | Uninformative |
| Representation and language revision (co-induction) | ABC repair system (doi 10.5220/0006959703350342, not cited); Bundy and Li 2023 (doi 10.1098/rsta.2022.0052); MetagolRCF (doi 10.1007/s10994-013-5358-3); counterexample-guided abstraction refinement | Diagnosed extension 18 against 17 base against 17 random; fixed view score 3 of 9 against 9 of 9 for the full bank in shuffled order | Untested proposal |
| Decision model, "learning what to change" | Russell and Wefald (doi 10.1016/0004-3702(91)90015-C); ARCANA (arXiv 2607.09059: learned meta-controller, failure feedback conditions the prior, 32.5% semi-private as reported by its authors) | No policy trained; the learned ranker lost to static search | Framing only |
| Boolean network inference: support, active selection, conditional construction | REVEAL (PSB 1998); Akutsu et al. (doi 10.1142/9789814447300_0003); Lahdesmaki et al. (doi 10.1023/A:1023905711304); LFIT (doi 10.1007/s10994-013-5353-8); Ideker et al. (doi 10.1142/9789814447331_0029, not cited); query by committee (doi 10.1145/130385.130417) | Support prior 99 of 333 and 101 of 595 (one-input rules), with no classical support-inference arm in those runs; a classical support-table learner tied conditional construction (433 against 433); active selection (320 against 291) is committee disagreement with no classical chooser arm | Results, not novelty |

## What the papers must change (in order of importance)

1. Rewrite the library-learning contrast as expressibility against budgeted reach and drop "compression adds none"
   (issue 1).
2. Repair the decision model and the records proposition, or call them illustrations (issue 2).
3. Add the missing assumptions to the growth and contract propositions (issues 4 and 5).
4. Retitle or move co-induction to a research-programme subtitle (issue 13), and narrow the introduction's gap (issue 12).
5. In the ARC paper: "elementary conditional results that account for" instead of "a theory that predicts" (issue 14),
   replace theory item 4 with the measured statement (issue 8), say the knowledge-keyed bar is untested (issue 9), and
   add the classical sources (issue 15).
6. Correct the admission and reuse bounds and Prediction 3 (issues 6, 7, 17).
