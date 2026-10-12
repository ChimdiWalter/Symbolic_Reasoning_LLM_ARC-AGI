# Automatic failure diagnosis v0: development plan (2026-10-12)

**Status: PLAN.** Nothing is implemented or run. The user's Kaggle-delivery
directive of 2026-10-12, Phase 5, asks for this plan only.

It builds on:
- the typed schema in `docs/CORA_FAILURE_TYPED_CONTROLLER_v0.md`;
- the evidence in `records/CTL0_PHASE1_FEASIBILITY_20261012.md`.

It is separate from the Kaggle NATIVE_BASELINE package, which contains none
of this.

## 1. What v0 must do

Read machine-readable traces of a failed attempt and emit a typed failure
record. The record has three layers:
1. **Observations**: facts, each pointing to the trace field it came from.
2. **Hypotheses**: categories with a status of OBSERVED, ESTABLISHED,
   SUSPECTED or UNKNOWN.
3. **Decision**: an action, or NO_ACTION when no verified safe intervention
   exists.

v0 has no learned component. It contains no task ids, no ARC view names and
no knowledge of kf892487f1049.

## 2. Inputs that already exist

Only recorded, permitted traces are used:
- reach v1 rows: proposals, gates, folds, timeouts;
- diagnosis rows: engine traces, deadline hits, variant lists;
- the static census: coherent, kept and cut views;
- the negative-control and P3 rows.

**ARC adapter.** It turns native events into domain-neutral observations:

| native event | domain-neutral observation |
|---|---|
| a view cut by the cap | unit of representation excluded |
| no proposal | no repair generated |
| train-exact, then a LOO failure | re-derivation unstable |
| a hard cap | budget exhausted |

The core never sees ARC names.

## 3. Categories in v0 and their evidence predicates

Each category is decided by a fixed predicate over observations; there are
no learned weights.

| category | ESTABLISHED when (all from traces) | SUSPECTED when | refuted when |
|---|---|---|---|
| REPAIR_NOT_GENERATED | the constructor ran on permitted evidence and produced 0 proposals | it ran on fewer than the minimum supporting demonstrations | any proposal exists |
| REPRESENTATION_EXCLUDED | the unit holding the evidence was coherent but cut, or not coherent, in the subset whose re-derivation failed | the evidence unit is unknown | the excluded unit's candidates also fail when searched |
| ENGINE_REJECTED | a train-exact candidate was rejected by the engine's own gate | the gate log is missing | acceptance |
| CERTIFICATION_UNSTABLE | the top-level program was accepted, or train-exact, and a re-derivation produced a different program | | every re-derivation reproduces the held-out pair |
| RESOURCE_EXHAUSTED | a hard cap or deadline hit occurred before a verdict | a deadline hit occurred somewhere in the run | the same failure occurs without any budget event |
| UNKNOWN | none of the above holds | | |

A single failure may carry several hypotheses, as in kf892487f1049 f1. The
record never forces one.

## 4. Decisions: no unsafe deployment

| hypothesis | permitted decision in v0 |
|---|---|
| REPAIR_NOT_GENERATED | CONSTRUCT with more permitted evidence, or ABSTAIN |
| REPRESENTATION_EXCLUDED | NO_ACTION, because no safe correction exists yet (P3 rejected, P2 forensic only, variant-first harmful) |
| ENGINE_REJECTED | NO_ACTION, plus a recorded investigation |
| CERTIFICATION_UNSTABLE | NO_ACTION, plus a recorded investigation |
| RESOURCE_EXHAUSTED | SEARCH_MORE only at matched accounting, otherwise NO_ACTION |
| MULTIPLE_PLAUSIBLE_REPAIRS | ABSTAIN |
| UNKNOWN | NO_ACTION |

No decision relaxes a certificate.

## 5. Validation, before any claim

1. **Determinism and boundary.** The same traces give the same record. A
   mutation test: changing a fold's held-out output changes nothing that the
   record of that fold uses.
2. **Agreement with the independent forensic record.** Compare against
   `records/LOO_V1_DIAGNOSIS_20261012.md` and the phase-1 audit, as an
   AUDIT, never as training. Report per category and per fold, including
   disagreements.
3. **Controls.** Shuffled traces (records permuted across folds),
   demonstration-only inputs, and a type-blind decision (the same action
   everywhere). Diagnosis quality must beat all three.
4. **Diagnosis quality and capability growth are kept apart.** Correct labels
   are progress of kind B at most. Nothing here counts as capability growth.

## 6. Milestones (planning targets, not promises)

1. Adapter and record schema, with tests and the mutation test.
2. v0 run on the recorded traces, plus the agreement audit.
3. The control comparison.
4. Connecting the decisions to the constructor and certifier: CONSTRUCT
   triggers the existing reach proposer on permitted evidence, under a new,
   separately frozen protocol. Only then can a decision change an outcome.

## 7. Kill rules and claim ceiling

**Kill rules:**
- v0 is rejected if it uses task ids or held-out outputs;
- or if it fails the mutation test;
- or if it does not beat the shuffled and type-blind controls on the
  recorded traces.

**Claim ceiling for v0:** "an automatic, typed reading of recorded failure
traces that agrees with independent forensic analysis at a measured rate".
It is not a controller that improves reasoning, and not D.

**Where it leads.** The first real milestone of CORA remains an
independently scored ARC task where an automatically constructed extension
passes full adaptive leave-one-out and is causally necessary. The durable
step, promotion and reuse, is the separate Step B experiment. It is not
integrated here and has no verdict.
