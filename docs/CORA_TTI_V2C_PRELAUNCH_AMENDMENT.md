# Corrected census (v2c): pre-launch amendment

Dated 2026-09-06, written BEFORE the corrected census is frozen or run, as
required by the evidence-closure directive section 11: any scientific change
discovered during implementation must be documented before launch and must not
enter silently.

What is NOT changed: the semantic constructor inventory, the scoped-fitting
scientific policy, the seven structural families, the structural holdout
{(2,), (2,1)}, and the research question. No learner, induced slot type,
semantic operation, representation, controller or model is added. The original
120-attempt result is untouched and its family-coverage decision stays NO-GO.

## A. Changes to the evidence path

### A1. Deterministic instantiation (corrects a reproducibility defect)

The v1.1 generator derived each concrete colour with
`1 + (index*3 + len(repr(value)) + abs(hash(repr(value))) % 7) % 9`. Python
salts string hashing per process, so the instantiated tables, and therefore the
demonstrations and the admission decisions, depended on an unrecorded
environment variable. Measured consequence: four reconstructions of the same
seeds admit 29, 25, 30 and 28 attempts.

v2c uses the identical formula with `abs(hash(repr(value))) % 7` replaced by
`int(sha256(repr(value))[:8], 16) % 7`. The distribution of colour terms is of
the same kind; the difference is that the value is a pure function of the
schema and seed. `PYTHONHASHSEED` is additionally pinned in the manifest and
checked at startup, so any remaining incidental dependence is fixed rather than
free.

This changes which concrete tables a given seed produces. It therefore produces
a DIFFERENT sample from the same generator family, not a re-run of the old one.
The corrected census is a new observation, never a correction of the old
numbers.

### A2. One identified baseline reasoner (corrects a provenance defect)

Requirement 4, the witness-separation comparison set, and the typed failure
graph now all come from one configuration, `cora_tti/meta_baseline.py`, whose
digest is recorded on every attempt and embedded in every graph. A row whose
recorded failure and graph carry different configuration digests is rejected
with `baseline_tfg_config_mismatch`.

The hypothesis set is unchanged: it is set-equal to the space
`meta_induction.search` enumerates, confirmed by a live call reporting exactly
200 hypotheses. The ordering differs from the actual search's container order,
which is immaterial under a fixed work limit with no deadline, and is recorded.
The baseline runs to a FIXED WORK LIMIT of all 200 schemas; a wall-clock limit
exists only as an operational safeguard and, if it ever fires, is recorded as
an explicit truncation rather than allowed to look like a baseline failure.

### A3. Persistent run-wide identity state (corrects an inert-guard defect)

`CensusState` is created once and owned by the runner. It is never recreated
inside the attempt loop, a fact the test suite checks by inspecting the loop
source. It carries the v1.1 historical exclusion set, loaded from a hashed file
named in the manifest. A restart rebuilds the state from the durable
per-attempt log before continuing.

### A4. Irreducibility evidence contract (corrects a conflation defect)

Each ablation now returns one of REPRODUCING_ABLATION_FOUND,
NO_REPRODUCING_ABLATION_FOUND_WITHIN_DECLARED_PROCEDURE, INCONCLUSIVE or
NOT_APPLICABLE, with a reason and resource accounting. Two complementary checks
run for every ablation: a DIRECT ablation of the fitted program preserving
surviving bindings, and a REFITTED ablation of the open schema. Either
reproducing establishes redundancy. An exception or a timeout is INCONCLUSIVE
and never evidence of necessity; a target whose audit is inconclusive is
rejected with `irreducibility_inconclusive` rather than admitted.

Measured consequence on the reconstructions: the direct check finds 2 locally
reducible targets that the original audit passed, because the original treated a
refit failure as evidence of necessity.

### A4b. A baseline that did not finish cannot be said to have failed

`if trace.exact:` was the whole of requirement 4, so a baseline that was
truncated, that errored on some hypotheses, or that never judged part of its
declared space was indistinguishable from one that enumerated everything and
failed. The trace now carries the full space size, the work actually done, the
error and exhaustion counts and the truncation causes, and an attempt whose
baseline is incomplete is rejected with `baseline_incomplete` instead of
admitted. A work limit set below the declared hypothesis space is itself
recorded as a truncation rather than passing as a complete search.

### A4c. Checker failures are counted apart from scientific outcomes

Six outcomes report a failure of the checking machinery rather than a property
of the target: `fit_execution_error`, `probe_execution_error`,
`irreducibility_inconclusive`, `baseline_tfg_config_mismatch`,
`baseline_incomplete` and `generation_timeout`. The census report counts these
in their own category, separate from both scientific rejections and uncaught
infrastructure exceptions, and reports for every family how many attempts were
actually evaluated scientifically. A family that admits nothing because every
attempt crashed is flagged, so it can never be read as a family that was
measured and found infeasible.

### A5. Explicit error outcomes

