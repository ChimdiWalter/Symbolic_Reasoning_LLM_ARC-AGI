# cora_rep_growth v0: failure-driven representation construction, plan and preregistration (2026-10-13)

**Status: PLAN v0, the second deliverable.** The grammar below is fixed
before any task family is designed. Nothing has been generated or run.

The plan follows `records/CORA_AUTONOMY_AUDIT_20261013.md`: natively, CORA
selects among 7 fixed views and never synthesizes a grouping. This tests
the missing step (L2 for representations), on synthetic data only. Not
touched: native v23, Kaggle, C2, Step B, VDCG, the frozen pilot, protected
evaluation data.

## 1. Hypotheses

- **H_rep.** When the frozen reasoner fails *because its representation
  language cannot express the needed grouping*, a constructor that
  synthesizes new grouping expressions yields new, independently correct
  held-out predictions. The engine, coherence test and leave-one-out stay
  unchanged.
- **H_cond.** Failure conditioning (gate plus failure-type-targeted
  ranking) beats a failure-blind constructor with the same grammar and
  budget, and beats a constructor fed another task's failure (shuffled).
- **H_safe.** No new false acceptances, and no loss of native solves.

## 2. Representation grammar G-rep v0 (fixed now; general relations, not task templates)

- **Types.** Grid; Partition (disjoint cell sets on non-background cells,
  background 0).
- **Base partitions B:**
  - `comp(conn ∈ {4, 8}, colour ∈ {same, any})`: the components that
    reproduce S1-S4;
  - `layer`: one object per colour, which reproduces S6;
  - `prox(2)`: Chebyshev distance at most 2, which reproduces S7.

  So 6 bases, all equivalent to existing views. They are a starting point,
  never counted as novel.
- **Merge relations R.** Merge two objects when the relation holds;
  transitive closure.
  - `same_colour`: the same colour set;
  - `same_shape`: identical cell pattern up to translation;
  - `same_size`;
  - `bbox_overlap`: bounding boxes intersect;
  - `bbox_contains`: one bounding box contains the other;
  - `same_row`: they share a row;
  - `same_col`: they share a column;
  - `near(3)`: Chebyshev distance at most 3;
  - `near(4)`.
- **Split S.** `split_colour`: split each object into its colour classes.
- **Programs** (depth at most 2 beyond the base):
  - `b`, `b∘S`, `b∘merge(r)`, `b∘S∘merge(r)`;
  - `b∘merge(r1)∘merge(r2)` with r1 < r2 in the fixed order above.
  - That is 6 x (1 + 1 + 9 + 9 + 36) = 336 programs. The canonical form is
    the tuple of operator names.
- **Novel on subset T** when the program's partition of *every* training
  input in T differs from every one of S1-S7's partitions of that input
  (the native segmenters are the reference).
- **Admission.** A constructed view is consumed only if the engine's own
  `evaluate_variant` finds it coherent. Incoherent views are never forced
  in; the ADMIT repair was harmful before.

## 3. Reversible adapter (in-process, inside a context manager, all restored)

At every `inducer._induce_candidate(train_pairs=T, ...)` call, so that every
leave-one-out fold regenerates its own view:
1. Run the native attempt unchanged. If it has train-perfect programs,
   return it (native success is untouched).
2. Diagnose (section 4). Unless the diagnosis is
   REPRESENTATION_LANGUAGE_INSUFFICIENT, return the native attempt (gated
   arms only).
3. The constructor proposes up to k = 2 programs computed from T and the
   task's unlabelled test inputs only.
4. For each program:
   - register a pseudo-variant (an enum value-map entry plus a
     `SEGMENTERS` entry);
   - prepend it to `inducer.SEGMENTATION_TRIAL_ORDER` during a re-run of
     the original `_induce_candidate`, within the *same* deadline;
   - restore the order afterwards.

   The first attempt with train-perfect programs wins. Otherwise the native
   attempt is returned.

Pseudo-variants stay registered for the task's run, so fold programs
re-render with their own view. Everything is removed afterwards.

**Identity test.** With construction disabled, the outcomes and program
identities equal the native run.

## 4. Failure diagnosis at the call (evidence from T only)

