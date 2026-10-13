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

## Amendment 1 (2026-10-13T19:00Z): CORA-RG under the post-Kaggle addendum. Before any final-split run

**Scope.** The user's "post-Kaggle zero-score research addendum" supersedes
sections 4-8 where they differ.
- Only development rows (arm A on 8 development tasks) existed at this
  point. No final-split task had been run.
- The final corpus is regenerated under section A3 below. The grammar
  (6870042) is unchanged.

### A1. Intervention-based failure diagnosis (the controller of arm F)

Per failed induction call on subset T, fold-local, the controller takes
the first branch whose probe succeeds. Probes are actual engine re-runs on
T: training-only, each with its own time slice.

| # | diagnosis | permitted observations | cheap probe | supported if | refuted if | adaptation | abstain when |
|---|---|---|---|---|---|---|---|
| 1 | SEARCH_BUDGET_EXHAUSTED | native deadline reached; near-solve fit ≥ 0.9 | native re-run with +1 slice | the re-run finds a train-perfect program | the re-run fails | use the re-run (search) | - |
| 2 | EXISTING_REPRESENTATION_EXCLUDED | coherent views cut by the cap on T | re-run with the cut views first, in native order | it finds a train-perfect program | it fails | use it (view correction; no construction) | - |
| 3 | REPRESENTATION_LANGUAGE_INSUFFICIENT | no train-perfect program with any existing view in budget (probes 1 and 2 failed or not applicable); stage segmentation, matching or selector | constructed views (k = 2, novel and coherent, ranked by stage) each re-run | at least 1 constructed view gives a train-perfect program | none does | use it (construction) | 2 or more constructed programs that **disagree on the unlabelled test inputs** (HYPOTHESIS_AMBIGUOUS) |
| 4 | EXECUTABLE_LANGUAGE_INSUFFICIENT | stage parameter: objects matched and selected, change unexplained | none in v0 (no operation constructor) | - | - | none | always |
| 5 | CANDIDATE_NOT_GENERATED | no near-solve (fit below the engine minimum), and construction yields no coherent novel view | - | - | - | none | always |
| 6 | HYPOTHESIS_AMBIGUOUS | see row 3 | - | - | - | none | always |
| 7 | CERTIFICATION_UNSTABLE | (induce_program level) train-exact but leave-one-out fails | - | - | - | none: the native verdict stands | - |
| 8 | INSUFFICIENT_EVIDENCE | a subset of 2 or fewer pairs where probe 3 gives programs that disagree on T's left-out input | - | - | - | none | always |
| 9 | UNKNOWN | otherwise | - | - | - | none | always |

**The construction rule.** A failure is never called language-insufficient
because bounded search returned nothing. Probe 3 must actually produce a
train-perfect program with a constructed view, and probes 1 and 2 must have
failed first.

### A2. Arms (the addendum's names)

| arm | behaviour per failed call |
|---|---|
| A FROZEN_NATIVE | none |
| B SEARCH_ONLY | none; budget raised to match F's mean measured total compute on development (fixed in freeze v1) |
| C EXISTING_VIEW_CORRECTION | probe 2 only (cut views first); no construction |
| D FAILURE_BLIND_CONSTRUCTOR | construction at every failed call (k = 2, canonical order, first success); no probes, no ambiguity check |
| E SHUFFLED_FAILURE_CONSTRUCTOR | F's decision path driven by another task's arm-A top-level observations (diagnosis and stage); its probes run on its own T |
| F FAILURE_CONDITIONED_CONSTRUCTOR | the A1 controller |
| G OPTIONAL_NEURAL_ASSISTED | pre-registered follow-on only (Kaggle GPU quota); not in the first frozen run |

### A3. Final corpus C3 v1

**Families are designed now**, after the grammar and before any final run.
At least 2 families contribute to every category in the final split. The
solver sees only grids: no family name, id or generator metadata.

| category | development | final (held out) |
|---|---|---|
| A solvable with existing views | A_recolour_map | A_translate, A_bbox_fill |
| B existing view cut by the cap | B_diag_drop | B_diag_count, B_layer_pieces |
| C new composition in G-rep | M_contain | M_shape, M_row, M_overlap |
| D needs a relation outside G-rep | D_diagonal | D_mirror_pairs, D_row_parity |
| E needs a new transformation | E_checker | E_cyclic_shift, E_outline |
| F ambiguous / insufficient evidence | F_largest_leftmost | F_colour_vs_half, F_size_vs_position |
| G misleading representation change | G_rowmates_colour | G_coincident_near, G_coincident_shape |

**Sizes.** 8 tasks per final family (17 families, 136 tasks); 5 per
development family (35).

### A4. Novelty test (bounded old language)

**The old representation language** is the 7 native views S1-S7.

**A constructed view is NOVEL for a task** when, on every grid the engine
segments for that task (training inputs and outputs, and the test inputs),
its partition differs from each of the 7 views' partitions. That is an
exhaustive check over the bounded old language.

**What is claimed:**
- COMPOSITION (L2) for every constructed view, since it is built from
  G-rep's primitives;
- never PRIMITIVE EXTENSION (L3).

### A5. Success thresholds and minimum sample (final split, single run)

**Units:** per task, correct means both held-out demonstrations exact.

**REPRESENTATION_CONSTRUCTION_JUSTIFIED** requires all of:
1. F has **at least 6 new correct** tasks over A, coming from **at least 2
   different category-C families**;
2. F > B and F > C on correct (exact McNemar p < 0.05);
3. F > D, or F = D with fewer harms;
4. F > E (McNemar p < 0.05);
5. **0 new false acceptances** by F, and **0 lost A-correct** tasks;
6. every F gain uses a novel constructed view, and the ablation (F without
   that view's program) removes it;
7. F constructs on categories D, E and G no more than D does, and causes
   no false acceptance there.

**Other outcomes:**
- **Composition-only** (the addendum's EXISTING_CAPABILITY / COMPOSITION
  reading): F ≈ D, or F ≈ E, with gains over A, B and C.
- **SEARCH or VIEW_CORRECTION only:** B or C reproduce F's gains.
- **Representation-reachability only:** constructed views become coherent
  or reachable, but there is no end-to-end gain.
- **NO_SUPPORTED_RESEARCH_GAIN:** no arm beats A safely.

**Minimum sample.** At least 16 category-C final tasks with an arm-A
REJECT. Otherwise the result is UNDERPOWERED.

### A6. Durable-growth interface (conceptual only; no integration)

A task-local constructed view would carry:
- its canonical program name (G-rep v0);
- its type (REPRESENTATION, a grouping);
- its dependencies (base and relation names);
- its verified scope (the task's demonstrations; the leave-one-out
  verdict);
- its certificate (the native leave-one-out report and the held-out
  outcome);
- its failure provenance (the A1 diagnosis and probe log);
- an artifact: the program tuple, re-executable by `grammar.apply`;
- promotion eligibility (none in v0);
- version and revocation (the grammar version; revoked if any later
  independent task gives a false acceptance).

Step B is untouched.
