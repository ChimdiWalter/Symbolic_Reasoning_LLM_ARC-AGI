# Theory to experiment: every theoretical claim, its proof status, its test and its result

Prepared 8 November 2026 (UTC) for the ARC Prize 2026 Paper Award submission of Chimdi Walter Ndubuisi (sole author).
Read-only analysis: nothing was run, rescored or edited; this file only proposes text. Paths are relative to
`/path/to/repository/` unless they start with `/`; the short names
used for sources are defined in section 10.

**Versions read** (SHA-256 prefix): Writeup `d09794e14c08` (1,470 words by `wc -w`), Paper 1 `97f07a8fa073`, Paper 2
`608fad32254f`. These are the versions whose find phrases the final-push brief lists (Brief lines 10-11).

**The criticism this answers.** A judge read: "The four 'conditional results' are one-line slogans, some true by
definition ..., with no stated conditions and no visible link to any number" and asked for "a four-row table, plus one
sentence of mechanism" (Judge read lines 25 and 41). The cold read says the same of "Theory. Four conditional results,
each tied to an experiment." (Cold read line 207).

Contents: 1 short answer; 2 conflicts with the binding audits; 3 index of every claim; 4 each claim in full;
5 deliverable 1, the Paper 1 table; 6 deliverable 2, the Writeup version; 7 deliverable 3, why the method works;
8 statement repairs the deliverables depend on; 9 UNKNOWN; 10 sources.

## 1. Short answer

- The three documents make 52 theoretical statements (section 3): 17 mathematical results or bounds, 19 mechanism or
  empirical claims stated as theory, 5 predictions, 5 conjectures or hypothesis groups and 6 framework definitions.
- Of the four results the Writeup lists, three have a direct test that supports them: few demonstrations fit many
  rules (32 of 134 answers from fitting programs were wrong), ranking cannot add ungenerated answers (at most 3 of 172
  over the neural comparison entry's candidates), and a missing input blocks recovery (0 of 274 gene rules needing
  three or more inputs). The fourth, growth under all-agree acceptance, has no test, and as written it is false for
  programs that return nothing at the query (Theory audit issue 4).
- The mechanism is supported on generated tasks as reliable discovery inside a supplied space: own typed holes 64 of
  95 in all three repeats, demonstrations alone 48, blind enumeration 3 (74 in some repeat), static search 38 with 3.2
  times the CPU. The binding audit says the holes are computed from the demonstrations and the failure only triggers
  construction, so "the failure itself can say what is missing" must be reworded (section 2, item 1).
- No completed result supports a learned or failure-conditioned choice of what to change; every test of it tied a
  fixed alternative or has not run (Companion audit, cross-cutting finding 8).

## 2. Conflicts with the binding audits (flagged; the first audit wins)

| # | Where the drafts say it | What they say | Binding correction | Use instead |
|---|---|---|---|---|
| 1 | Writeup lines 7, 21, 27, 38; Paper 1 lines 73-75, 112-114, 216-219, 234-235, 288-289; Paper 2 lines 78-79, 1621-1627, 1636 | "the failure itself can say what is missing"; "16 with shuffled failure evidence"; "failure-derived typed holes"; Popper contrast "here the failure instead specifies the operation" | Holes are computed from the demonstrations, directly or after undoing one starting-language operation; the failed program and residue are recorded but unused; "the failure only triggers construction"; "16 with holes taken from another task's demonstrations ... shows the task's own data matters, not that failure analysis does" (Loop audit section 3, corrections 1, 3 and 6; Companion audit, cross-cutting finding 4 and corrections table) | "typed holes computed from the demonstrations once search fails"; "16 with another task's holes"; add that all 16 fall in the one world whose removed operations compose into one another (section 4, B2) |
| 2 | Writeup line 7; Paper 1 lines 72-73, 110-112, 219-220 | "searching longer cannot help"; "more search in the original language cannot supply a missing operation" | Static search found a correct starting-language program for 38 of the 95 tasks, so "an operation is missing" is a budget-limited hypothesis (Loop audit section 3); the starting language can rebuild 6 of the 11 removed operations at cost levels 10 to 14 (Construction protocol lines 163-176) | "longer search is a slow and partial substitute" or "often cannot help", with the 38 beside it (section 4, B1) |
| 3 | Writeup lines 23, 67; Paper 1 lines 187, 483 | four results that "explain the pattern", "each tied to an experiment", "proved in the full paper" | "elementary conditional results that account for the measurements", citing dates where a prediction came first (Theory audit issue 14; Companion audit corrections table, last row) | Section 8 lead sentence; dates from Paper 2's history: the nesting result on 27 October (git `7417190d`), the others on 6 November (git `2428b3e7`) |
| 4 | Paper 1 lines 203-207, 222-223; Paper 2 lines 933-952 and table line 1151 | growth proposition without its missing assumption; "which the biology results test"; measured face "bioimage calibration (the mechanism)" | False when every fitting program returns nothing at the query; the imaging case is a fixed language and should be called an illustration (Theory audit issue 4) | Repaired statement (section 8); "untested" (section 4, A8) |
| 5 | Writeup line 56; Paper 1 lines 302-303, 451-457 ("independently audited"); Paper 2 lines 359, 1641-1657, 1965-1966 | "219 of 256 constructed Boolean tasks"; "tied a strong fixed search"; 12.9% less work as "an initial measured signal that reading the failure helps choose". The brief (P1-A4, W2) relabels it "companion-audited; our own audit not done" | Our audit now exists: numbers PASS; FAIL for "219 constructed" and for any reading that diagnosis helped; the 12.89% saving is entirely the fixed schedule's one failed build attempt before it asks for the missing row (Loop audit section 2, corrections 1, 3 and 8; Companion audit row 9) | "219 of 256 authored Boolean functions recovered exactly (38 two-input rules accepted at once, 181 three-input tables built); a fixed build-then-ask schedule recovered the same 219" and the saving explained as above (section 4, B11) |
| 6 | Brief rule 9 (lines 44-46) | "companion-audited; our check pending" for the bounded loop, the cofactor query-policy repair, the sparse engine and the completion vote | The first audit covers all four (Loop audit sections 2, 4 and 5; Biology audit section 4) | "independently audited", with that audit's verdicts and corrections |
| 7 | Paper 2 line 1035; Brief P2-A12 (line 278) | knowledge-keyed bar: "strongest evidence" (Paper 2) or "the closest available test of this reading" (Brief) | "say the bar is untested; present 85 to 99 and 66 to 101 as a support-prior result" (Theory audit issue 9) | "untested" (section 4, A14) |
| 8 | Paper 1 lines 220-222, 255-256; Paper 2 lines 833-834, 1971-1980, 2605-2607 | "adds no new reach"; "catches up at a large cap"; "only within the language's reach"; "not its asymptote" | Tautology or contradicted; "guidance changed which answers a fixed budget found, and at 20,000 the counts tied (327 against 329)"; 20,000 is not an asymptote (Theory audit issues 8 and 21; Order audit lines 103-108: 11 tasks still capped at 20,000) | The audit's sentence (section 4, B4 and B5) |
| 9 | Paper 2 lines 1998-2001, 2601-2603 | library learning "compresses what is already reachable"; "compression adds none" | Major FAIL: both compression and CORA's construction act on budgeted reach (Theory audit issue 1; Companion audit corrections table) | Claim no difference from DreamCoder, LILO or Stitch until a matched natural comparison exists (section 4, B14) |
| 10 | Paper 2 lines 807-817, 1092-1104, 1005-1019, 1165-1175, title line 57 | records proposition; Prediction 3; admission and reuse bounds; contract proposition; "forthcoming" theory packet; "Co-Induction" title | Records proposition empty as written (issue 2); Prediction 3 false as stated (issue 17); bounds omit selection among many candidates and the wider search (issues 6, 7); contract soundness mis-specified (issue 5); the packet exists ("Checked and correct", last bullet); title names an untested programme (issue 13) (all Theory audit) | Section 4, A12, C3, A16, A17, A11, D2; section 8 |
| 11 | Paper 2 lines 841-845 | the missing-input result "explains why inferring regulators helped (101 against 66)"; the counting bound "explains why choosing observations matters (320 against 291)" | Every exact recovery in the replication was a one-input rule, which the rule language without wiring could express (Biology audit sections 1 and 6), so 101 against 66 is a support prior (Theory audit issue 9); 320 against 291 compares two ways of choosing 20 observations, which tests the bound's consequence, not the bound | Pair the missing-input result with 0 of 274 and the shortlist losses, the bound with the design simulation (section 4, A9 and A10) |
| 12 | Writeup line 60; Paper 1 lines 136-137, 451 | "Availability and discovery moved" | On ARC-style tasks construction selected from a supplied space that contained the answers: discovery, not availability (Construction protocol lines 52-55; Loop audit section 3, correction 3; Theory audit issues 1 and 11) | "Discovery moved inside supplied spaces, and a larger gene-rule language raised coverage; selection is next" (section 4, B8) |
| 13 | Paper 1 lines 191-195 (found in this check, not in the audits) | Proposition 1 drops Paper 2's assumption that some program fits the demonstrations (Paper 2 line 880) | With no fitting program the conclusion is false | Repaired statement (section 8) |

## 3. Index of every theoretical claim

Proof status: proved, proved with a gap, sketched or conjectured (an empirical claim with no proof is listed as
conjectured). Result: supported, partly supported, contradicted or untested. Line numbers: W = Writeup, P1 = Paper 1,
P2 = Paper 2.

