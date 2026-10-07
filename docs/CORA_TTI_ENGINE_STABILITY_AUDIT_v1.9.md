# CORA-TTI Item-2 v1.9: K* engine acceptance stability audit

Status: DIAGNOSIS PROTOCOL, written 2026-10-06 before any v1.9 measurement.
Sections 1 to 13 are frozen by the diagnostic pre-freeze commit and are
not changed after the development diagnosis runs. The repair sections
(14 onward) are written after the diagnosis and frozen with the package.

Licensed by: v1.8 prospective FAILURE_SPECIFIC_BUT_NOT_END_TO_END (3ed21bf,
verifier 31/31). Claim stays LEVEL 1. This block runs no real ARC task,
does not rerun v1.8, does not change the v1.8 proposer and touches neither
the 1000 tasks nor the protected 120.

## 1. Question

Frozen: WHY DOES THE SAME REASONER ACCEPT THE SAME COMPILED EXTENSION WITH
ONE DEMONSTRATION SET AND REJECT IT WHEN ONE DEMONSTRATION IS REMOVED?

When the proposer and compiler produce the same serialized extension e,
which engine-internal state transition differs between seven
demonstrations (accepted) and six (rejected)?

## 2. What v1.8 contributes

Only the failure class: same-program six-pair rejection (79 of 81 failed
leave-one-out folds ended in engine rejection; 77 carried the same program
as the full task; on 14 tasks the same program was accepted with seven
pairs and rejected with six). No v1.8 prospective task, row or outcome is
used to fit, tune, select or test anything in v1.9.

## 3. The engine path, read from source

`ObjectReasoningEngine.solve` calls `inducer.induce_program` once (the
dihedral, overlay, generative, gen-compose and analogy routes are
environment-gated and off under K*). `induce_program`:

1. runs the composed search on the N training pairs; its CORA expression
   phase (`meta_induction.induce_computed_candidates`) routes by
   `trigger_fires` (same shape, additive, every pair changes), then searches
   the installed concepts (K*-3 overlay) with `search_with_concepts`,
   fitting the concept's induced tables by K*-2, the frozen scoped fitter
   (`fit_induced_occurrences`), which refuses a table when a key is
   witnessed by fewer than MIN_KEY_WITNESSES = 2 demonstrations or a
   produced key is never visible;
2. if a train-perfect candidate exists, runs the engine's own
   leave-one-out by re-induction (`loo_validate`): for each pair, the WHOLE
   search re-runs on the other N-1 pairs and its top-ranked program must
   reproduce the held-out pair exactly (phase A);
3. on failure, phase B (forced composition, only when the top program is
   flat) and phase C (relational re-search, only when more than 5 s of the
   budget remain) each re-run the search inside their own leave-one-out;
4. otherwise appends HYPOTHESIS_REJECTED: train-perfect but
   leave-one-out-failed.

So a K* + {e} run on six pairs is accepted only if each of six re-inductions
on five pairs reproduces its held-out pair. The audit measures which step
fails inside those re-inductions.

## 4. Instrumentation (observation only)

`cora_arc2026/v19_trace.py` wraps, for the duration of one frozen-runner
call (`v17_compiler.run_reasoner`, unchanged): `engine.induce_program`,
`inducer.loo_validate` (per fold: held-out index, pairs, time, result),
`inducer._induce_composed` (the ranked candidate pool per context),
`meta_induction.trigger_fires`, `meta_induction.search_with_concepts` and
the fitter's `fit_induced_occurrences` (with the fitter's own failure code
and detail). Every wrapper calls the original with the same arguments and
returns its value unchanged; all are removed on exit and are applied outside
`kstar()`, so K*'s restoration snapshot sees one consistent set of
functions. No engine, fitter, compiler or proposer file is edited; the K*
identity (b009a9fb) and the v1.7 and v1.8 freezes are unchanged.

Decision identity is tested, not assumed: a traced and an untraced run of
the same input must agree on acceptance, program and events (section 11).

## 5. Rejection taxonomy and rules

