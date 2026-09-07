# Protocol v2 census: evidence status and interpretation corrections

Additive record. It changes no earlier document, no earlier manifest and no
earlier result. Written in response to the evidence-closure directive of
2026-09-05, sections 3, 4, 5 and 10.

Subject of the reconciliation:

| item | value |
| --- | --- |
| development checkpoint | `e5ef8b5add2f31a37439a3bbbcbf8d0aaa02b724` |
| feasibility manifest | `d0cef1262444f848ce635f0bcf631ccbd6a298c2841eb9ed88e7a14728d295d0` |
| feasibility results | `d2f53cd8cff5c3e1480ccfd5f82eed218786dd54ed153a837d6c8abceb9b0d5c` |
| v1.1 protocol manifest | `66780880697d5557a8c79aa100c30cd4a653dd2d62ddc13559d90eb5ac78acd3` |
| v1.1 generation manifest | `36b6989ab77f96a0e68bafe36fd008aa8e51d3388b4b9861ba76c1ccebf03960` |

All four were recomputed from disk. None was taken from a prefix.

## 1. Original observations, preserved

The executed census attempted 120 targets in each of 7 structural families,
840 attempts in total, and recorded these admissions.

| family | admitted attempts |
| --- | --- |
| (0,0) | 12 |
| (1,0) | 8 |
| (0,1) | 5 |
| (1,1) | 5 |
| (0,0,0) | 0 |
| (2,) | 0 |
| (2,1) | 0 |

These remain the original observations. They are not relabelled as 30 unique
targets. For the three families with no admission the correct statement is: no
admissible target was found among the 120 attempts under the recorded generator
and admission procedure. The original family-coverage decision remains NO-GO,
and nothing in this document or in any later corrected run converts that run
into a GO.

## 2. Chronology, so the reconciliation is honest about what was executed

The census was executed under the protocol-v2 directive of 2026-09-04, before
the strengthened R2 directive existed. Where the table below marks a
requirement NOT_IMPLEMENTED or DEVIATED, that is a statement about what the
executed code did, not a claim that the run ignored an instruction it had
already received. The strengthened schedule of at least 128 attempts per family
is one such case: the run used 120 because 120 was the number in force.

## 3. Requirement reconciliation

Status vocabulary: DEMONSTRATED, IMPLEMENTED_NOT_DEMONSTRATED, NOT_IMPLEMENTED,
DEVIATED, NOT_APPLICABLE.

| # | requirement | status | evidence or reason |
| --- | --- | --- | --- |
| 1 | attempt schedule of at least 128 per family | DEVIATED | 120 per family executed; the strengthened schedule postdates the run |
| 2 | parity of the scoped fitter with the v1.1 learner on family (1,) | DEMONSTRATED for verdict and rendering agreement, IMPLEMENTED_NOT_DEMONSTRATED for positive coverage | `tests/test_scoped_slot_parity.py` compares all 200 schemas on 4 deterministic demonstration sets, but its transformation yields few positive fits, so most terminals were never exercised in a SUCCESS case; positive coverage is added by `scripts/parity_positive_coverage.py` in the corrected block |
| 3 | safe key codec | NOT_IMPLEMENTED at the time of the run | the fitter serialized descriptor keys with `repr` and restored them with `eval`; replaced in commit `fa85495` by raw descriptor values with a typed JSON codec, preserving reference lookup semantics and introducing no Boolean/integer distinction |
| 4 | actual-search and adapter schema-set identity | DEMONSTRATED | `scripts/baseline_enumeration_identity.py`: the sets are equal and a live call to the actual search reports exactly 200 hypotheses; the ORDER differs, and the two procedures differ in fitter, deduplication and budget. Recorded separately, never asserted as procedural equivalence |
| 5 | common fitter authority for baseline and target | DEMONSTRATED for the implementation hash, NOT_IMPLEMENTED for the options | both paths called one implementation and recorded its hash, but the scientific options each path ran under were not recorded; `scoped_slot_fitting.fitter_options` now records them and the corrected admission law compares them |
| 6 | repeated-Select semantics established from the executor | NOT_IMPLEMENTED at the time of the run | asserted, not measured; now established in `scripts/predicate_semantics_audit.py` (see section 5B) |
| 7 | historical target exclusion against v1.1 | NOT_IMPLEMENTED | the runner passed an empty exclusion set on every attempt, and no v1.1 digest set existed; the set has since been derived from the recorded v1.1 seeds (1500 attempts, 1453 unique digests, sha256 `856721d18948878c4b9b5e2e5362ce9be651819673209ee688e1e06a3616d690`) |
| 8 | run-wide deduplication | NOT_IMPLEMENTED | the runner passed empty `seen_digests` and `seen_train_digests` on every attempt, so both guards were inert |
| 9 | complete attempt records | NOT_IMPLEMENTED | only per-family outcome counts and two example summaries per family were retained |
| 10 | independent audit of the positives | NOT_APPLICABLE at the time, now DEMONSTRATED on reconstructions | no per-attempt evidence existed to audit; `scripts/audit_reconstructed_positives.py` audits the reconstructed positives instead, under an explicit label |
| 11 | failure-graph provenance | NOT_IMPLEMENTED | admission evaluated the 200-schema adapter with the scoped fitter, then called the blind-runtime trace search for the TFG: a different language with a different fitter. Every one of the 112 audited reconstructed positives carries a graph from that other reasoner |
| 12 | manifest pin before the run | DEMONSTRATED | the manifest was frozen and hashed before execution; that establishes artifact identity only, and is not evidence that any scientific check above was implemented |