| # | Claim | Where | Proof status | Result |
|---|---|---|---|---|
| A1 | Many explanations: few demonstrations fit many programs | W 23; P1 191-195; P2 878-896 | proved (P1 drops an assumption) | supported |
| A2 | Build before you rank: solved at most generated at most expressible | W 23; P1 197-201; P2 848-857 | proved (accounting identity) | supported |
| A3 | Selection headroom corollary | P2 858-861 | proved | supported |
| A4 | Reachability: nothing correct within one action, so no one-step policy helps | P2 863-866 | proved | partly supported |
| A5 | A larger language can lower accuracy | P2 868-876 | sketched | untested |
| A6 | Verification establishes consistency, not intended correctness | P1 214-215, 269-270; P2 904-918 | proved | supported |
| A7 | Selective acceptance trades coverage for precision | P2 920-931 | proved | supported |
| A8 | Bigger language, more ambiguity (growth under all-agree acceptance) | W 23; P1 203-207; P2 933-952 | proved with a gap | untested |
| A9 | A missing input blocks exact recovery | W 23, 50; P1 209-211; P2 954-964 | proved | supported |
| A10 | Counting limit: m yes-or-no observations single out at most 2^m rules | P1 211; P2 966-983 | proved | supported (bound); partly (its consequence) |
| A11 | Sound contracts prune exactly | P2 1005-1019 | sketched (mis-specified) | partly supported |
| A12 | A failure record does not identify its cause | P2 807-817; W 13; P1 116-122 | proved but empty as written | untested |
| A13 | Value of an intervention; interventions are also experiments | P2 778-805 | definition inconsistent with its claim | untested |
| A14 | Knowledge-keyed acceptance bar | P2 1028-1046; W 52; P1 401-402 | conjectured | untested |
| A15 | Exact acceptance under noise; the bar as a count (proposed insertion) | Noisy theory section 9; Brief P2-B12 | proved (draft) | partly supported |
| A16 | Admission bound epsilon to the power v | P2 1095-1100 | sketched (wrong as stated) | untested |
| A17 | Reuse bound b to the power k-prime | P2 1101-1104 | sketched (omits wider search) | contradicted as stated |
| B1 | "Searching longer cannot help" | W 7; P1 72-73, 110-112 | proved only by definition | partly supported |
| B2 | "The failure itself can say what is missing" | W 7, 27; P1 73-75, 216-219, 227-238; P2 1614-1637 | conjectured | partly supported; not as worded |
| B3 | Construction reaches answers that equal-CPU static search does not | P1 219-220, 245; W 29 | conjectured | supported (exposed tasks) |
| B4 | A learned order changes which program is found first, not which exist | W 31; P1 220-222, 250-256; P2 1676-1730 | proved in part (complete search) | supported at a binding cap |
| B5 | "Guidance converted budget into answers only within reach" | P2 1971-1980; P1 256 | empty or empirical | contradicted as worded |
| B6 | Learned control in a fixed language can only reorder or remove | P2 1675-1677, 1745-1749 | proved | supported |
| B7 | Checked answers are usually right; coverage, not precision, limits CORA | W 33; P1 267-272 | conjectured | supported |
| B8 | Availability and discovery moved; selection is next | W 60; P1 136-137, 451-457 | interpretation | partly supported |
| B9 | The procedure moved; learned content did not | W 52; P1 395-397; P2 2377-2388 | conjectured | partly supported |
| B10 | Noisy domains need relational guards and a prior-weighted bar | W 52; P1 400-402; P2 2432-2443 | conjectured | untested |
| B11 | Routing by the diagnosed failure saves work | W 56; P1 451-457; P2 1641-1657 | conjectured | contradicted as evidence that diagnosis helps |
| B12 | Two rival rules name the discriminating intervention | W 50; P1 398-400; P2 2334-2341 | proved | untested experimentally |
| B13 | Fits generalize wrongly when the rule is outside the language | P2 1992-1996 | proved in a weaker form | supported (illustrations) |
| B14 | Compression does not extend reach; "compression adds none" | P2 1998-2001, 2601-2603 | conjectured | contradicted |
| B15 | Limits come in order: reach, search order, acceptance | P2 1982-1990 | interpretation | supported |
| B16 | What a record, a control or further data can identify | P2 714-728 | interpretation | partly supported |
| B17 | The binding limit is reach; proved for 754 of 842 training tasks in one grammar | P2 1480-1491 | proved (finite grammar) | supported (diagnosis) |
| B18 | Novelty: each link tested by removal | W 69; P1 485 | conjectured | partly supported |
| B19 | Learning enters twice: what the language contains, how it is searched | P1 179-183 | interpretation | supported |
| C1 | Prediction 1: execution gives constraints; sound pruning loses no correct program | P2 1085-1088 | sketched | supported (finite scope) |
| C2 | Prediction 2: acting on the failure report beats acting without it | P2 1089-1091 | conjectured | partly supported; contradicted for choosing revisions |
| C3 | Prediction 3: only a new capability raises coverage when nothing fits | P2 1092-1094 | false as stated | partly supported (budgeted reach) |
| C4 | Prediction 4: admission checks limit overfitting | P2 1095-1100 | sketched | partly supported |
| C5 | Prediction 5: reuse makes later synthesis cheaper | P2 1101-1104 | sketched | partly supported; contradicted in two dimensions |
| D1 | Conjecture: learned intervention choice | P2 1116-1121; W 60 | conjectured | untested |
| D2 | Conjecture: co-induction of representation and language | P2 1123-1127; title | conjectured | untested |
| D3 | Conjecture: transfer of procedure, not content | P2 1129-1133 | conjectured | untested as stated |
| D4 | Working hypotheses 1 to 4 | P2 2629-2639 | conjectured | as the paper states |
| D5 | Paradigm and open-problem hypotheses | P2 2525-2625, 2642-2801 | conjectured | untested |
| E1 to E6 | Framework definitions (section 4E) | various | definitions | not testable as claims |

## 4. Each claim in full

Each entry gives the statement, where it is, its proof status, the test, the result with its record and, for every
negative, the lesson and the direction it opens.

### 4A. Mathematical results and bounds

**A1. Many explanations (demonstrations underdetermine programs).**
- Statement: if some program fits the demonstrations, the language can return any allowed output when the input
  equals the query input and otherwise run any of its programs, and the query input differs from every demonstration
  input, then every allowed output is predicted at the query by some fitting program.
- Where: W line 23; P1 lines 191-195, 214-215; P2 lines 828-830, 878-896, table line 1148.
- Proof status: proved (P2 lines 887-889; Theory audit, "Checked and correct"). P1 omits "some program fits the
  demonstrations" (present in P2 line 880); without it the statement is false. In P2 since 6 November (git `2428b3e7`).
- Tests: (1) accept the top program that fits every demonstration, against the strict rule that also rebuilds without
  each demonstration, on 924 public ARC-style tasks (1,244 query outputs) scored once before; (2) count fitting but
  wrong functions on 595 published gene rules; (3) the same on 256 authored three-input Boolean functions.
- Result: supported. (1) 32 of 134 fitting answers were wrong; the strict rule removed 21 of the 32 and 31 right
  answers, keeping 71 of 82 right (Strict follow-up lines 40 and 42, and line 114; Registry rows 456, 457, 461). (2) 91 of
  524 programs that fitted all 40 observations were wrong functions, and at least 65 of the 91 predicted all four held
  inputs right (Sparse audit section 4). (3) 37 two-input rules fitted all seven shown rows but were wrong, in every
  condition (Loop audit section 2). The proposition assumes a very expressive language; these tests show rival fits
  in CORA's own bounded languages.

**A2. Build before you rank (nesting).**
- Statement: if attempts are drawn from the predictions a search retained within its budget, no selection rule,
  however learned, raises two-attempt accuracy above the share of tasks whose answer was retained, and that share
  cannot exceed the share whose answer the language can express.
- Where: W line 23; P1 lines 197-201, 215-216, 256; P2 lines 618-621, 831-834, 848-857, 1146, 1410-1411, 1676-1677.
- Proof status: proved; an accounting identity, immediate from the definitions, with no written proof (P2 line 855;
  Theory audit, "Checked and correct"). Expressibility is defined two ways (Theory audit issue 18; repair in section
  8). Stated 27 October (git `7417190d`), before the generated-task, held-back and search-order tests.
- Test: the best possible selection among the neural comparison entry's candidates on the 172 public evaluation query
  outputs (inspected during development), and a frozen contract-based selector over the same candidates.
- Result: supported. A right answer was among the candidates for 46 outputs and the entry chose it for 43, so any
  selection could add at most 3 (Headroom: `pool_has_correct` 46, `h_correct` 43, `headroom_queries` 3); the frozen
  selector changed 8 second attempts and gained 0, lost 0 (Selector score: `H` 43, `H2` 43, `gained` and `lost`
  empty, `changed_outputs` 8).

**A3. Selection headroom (corollary).**
- Statement: a change of selection rule alone adds at most coverage minus two-attempt accuracy.
- Where: P2 lines 858-861. Proof status: proved (immediate from A2).
- Test and result: as A2; supported (3 of 172).

**A4. Reachability.**
- Statement: if no program in the hypothesis memory or one action away from it is correct, no ranking of the memory
  and no one-step revision gives a correct answer in one step.