Codes (directive section 3): EXTENSION_NOT_VISIBLE, EXTENSION_TYPE_REJECTED,
SLOT_FIT_FAILED, SLOT_FIT_AMBIGUOUS, TRAINING_PAIR_MISMATCH,
HYPOTHESIS_SCORE_BELOW_GATE, RANKED_BELOW_COMPETITOR,
SEARCH_BUDGET_EXHAUSTED, EXPRESSION_BUDGET_EXHAUSTED,
ROUTER_BUDGET_EXHAUSTED, TIME_BUDGET_EXHAUSTED, CERTIFICATE_FAILED,
ATTRIBUTION_FAILED, FINAL_EXECUTION_MISMATCH, BASELINE_ALREADY_SOLVES,
OTHER_EXPLICIT_REASON; a sub-reason follows a colon.

Rules (`v19_audit.reason_codes`), applied to a rejected run:
- no induction recorded: OTHER_EXPLICIT_REASON:no_induction;
- top-level trigger false: EXTENSION_NOT_VISIBLE:trigger;
- no top-level candidate: the concept-search code below;
- otherwise one code per FAILED fold of phase A:
  - the fold raised: OTHER_EXPLICIT_REASON:<exception>;
  - the fold's trigger false: EXTENSION_NOT_VISIBLE:trigger;
  - concept search absent: EXTENSION_NOT_VISIBLE:no_concept_search;
  - search stopped before trying every binding with its deadline past:
    EXPRESSION_BUDGET_EXHAUSTED;
  - the fit refused the table: SLOT_FIT_FAILED:witness (fewer than two
    witnesses for some key), SLOT_FIT_FAILED:hidden_key (a produced key never
    visible) or SLOT_FIT_FAILED:<fitter failure code>;
  - the fit succeeded but the concept was not admitted:
    TRAINING_PAIR_MISMATCH:observational_signature;
  - the concept fitted but the fold's top-ranked program is another
    candidate: RANKED_BELOW_COMPETITOR (the competitor and the concept are
    recorded with what the engine's canonical ranking reads: program class,
    split and mode for reductions, worst parameter class, value-bound
    literals, stages, rules, expression size, and the concept's rank);
  - the concept was the fold's program and mispredicted the held-out pair:
    SLOT_FIT_AMBIGUOUS:unseen_key when the held-out pair shows a key the
    fold's pairs never witness, else FINAL_EXECUTION_MISMATCH.
- a run's codes are the set of its failed folds' codes.

BASELINE_ALREADY_SOLVES is recorded for the BASE run (K* alone accepted).
A code is "mechanistic" unless it is OTHER_EXPLICIT_REASON.

## 6. Mechanism classes

Per failed fold (`v19_audit.mechanism`), with `permissive_predicts` = the
extension, fitted from the fold's own pairs with every consistent witness
(one witness suffices), reproduces the held-out pair exactly:
- H1 re-induction instability: SLOT_FIT_FAILED, RANKED_BELOW_COMPETITOR or
  TRAINING_PAIR_MISMATCH with permissive_predicts true (the semantics are
  identified by the fold's pairs; the refit or the ranking refuses them).
  Sub-kind "fitting" for SLOT_FIT_FAILED and TRAINING_PAIR_MISMATCH,
  "ranking" for RANKED_BELOW_COMPETITOR. A ranking case also says the
  fold's pairs admit a second train-perfect program that disagrees on the
  held-out pair; it is H1 because the extension itself is identified and
  correct, and the record keeps the competitor so the reader can see it;
- H2 identifiability loss: the same codes with permissive_predicts false,
  or SLOT_FIT_AMBIGUOUS/FINAL_EXECUTION_MISMATCH with an unwitnessed needed
  key or permissive_predicts false;
- H3 search or budget: EXPRESSION_BUDGET_EXHAUSTED, TIME_BUDGET_EXHAUSTED or
  SEARCH_BUDGET_EXHAUSTED; and, in section 9, any decision that changes
  with the clock;
- H4 selection quality (per task, section 10);
- UNRESOLVED otherwise.

The census behind permissive_predicts mirrors the fitter's constraint
collection (same helpers, same ownership law) without its admission rules;
a test checks it against the fitter wherever the fitter succeeds.

## 7. The paired 7-versus-6 audit

For a task with seven training pairs, one held-out pair and the extension
e that the frozen v1.8 FAILURE_CONDITIONED proposer selects and the v1.7
compiler compiles from the seven pairs:
- BASE: K* alone on the seven pairs;
- FULL: K* + {e} on the seven pairs, predicting the held-out pair;
- FOLD_i, i = 0..6: K* + {e} on the six pairs without pair i, predicting
  pair i, with e BYTE-IDENTICAL (same serialized bytes, sha256 recorded per
  run; nothing reselected or recompiled).

Recorded per run: production bytes, name and signature; the concept's
fitted tables at the top level and the fitter's evidence; the ranked
candidate pool and the overlay's rank; the trigger; every leave-one-out
phase with per-fold results, times and deadlines; acceptance, events,
attribution (`uses_extension`) and the held-out prediction.

## 8. Repeatability

Every rejected run, and the FULL run of every task, is repeated in the same
process (repeat A) and again in a fresh process from the saved production
bytes and pairs (repeat B). A reason reproduces when acceptance, the run's
codes and the per-fold (held-out index, code) list are identical.

## 9. Load and budget diagnosis (development fixtures only)

The engine's decisions depend on time only through its clock reads
(deadlines, the expression slice, the phase C condition). The same runs
are repeated with the clock replaced inside geocat_arc and the fitter:
- WALL: the host's wall clock (ordinary permitted host conditions);
- CPU1: process CPU time (the controlled low-contention condition: host
  contention cannot move a deadline);
- CPU10: process CPU time at one tenth rate (ten times the CPU budget).

Scope: the first 12 rejected runs and the first 6 accepted runs, in corpus
order, with the same task, extension, engine and environment. The quantity
is whether the ACCEPT/REJECT decision (and the codes) change. Timing alone
establishes nothing. If decisions are identical across WALL and CPU1, load
is eliminated as the primary hypothesis; if identical across CPU1 and
CPU10, budget is eliminated for those runs.

## 10. Selection quality (H4) and the descriptive splits

Per task, the frozen v1.8 proposer's verified and deduplicated pool on the
seven pairs is recomputed with its own functions, and each candidate gets
the fitter-level proxy of the engine's acceptance on each outer fold
(`v19_audit.nested_proxy`: every five-pair refit by the frozen fitter
reproduces its held-out pair). H4 holds for a task when the selected
extension fails the proxy on some outer fold while another verified
candidate passes it on every outer fold.

Reported: fold failure rates by the selection level that chose e, by
family, and by seen and unseen structure (descriptive only).

## 11. Data boundary

- Development diagnosis range: seeds 870,000,000 + 100k, k = 0..1999,
  never used before (checked in this repository on 2026-10-06).
- Future prospective range, RESERVED and untouched in this block: seeds
  880,000,000 + 100k.
- Corpus law: `scripts/v18_corpus.py` `tasks(870_000_000, n,
  exclude_digests=E_dev, distinct=True)` with the v1.7 filter and the
  erratum-01 conditioning unchanged.
- E_dev: the 3,817 digests of `outputs/tti/v18_prospective_exclusion.json`
  plus the 30 v1.8 prospective target digests.
- The future prospective exclusion set: E_dev plus every target digest of
  the v1.9 development corpus, written before any prospective task is
  generated.
- Not accessed: real ARC data, Step B outputs, the protected holdout,
  VDCG, E_transfer, the lockbox. The generator's schema is used only for
  the corpus law and the descriptive seen/unseen split.

Harness disclosure: before this protocol was frozen, the harness was
smoke-tested on four v1.8 development tasks (seeds 840001000, 840005000,
840005600, 840008100). Three were accepted on every same-extension fold;
on 840005000 two folds were rejected, each by one internal refit in which a
pixel-rule reduction (worst parameter class RELATIONAL, a 21-entry
neighbour-count table) outranked the fitted extension (INDUCED_MAP) and
mispredicted. That observation shaped the competitor fields above. These
are engineering checks, not measurements, are not part of any reported
distribution, and the repair is not designed from them.

## 12. Diagnostic corpus selection law

Tasks are taken in corpus order. For each task the frozen v1.8
FAILURE_CONDITIONED proposer runs on the seven pairs; a task enters the
audit when it returns SELECTED and the selection compiles; other tasks are
recorded with their class and skipped.

Categories (recorded, never balanced):
- A: FULL accepted, some FOLD rejected; B: FULL accepted, every FOLD
  accepted; R: FULL rejected;
- C, D, E: selection decided by VERIFICATION_UNIQUE, D or MDL (P0 apart);
- F: family (1,1); G: families (1,0) and (0,1); other families apart.

Stop rule: process at least 30 audited tasks, then continue in order until
A has at least 12 tasks and B at least 6, or 60 audited tasks, whichever
comes first.

## 13. Diagnosis success condition

The audit succeeds only if at least 90 percent of rejection events (failed
phase-A folds of rejected runs) receive a mechanistic code (not
OTHER_EXPLICIT_REASON) whose run reproduces in repeat A and repeat B, and
the boundary holds: decision identity under tracing, no answer access
beyond the held-out pairs of the synthetic corpus, no task, family or seed
branch, no generator schema in any engine input, no prospective tuning.

The distribution of codes and mechanisms is reported. A mechanism is
dominant when it accounts for at least half of the rejection events; if
none does, the record says so.

## 14. The repair: K*-4, installed-extension re-induction

Written 2026-10-06 after the development diagnosis
(`records/ITEM2_V19_AUDIT_DIAGNOSIS.md`: 145 of 145 rejection events H1;
86 single-witness refits, 59 pixel-rule rankings; load, budget and
selection quality eliminated). Implementation `cora_arc2026/v19_repair.py`.

Rule (one rule, one principle): while an extension is installed (K*-3
overlay non-empty), every re-induction of the run re-derives the installed
extension ITSELF from that re-induction's demonstrations, and the engine's
unchanged gate decides:
- fitting: the installed concept's induced tables are fitted by the frozen
  scoped fitter with every consistent witness (MIN_KEY_WITNESSES = 1 for
  the duration of the installed-concept search). Identification is left to
  the leave-one-out, which re-fits the concept without the held-out pair
  and requires that pair exactly, so a key must still appear in at least
  two demonstrations: the witness rule's own stated standard ("a key
  witnessed by a single demonstration cannot be re-derived by the fold that
  holds that demonstration out"), enforced once by the gate instead of
  again inside every re-induction, where it demanded a third witness;
- ranking: in every ranking of the run (`inducer.rank_candidates`,
  `inducer.rank_by_score`) the installed concept's candidates come first
  in the native order among themselves, then the native candidates in the
  native order. A native candidate still wins every re-induction whose
  demonstrations the installed concept does not verify. The native lattice
  is unchanged; it simply no longer adjudicates between the task-time
  hypothesis under test and native candidates it does not price (pixel-rule
  tables labelled RELATIONAL with no value-bound literal).

Why it attacks the measured mechanism: both diagnosed failure kinds are
re-induction-time heuristics designed for native hypotheses displacing an
extension whose fold-fitted semantics reproduce the held-out pair
(permissive fit predicts in 145 of 145). The development projection: 12
of 30 tasks fully stable today, 21 with the fitting clause alone, 19 with
the ranking clause alone, 30 with both; the clauses are not separable
repairs of separate mechanisms.

Unchanged: geocat_arc; the acceptance gate (train-perfect, leave-one-out by
re-induction, every fold exact); the fitter's other admission rules
(coverage, region rules, functional tables, hidden keys, exact replay);
the native search; K*-1 to K*-3; the v1.7 compiler; the v1.8 proposer. The
patches are applied outside `kstar()` and restored on exit; with nothing
installed every patched function returns the native value, so K* alone is
identical (tested). A one-block production keeps the engine's own learner
and its witness rule (K*-2); the v1.8 proposer only produces two- and
three-block compositions.

Identity: K*' = K* + K*-4, `v19_repair.repair_identity()` (K* identity,
rule text, implementation hash). Productions compiled by the v1.7 compiler
for K* install unchanged.

Not a repair of this kind, and not done: task, family or seed branches;
special-casing one extension; memorized outputs; larger budgets; a lower
acceptance threshold. The gate still requires every held-out pair exactly.

## 15. Development ablation (DEVELOPMENT ONLY, the 30 audited tasks)

Script `scripts/v19_repair_dev.py`, written before it runs. Same tasks and
the same byte-identical e as the diagnosis.

Arms (directive section 12):
- A: K* alone, 8 s (the diagnosis BASE run);
- B: K* + e under the old logic (the diagnosis FULL run and same-e folds);
- C: K*' + e (FULL and the seven same-e folds);
- D: K*' alone, 8 s (extension removed);
- E: K*' alone at 3x budget, 24 s (matched compute, no extension);
- supplementary: C with the fitting clause only and with the ranking
  clause only, on FULL and the same-e folds of category A and R tasks.

Adaptive leave-one-out (the L leg): the frozen v1.8 `real_loo` (proposer,
compiler, installation and reasoner from scratch inside every fold) run
under K* (old) and under K*' (repaired).

Witness under K*': B (A not accepted), P (selected), U (C's winner uses e),
L (K*' adaptive leave-one-out, every fold SUCCESS), T (C reproduces the
held-out pair), A (E does not reproduce the held-out output). The same
legs under the old logic are computed from B and the K* adaptive
leave-one-out.

