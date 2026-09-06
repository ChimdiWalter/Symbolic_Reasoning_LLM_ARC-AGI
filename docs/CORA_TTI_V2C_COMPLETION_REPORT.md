# Corrected census (v2c): completion report

Evidence-closure directive, section 17. Written after the single corrected
census completed. It reports what the mechanism does, under what baseline and
evidence assumptions, and nothing further.

Answer to the question the block was set: **occurrence-scoped fitting makes
two-block programs with at most one filter per block recoverable when the
complete 200-schema single-block baseline fails exactly. It made nothing
recoverable in the three-block family or in either repeated-Select family. The
yield is 13 distinct targets in 896 attempts, and 4 of those 13 have a stage the
demonstrations never witness.**

## 1. The original census, preserved

| item | value |
| --- | --- |
| commit | `e5ef8b5add2f31a37439a3bbbcbf8d0aaa02b724` |
| manifest | `d0cef1262444f848ce635f0bcf631ccbd6a298c2841eb9ed88e7a14728d295d0` |
| results | `d2f53cd8cff5c3e1480ccfd5f82eed218786dd54ed153a837d6c8abceb9b0d5c` |

Observed: 840 attempts, 120 per family, admitting 12 / 8 / 5 / 5 / 0 / 0 / 0 in
(0,0), (1,0), (0,1), (1,1), (0,0,0), (2,), (2,1). For the three zero families
the correct statement is that no admissible target was found among the 120
attempts under the recorded generator and admission procedure.

## 2. Protocol conformance of the executed run

The full table is in `docs/CORA_TTI_V2_EVIDENCE_STATUS.md`. In summary: 4
requirements DEMONSTRATED, 1 partially demonstrated, 5 NOT_IMPLEMENTED
(safe key codec, repeated-Select semantics, historical exclusion, run-wide
deduplication, complete attempt records, failure-graph provenance), 1 DEVIATED
(120 attempts against the later strengthened 128), 1 NOT_APPLICABLE. A manifest
pin was present and establishes artifact identity only.

## 3. Unique versus repeated attempted schemas, and historical overlap

Reconstructed from the pinned generator, labelled
RECONSTRUCTED_FROM_PINNED_GENERATOR:

- 829 of 840 attempted schemas distinct; 11 repeats, 5 in (0,0) and 5 in (2,);
- 39 attempts sampled a schema v1.1 had already attempted;
- 7 to 8 admitted attempts per reconstruction fell inside that historical set;
- families (1,0) and (0,1) shared an identical numeric seed schedule.

## 4. Audited status of every recoverable original positive

Every original positive is **UNVERIFIABLE_FROM_RETAINED_EVIDENCE**. The runner
retained only two example summaries per family, and the run is not reproducible
from its seeds because the generator's colour term used Python's salted hash
with `PYTHONHASHSEED` unset and unrecorded. Four reconstructions admit 29, 25,
30 and 28 attempts against the original 30, and two of the eight retained
example digests do not reproduce as admitted.

The 112 reconstructed positives (40 distinct schemas) were audited in full:

| status | count |
| --- | --- |
| VERIFIED_WITHIN_STATED_SCOPE | 0 |
| DOWNGRADED | 110 |
| FAILED_AUDIT | 2 |

Reasons: 112 carry a graph from the blind-runtime search rather than the
admission baseline; 42 are defined on zero frozen probes; 31 overlap the v1.1
attempted set; 2 are locally reducible under the corrected contract and were
missed by the original audit. Re-checked under the single identified baseline,
all 112 still have zero exact baseline fits and all 112 still refit exactly. The
core observation survived; its supporting evidence did not.

## 5. Positive parity coverage

`scripts/parity_positive_coverage.py`, 200 schemas over 3 deterministic
demonstration sets:

| quantity | value |
| --- | --- |
| cases exercised | 493 |
| old (v1.1 learner) successes | 253 |
| new (scoped fitter) successes | 253 |
| both succeed | 253 |
| mutual failures | 240 |
| old success and new failure | 0 |
| old failure and new success | 0 |
| behaviour disagreements | 0 |

Every partition, predicate and key feature is POSITIVE_COVERED: none is left
UNKNOWN. One case shows the actual fixed search solving a task exactly while the
particular schema under test does not fit; that is the whole search succeeding
through a different triple, not a parity violation.