- Where: P2 lines 863-866, 1424-1431, 1986. Proof status: proved (immediate).
- Test: one-step reachability audit of 113 public evaluation puzzles (7 of 120 cut by a CPU guard).
- Result: partly supported. The condition held on all 113 (Reachability: `tasks` 113, every row `no_reach`,
  `tasks_with_any_correct_behaviour` 0), but the audit used the harness's edit menu, not the decision model's action
  menu (Theory audit issue 21). Lesson: statement and measurement use different action sets. Direction: state it for
  the harness's menu.

**A5. A larger language can lower accuracy.**
- Statement: if a larger language adds fitting programs that predict differently at the query and outrank the correct
  program, two-attempt accuracy can fall while coverage rises.
- Where: P2 lines 868-876, 1095-1097, table line 1147.
- Proof status: sketched; the one-task construction does not show coverage rising (it needs a second task), and the
  two outranking programs must predict two different wrong outputs (Theory audit issue 16). Stated 27 October (git
  `7417190d`).
- Test: none. The table's measured face, puzzle 97d7923e with 98 and 162 fits and none right, shows
  inexpressibility, not a loss caused by growth (Theory audit issue 16; P2 lines 692-697).
- Result: untested. In the held-back-half test adding a library or registry never lowered the correct total below
  the starting language on any benchmark (library 37 against 6 in all, 8 against 4, 2 against 2 and 27 against 0 by benchmark; reused operations 9 against
  4, 2 against 2 and 216 against 0; Held-back audit sections 2-3), but these are totals and the audited aggregate has no per-task rows
  (Unfinished B9). Lesson: no run isolated a loss caused by growth. Direction: compare starting-language and
  grown-language attempts task by task from saved rows (section 9).

**A6. Verification establishes consistency, not intended correctness.**
- Statement: two tasks that share demonstrations and a query input but intend different outputs are answered alike by
  any acceptance rule that reads only the demonstrations and the query, so if it answers it is wrong on one.