A rescue counts only if: A is not accepted; the old witness is incomplete
(B not accepted, or the K* adaptive leave-one-out has a failed fold); C is
accepted, its winner uses e and the held-out pair is exact; D is not
accepted; E does not reproduce the held-out output; the K*' adaptive
leave-one-out passes.

False-acceptance control: per task, e_wrong is the first candidate, in the
proposer's MDL order over its verified and deduplicated pool on the seven
pairs, whose fitter-level prediction of the held-out pair is wrong (tasks
without one are skipped). K* + e_wrong and K*' + e_wrong run on the seven
pairs; a false acceptance is an accepted run whose prediction of the
held-out pair is wrong.

Safety gates on development (directive section 13), each required:
1. inertness: D equals A on every task (acceptance, program, events);
2. no regression: every run accepted under the old logic (FULL and same-e
   folds) is accepted under K*' with the identical program;
3. no demonstration violation: every program K*' accepts reproduces every
   training pair of its run;
4. attribution: every accepted K*' + e run's winner uses e, and its
   direct execution equals the engine's prediction on the held-out pair;
5. no residue: K*'s restoration snapshot holds after every run and no
   K*-4 patch survives a run;
6. no protected-data access (the script reads only the development
   corpus, its rows and the frozen package);
7. fresh-process reproduction: C and the K*' same-e folds re-run in a
   fresh process with identical decisions;