| category | evidence | action |
|---|---|---|
| SEARCH_INSUFFICIENT | the deadline was reached during the native attempt | none |
| REPRESENTATION_EXCLUDED | at least one coherent view was cut by the cap | none: the PROMOTE and P3 evidence says admission changes cause harm |
| REPRESENTATION_LANGUAGE_INSUFFICIENT | no train-perfect program, no coherent view cut, deadline not reached, and the failure stage is segmentation, matching or selector | **construct** |
| EXECUTABLE_OPERATION_MISSING | the failure stage is parameter: objects were selected but the change is unexplained | none |
| CERTIFICATION_UNSTABLE | (at the induce_program level: train-exact but leave-one-out fails) | none |
| UNKNOWN | otherwise | none |

## 5. Ranking

- **D, failure-blind:**
  - constructs at every failed call (no gate);
  - ranks the novel, coherent programs by grammar order: fewest operators
    first, then canonical order.
- **E, failure-conditioned:**
  - gated as above;
  - ranks the novel, coherent programs by a criterion chosen by the
    failure stage, computed on T:
    - segmentation: the engine's coherence, then coverage;
    - matching: consistency of the input/output object-count relation
      across pairs;
    - selector: separability of changed from unchanged objects by one
      simple feature (size, colour or shape class), consistent across
      pairs.
- **E-shuffled:** E's procedure, with the gate decision and stage taken from
  another task's native attempt on its full training set (the next task in
  id order with a different stage when one exists).

## 6. Arms

All arms use one `induce_program` call per task (3 demonstrations, its own
adaptive leave-one-out), sealed flags, and budget_s 20 unless stated.

| arm | what |
|---|---|
| A | frozen native |
| B | native, budget_s 40 (matched extra search: an upper bound on the constructors' extra time) |
| C | native with the cap lifted to 7 (all existing views; no new operator) |
| D | failure-blind constructor |
| E | failure-conditioned constructor |
| E-shuf | E with shuffled failure evidence |

**Ablation:** for every task E solves, A is by construction the removal
arm. A second ablation re-runs E forbidding the program E used.

## 7. Corpus C3 (designed after this grammar; generator committed and frozen before any arm runs)

- Fresh seeds, 3 training plus 2 held-out demonstrations.
- **Development family:** M_contain (a frame plus the content enclosed in
  its bounding box acts as one object).
- **Final families, held out entirely:**
  - **M_shape:** all same-shape objects act as one group;
  - **M_row:** objects sharing a row act as one group.
- **Controls in every split:**
  - **native-solvable:** construction must not fire or harm;
  - **operation-missing:** the grouping is ordinary but the change is not
    in the DSL, so construction is wrong;
  - **outside the grammar:** the grouping relation is not in G-rep v0, so
    construction should not help.
- **Final size:** 15 seeds per family, 5 final families, 75 tasks.
- **Limitation, stated now:** the authors designed both the grammar and the
  families. The controls and the failure-blind arm D are what guard against
  success by construction.

## 8. Metrics and decision rule (final split only, single frozen run)

**Per arm:**
- CORRECT, FALSE_ACCEPT and REJECT on the 2 held-out demonstrations;
- new correct versus A; new false acceptances; lost A-solves;
- construction attempts, admissions and novelty;
- compute time;
- for E, the second ablation.

**Paired tests:** exact McNemar on correct.

**Decision:**
- **AUTONOMOUS_REPRESENTATION_GROWTH_SUPPORTED (L2, bounded grammar).**
  Requires all of:
  - E gains at least 5 over A;
  - E > B and E > C;
  - E > D, or E = D with fewer harms;
  - E > E-shuf;
  - 0 new false acceptances and 0 lost solves;
  - every gain uses a novel view;
  - the ablation removes each gain.
- **COMPOSITION_ONLY_SUPPORTED:** constructed views give gains over A, B
  and C, but failure conditioning adds nothing (E ≈ D or E ≈ E-shuf).
- **SEARCH_GAIN_ONLY:** B or C matches E's gains.
- **NO_VERIFIED_GAIN:** no arm beats A, or the gains come with any harm.
- **EXPERIMENT_BLOCKED:** infrastructure failure.

**Not claimed in any case:**
- L3 (new operators);
- real-ARC capability growth;
- retention or reuse;
- transfer.

## 9. Order and freezes

1. `cora_rep_growth/`: grammar, adapter, diagnosis and constructors, with
   tests (identity, leakage mutation, novelty, reversibility).
2. The C3 generator.
3. Development run (M_contain plus controls): debugging only.
4. Freeze v1: code, generator, seeds, budgets.
5. The final run, once.
6. Result record; paper, poster and abstract.

**Compute.** CPU, nice 19, at most 6 workers. It runs after the C2 ceiling
job, so they never compete.