- Where: P2 lines 904-918, 1149, 1401-1404; P1 lines 214-215 (plain words) and 269-270 (measured face).
- Proof status: proved (P2 lines 912-913; Theory audit: correct for a deterministic rule). In P2 since 6 November.
- Test: give each task another task's demonstrations, keeping its own query, on the 1,244 outputs of three public
  ARC-style benchmarks (the entries' first run on them, 2 November).
- Result: supported. With its own demonstrations the CORA-only entry answered 382 outputs and 358 were right; with
  another task's it still answered 307, and 6 were right (ConceptARC 50 and 0, Mini-ARC 7 and 0, 1D-ARC 250 and 6)
  (Benchmarks run lines 44-45, 50-51, 56-57; Registry row 707).

**A7. Selective acceptance trades coverage for precision.**
- Statement: if a strict rule accepts a subset of a looser rule's answers, its coverage is no higher, and its
  precision is higher exactly when the removed answers are less precise than the looser set.
- Where: P2 lines 920-931, 1150, 1311.
- Proof status: proved (a weighted mean, P2 line 925). Added 6 November, after the measurement it describes (Theory
  audit issue 14), so it accounts for the result rather than predicting it.
- Test: strict acceptance against accepting every fitting program, same 1,244 outputs.
- Result: supported: precision 71 of 82 (0.866) against 102 of 134 (0.761); the 52 removed answers were 31 of 52 right
  (0.596) (Strict follow-up lines 40 and 42; Reproduction section 10). The gain belongs to the whole strict policy;
  leave-one-out alone was not significant (+0.087, Holm-adjusted p 0.176) (P2 lines 1367-1368; Theory audit issue 10).

**A8. Bigger language, more ambiguity (growth under all-agree acceptance).**
- Statement (P1): if an answer is given only when every fitting program agrees and the language grows, then on tasks
  the smaller language already fits, growth never adds or changes an answer, and turns an answer into an abstention
  exactly when it adds a fitting program that predicts differently.
- Where: W line 23; P1 lines 203-207, 222-223; P2 lines 835-838, 933-952, 1151, 2722-2723.
- Proof status: proved with a gap. If every fitting program of the smaller language returns nothing at the query, the
  larger language can add an answer, and CORA's search records such undefined predictions (Theory audit issue 4). The
  repaired statement in section 8 is proved by the same argument. Added 6 November.
- Test: none. P2's measured face, an imaging calibration in which 152 programs fitted the closing operator's
  demonstrations and all-agree acceptance admitted no edit (P2 lines 1388-1392), changes acceptance inside one fixed
  language (Theory audit issue 4). P1 lines 222-223 say the biology results test it: no biology run varied the
  language under all-agree acceptance, and the 433-rule study returns any fitting two-input rule unchanged and builds a
  larger rule only when none fits (Sparse audit section 6), which follows the proposition's consequence by design. The
  judge's suggested pairings (library 37 against 56; ConceptARC 9 against 27; Judge read line 41) compare grown
  languages with longer static search, not with the smaller language, and that study answered with the base search's
  two attempts, not all-agree acceptance (Held-back protocol amendment 2, lines 21-24).
- Result: untested. Lesson: all-agree acceptance and language growth were never varied together. Direction: the run
  in section 9.

**A9. A missing input blocks exact recovery (omitted essential input).**
- Statement: if the intended rule depends on an input v (two inputs that differ only in v get different values) and
  every candidate ignores v, no candidate equals the rule, and none fits demonstrations that contain such a pair,
  however good the search.
- Where: W lines 23 and 50; P1 lines 209-211, 384-385; P2 lines 839-842, 954-964, 1152, 1979-1980, 2121-2122.
- Proof status: proved (P2 line 959; Theory audit). In P2 since 6 November; the 433-rule test ran on 7 November (Sparse
  audit section 3), after it.
- Tests: (1) rules reading at most two inputs, on 595 published gene rules (reused cohort; simulated observations), 274
  of which have three or more essential inputs; (2) the same rule language in the observation-choice study; (3)
  regulator shortlists chosen from ten demonstrations; (4) the authored A, B, C, Y case.
- Result: supported (each instance holds by necessity, so the tests show where the losses sit rather than putting the
  proposition at risk). (1) 0 of 274 at 40 and at 60 observations; conditional construction, which reads up to four
  inputs, recovered 112 of them (81 of 90 three-input, 31 of 184 four-or-more), and a classical learner given the same
  observations tied at 433 (Sparse audit section 6). (2) 0 of 274 in every condition (Biology audit section 4). (3) An
  essential regulator lay outside the eight-variable shortlist for 59 of 182 source tasks and 176 of 356 prospective
  tasks, so no candidate could be right (Shortlist review lines 234-236). (4) 0 of 16 two-input rules fit the five
  observations and 8 of 256 three-input rules do (Toy case line 132; Toy check lines 51-53).
- Pairing to drop: P2 line 842 says it "explains why inferring regulators helped in biology (101 against 66 of 595)";
  see section 2, item 11.

**A10. Counting limit (bounded information).**
- Statement: from m yes-or-no observations, chosen in advance or one after another, at most 2^m rules of a class can be
  left as the only consistent rule; singling out every rule needs m at least log2 of the class size.
- Where: P1 line 211; P2 lines 843-845, 966-983, 1153, 2742-2750.
- Proof status: proved (decision tree, adaptive choice included; P2 lines 972-973; Theory audit, which recomputed
  log2 C(20,3) = 10.155 and 1,024 of 388,656 = 0.263%). Credit Angluin 1988 and Akutsu et al. 1999, Theorem 3 (Theory
  audit issue 21). In P2 since 6 November.
- Tests: a design simulation on invented random rules (a simulation, not biology evidence); observation choice on 595
  published gene rules.
- Result: supported for the bound, partly supported for its consequence that chosen evidence beats random evidence.
  No design exceeded the bound: with 10 variables and 10 transitions at most 3% of three-input rules were singled out
  (bound 3.9%); with 60 variables and 20 transitions at most 13% (bound 14.1%) (Design simulation line 7; Theory
  audit). Above the floor, states chosen where the surviving rules disagree singled out 97% of three-input rules
  against 8% for random states at 15 transitions (Design simulation line 7). On gene rules, 20 chosen observations gave
  320 exact rules against 291 for uniform choice, all of the gain on two-input rules (155 against 126 of 156), with
  held-input accuracy lower (1,586 against 1,747 of 2,380) (Biology audit section 4); in the later study the two-input
  language on chosen and on uniform observations tied at 40 (321 against 321) (Sparse audit section 5). Lesson: choice
  helps where identification, not the bound, limits recovery. Direction: count the floor before choosing a budget.

**A11. Sound contracts prune exactly.**
- Statement: if every operator's forward contract is sound on a scope and every grid the search meets lies in it,
  pruning returns exactly the fitting programs of exact execution and never executes more programs.
- Where: P2 lines 446, 1005-1019, 1154, 2003-2006.
- Proof status: sketched ("immediate from soundness", P2 line 1013); soundness is defined on concrete grids while the
  code prunes against summaries of all completions over merged abstract states, and the completion and 64-fit cap
  conditions are missing (Theory audit issue 5). Stated 2 November (git `e06d4834`).
- Test: finite-scope soundness checks (every grid up to 3 by 3 over three colours, every 4 by 4 over two, random
  abstract and structured grids up to 20 by 20) and a lost-correct audit.
- Result: partly supported: no fitting behaviour was lost on the tasks run, with 44,485 instead of 1,269,443
  executions and budget stops 32 to 0 at depth 2 (Contracts report lines 1-7 and 44-61). This is finite-model
  validation, not a proof for arbitrary grids (Contracts report lines 98-101). Lesson: the statement and the code
  differ. Direction: restate soundness for abstract inputs and add the completion and cap conditions (Theory audit
  issue 5).

**A12. A failure record does not identify its cause.**
- Statement: if two failure hypotheses give the same distribution of records, every policy that reads only the record
  acts the same under both; only an intervention whose records differ can separate them.
- Where: P2 lines 807-817, 1155; illustrated in W line 13 and P1 lines 116-122.
- Proof status: proved as written but empty: the record is a deterministic function of the system and the
  demonstrations, so the condition always holds for a fixed task, and acquiring evidence changes the demonstrations,
  which the statement cannot express (Theory audit issue 2). Added 6 November.
- Test: none. The worked case (five states of CORA, one public task, four causes) shows four different systems, not
  one system under two hypotheses (Theory audit issue 2), and the task was inspected while building (P1 lines
  121-122).
- Result: untested. Lesson: as stated it cannot be tested. Direction: restate it over task distributions given a set
  of causes, with observations after an action including new evidence (Theory audit issue 2), then test with
  planted-cause tasks.

**A13. Value of an intervention, and interventions as experiments.**
- Statement: a policy holding a belief over failure causes can choose the intervention with the largest expected gain
  in correct answers, less priced wrong answers and cost; many interventions also carry information value.
- Where: P2 lines 778-805.
- Proof status: a definition plus a claim that the formula does not carry: it has no information-value term, so a
  purely diagnostic action scores below zero and would never be chosen (Theory audit issue 3).
- Test: none; no policy was trained (Loop audit section 6).
- Result: untested. Lesson: the formula and its prose disagree. Direction: add an expected value-of-information term,
  or state that the myopic rule undervalues diagnostics (Theory audit issue 3).

**A14. Knowledge-keyed acceptance bar.**
- Statement: accept a revision only when its log-likelihood ratio over the current explanation exceeds a threshold
  plus the log prior odds against it.
- Where: P2 lines 1028-1046, 1405-1406, 2732-2739; W line 52 and P1 lines 401-402 ("an acceptance bar that weighs a
  prior").
- Proof status: conjectured (a proposed criterion).
- Test: none separated the bar from the prior. Inferred wiring is a prior built from the same demonstrations, supplied
  wiring is the target's own published support, and for exact fits the likelihood ratio is 1 or infinite, so the bar
  reduces to a prior threshold (Theory audit issue 9).
- Result: untested; 85 to 99 of 333 and 66 to 101 of 595 are support-prior results (Theory audit issue 9; Biology audit
  section 1). Lesson: the bar was never varied with the prior fixed. Direction: vary the bar with the prior fixed and
  the prior with the bar fixed (P2 lines 2734-2735).

**A15. Exact acceptance under noise, and the bar as a count (proposed insertion; not yet in Paper 2).**
- Statement: (i) a zero-error check passes the true rule with probability at most (1 - epsilon)^n when each of n
  observations disagrees with it with probability at least epsilon; (ii) under a symmetric class-noise model the
  likelihood bar admits a revision exactly when its net corrections reach a fixed count; (iii) no revision passes for a
  unit on which the current rule makes fewer errors than that count.
- Where: Noisy theory section 9; Brief P2-B12 (lines 472-477) and P1-B2 (line 655, "proved in the full paper"). Paper 2
  has no such proposition yet (`grep -c noisybar` gives 0).
- Proof status: proved in the draft (Noisy theory section 9); the count is checked: (log 20 + log 48) / log 8 = 3.30,
  so 4 net corrections (Brief line 475; Biology audit section 5).
- Test: the Perturb-seq follow-up (64 readout genes, 255 held perturbations).
- Result: partly supported: 0 of 64 rules admitted, and even on training data no candidate gained more than one net
  correction against the four required (Biology audit section 5). Whether too few correctable events existed, the
  floor of part (iii), was not counted (Brief P2-A10, line 203). Lesson: the bar is a count, and the data may hold fewer
  events than the count. Direction: count per-gene correctable events among the 243 admission perturbations on
  training data before any run (section 9). Paper 1 cannot say "proved in the full paper" until the insertion is made.

**A16. Admission bound.**
- Statement (inside Prediction 4): if chance fits on v validation tasks were independent, each with probability at
  most epsilon, a spurious operation would pass with probability at most epsilon^v.
- Where: P2 lines 1095-1100.
- Proof status: sketched for one pre-specified operation; wrong for a constructor choosing among up to 211 structures,
  where a union bound gives 211 times epsilon^v, which is 2.11 at epsilon 0.1 and v = 2, no bound (Theory audit issue
  6; Reproduction section 10).
- Test: none of the bound (C4 covers the prediction).
- Result: untested, and wrong as stated. Lesson: choosing among many candidates multiplies chance passes. Direction:
  state the bound over the family, or validate on tasks held out after selection (Theory audit issue 6).

**A17. Reuse bound.**
- Statement (inside Prediction 5): a program of cost k shortened to k-prime by a new operation needs about b^k-prime
  rather than b^k candidates.
- Where: P2 lines 1101-1104.
- Proof status: sketched; it omits that new operations widen the branching factor (Theory audit issue 7).
- Test: the learned library on the 120 public evaluation tasks.
- Result: contradicted as stated where the operations do not apply: predictions were identical in all six conditions
  (3 of 172 right), while execution-budget stops rose from 9 without the library to 43 with it (P2 lines 1911-1912 and
  3265). Lesson: reuse has a search cost (the utility problem). Direction: compare (b + delta b)^k-prime with b^k, with
  9 against 43 as the measured face (Theory audit issue 7).

### 4B. Mechanism and empirical claims stated as theory

**B1. "When the language lacks an operation a task needs, searching longer cannot help."**
- Where: W line 7; P1 lines 72-73, 110-112.
- Proof status: true by definition when "lacks" means no program of the language gives the answer (a case of A2);
  otherwise an empirical claim.
- Test: 95 generated tasks built by removing one operation from the starting language.
- Result: partly supported. Longer static search of the starting language still solved 38 of the 95, with 8.47
  CPU-hours against 2.61 for all three construction repeats (Construction progress lines 277-285); the starting
  language can rebuild 6 of the 11 removed operations, some only at one parameter value, at cost levels 10 to 14
  (Construction protocol lines 163-176); the binding audit calls "an operation is missing" a budget-limited hypothesis
  (Loop audit section 3). Lesson: removing an operation did not always remove the answer. Direction: write "often
  cannot help" with the 38 beside it (Cold read line 201).

**B2. "The failure itself can say what is missing" (the thesis).**
- Where: W lines 7, 21, 27, 35-38; P1 lines 73-75, 112-114, 132-133, 216-219, 227-238, 288-289; P2 lines 78-79,
  1499-1502, 1614-1637, 1666-1668.
- Proof status: conjectured (an empirical mechanism claim).
- Test: the pre-registered construction study at scale: 95 generated tasks from public training inputs in three
  constructed worlds, each missing one operation of a declared space of 211 structures; three seeded repeats.
- Result: partly supported; not supported as worded.
  - The task's own typed holes recovered 64 in all three repeats; the demonstrations taken as they are (the identity
    hole) recovered 48, all inside the 64, so undoing a starting-language operation added 16 tasks and lost none
    (Construction analysis `descriptive.counts`; its contrast named `S-hole vs S-demo (majority)`, own holes against demonstrations alone: 48 both,
    16 only own holes, 0 only demonstrations; Loop audit section 3).
  - All 16 of those gains lie in the two worlds without cross-family composition (own holes 44 against 28 there; 20
    and 20 in the third world) (Construction analysis `descriptive.by_world`).
  - Another task's holes recovered 16, all in the one world whose four removed symmetries compose into one another, as
    the protocol expected (Construction protocol lines 186-198); in the other two worlds they recovered 0 of 59, against
    44 for the task's own holes (Construction analysis `descriptive.by_world`).
  - Static search of the starting language recovered 38 with 3.2 times the CPU; blind enumeration of the same 211
    structures 3 in every repeat, 32 in at least two and 74 in some (Construction analysis `descriptive.counts`;
    Construction progress lines 277-285). In the first world blind enumeration, by the at-least-two rule, recovered 26
    against 23 for own holes while charging about three times the CPU per run (`by_world`; `cpu_accounting`: 141.15
    against 43.61 charged CPU-seconds).
  - What the code does: holes are computed from the demonstrations, directly or after undoing one invertible
    starting-language operation; the closest failed program, its residue and the shape relation are recorded but
    unused (Loop audit section 3; P2 line 1530 says the same).
  - Where no invertible operation was left (list functions), the hole equalled the demonstrations alone, 5 and 5 of 9
    (List-function report lines 124-127).
  - Lesson: the demonstrations, read through an invertible operation, say what is missing; the failure says when to
    look. Direction: test features taken from the failed search itself against the demonstrations-only hole (Brief
    P2-B7), in a space too large for blind enumeration (P2 lines 1669-1671).

**B3. Construction reaches answers that static search at the same CPU does not (P1: "more search in the original
language cannot supply a missing operation").**
- Where: P1 lines 219-220, 245, 294; W line 29.
- Proof status: "cannot" holds only for expressibility (A2); as measured it is an empirical claim.
- Test: the pre-registered held-back-half test: 464 held tasks of ConceptARC, Mini-ARC and 1D-ARC (624 query outputs),
  held out from development but scored once before.
- Result: supported at matched CPU on exposed related tasks: the construction condition answered 343; static search
  with construction's CPU allowance 118; construction on another task's demonstrations 10; on the two-dimensional
  benchmarks 57 against 30 of 315 (Held-back audit sections 2 and 3). The construction condition first searches the
  starting language plus the reused operations and builds only when that fails (Held-back protocol amendment 2, lines
  21-27), so its 343 starts from the search that answered 227. Not shown: that the starting language cannot express
  these answers (section 9).

**B4. A learned order changes which program is found first, not which programs exist.**
- Where: W line 31; P1 lines 220-222, 250-256, 298-300; P2 lines 833-834, 1676-1730, 2605-2607.
- Proof status: the "not which exist" half follows from A2 for complete search; the cap results are empirical.
- Test: the pre-registered held run: learned guide against the hand-set order on 464 held tasks (624 outputs) at caps
  of 125, 500, 2,000 and 20,000 counted operations per hole.
- Result: supported at a binding cap: 320 against 234 at 500 (87 tasks gained, 1 lost); a frequency table 318 and a
  linear model 323 were inconclusive against the guide; at 20,000, 327 against 329 (4 against 3 discordant tasks)
  (Order audit lines 80-108; P2 table at lines 1691-1704). Two of three pre-registered predictions were refuted: at
  20,000, 11 held tasks still had different attempts, each with a capped hole, and on ARC-AGI-2 at 500 the hand-set
  order solved a task the guide did not (Order audit lines 103-108; Order protocol lines 221-229). Lesson: 20,000 is not
  an asymptote, so "no new reach" holds only as a count (Theory audit issue 21). Direction: report each cap's counts
  and the capped tasks.

**B5. "Guidance has converted budget into answers only within reach."**
- Where: P2 lines 1971-1980; P1 line 256 ("adds no new reach").
- Proof status: empty if reach means expressibility; empirical if it means what static search finds.
- Result: contradicted as worded in the second reading: the guide at 500 found 4 tasks the hand-set order missed at
  20,000 (Theory audit issue 8; P2 lines 1718-1720). Lesson: "reach" named two things. Direction: "guidance changed
  which answers a fixed budget found, and at 20,000 the counts tied (327 against 329)" (Theory audit issue 8).

**B6. Learned control inside a fixed language can only reorder or remove, and removing only loses.**
- Where: P2 lines 1675-1677, 1745-1749, 1777-1780. Proof status: proved for a fixed language and budget (a case of A2).
- Test: a learned failure controller that could only prune, against static search, in controlled pilots.
- Result: supported: 33 of 128 grid queries against 87 for static search, and 14 of 128 graph queries against 72 (P2
  lines 1745-1747).

**B7. Checked answers are usually right; coverage, not precision, limits CORA.**
- Where: W line 33; P1 lines 267-272, 442. Proof status: conjectured (empirical).
- Test: the scored CORA-only system on three public ARC-style benchmarks and on the public evaluation set.
- Result: supported: right on 295 of 308, 19 of 20 and 44 of 54 answered outputs, and 3 of 172 public evaluation outputs
  answered, all right (Benchmarks run lines 44, 50, 56; P2 lines 1348-1352). Exposed data; the public evaluation set
  was inspected during development.

**B8. "Availability and discovery moved; selection is next."**
- Where: W line 60; P1 lines 136-137, 451-457; P2 lines 1960-1969. Proof status: interpretation.
- Result: partly supported. Selection: no completed result shows a learned or failure-conditioned choice beating a
  strong fixed alternative (Companion audit, cross-cutting finding 8; Loop audit section 6). Discovery: supported (B2
  to B4). Availability: on ARC-style tasks construction selected from a supplied space that contained the answers
  (Construction protocol lines 52-55; Theory audit issues 1 and 11); in gene rules a larger rule language did raise
  executable coverage, 433 against 321 of 595, tied by a classical learner (Sparse audit sections 1 and 6). Lesson and
  direction: section 2, item 12.

**B9. "The procedure moved; learned content did not."**
- Where: W lines 48, 52; P1 lines 321-325, 395-397, 440; P2 lines 1129-1138, 2377-2388. Proof status: conjectured.
- Tests: an order counted from 22 Boolean witnesses in ARC training demonstrations, applied to 595 gene rules; the
  provenance of the gene studies' code.
- Result: partly supported. Content: 177 exact rules against 168 for plain index order, 182 for the same counts
  reassigned at random and 194 for a hand-set simplicity order (0 gained and 5 lost against the reassigned counts; 3
  gained and 20 lost against the simplicity order); no contrast survived Holm correction (Companion audit row 11;
  Biology audit section 2). Procedure: the gene results came from a rule-reconstruction procedure written for biology
  that reuses CORA's verify-or-abstain design but none of the entries' code (Biology audit section 0 and section 1,
  correction 2). Lesson: puzzle-learned content did not help gene rules even with a shared binary alphabet (Theory
  audit issue 20). Direction: learn priors inside each domain; test transfer of a revision policy (D3).

**B10. Noisy domains need relational guards and a prior-weighted acceptance bar.**
- Where: W line 52; P1 lines 400-402, 441; P2 lines 2432-2443. Proof status: conjectured (stated as a hypothesis).
- Tests: three frozen follow-ups on previously used data.
- Result: untested as a hypothesis; the follow-ups were not designed to test it (Brief P2-B14, lines 493-497). Spatial:
  on one donor a neighbour check alone, a predeclared secondary, gave 36 corrections against 12 harms, with no matched
  shuffled control, while the primary failed its gate; Perturb-seq: no rule admitted, a null without sensitivity (A15);
  cell images: an out-of-memory error and no result (Biology audit section 5). Lesson: none of the three could separate
  the hypothesis from simpler causes. Direction: count informative events first, and repeat the neighbour check on a
  second donor with a matched shuffle (Brief P1-A13).

**B11. Routing by the diagnosed failure saves work (bounded diagnosis loop).**
- Where: W line 56; P1 lines 302-303, 439, 451-457, 561; P2 lines 359, 1641-1657, 1965-1966. Proof status: conjectured.
- Test: all 256 authored three-input Boolean functions (not ARC), each among eight inputs with seven of its eight
  truth-table rows shown.
- Result: contradicted as evidence that diagnosis helps. The fixed controller and a fixed build-then-ask schedule both
  recovered 219 (0 gains, 0 losses): 38 two-input rules accepted at once and 181 three-input tables built after buying
  the one unseen row; 38 is all the two-input language can express. The 12.89% work saving is entirely the schedule's
  one failed build attempt before asking; misleading routing features cost 46 functions (Loop audit section 2).
  Lesson: the gain came from the supplied larger language and one bought label per built function. Direction: the
  causal routing test at a budget that binds, against shuffled and failure-blind routing at equal cost (Brief P2-A3;
  Unfinished A3).

**B12. Two rival rules that fit every observation name the experiment that separates them.**
- Where: W line 50; P1 lines 384-385, 398-400; P2 lines 2334-2341.
- Proof status: proved (two different rules disagree on some input state); the authored case was checked by
  enumeration: 8 three-input rules fit its five observations (Toy case lines 92 and 132).
- Test: none; no intervention or laboratory test has been run (Brief P1-A11, lines 613-615).
- Result: untested experimentally. Lesson: observation alone cannot show that C drives Y rather than something that
  varied with C (Brief P2-A8). Direction: set C by intervention at A = 0, B = 1, where the rules disagree.

**B13. Programs that fit the demonstrations generalize wrongly when the rule is outside the language.**
- Where: P2 lines 1992-1996. Proof status: proved in the weaker form "every fit is wrong on some input"; being wrong at
  the query is not entailed.
- Result: supported by counterexamples: 3 of 11 unfiltered sealed answers, 7 of 7 companion symbolic candidates and 22
  of 33 nuclei deletions fitted and were wrong (P2 lines 1373-1383).

**B14. Compression does not extend search reach; "compression adds none".**
- Where: P2 lines 1998-2001, 2601-2603. Proof status: conjectured.
- Result: contradicted as worded (Theory audit issue 1, major; Companion audit corrections table). DreamCoder's
  held-out ablations solve at most 60% of held-out tasks against nearly 100% with compression, and CORA's own
  construction acts on budgeted reach as compression does: blind enumeration recovered 10 of 11 construction-test tasks,
  and trim and upscale are compositions of the starting language (Theory audit issue 1). CORA's own compression
  shortened programs from a median of 28 nodes to 27 with no reach gain, one test (P2 lines 1998-2000). Lesson:
  expressibility and budgeted reach were conflated. Direction: claim no difference from DreamCoder, LILO or Stitch
  until a matched natural held-task comparison exists (Unfinished C4).

**B15. Limits come in order: reach, then search order, then acceptance.**
- Where: P2 lines 364, 1982-1990. Proof status: interpretation (P2 labels it a supported interpretation).
- Result: supported on exposed or constructed data: no fitting program for 113 audited puzzles (A4); 320 against 234 at
  a binding cap (B4); strict acceptance 71 of 82 against 102 of 134 (A7).

**B16. What a record, a control or further data can identify.**
- Where: P2 lines 714-728. Proof status: interpretation.
- Result: partly supported. Its example "a missing operation (construction that succeeds where matched search fails)"
  misidentifies trim and upscale, which the starting language reaches as compositions (Theory audit issue 21;
  Construction protocol lines 163-176).

**B17. The binding limit is reach; for one explicit grammar it is proved for 754 of 842 training tasks.**
- Where: P2 lines 1480-1491, 1979. Proof status: proved for a finite, frozen, one-step language (Theory audit, "Checked
  and correct").
- Result: supported as a diagnosis of that language on training tasks, not accuracy. "A search reaching programs of
  about 29 nodes" treats reference length, an upper bound, as a requirement (Theory audit issue 21).

**B18. Novelty: each link tested by removal.**
- Where: W line 69; P1 line 485. Proof status: conjectured.
- Result: partly supported. The specification was removed (another task's holes 16 of 95; another task's
  demonstrations 10 of 624) and reuse was removed (shuffled registry 6 of 624) (P1 line 485; Held-back audit section 2,
  S3 and S9); checked admission has no removal test (Cold read line 208). The construction claim is graded incremental,
  with the shuffled-specification control as its new element (Theory audit, novelty table).

**B19. Learning enters twice: what the language contains and how it is searched.**
- Where: P1 lines 179-183. Proof status: interpretation.
- Result: supported descriptively: 11 capabilities were admitted by automatic gates, each a selection from the supplied
  space (Loop audit section 7); the learned order (B4).

### 4C. Predictions (P2 lines 1080-1110)

**C1. Prediction 1: execution gives observable constraints; sound pruning loses no correct program.** P2 lines
1085-1088. Sketched. Supported on the finite scope only (A11).

**C2. Prediction 2: acting on the failure report beats acting without it at equal compute; falsified if
failure-blind proposals, or another task's report, do as well.** P2 lines 1089-1091, 1106-1110. Conjectured.
- Tests and results: neural inventor, own report 2 against 2 for failure-blind invention of 11 tasks (P2 lines
  1513-1514); symbolic constructor, own specification 8 of 11 against 0 for another task's (exact p 0.0078 treats 11
  dependent tasks as independent; at family level 4 of 4, p 0.125) and 8 against 4 for the demonstrations alone, p
  0.125 (P2 lines 1557-1565; Theory audit issue 11); at scale, B2; bounded loop, B11 (tie); on 288 synthetic groups,
  adding failure evidence changed the share of correct repair choices by -0.6 points (interval -2.6 to +1.4) (Selection
  tests, first file, lines 96-98); in a 27-task repair study the authentic, failure-blind and shuffled conditions each
  reached 7 correct, 3 gains each (Selection tests, second file, lines 19-24).
- Result: partly supported for construction (the task's own demonstrations matter); contradicted for failure reports
  as a guide to which revision to make. Lesson: a failure descriptor helps only if it carries information the
  demonstrations lack (Brief P2-B7). Direction: features taken from the failed search itself.

**C3. Prediction 3: when nothing in memory or k actions from it fits, only a new operation, relation or representation
can raise coverage.** P2 lines 1092-1094.
- Proof status: false as stated, since more search could also raise coverage (Theory audit issue 17).
- Tests and results: 11-task test, specification 8 against matched search 5 (p 0.375) and blind enumeration 10 in some
  seed at five times the compute (P2 lines 1557-1572); at scale 64 against 38 (B2); held-back 343 against 118 (B3).
- Result: partly supported, as budgeted reach at equal or lower CPU. Lesson: in a small declared space blind search
  reaches the same answers with more CPU. Direction: spaces too large for blind enumeration (P2 lines 1669-1671).

**C4. Prediction 4: admission checks limit overfitting.** P2 lines 1095-1100. Sketched.
- Result: partly supported. Promoted operations broke none of 14 solved tasks and none was rolled back (P2 lines 1516,
  1572); the grown grammar recovered 51 of 60 excluded tasks of the same families against 28 for static search,
  descriptive because its pre-registered condition failed, and 23 against 28 in other families (Construction progress
  lines 277-281; Loop audit section 3). The bound itself is wrong as stated (A16).

**C5. Prediction 5: reuse makes later synthesis cheaper; falsified if promoted operations do not solve later tasks
that need them at the base budget.** P2 lines 1101-1104, 2777-2778. Sketched.
- Result: partly supported in one dimension, contradicted elsewhere. Reused operations answered 227 against 118 for
  static search, 216 against 88 on 1D-ARC and 9 against 27 on ConceptARC (Held-back audit section 3); a whole-program
  library lost to its static comparator, 37 against 56 (Held-back audit section 2, S1); a frozen learned library
  changed no prediction on 924 public ARC-style tasks or on the public evaluation (P2 lines 1908-1910). Lesson:
  one-dimensional operations rarely fit two-dimensional tasks. Direction: reuse only after a check on another family
  (P1 line 436).

### 4D. Conjectures and hypotheses

**D1. Learned intervention choice.** P2 lines 1116-1121, 2565-2568, 2793-2801; W line 60 and P1 lines 459-468 (as a
direction). Conjectured. Untested: the causal follow-up exists only as a reviewed draft and no completed test of
learned or failure-conditioned choice exists (Unfinished A3, A4). Related results: the learned revision ranker lost to
streaming static search, 8 against 12 of 16 held grid tasks (P2 lines 1742-1743); learned action selection equalled
every control at 111 of 128 while a whole-vector shuffled order found 118 (P2 lines 1974-1976); the bounded loop tied
(B11). Lesson: every revision so far was chosen by people or fixed rules (Loop audit section 6). Direction: the
decisive test (P2 lines 2795-2800; Brief P2-A3). P2 line 2661 still says that test "is running"; it has not run (Brief
rule 3; Unfinished A3).

**D2. Co-induction of representation and language.** P2 lines 1123-1127, 2532-2543; title line 57. Conjectured.
Untested. Related: one researcher-diagnosed extension fitted 18 training tasks against 17 for the base language and 17
for a random extension of the same size, so its pre-declared criterion failed (Registry row 507; P2 line 3266); a fixed
hand-written view score solved 3 of 9 authored cases against 9 of 9 for the full view bank (Companion audit rows 5-6).
The title names this conjecture as the result (Theory audit issue 13). Lesson: the conjecture must say whether
researcher-diagnosed changes count; if they do, 18 against 17 is a failed instance (Theory audit issue 21). Direction:
failure-chosen representation changes against random changes of the same size at matched work (P2 lines 2711-2717).

**D3. Transfer of procedure, not content.** P2 lines 1129-1133, 2781-2791. Conjectured. Untested as stated, since no
revision policy was learned; the content half is B9 (did not help), and the procedure was reimplemented, not
transferred (B9).

**D4. Working hypotheses 1 to 4.** P2 lines 2629-2639. Statuses as the paper gives them, which the records support:
1 open (no policy trained); 2 open (inventor 2 against 2; the ranker matched by blind and shuffled conditions; list
functions 4 of 9 against 1, smallest attainable p 0.25); 3 consistent with the evidence as a measurement (113 puzzles;
29 of 46 sampled failures); 4 design in place, policy absent.

**D5. Paradigm and open-problem hypotheses.** P2 lines 2525-2625, 2642-2801. Stated as untested hypotheses with
falsifiers (P2 lines 2646-2647); untested. Two carry evidence: the library-learning contrast is contradicted (B14), and
"guidance moves the left part of the budget curve, not its asymptote" is partly supported, since it follows from
complete enumeration and 20,000 operations is not an asymptote (Theory audit issue 21; B4).

### 4E. Framework definitions (not testable as claims)

| # | Definition | Where |
|---|---|---|
| E1 | Three requirements: availability, discovery, selection | W 23; P1 134-137; P2 1048-1055 |
| E2 | Decision model: system, failure record, interventions, value (does not fit its own example: Theory audit issue 2) | P2 765-805 |
| E3 | Eight failure types, each with measured cases | P2 605-674 |
| E4 | Decision rule: which claim a result supports (row 3 updated by Brief P2-B3) | P2 1057-1078 |
| E5 | Transfer means the pipeline carries over through an adapter (the author's definition, Biology audit section 0) | W 48; P1 321-323 |
| E6 | Three levels of validity: computational, predictive, mechanistic | P1 397-399; P2 2334 |

## 5. Deliverable 1: compact table for Paper 1 (8 rows)

Markdown mirror with sources (the sources are for the paper's registry, not for print):

| # | Result | Test | Measured | Reading | Sources |
|---|---|---|---|---|---|
| 1 | Many explanations | fit-only against strict acceptance, 1,244 previously scored outputs; another task's demonstrations | 32 of 134 fitting answers wrong; strict rule removed 21 wrong and 31 right; with another task's demonstrations 307 answered, 6 right | supported | Strict follow-up lines 40, 42 and 114; Benchmarks run lines 44-57 |
| 2 | Build before you rank | best selection among the neural comparison entry's candidates, 172 outputs | right answer present for 46, chosen for 43, so at most 3 to gain; frozen selector 0 gained, 0 lost | supported | Headroom; Selector score |
| 3 | Bigger language, more ambiguity | none run | fixed-language illustration only: 152 fitting programs, no edit admitted | untested | P2 lines 1388-1392; Theory audit issue 4 |
| 4 | A missing input blocks exact recovery | two-input rules on 595 published gene rules, 40 observations | 0 of 274 rules with three or more essential inputs; conditional construction 112 of them; classical learner tied at 433 | supported | Sparse audit section 6 |
| 5 | Counting limit | design simulation, invented rules | at most 3% singled out at 10 observations (bound 3.9%); 97% against 8% at 15 | supported | Design simulation line 7; Theory audit |
| 6 | The typed hole gives an exact target | 95 generated tasks, declared space of 211 structures | own holes 64; demonstrations alone 48; another task's holes 16 (0 of 59 outside one world); static search 38 with 3.2 times the CPU; blind enumeration 3 (74 in some repeat) | supported on generated tasks | Construction analysis; Construction progress lines 277-285 |
| 7 | Construction finds what equal-CPU search does not | 464 held-back tasks, 624 outputs, previously scored | 343 against 118; another task's demonstrations 10; two dimensions 57 against 30 of 315 | supported, exposed tasks | Held-back audit sections 2-3 |
| 8 | A learned order changes what a capped search finds | learned against hand-set order, four caps | 320 against 234 at 500; 327 against 329 at 20,000; frequency 318, linear 323 | supported at a binding cap | Order audit lines 80-108 |

Paste-ready LaTeX for Paper 1 (column types `P` and `Y` and all labels exist in Paper 1 lines 50, 186, 191-209, 226).
It assumes the repaired Proposition 3 of section 8. Place it after the four propositions, replacing the "Three tested
sentences" prose (P1 lines 216-223) together with the paragraph of section 7; if the 15-page main-text limit binds
(Brief section 2), shorten the Theory row of the criteria table instead.

```latex
\begin{table}[t]
\centering\footnotesize
\renewcommand{\arraystretch}{1.08}
\begin{tabularx}{\linewidth}{@{}P{3.0cm}P{3.6cm}YP{1.6cm}@{}}
\toprule
result & test & measured & reading \\
\midrule
Many explanations (Proposition~\ref{prop:under}) & answer whenever a program fits every demonstration, or also
require the strict rule's rebuilds without each demonstration, on 1,244 query outputs of three public ARC-style
benchmarks scored once before & 32 of the 134 answers from fitting programs were wrong; the strict rule removed 21 of
those 32 and 31 right answers. In the first run on these benchmarks, given another task's demonstrations, the
CORA-only entry still answered 307 of the 1,244, and 6 were right & supported \\
Build before you rank (Proposition~\ref{prop:nest}) & the best possible choice among the neural comparison entry's
candidates, 172 public evaluation query outputs (inspected during development) & a right answer was among the
candidates for 46 and chosen for 43, so any ranking could add at most 3; a frozen ranking by CORA's contracts added 0
and lost 0 & supported \\
Bigger language, more ambiguity (Proposition~\ref{prop:unanimity}) & not yet run: grow a language under all-agree
acceptance and count, on tasks the smaller language fits, answers turned into abstentions & no test; in one fixed
imaging language, 152 programs fitted an operator's demonstrations and all-agree acceptance admitted no edit (an
illustration) & untested \\
A missing input blocks exact recovery (Proposition~\ref{prop:essential}, first part) & rules reading at most two
inputs, on 595 published gene rules with 40 simulated observations each (reused cohort; simulations) & 0 of the 274
rules with three or more essential inputs; conditional construction, which reads up to four, recovered 112 of them
(81 of 90 three-input); a classical learner given the same observations also reached 433 & supported \\
Counting limit (Proposition~\ref{prop:essential}, second part) & designs of observations for invented random rules
over 10 variables (a simulation, not biology) & with 10 observations no design singled out more than 3\% of
three-input rules (the bound allows 3.9\%); with 15, observations chosen where the surviving rules disagree singled
out 97\%, random ones 8\% & supported \\
A typed hole gives the missing piece an exact target (Section~\ref{sec:arc}) & 95 generated tasks, each missing one
operation of a declared space of 211 structures; three seeded repeats; pre-registered & the task's own holes 64;
demonstrations alone 48 (16 gains, 0 losses); another task's holes 16, all in the one world whose removed operations
compose into one another (0 of 59 in the other two); static search 38 with 3.2 times the CPU; blind enumeration 3 in
every repeat, 74 in some & supported on generated tasks: discovery in a supplied space \\
Construction finds answers that static search at the same CPU does not (Section~\ref{sec:arc}) & 464 held-back tasks
of ConceptARC, Mini-ARC and 1D-ARC, 624 query outputs, held out from development but scored once before & reused
operations, then construction where their search failed, 343; static search with the same CPU allowance 118;
construction from another task's demonstrations 10; on the two-dimensional benchmarks 57 against 30 of 315 &
supported on exposed related tasks \\
A learned order changes what a capped search finds, not what exists (Section~\ref{sec:arc}) & learned against
hand-set search order on the same 624 outputs, at four caps & 320 against 234 at 500 counted operations per hole; 327
against 329 at 20,000, where the cap still bound on all 11 tasks whose attempts differed; a frequency table 318, a
linear model 323 & supported at a binding cap \\
\bottomrule
\end{tabularx}
\caption{Each theoretical statement and the test that bears on it. Rows 1 to 5 are elementary conditional results,
proved in the full paper \citep{ndubuisi2026full} under their stated assumptions; rows 6 to 8 are mechanism statements
tested in pre-registered studies. Proposition~\ref{prop:nest} was stated on 27 October, before these tests; the
others were added on 6 November, after some of them, so the table shows what the tests account for, not predictions
made in advance. A fitting program reproduces every demonstration; all-agree acceptance answers only when every
fitting program returns the same output; an essential input is one whose value can change the rule's output; static
search searches the starting language with no new operation; blind enumeration adds the declared structures one at a
time and searches the task with each. The strict-rule test of row 1 and rows 2, 7 and 8 use previously exposed
tasks; rows 4 and 5 use simulations.}
\label{tab:theorytests}
\end{table}
```

Terms: Paper 1 says "original language" (lines 220, 248, 293); the brief asks for "starting language" in every document
(Brief rule 4). Use one term, defined once.

## 6. Deliverable 2: Writeup version (60 words by `wc -w`)

Replace the second sentence of Writeup line 23 ("Four conditional results explain the pattern: ...", 32 words) with:

> Four conditional results: few demonstrations fit many rules (of 134 answers from fitting programs, 32 were wrong);
> ranking cannot add ungenerated answers (the neural comparison entry's candidates allowed 3 more of 172); a missing
> input blocks recovery (two-input rules recovered 0 of 274 gene rules needing more); growth under all-agree acceptance
> only adds abstentions where the smaller language fits (untested).

- Sources: 32 of 134 (Strict follow-up lines 40 and 42); 3 more of 172 (Headroom); 0 of 274 (Sparse audit section 6);
  "untested" and "where the smaller language fits" (section 4, A8; Theory audit issue 4).
- Line 67 then reads: "**Theory.** Four conditional results; three tested, one untested." (same 7 words).
- Word count: net +28 words, so the body goes from 1,470 to 1,498 by `wc -w` if the brief's items W1 to W3, C1 and C2
  are applied (net 0; Brief lines 699-704). That fits only if the title lines are a separate field; if the platform
  counts them (1,494 now; Brief line 683), offset at least 22 words. The judge read proposes shortening the Section 8
  lines, which repeat numbers given earlier (Judge read, "Paying for it").

## 7. Deliverable 3: why the method works (120 words by `wc -w`)

For Paper 1, under a paragraph heading such as "Why construction works", in place of P1 lines 216-222; the same text
can serve Paper 2 at the end of the construction-at-scale paragraph (P2 line 1637):

> When static search of the starting language fails, CORA forms a typed hole: undoing one invertible starting-language
> operation on the demonstrations, or none, gives the exact input-output pairs the missing piece must produce. The
> failure triggers this step; the demonstrations supply its content. All 211 declared structures are checked against
> these pairs in about 0.02 CPU-seconds; only matches enter a search. On 95 generated tasks this recovered 64 in all
> three seeded repeats; the demonstrations alone gave 48, blind enumeration (one search per structure) 3, or 74 in some
> repeat, and longer static search 38 with 3.2 times the CPU. This is reliable discovery in a supplied space, not new
> availability: no hole from 425 natural failures matched a structure.

Source for each sentence:
1. Holes from the demonstrations, directly or after undoing one invertible starting-language operation: Construction
   protocol lines 320-321 (sketches: the identity, or an invertible operation before or after the hole); Loop audit
   section 3.
2. The failure only triggers: Loop audit section 3; P2 line 1530.
3. Checking against the pairs, then searching only with matches: Construction protocol lines 323-333 (candidates are
   structures that map every hole input exactly to its target; at most three retries per unit); mean
   specification-enumeration CPU per run 0.022, 0.017 and 0.010 seconds in the three worlds (Construction analysis
   `descriptive.cpu_accounting`, `mean_spec_enum_cpu_s`); blind enumeration searches the task once per structure
   (Construction protocol line 334).
4. 64, 48, 3 and 74, 38 and 3.2 times: Construction analysis `descriptive.counts`; Construction progress lines 277-285
   (8.47 against 2.61 CPU-hours, the 2.61 for all three repeats together).
5. Discovery in a supplied space: Construction protocol lines 52-55 ("select the right member of a known,
   pre-registered space, not open invention"); Loop audit section 3, correction 3; Theory audit issues 1 and 11. No
   hole of 425 natural failures matched any of the 211 structures: Natural growth result lines 5-6.

What the paragraph deliberately leaves out, because the evidence does not support it: that the failure's content
guides construction (section 2, item 1); that construction invents operations outside the space; that the gain
transfers to other families (23 against 28; Construction progress lines 277-281; Loop audit section 3).

## 8. Statement repairs the deliverables depend on

**Paper 1 propositions** (each follows the theory audit; replace P1 lines 191-212):

```latex
\begin{proposition}[Many explanations]\label{prop:under}
If some program of $\mathcal L$ fits $D$, $\mathcal L$ can return any allowed output on an exact match to $x^*$ and
otherwise run any program of $\mathcal L$, and $x^*$ differs from every demonstration input, then every allowed output
is predicted at $x^*$ by some program in $V_{\mathcal L}(D)$ \citep{mitchell1997ml}.
\end{proposition}

\begin{proposition}[Build before you rank]\label{prop:nest}
If attempts are drawn from the retained predictions within budget $b$, no selection rule, however learned, raises
accuracy above the share of tasks whose answer is retained, and that share cannot exceed the share of tasks whose
answer some program of $\mathcal L$ that fits $D$ predicts at $x^*$.
\end{proposition}

\begin{proposition}[Bigger language, more ambiguity]\label{prop:unanimity}
Suppose an answer is given only when every fitting program returns the same output at $x^*$, a program that returns
nothing counting as disagreement, and $\mathcal L\subseteq\mathcal L'$. On every task that $\mathcal L$ already fits,
growing to $\mathcal L'$ never adds or changes an answer; it turns an answer into an abstention exactly when
$\mathcal L'$ adds a fitting program that does not return that output at $x^*$.
\end{proposition}

\begin{proposition}[A missing input blocks exact recovery]\label{prop:essential}
Say that a rule depends on an input $v$ when some two inputs that differ only in $v$ receive different values. If a
rule depends on $v$ and every candidate gives equal values to any two inputs that differ only in $v$, no candidate
equals the rule, however good the search; and $m$ binary observations can single out at most $2^m$ rules
\citep{angluin1988queries,akutsu1999identification}.
\end{proposition}
```

- Repairs: Proposition 1 adds the fitting-program assumption (section 2, item 13); Proposition 2 defines expressible
  through fitting programs (Theory audit issue 18); Proposition 3 counts "returns nothing" as disagreement (Theory
  audit issue 4; the proof: fitting programs of $\mathcal L$ are fitting programs of $\mathcal L'$, so if all of
  $\mathcal L'$'s return one output, all of $\mathcal L$'s, a non-empty set, return it too); Proposition 4 defines
  "depends" and "ignores" and credits the counting bound (Theory audit issue 21).
- Bibliography: `angluin1988queries` and `akutsu1999identification` are in `paper/final_20261108/refs_final.bib` (lines
  610 and 580); `mitchell1997ml` is only in `paper/v2_neural_cora/refs.bib` (line 869) and must be copied.
- P1 line 187, lead sentence: "Each is an elementary conditional result, proved in the full paper
  \citep{ndubuisi2026full} under its stated assumptions; together they account for the measurements below
  (Table~\ref{tab:theorytests}) rather than predicting them, and no priority is claimed." (Theory audit issue 14.)
- P1 lines 214-223: keep the first "In plain words" sentence, add "Table~\ref{tab:theorytests} gives the test of each;
  Proposition~\ref{prop:unanimity} is not yet tested.", then the paragraph of section 7. Delete "which the biology
  results test" (section 2, item 4).
- P1 line 483, Theory row: "four elementary conditional results, three tested and supported and one untested, and one
  tested mechanism (Table~\ref{tab:theorytests}) & they account for the measured pattern under their assumptions; the
  next test is growth under all-agree acceptance".

**Paper 2**: apply the theory audit's list ("What the papers must change", items 1 to 6) and the repaired Proposition
3 above to `prop:unanimity`; replace the table's measured faces for `prop:larger` (none yet) and `prop:unanimity`
(illustration only); drop the two loose pairings at P2 lines 841-845 (section 2, item 11); remove the "forthcoming"
box at P2 lines 1165-1175, because the packet exists (Theory audit, "Checked and correct"); insert the noise
proposition (A15) only with the sentence that the event floor has not been counted.

## 9. UNKNOWN, and what would settle it

1. **Proposition 3 has no test.** No record varies the language under all-agree acceptance. Settled by a frozen run
   that adds admitted operations to a starting language under all-agree acceptance and reports, on tasks the starting
   language fits, answers kept, answers changed (the proposition says none) and answers turned into abstentions, and,
   separately, newly reachable tasks, beside the same languages under the base search's two attempts.
2. **Whether growth ever cost a correct answer (A5).** The held-back-half aggregate has no per-task rows (Unfinished
   B9). Settled by comparing the starting-language and grown-language attempts task by task from saved rows, with no
   rescoring.
3. **The construction step's own share of the 343 (B3).** The construction condition answers through the reuse search
   first (Held-back protocol amendment 2, lines 21-27); which outputs only the construction step answered is not in the
   audited aggregate. Settled from the saved per-task rows.
4. **Availability or discovery on held-back tasks (B3, B8).** Whether the starting language can express the 343 minus
   118 extra answers at all is unknown. Settled by a much longer or exhaustive starting-language search on those
   exposed tasks, reported as a diagnosis, not accuracy.
5. **The event floor of the noise proposition (A15).** Not counted. Settled by counting per-gene correctable events
   among the 243 admission perturbations on training data (Brief P2-A10).
6. **The inverse-hole gain outside generated worlds (B2).** The 16 extra tasks from undoing an operation all come from
   two generated worlds. Settled by a held natural-task run with and without the undo step, at equal CPU.
7. **Order of statement and test for the design simulation (A10).** The bound entered Paper 2 at 14:05 UTC on 6
   November (git `2428b3e7`); the simulation's run time relative to that is not established here. Settled from the
   simulation's run receipts.

## 10. Sources and short names

All read-only. Lines are those of the versions read on 8 November 2026.

| Short name | Path |
|---|---|
| Writeup (W) | `paper/final_20261108/KAGGLE_DRAFT_PACKAGE/WRITEUP_BODY_v2_candidate.md` |
| Paper 1 (P1) | `paper/final_20261108/cora_final.tex` |
| Paper 2 (P2) | `paper/v2_neural_cora/main.tex` |
| Companion audit | `records/audit_20261108/COMPLETE_COMPANION_RESEARCH_AUDIT.md` |
| Theory audit | `records/audit_20261108/THEORY_AND_NOVELTY_AUDIT.md` |
| Loop audit | `records/audit_20261108/AUTONOMOUS_REASONING_LOOP_RESULTS.md` |
| Biology audit | `records/audit_20261108/BIOLOGICAL_TRANSFER_AUDIT.md` |
| Reproduction | `records/audit_20261108/INDEPENDENT_REPRODUCTION_RESULTS.md` |
| Unfinished | `records/audit_20261108/UNFINISHED_WORK_RECOVERY.md` |
| Sparse audit | `records/SPARSE_COFACTOR_NATURAL_INDEPENDENT_AUDIT_20261108.md` |
| Brief | `paper/final_push_20261108/INSERTION_BRIEF.md` |
| Registry | `paper/writeup/RESULTS_TO_SOURCE.md` |
| Construction analysis | `experiments/construction_at_scale_20261105/runs/analysis/ANALYSIS.json` |
| Construction protocol | `experiments/construction_at_scale_20261105/PROTOCOL.md` |
| Construction progress | `experiments/construction_at_scale_20261105/PROGRESS.md` |
| Held-back audit | `experiments/natural_growth_b_20261105/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` |
| Held-back protocol amendment 2 | `experiments/natural_growth_b_20261105/PROTOCOL_AMENDMENT_2.md` |
| Order protocol | `experiments/guided_construction_20261106/PROTOCOL.md` |
| Order audit | `experiments/guided_construction_20261106/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` |
| Strict follow-up | `records/NOV2_U2B_CONTROLS_RESULT.md` |
| Benchmarks run | `records/NOV2_UNIVERSALITY_SIMILAR_PROBLEMS_RESULT.md` |
| Headroom | `kaggle/score_first_2026/configs/h2/results/headroom_eval120.json` |
| Selector score | `kaggle/score_first_2026/configs/h2/results/cast_contract_select_v1.score.json` |
| Reachability | `experiments/architecture_sweep_20261026/runs/episodes_v1/reach_eval_dev.json` |
| Design simulation | `experiments/boolean_design_simulation_20261106/sim/RESULTS.md` |
| Contracts report | `experiments/cora_cast_20261026/CONTRACT_SOUNDNESS_REPORT.md` |
| List-function report | `experiments/capability_growth_20261027/reports/TEST_U3_REPORT.md` |
| Natural growth result | `experiments/natural_growth_20261105/PHASE1_RESULT.md` (and `PROTOCOL.md` line 313) |
| Shortlist review | `records/NOV5_BIOLOGY_TRANSFER_PRE_RUN_REVIEW.md` |
| Toy case; Toy check | `paper/final_push_20261108/BIOLOGICAL_RULE_GROWTH_CASE_STUDY.md`; `paper/final_push_20261108/check_abcy_toy_enumeration.py` |
| Noisy theory | `paper/final_push_20261108/CONTINUOUS_DOMAIN_ADAPTER_THEORY.md` |
| Selection tests | `records/ITEM2_V15_SELECTION_RESULT_20261001.md`; `records/CORA_FHR_DEV_RESULTS_20261014.md` |
| Judge read; Cold read | `paper/final_20261108/reviews/JUDGE_READ_WRITEUP_v2.md`; `paper/final_20261108/reviews/COLD_READ_WRITEUP_v2.md` |
| Git history | read-only `git log -S` on Paper 2: commits `7417190d` (27 October), `e06d4834` (2 November), `2428b3e7` (6 November) |