## 4. What the original census can and cannot support

**The run is not reproducible from its seeds.** `constructive_dataset.instantiate_tables`
derives each concrete colour with `abs(hash(repr(value))) % 7`. Python salts
string hashing per process, `PYTHONHASHSEED` was unset, and its value was not
recorded. Four reconstructions under the pinned snapshot at `e5ef8b5` therefore
differ from the original and from each other.

| reconstruction | admitted attempts | (0,0) | (1,0) | (0,1) | (1,1) | (0,0,0) | (2,) | (2,1) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 30 | 12 | 8 | 5 | 5 | 0 | 0 | 0 |
| hash seed unset | 29 | 12 | 7 | 7 | 3 | 0 | 0 | 0 |
| hash seed 0 | 25 | 11 | 7 | 4 | 3 | 0 | 0 | 0 |
| hash seed 1 | 30 | 11 | 8 | 6 | 5 | 0 | 0 | 0 |
| hash seed 2 | 28 | 12 | 7 | 5 | 4 | 0 | 0 | 0 |

Two of the eight retained example digests do not reproduce as admitted. Every
original admitted attempt is therefore UNVERIFIABLE_FROM_RETAINED_EVIDENCE at
the attempt level. The zero-yield families are zero in every reconstruction.

**Schema identities are unaffected**, because the sampler is a pure function of
the seed. Analysed offline from the reconstructed identities:

- 829 of the 840 attempted schemas are distinct; 11 attempts repeat a schema
  already attempted, 5 of them inside family (0,0) and 5 inside family (2,);
- 39 attempts sample a schema that v1.1 had already attempted, so a working
  exclusion set would have rejected them before evaluation;
- of the admitted attempts, 7 to 8 per reconstruction fall inside that
  historical set;
- families (1,0) and (0,1) have an IDENTICAL numeric seed schedule, because the
  original seed expression `namespace + attempt*7919 + len(family)*1013 +
  sum(family)*37` is symmetric in those two families. That is paired sampling.
  It may be useful, but it must not be described as independent sampling.

## 5. Interpretation corrections

### A. Single-block parity

Parity on family (1,) establishes agreement between the scoped fitter and the
v1.1 learner on that family and on the evidence set tested. It does not
establish that every schema with one map slot behaves like the original
learner. Family (2,) carries two Select stages and lies outside the tested
family. The earlier claim that scoping is "a no-op by construction" on (2,) was
an inference, not a measurement, and is withdrawn.

### B. What repeated Select actually expresses

Established from the executor and the registered inventory, not assumed
(`scripts/predicate_semantics_audit.py`).

Proved from definitions: every registered predicate is a pure function of the
descriptor fields `touches_border` and `is_rect`; `meta_ast.evaluate` computes
every stage from the UNCHANGED input grid and only `Paint` writes, so later
blocks read the original grid and overlapping paints resolve last-writer-wins.
Therefore `Select(q2)(Select(q1)(S)) = {r in S : q1(r) and q2(r)}`, and two
ordered pairs agree exactly when their conjunction truth tables agree over the
four-point domain. All four domain points are realized by actual regions in the
fixture and probe grids, so the classification is not vacuous.

Of the 25 ordered pairs: 13 are equivalent to a single registered predicate
(every pair involving `all`, and every repetition of one predicate), 4 are
contradictory and select nothing, and 8 are genuine conjunctions that no single
registered predicate expresses. Conjunction is commutative, so the 8 reduce to
4 unordered conjunctions, all of the form (border condition and rectangularity
condition).

Observed, not proved: on the fixture distribution the composed selection
differs from EVERY single-predicate selection only for `colour_components`
paired with `not_touching_border` and `rectangular`, on 21 of 60 grids. On the
other three partitions the conjunction coincides with a single-predicate
selection on every grid sampled. This is a finite observation about the
generator's grids, not a statement about the language.

### C. Zero-yield families

Zero admissions can arise from generator coverage, observability restrictions,
learner incompleteness, baseline expressibility, redundant syntax,
implementation defects or resource bounds. What the retained records show, as
hypotheses to be tested rather than conclusions:

- **(2,)**: 50 of 120 attempts were rejected because the single-block baseline
  solved the task exactly; 47 rendered no usable demonstrations. Splitting by
  the classification above, 41 of the 50 baseline-solved attempts used a
  predicate pair equivalent to a single predicate, and 9 used a genuine
  conjunction. So redundant syntax explains most but not all of it, and the
  genuine conjunctions failed for a different reason.