8. false acceptances of e_wrong under K*' do not exceed those under K*.

## 15a. False-acceptance development measurements (after section 15, before the freeze)

Written 2026-10-06 after three supplementary development measurements,
each committed before it ran, on the 30 audited development tasks.

1. Section 15's single e_wrong per task and a wider rule (up to three
   wrong pool candidates plus the transplant and BLIND selections when not
   useful; `scripts/v19_falseaccept_dev.py`, 8c668f8) found 0 wrong
   extensions in 30 tasks: with seven demonstrations every verified
   candidate reproduces the held-out pair. Section 15's gate 8 is therefore
   vacuous on development data (0 against 0).
2. Reduced demonstrations (`scripts/v19_falseaccept_reduced_dev.py`,
   K = 4: train on pairs 0-3, evaluate on pairs 4-6 and the held-out pair):
   43 trials, 24 RIGHT (the proposer's selection on the four pairs, right on
   every evaluation pair in all 24 tasks where it selected) and 19 WRONG
   (pool candidates). K* accepted 8 of 24 right and 6 of 19 wrong; K*'
   accepted 24 of 24 right and 19 of 19 wrong.
3. Clause by clause (`scripts/v19_clause_safety_dev.py`): fitting clause
   alone 13 of 24 right and 9 of 19 wrong; ranking clause alone 17 of 24
   and 10 of 19.

