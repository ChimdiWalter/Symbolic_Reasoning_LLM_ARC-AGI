# Real-ARC failures: a descriptive analysis for the next architecture (21 October 2026)

**Status:** descriptive engineering on the finished, now EXPOSED, real-ARC cohort
(`records/NEURAL_CORA_V2G2_REALARC_REPORT_20261020.md`). It is not a new evaluation and does not change
NO_REAL_GAIN. Every measure below reads demonstrations only, except the certificate checks in section 3.4, which
read native's certified programs (solver outputs, not answers). The cause classes are heuristics: a task in a
"representation" class has not been shown to need a new representation. It is only one where the current
diagnostics do not describe its change.

Sources:
- `scripts/neural_cora_v2g3_realarc_failure_taxonomy.py` → `failure_taxonomy.json`;
- `scripts/neural_cora_g4_realarc_observables.py` → `observables.json` (both in `outputs/neural_cora_v2g2/realarc/`).

## 1. Observables by class (40 primary tasks)

| class | n | every change group has an exact selector | a group no selector separates | median share of changed objects changed only in part | tasks with an output object spanning 2+ input objects | median view gap* | added cells |
|---|---|---|---|---|---|---|---|
| object mismatch | 13 | 13 | 0 | 1.00 | 6 | 0.00 | mostly ray-like where present |
| object-explained, no rule found | 12 | 10 | 0 | 0.00 | 4 | 0.68 | few |
| additive | 7 | 6 | 1 | 0.64 | 4 | 0.07 | ray-like (median 0.44 of added cells); no fill, copy or mirror |
| generator gap | 2 | 2 | 0 | 0.13 | 1 | 1.00 | — |
| beyond budget | 1 | 1 | 0 | 0.57 | 1 | 0.44 | — |
| fit_wrong | 2 | 2 | 0 | 0.11 | 0 | 0.89 | — |
| mixed | 1 | 1 | 0 | 0.31 | 1 | 0.37 | fill 0.42, copy 0.58 |
| solved | 2 | 2 | 0 | 0.00 | 0 | 1.00 | — |

\* The difference between the best and worst view in the share of changed cells explained by object fates. 0 means
no view explains the change better than another.

"Exact selector" means that some existing ncv2-g2 selector picks exactly the group's objects in every demonstration,
in the best view (coarse groups: one per fate).

## 2. What the observables say

1. **Missing relational selectors are rare.** In 37 of 40 tasks, every change group (the objects that recolour, move,
   are deleted, or change otherwise) has an exact existing selector. *Which* objects change is usually describable.
2. **The 13 object-mismatch tasks change objects in part.** The median share of their changed objects changed only in
   part is 1.00, and no view helps (median view gap 0). The objects to change are selectable, but the change lives
   below the object: in parts, components, interiors or cells. Six of them also have output objects spanning several
   input objects, so grouping is present.
3. **The additive tasks extend lines.** Ray-like additions dominate. There are no fills, copies or mirrors (at the
   median). The cells are added next to objects that are themselves partly changed (0.64).
4. **The 12 object-explained tasks are whole-object changes whose rule was not found.** In 10 of them every group has
   an exact selector, and the right view matters (gap 0.68). This is the class ncv2-g3's joint construction targets:
   the missing piece is the action, its parameters, the composition or the search order.

## 3. Competing explanations and tests that would separate them

### 3.1 Object mismatch (13): a part-level change

| explanation | observable test |
|---|---|
| a component representation is missing (sub-object parts: colour components of multicolour objects, interiors, borders) | re-parse each changed object into candidate components (per-colour components, border vs interior, holes); measure the share of changed cells explained by component fates. A large rise supports this |
| the change is per-cell (local neighbourhoods), not per-object | does a local rule (native pixel rule, or a bounded neighbourhood table) fit, and is it supported across demonstrations (support ≥ 2 per entry)? ncv2-g2 already tried native's pixel rule; a wider neighbourhood is the remaining test |
| the operation exists, but the search never paired it with the right selector | bounded exhaustive single-rule check over the existing language (as `cora_neural_v2.search.exhaustive_single_rule`), with the exact selectors from section 1. If a fit exists, this is a search gap, not a representation gap |
| grouping: the unit is a set of objects | for the 6 tasks with spanning outputs, form candidate groups (same row/column bands, adjacency clusters, enclosures); measure fate explanation at the group level |

### 3.2 Additive (7): line extension

| explanation | observable test |
|---|---|
| a ray variant is missing (stop at an obstacle, change colour on contact, start from a part, or several rays per object) | enumerate bounded ray variants (directions × stop rules × colour rules × start points) and measure the share of added cells each explains on every demonstration |
| the ray exists, but its emitting objects need a relational selector | the one additive task with an unseparable group is the candidate; check separability with relational selectors (alignment, between, facing) |
| search reach | position of the best-explaining ray rule in the existing order, at fixed budgets |

### 3.3 Incomplete relational descriptions (3 tasks with an unseparable group)

| explanation | observable test |
|---|---|
| a missing relation (alignment, betweenness, ordering, facing) | add candidate relational predicates one family at a time; measure separability gained per family on the demonstrations |
| a missing feature (shape class, symmetry, count of a sub-part) | the same test with feature families |

### 3.4 Generator gaps (2): what native's certified programs need (post hoc)

| task | native's certified program | missing from ncv2-g2's pools |
|---|---|---|
| `b2bc3ffd` | `(rule (test color != 8) (translate (scaled up (feature size))))`, view S5 | the selector (only `==` colour tests are generated) and the action (vectors scaled by a feature) |
| `63613498` | `(rule (exists same_shape (test is_contained == #t)) (recolor (color_of (nearest_of_color 5))))`, view S1 | the selector (`exists` over `same_shape` with a feature test) and the action (the `nearest_of_color` reference) |

Test: generate these construct families (non-equality comparisons, feature-scaled vectors, `exists` over every
relation with feature tests) and measure the candidate-set growth they cost and the fits they add on new tasks, not
on these two.

### 3.5 Beyond budget (1)

`74dd1130`: the certified program `(rule (true) (reflect (axis diag_main)))` in view S3 is in ncv2-g2's pools but was
not reached within 40,000 by structural match. **Hypothesis:** ncv2-g2's order puts two-rule programs first when two
kinds of change are observed, which buries a cheap single rule. **Test:** that program's position with the two-first
switch off, and its probe position in ncv2-g3's joint order. The second is engineering only on an exposed task.

### 3.6 Fitting but wrong (2)

`7f4411dc` and `d23f8c26` each had a single fitting reading, which was wrong, and no native certificate.

| explanation | observable test |
|---|---|
| underdetermined demonstrations | continue the search past 3,000 and count distinct fitting readings |
| a memorized parameter | genuine leave-one-out re-derivation of the fitting program (does it survive dropping each demonstration?) |

## 4. What can and cannot be concluded

- **Can:**
  - with the current views and selectors, most real failures are not about choosing which objects change;
  - the largest class changes objects in part, below the current object representation;
  - the second largest is whole-object change where the selector exists but the rule was not found.
- **Cannot:**
  - that these tasks are inexpressible;
  - that any proposed representation would solve them;
  - that ncv2-g3 would solve the 12 object-explained tasks. Testing it on this cohort now would be in-sample.
- **Next evidence** must come from new tasks: a fresh real cohort and new synthetic families
  (docs/NEURAL_CORA_V2G4_REPRESENTATION_AWARE_PROPOSAL.md, section 6).