## 6. Actual-search and adapter equivalence, and fitter fairness

The hypothesis SET is equal, confirmed by a live call reporting exactly 200
hypotheses. The ORDER differs. The procedures differ in fitter, deduplication
and budget, and those differences are recorded rather than asserted away. The
adapter is retained as the baseline hypothesis generator with that evidence
attached.

Both paths call one fitter implementation, and the manifest now records the
scientific OPTIONS each runs under; the runner refuses to start if the live
options differ from the manifest, so a hashed option set cannot be reported as
executed while a different one ran.

## 7. Baseline and TFG configuration identity

One configuration is the single authority for the hypothesis generator,
ordering, fitter, evaluator, budgets, success predicate and trace observer. Its
digest is stamped on the trace and inside every graph, and a row whose failure
and graph carry different digests is rejected. In the census, 95 attempts
reached the baseline, every one enumerated all 200 hypotheses, and none was
truncated or errored.

## 8. Predicate semantics findings

Proved from the definitions and the executor: every registered predicate is a
pure function of `touches_border` and `is_rect`; every stage reads the unchanged
input grid and only Paint writes, so composition is conjunction and overlapping
paints resolve last-writer-wins. All four domain points are realized by actual
regions, so the classification is not vacuous.

Of 25 ordered predicate pairs: 13 equivalent to a single predicate, 4
contradictory, 8 genuine conjunctions. Observed on the fixture distribution, the
conjunction differs from every single-predicate selection only for
`colour_components` with `not_touching_border` and `rectangular`, on 21 of 60
grids. That is an observation about these grids, not about the language.

## 9. The corrected census

Manifest `281624001ee3c69b9c2f1cb4bac700f580eb3f30ba809f31445a8f6d42ac4790`,
frozen on commit `9c1f4386c22dce536e4fa9ae72b23dd26ecffddf` with a clean tree,
before the first attempt. Executed under `PYTHONHASHSEED=0`, numpy 2.4.3,
Python 3.12.3, one worker at nice 15 with single-threaded BLAS, in 43 seconds.
Code hashes captured at execution matched at completion. Attempts file
`d169563eef78de6d...`.

| family | attempts | evaluated | admitted | distinct | checker failures | infra errors |
| --- | --- | --- | --- | --- | --- | --- |
| (0,0) | 128 | 128 | 7 | 7 | 0 | 0 |
| (1,0) | 128 | 128 | 3 | 3 | 0 | 0 |
| (0,1) | 128 | 128 | 2 | 2 | 0 | 0 |
| (1,1) | 128 | 128 | 1 | 1 | 0 | 0 |
| (0,0,0) | 128 | 128 | 0 | 0 | 0 | 0 |
| (2,) | 128 | 128 | 0 | 0 | 0 | 0 |
| (2,1) | 128 | 128 | 0 | 0 | 0 | 0 |

896 attempts, 882 unique schemas, 672 unique concrete instantiations, 667
unique demonstration bundles, 13 admitted attempts and 13 distinct admitted
schemas. Every family was scientifically evaluated, so no gate rests on a family
that merely crashed.

**Guards that were inert in the original run did work here**: 41 attempts
rejected as historical overlap with v1.1, 14 as duplicates within the run, and
32 as probe-coverage vacuous.

**Reproducibility, the property the original run lacked**: all 13 admitted
attempts plus a rejection sample, 23 in total, replicate identically in a fresh
process, and identically again under a different `PYTHONHASHSEED`.

## 10. Rejection and infrastructure accounting

Zero checker failures and zero infrastructure errors across all 896 attempts.
No `baseline_incomplete`, no `irreducibility_inconclusive`, no
`fit_execution_error`, no `probe_execution_error`, no timeout, no uncaught
exception. Dominant scientific rejections are `slot_key_unobserved` (200),
`region_colour_conflict` (210), `slot_unobservable` (150),
`execution_undefined` (174) and `base_search_solved` (37).

## 11. What the 13 admissions are, and their weaknesses

All 13 are two-block programs. Seven come from (0,0), three from (1,0), two
from (0,1), one from (1,1). Seven are defined on all 16 frozen probes; the
others on 5, 8 or 13.

Two qualifications belong with the number, not in a footnote:

- **4 of the 13 have a demonstration-only reproducing ablation**: removing one
  stage still replays every demonstration, and only the frozen probes
  distinguish the reduced program. For those four the demonstrations never
  witness the need for that stage. Nine of the thirteen have every stage
  witnessed.