Reading. Under four demonstrations the engine's own leave-one-out gate
does not discriminate right from wrong installed extensions in any variant:
K* accepts about a third of each (0.33 and 0.32); each K*-4 clause raises
both rates together; K*' accepts every verified, leave-one-out-stable
installed extension. The old gate's rejections of installed extensions
were therefore indiscriminate: they cost recall without buying safety. It
follows that no repair that raises acceptance can pass a rule "false
acceptances of deliberately installed wrong extensions must not increase"
under scarce demonstrations, and that under K*' the correctness of an
accepted installed extension rests on the proposer's selection and on the
held-out and adaptive leave-one-out checks, not on the engine's internal
gate. Narrowing the repair to one clause does not change this (both clauses
alone also raise wrong acceptance), so the repair stays as in section 14.

4. The section-15 ablation's adaptive leave-one-out (proposer, compiler,
   installation and reasoner from scratch per fold, six pairs): certified
   folds with a wrong held-out prediction, K* 1 (task 17 fold 3, an MDL
   selection both logics accept) and K*' 2 (the same, plus task 18 fold 0,
   a D selection the old logic happened to reject). Precision of certified
   folds: K* 132 of 133 (0.992), K*' 206 of 208 (0.990), with 74 more
   correct certified folds.

Design consequence (fixed here, before the freeze). Because the old gate is
indiscriminate, any recall-raising change will sometimes certify a wrong
selection the old gate happened to reject; a strict "no more wrong
certified outputs than K*" count therefore answers a question these data
already answer (yes, one in 208 folds) and would make the prospective
verdict hinge on one or two rare events. The prospective safety gate
(section 16, G4) instead requires that the false-acceptance cost not
offset the gain, as precision over everything the system certifies: K*'
precision is at least 0.95 (a certified output wrong at most one time in
twenty), and at most 0.02 below K* precision on the same tasks. Both
numbers are design choices made here, before any prospective data; on
development they would read 236 of 238 for K*' and 159 of 160 for K*.
(A first draft required the 95 percent Wilson lower bound to clear 0.95;
the prospective tests showed that it labels a perfect but low-volume
system unsafe, for example 65 of 65 correct gives a bound of 0.944, which
would put REPAIR_UNSAFE ahead of REPAIR_NOT_MATERIAL. The bounds are
reported instead.) Every count of
wrong certified outputs (selected seven-pair runs, adaptive leave-one-out
folds, seven-pair wrong-extension trials) is reported. The
reduced-demonstration control is run prospectively and reported with its
pre-registered expectation (K*' accepts at least as many wrong extensions
as K*, and neither logic discriminates); it does not gate. The diagnosis's H1 classification of the 86 fitting events also
depends on the one-witness identification standard of section 6; under the
fitter's two-witness standard they would be H2. The diagnosis record says
so.

