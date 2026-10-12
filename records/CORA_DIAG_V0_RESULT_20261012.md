# Automatic failure diagnosis v0: first run on recorded traces (2026-10-12)

Plan: `docs/CORA_AUTOMATIC_DIAGNOSIS_v0_PLAN.md` (64f15f4).

| item | identity |
|---|---|
| code | `cora_diag/` (ecb907e) |
| output | `outputs/cora_diag/records.jsonl`, `outputs/cora_diag/audit.json` (b417dff) |

**Scope.** Observation only, on recorded traces: no engine run, no repair,
nothing frozen touched. The units are the four failure-conditioned (FC)
development tasks: 4 full-data runs and 14 outer folds, 18 units in all.

**What ran.**
- A domain-neutral core of fixed predicates (`cora_diag/diagnose.py`), with
  no task ids, view names or weights.
- An ARC adapter that reads permitted fields only. A mutation test shows that
  held-out fields cannot change a fold's record.
- An agreement audit against a forensic reference hand-encoded from the
  diagnosis record and the phase-1 record. The reference sits in a separate
  module that the core never imports.

| | primary accuracy | set precision | set recall |
|---|---|---|---|
| **v0** | **0.722 (13 of 18)** | **1.000** | **0.857** |
| shuffled traces (1,000 seeded permutations) | mean 0.276; none at or above v0 | | |
| type-blind majority label (REPRESENTATION_EXCLUDED) | 0.333 | 0.778 | 0.333 |
| demonstration-only | 0.000 | | 0.000 |

**Per category** (true positives / misses; there were no false positives):

| category | true positives | misses |
|---|---|---|
| ENGINE_REJECTED | 7 | 0 |
| CERTIFICATION_UNSTABLE | 7 | 0 |
| REPAIR_NOT_GENERATED | 5 | 0 |
| RESOURCE_EXHAUSTED | 5 | 0 |
| MULTIPLE_PLAUSIBLE_REPAIRS | 1 | 0 (kf892487f1049 f1) |
| REPRESENTATION_EXCLUDED | 11 | 3 |
| INSUFFICIENT_EVIDENCE | 0 | 3 |

**The misses.**
- REPRESENTATION_EXCLUDED: all 3 misses happened inside the extraction of
  NO_PROPOSAL folds. v0 has no extraction-stage predicate.
- INSUFFICIENT_EVIDENCE: outside the v0 vocabulary.
- Primary disagreements:
  - 4 units carry both REPRESENTATION_EXCLUDED and RESOURCE_EXHAUSTED; only
    the priority order differs.
  - 1 unit's reference primary is INSUFFICIENT_EVIDENCE.

**Caveats.**
- The same analyst wrote the predicates and the reference, knowing these 18
  cases. The agreement is a consistency check, not validation.
- The 18 units come from 4 tasks and are correlated.
- Validation needs fresh traces that no one has labelled, scored
  prospectively.

**Claim ceiling.** An automatic, typed reading of recorded traces that agrees
with the forensic analysis at the rates above. It is kind B at most. It
improves no reasoning outcome and is not capability growth. Its decisions
are recorded, never executed: NO_ACTION, ABSTAIN, or CONSTRUCT with more
evidence.