- **Witness separation did no work.** Only 25 attempts reached that check, and
  the constraint-consistent comparison set was EMPTY in all 25. In this grammar
  constraint satisfaction and exact replay very nearly coincide, so there is no
  near-miss band to compare against. The separation evidence that does real work
  is the exact-fit failure of all 200 baseline hypotheses, which is recorded and
  complete for every one of the 95 attempts that reached it.

## 12. The three zero-yield families

No admissible target was found among the 128 attempts under this generator and
admission procedure. That is a measurement, not a proof of impossibility. The
following are hypotheses, and are labelled as such.

- **(2,)**: 34 attempts were solved exactly by the single-block baseline. Split
  by the proved predicate classification, 25 of those used a pair equivalent to
  a single predicate and 9 used a genuine conjunction, so redundant syntax
  explains most but not all. A further 40 rendered no usable demonstrations and
  25 failed key observability. No (2,) attempt ever reached the irreducibility
  stage.
- **(0,0,0)**: 55 rejected as `slot_unobservable` and 52 as
  `region_colour_conflict`. The hypothesis is that with three blocks over these
  small grids, last-writer ownership leaves an earlier block with no visible
  constrained cell.
- **(2,1)**: 75 of 128 rendered no usable demonstrations.

## 13. Decision A: the original R2 family-coverage question

**NO-GO, unchanged.** The required coverage is not satisfied: gate 3
(a repeated-Select target) and gate 5 (both holdout families) both fail, in the
original run and again in the corrected one. A corrected run with different
instantiation is a new observation about the generator family, never a
re-scoring of the old one, and cannot convert that decision into a GO.

## 14. Decision B: is a narrower follow-up justified

**Yes, as a NEW study, with the limits stated.** The corrected evidence does
establish nontrivial two-block recoverability beyond the identified baseline:
13 distinct generated two-block targets fit exactly under occurrence-scoped
fitting while a complete, untruncated, error-free enumeration of all 200
single-block hypotheses fails exactly, with historical exclusion and
deduplication active, with vacuous probe evidence excluded, and with local
irreducibility established under a contract that separates inconclusive checks
from evidence. Nine of the thirteen have every stage witnessed by the
demonstrations.

The proposal is in `docs/CORA_TTI_V2_1_PROPOSAL.md`. It is a proposal only: no
corpus is generated and no model is trained in this block.

## 15. Claim boundaries

What this work concerns is RECOVERABLE SUPPLIED SCHEMA: a human-defined schema
is given to the fitter and its parameters are recovered from demonstrations. It
is not a CONSTRUCTIVE PROPOSAL, because no search or learned proposer generated
the schema. It is not an OPERATIONAL LANGUAGE EXTENSION, because nothing was
installed into a bounded learner and measured. It is not a SEMANTIC
EXPRESSIVITY EXTENSION, which would require separation from the declared prior
language rather than the failure of one restricted search template.
Occurrence-scoped fitting is human-designed infrastructure and is never a
machine-discovered capability. A composition of existing evaluator operations is
not new semantics merely because the fixed search does not enumerate it.

## 16. Outstanding uncertainty

- The original run's per-attempt admissions cannot be recovered. That is
  permanent.
- Witness separation has never been exercised against a non-empty comparison
  set, so its discriminating power is untested.
- Local irreducibility is established against demonstrations plus 16 frozen
  probes. It is a finite test, never global minimality, and two programs
  agreeing on it may still differ elsewhere.
- The three zero-yield families have explanations that remain hypotheses.
- All results are on a synthetic fixture generator. A yield of 13 in 896 says as
  much about that generator's grids as about the fitter.
- The ledger is hash-chained internally, which detects accidental corruption. It
  is not proof against a rewrite unless its head has an independently retained
  commitment, and no such external commitment exists. A file hash likewise
  proves content, never that nobody read the file.

## 17. Step-B status, timestamped

At 2026-09-06T22:15:17Z: runner pid 106593 alive, elapsed 10 days 18:05:40,
22 worker processes, phase `propose K2 175/497`, journal 186 lines, zero error
signatures in the run log, no final output hash present, host load average
21.15. Quantitative monitoring only; nothing in this block read, modified or
delayed the experiment, and no Step-B result was imported.