## 15b. Development ablation result and the inertness finding

The pre-registered ablation (section 15; `outputs/tti/v19_repair_dev_report.json`,
af4b7c1) gave: K*' complete witnesses 26 of 30 against 12 under K* (14
rescues; A 12 of 15, B 12 of 12, R 2 of 3); FULL accepted 30 of 30 with the
held-out pair exact 30 of 30; same-e folds accepted 210 of 210 (K* 134);
adaptive leave-one-out passed 26 against 12, folds 206 of 210 against 132
(the four K*' non-successes: two K_ALREADY_SOLVES folds, unchanged by the
repair, and two wrong certified folds, section 15a); no residual K*'
rejection; D and E never accepted; clause-only on the 18 A and R tasks:
fitting fully stable 9, ranking 7, both 18.

Gates 2 to 8 pass (no regression 161 of 161, replay 240, attribution 240,
restoration 300, fresh process 240 of 240, false acceptance 0 against 0
with no trial, protected data). Gate 1 (inertness: D equals A in
acceptance, program and events) FAILED on 1 of 30 tasks: on task 3 both
reject with no program, and K*' alone also stored a near-solve. A follow-up
probe (`logs/v19/inert_probe.py`, log beside it) repeated that task's K*
alone run three times without the repair module: the near-solve event
appeared in one of three, decisions identical in all six runs. The event
records how far the search got within the 8 s wall-clock budget; it is
base-engine timing variability, not a K*-4 effect (with nothing installed
every patched function returns the native value, tested). The gate as
pre-registered is nevertheless reported as failed. The prospective G4
inertness check compares decisions (acceptance and program) and reports
event differences.