- **(0,0,0)**: 53 of 120 were rejected as `slot_unobservable` and 39 as
  `region_colour_conflict`. The hypothesis is that with three blocks over the
  same small grids, last-writer ownership leaves an earlier block with no
  visible constrained cell. It is a hypothesis.
- **(2,1)**: 64 of 120 rendered no usable demonstrations.

Zero in 120 attempts is not a proof that a family is impossible. It is the
observation that this generator, at this attempt count, produced none.

### D. Positive targets

A supplied target schema that fits while a restricted baseline search fails
demonstrates recoverability beyond that search procedure. It does not by itself
demonstrate learned proposal quality, semantic invention, or non-definability
in the evaluator language.

### E. The fitter is human-designed infrastructure

Occurrence-scoped fitting was designed and written by hand. It is not a
machine-discovered capability and must never be described as one.

## 6. Audit of the recoverable positives

`scripts/audit_reconstructed_positives.py`, output
`outputs/tti/constructive_v2_corrected/original_positives_audit.json`.

Every ORIGINAL positive is UNVERIFIABLE_FROM_RETAINED_EVIDENCE, for the reasons
in section 4. The 112 reconstructed positives across the four reconstructions
(40 distinct schemas, 21 admitted under all four hash seeds, 11 under exactly
one) were audited in full against the corrected checks.

| audit status | count |
| --- | --- |
| VERIFIED_WITHIN_STATED_SCOPE | 0 |
| DOWNGRADED | 110 |
| FAILED_AUDIT | 2 |

Reasons, which overlap:

- **112 of 112** carry a failure graph from the blind-runtime trace search
  rather than from the baseline whose failure admitted them.
- **42 of 112** are defined on ZERO of the 16 frozen probes. Their
  frozen-probe fingerprint is the all-undefined fingerprint, so the
  witness-separation check that passed them was vacuous.
- **31 of 112** sample a schema v1.1 had already attempted.
- **2 of 112** are locally reducible under the corrected contract and were not
  detected as such by the original audit: in each, a direct ablation that
  removes one Select stage from the fitted program still replays every
  demonstration and matches the frozen-probe fingerprint. The original audit
  missed them because it refitted from the open schema and treated a refit
  failure as evidence of necessity.

Two further facts hold for all 112 and are properties of the procedure, not of
any individual target:

- the constraint-consistent comparison set was EMPTY in every case, so the
  witness-separation requirement was satisfied against nothing. In this grammar
  the fitter's constraint system and exact replay very nearly coincide, so
  there is no near-miss band for the check to examine. The separation evidence
  that does real work is the exact-fit failure of all 200 baseline schemas;
- re-checked under the single identified baseline reasoner, all 112 still have
  zero exact baseline fits and all 112 still refit exactly under the current
  fitter. The core observation survives; its supporting evidence did not.

Applying the corrected filters together (at least one defined probe, no
historical overlap, not reducible and not inconclusive under the corrected
contract), 47 of the 112 audited episodes survive, covering 17 distinct
schemas across all four two-block families. That is the honest residual of the
exploratory result. It is not a validated finding, and it does not restore the
family-coverage GO.


## 7. Test-suite status, closed 2026-09-07

The repository-wide suite was compared against the pinned pre-change snapshot at
`e5ef8b5` (`logs/run_slow_suites.sh`, output `logs/slow_suites_ab.log`). The
comparison is closed and no further audit is open.

| set | current tree | pinned snapshot |
| --- | --- | --- |
| `test_v2_preserves_v1_behavior` + `test_v21_contract_integrity` | 3 failed, 15 passed | 3 failed, 15 passed |
| test files 7 to 20 | 5 failed, 239 passed | 5 failed, 239 passed |

The failing test identifiers are identical in both trees:

- `test_v2_preserves_v1_behavior::test_v2_reproduces_v1_certified` for `d89b689b`,
  `e9ac8c9e` and `a48eeaf7`;
- `test_adaptive_loop::TestAdaptiveReasoningLoop::test_multi_view_tried_on_failure`;
- `test_adaptive_orchestrator::TestNoModuleBypassesVerifier::test_orchestrator_always_verifies`;
- `test_baseline_restore_regressions::test_frontier_operator_regression` for
  `bb43febb` and `a5313dff`;
- `test_composed_frontier_operators::TestSelectThenRecolorOperator::test_verifier_accepts_correct_proposal`.

None is caused by this work. One reports `status=timeout` and these suites run 36
to 64 minutes under the live experiment's load, so some may be load-induced
rather than logic failures; that is a hypothesis, not a finding. They are
pre-existing repository debt to triage before any merge to main.

Every suite that imports the modules changed in this block passes: 116 tests
across `test_cora_parent_isolation`, `test_constructive_dataset`,
`test_constructive_probes`, `test_constructive_vocabulary`,
`test_scoped_slot_fitting`, `test_scoped_slot_parity`,
`test_v2c_evidence_contract`, `test_meta_v2_architecture` and `test_mdl_v2`,
plus 9 in `test_candidate_trace`.