Fitting reports EXACT_DEMONSTRATION_FIT, CONSTRAINT_CONSISTENT_BINDING,
FIT_FAILURE, EXECUTION_ERROR and RESOURCE_EXHAUSTED separately. The
constraint-only mode may be used to inspect candidate bindings and to build the
failure frontier; it can never admit or certify a target. Exceptions surface as
`fit_execution_error` or `probe_execution_error`, in the scientific outcome
vocabulary but distinct from every scientific rejection, and infrastructure
exceptions stay in their own `infra_exception:` namespace.

### A6. Typed key codec

Constraint keys are the raw descriptor values, used as dictionary keys exactly
as the v1.1 learner used them, so lookup semantics are the reference semantics.
Serialization uses the same typed JSON codec `meta_ast` already uses for Lookup
tables. The previous `repr` and `eval` round trip is gone.

Direction of the semantic difference: the removed codec compared keys by their
`repr`, which distinguished `True` from `1` even though the reference lookup, a
plain dictionary, treats them as one key. The correction REMOVES a distinction
the reference does not make; it adds none. In practice no registered key
feature mixes Booleans with integers, so no behaviour changes, which is what
the positive-coverage parity run confirms: 253 positive fits, zero verdict
divergence and zero rendering divergence in either direction.

## B. The one change that alters admission strictness

**A target must be defined on at least one frozen probe** (manifest key
`admission.min_defined_probes = 1`; rejection code `probe_coverage_vacuous`).

Reason. 42 of the 112 audited reconstructed positives are defined on ZERO of
the 16 frozen probes. Their fingerprint is the all-undefined fingerprint, so
the witness-separation check that admitted them compared one undefined
behaviour against others and established nothing. The directive is explicit
that an all-undefined fingerprint is not substantive evidence of behavioural
separation.

Direction of the change. This makes admission STRICTLY HARDER. It cannot
manufacture a positive result, and any family that yields admissions under it
would have yielded at least as many without it.

### B2. A frozen-probe fingerprint match must be non-vacuous

Measured while reviewing this code: every program that is undefined on every
frozen probe carries the SAME all-undefined fingerprint. Three semantically
different programs (different partitions, different key features, disjoint
tables) collide on one fingerprint. Fingerprint equality is therefore not
evidence of behavioural agreement unless the two programs are jointly defined
somewhere.

Both places that compare fingerprints now require at least one jointly defined
probe, and record a vacuous match explicitly when they see one:

- the irreducibility audit, so an ablation is never stamped
  REPRODUCING_ABLATION_FOUND on an all-undefined collision;
- witness separation, so a baseline is never called witness-equivalent on one.

The default value of `min_defined_probes` in the admission law is also changed
from 0 to 1, so a caller that omits it cannot silently get the vacuous
behaviour.

Direction of the change. Under the frozen manifest these guards are INERT: the
section-B floor already rejects any target defined on zero probes before either
comparison runs, so no jointly-undefined comparison can arise. They exist so the
criterion is correct independently of the floor. Where the guards would matter,
they make reducibility HARDER to establish and witness equivalence HARDER to
establish, which is a loosening of admission; that is the correct direction,
because the rejection they prevent would have rested on no evidence at all.

Related honesty note, not a change: the constraint-consistent comparison set
was empty for all 112 audited positives, so witness separation was satisfied
against nothing in every case. In this grammar constraint satisfaction and
exact replay nearly coincide, leaving no near-miss band. The corrected census
records the size of that set on every attempt so the report can state how often
the check was vacuous instead of counting it as evidence.

## C. Schedule and seeds

- 128 attempts per family, the strengthened schedule, against the executed
  run's 120. Seven families, 896 attempts.
- New seed namespace `5_300_000`, with `seed = namespace + family_index *
  2_000_003 + attempt * 7919`. The family term is now a distinct large stride
  per family index rather than a function of length and sum, so no two families
  share a seed schedule. The executed run's (1,0) and (0,1) collision does not
  recur. Collision-freedom over the 7 x 128 grid is checked by a test.
- The v1.1 exclusion set (1453 digests) is active, so a target v1.1 already
  attempted is rejected as `prior_v1_target_overlap` before evaluation. The
  original census overlapped it 39 times.

## D. Recording

Every attempt, including every failure, is appended durably as it completes.
Four units of analysis are recorded separately: attempt, unique schema,
concrete instantiation and demonstration bundle. Code hashes are captured at
execution as well as at report time, and compared. Resource use is recorded
without any causal claim. Wall-clock truncations are recorded explicitly, and
the report will state that deterministic seeds alone do not promise
byte-identical acceptance across machines wherever a deadline can fire.

## E. Decisions this run can and cannot reach

Decision A, the original R2 family-coverage question, is already NO-GO and this
run cannot change it. A corrected run with different instantiation is a new
observation about the generator family, not a re-scoring of the old one.

Decision B, whether a narrower follow-up study is justified, is what this run
informs. It is answered only by evidence of nontrivial two-block recoverability
beyond the identified baseline, with the vacuity and reducibility checks
active. If it is justified, it is a NEW study, not a rescued R2 success.