## 16. Prospective synthetic test (frozen here, run ONCE in the next session)

Script `scripts/v19_prospective.py`; independent terminal verifier
`logs/v19/verify_prospective.py` (written before any prospective data).
Thresholds come from `records/ITEM2_V19_FEASIBILITY.md`, fixed before any
prospective task is generated; the script refuses to run while they are
unset or the freeze is broken.

Corpus: seed base 880,000,000 + 100k (reserved in section 11, never
generated before), the v1.8 corpus law unchanged, distinct target digests,
the first N_TASKS qualifying tasks within 2,000 seeds, skipping every
digest in `outputs/tti/v19_prospective_exclusion.json` (E_dev plus all 60
digests of the v1.9 development corpus).

Per task:
- proposer arms FAILURE_CONDITIONED, SHUFFLED_FRONTIER (transplant, fixed
  derangement, never the task's own digest) and BLIND, each with the
  fitter-level held-out check ("useful");
- for FAILURE_CONDITIONED: the paired ablation under K* (old logic: K* + e
  against K*) and under K*' (K*' + e against K*' alone); K* alone at 3x
  budget (24 s); the v1.8 adaptive leave-one-out (proposer, compiler,
  installation and reasoner from scratch in every fold) under K* and under
  K*'; the false-acceptance control: wrong extensions, distinct by
  production name and never the selected e, are up to three candidates of
  the FAILURE_CONDITIONED proposer's verified, deduplicated pool in MDL
  order whose fitter prediction of the held-out pair is wrong, then the
  SHUFFLED_FRONTIER and BLIND selections when selected and not useful
  (verified on the seven pairs, wrong on the held-out pair); each is
  installed into K* and into K*' on the seven pairs (section 15a: none
  existed on the development tasks, so this control may be empty);
- the reduced-demonstration control of section 15a (K = 4, the frozen
  `scripts/v19_falseaccept_reduced_dev.py` trial rule) under K* and K*',
  reported only.

Witness legs under K*' (primary): B (K*' alone not accepted), P (selected),
U (K*' + e winner uses e), L (K*' adaptive leave-one-out, every fold
SUCCESS), T (K*' + e reproduces the held-out pair), A (K* alone at 3x
budget does not reproduce the held-out output). The same legs under K* are
reported.

Gates:
- G1 failure specificity: one-sided exact sign tests on tasks discordant in
  usefulness, FAILURE_CONDITIONED against SHUFFLED_FRONTIER and against
  BLIND, alpha 0.05 each, both must pass (as in v1.8).
- G2 end to end: at least W_MIN of N_TASKS tasks give a complete K*'
  witness.
- G3 leave-one-out stability improves materially: with b tasks whose K*'
  adaptive leave-one-out passes while K*'s does not, and c the reverse,
  b - c >= DELTA_MIN and the one-sided exact sign test on (b, c) has
  p < 0.05.
- G4 no offsetting cost, every check required: K*' alone equals K* alone on
  every task in acceptance and program (events are reported, not compared:
  section 15b); every task whose K* + e run is
  accepted with the held-out pair exact is accepted by K*' + e with the
  identical program and the held-out pair exact; every adaptive
  leave-one-out fold that succeeds under K* succeeds under K*'; every
  program K*' accepts replays its training pairs; every accepted K*' + e
  winner that uses e executes directly to the engine's prediction; no
  K*-4 patch survives a run; and the false-acceptance cost does not offset
  the gain (section 15a): over the system's certified outputs (accepted
  K*' + e runs on the seven pairs and accepted K*' adaptive leave-one-out
  folds), with precision = certified outputs reproducing their held-out
  pair over certified outputs, K*' precision is at least 0.95 and at least
  K* precision on the same tasks (accepted K* + e runs and K* adaptive
  leave-one-out folds) minus 0.02; the 95 percent Wilson bounds are
  reported. Reported, every level: wrong certified seven-pair runs, wrong
  certified folds, and false acceptances in the seven-pair wrong-extension
  trials, under K* and K*'.

Reported, not gating (section 15a): the reduced-demonstration control's
true and false acceptances under K* and K*' and each logic's
discrimination (acceptance rate of right minus acceptance rate of wrong
extensions). Pre-registered expectation: K*' accepts at least as many wrong
extensions as K*, and neither logic discriminates.

Outcomes (first match):

| outcome | condition |
|---|---|
| PROPOSER_LEAKAGE | any arm or any adaptive leave-one-out fold reports LEAKAGE_FAILURE |
| NO_VERDICT_RUN_ERROR | an exception outside the failure classes, or a missing row |
| NO_VERDICT_FIXTURE_SHORTFALL | fewer than N_TASKS tasks within 2,000 seeds |
| REPAIR_UNSAFE | G4 fails |
| ENGINE_STABILITY_REPAIR_ACCEPTED | G1, G2, G3 |
| FAILURE_SPECIFICITY_LOST | G2 and G3, not G1 |
| REPAIR_STABILIZES_BELOW_WITNESS_THRESHOLD | G3, not G2 |
| REPAIR_NOT_MATERIAL | not G3 |

Run: one coordinator writes the start record, generates the corpus once
into `outputs/tti/v19_prospective_tasks.json` and spawns WORKERS worker
processes that take tasks by claim; rows are appended under a lock. The
coordinator refuses a second start; `--resume` is allowed only after a
genuine interruption (start record present, report and marker absent): the
task file is reused, finished tasks are kept, unfinished claims are
dropped, and every resume is recorded. Nothing else may be rerun.

## 17. Claim ceiling

- If ENGINE_STABILITY_REPAIR_ACCEPTED: on synthetic constructive tasks
  only, extensions built from K's own failure, without the target or a
  candidate pair, are compiled, necessary and certified in the same
  reasoner K*' = K* + K*-4 with the leave-one-out proposal rebuilt inside
  every fold, the selection stays failure-specific against the transplant
  and blind controls, and the end-to-end witness rate clears the frozen
  threshold without a measured safety cost. That is LEVEL 2 on the claim
  ladder for the synthetic domain.
- K*-4 is an engine-side rule for installed extensions; it adds no
  vocabulary, and the extension remains a composition of K's own blocks.
- Under K*' the engine accepts every verified, leave-one-out-stable
  installed extension; with scarce demonstrations it accepts a wrong one as
  readily as a right one (section 15a), as the old logic, at a third of the
  rate, also did. Correctness of an accepted extension rests on the
  proposer's selection and on the held-out and adaptive leave-one-out
  checks. This is the central caveat for real ARC tasks (two to five
  demonstrations) and must shape the real ARC pilot's protocol.
  Completeness by construction (v1.8 protocol section 15) still applies:
  the corpus law places a verifying composition in the search space.
- Not a real ARC result. LEVEL 3 needs a real ARC B/P/U/L/T/A witness from
  the same-reasoner causal pilot, under its own frozen protocol.
- The development diagnosis (section 13 and the diagnosis record) stands
  on its own as a mechanistic result whatever the prospective outcome.

## 18. Failure policy and order

- One diagnosis, one repair, one prospective test (directive section 22).
  If the repair does not materially improve end-to-end stability on new
  data, this synthetic repair line stops; the paper claim moves to the
  mechanistic result, and whether another independent architecture is
  justified is decided with the user. No v1.10 synthetic repair loop, no
  change of thresholds after data.
- Order after this protocol: tests; freeze; ONE adversarial review; genuine
  defects fixed by recorded erratum and re-frozen; STOP. The prospective
  test runs once, in the next session. The real ARC pilot, the 1,000
  training tasks and the protected 120 stay blocked.
