# NS Failure Families (Near-Solve Compiler v0: CORA Stage A)

Generated: 2026-08-18. Every number below is reproduced by:

```
python scripts/nearsolve_compiler_v0.py
```

which writes `outputs/nearsolve_compiler/ns_dataset.jsonl` (one semantic
record per near-solve) and `outputs/nearsolve_compiler/family_table.json`
(this table, machine-readable), and prints the table to stdout. The script is
analysis-only: no engine imports, no LLMs, no per-task solvers.

**Corpus**: `outputs/unified_harness_v22/near_solves.jsonl`: 824 records,
config `full_v22`, matching the current 181-sealed engine state. Chosen over
the older v10 corpus (847 records, `full_v6_round6`) because it reflects the
live engine. 333 of the 824 records are backed by rich object-layer parts
(`outputs/unified_harness_v22/object/near_solve_parts/`) carrying the stored
program, residual, and per-fold LOO divergence: including 158 tasks whose
best layer is recorded as geocat but where the object layer ALSO reached a
program (91 of them train-perfect and LOO-failing). These parts-backed
records are the modern analogue of the earlier "269 near-solves" census.

## NS-level histogram (all 824)

| Level | Meaning | Count |
|---|---|---|
| NS-0 | pixel-near (output is a near-copy; no layer engaged) | 102 |
| NS-1 | structural-near (right geocat strategy, wrong cells) | 90 |
| NS-2 | correspondence-near (object matching fails) | 32 |
| NS-3 | program-near (wrong parameter/expression, structure right) | 48 |
| NS-4 | abstraction-near (shape of solution right, DSL cannot express one needed relation) | 157 |
| NS-5 | representation-near (needs different segmentation/view) | 292 |
| UNDET | record lacks structure to decide | 103 |

## 1. Failure-family table (clusters with >= 3 tasks: 21 of 27)

| Family (cluster_key) | Count | NS | Example tasks | Needed abstraction | Expressible today? |
|---|---|---|---|---|---|
| view\|view_change\|shape-change-no-engagement | 234 | NS-5 | 00576224 007bbfb7 017c7c7b | different output view (crop/tile/panel/quotient); no layer engaged and train pairs change grid shape | no |
| pattern\|outside_vocabulary\|extensional-pattern | 111 | NS-4 | 00dbd492 05269061 0962bcdd | generative pattern derivation: grow `pattern` is a literal per-object mask, fold-unstable; must be DERIVED from object features/geometry (PatternExpr is const-only) | no |
| pixel\|unknown\|near-copy | 102 | NS-0 | 025d127b 06df4c85 0e206a2e | sparse-edit view: output ~= input (>=80% pixels) yet no segmentation produced a fitting delta program | unknown |
| structural\|partial\|grid:fill_enclosed_adaptive | 84 | NS-1 | 05a7bcf2 0607ce86 070dd51e | object-level residual rule on top of a structural fill strategy | unknown |
| view\|view_change\|same-shape-no-engagement | 51 | NS-5 | 12eac192 13713586 150deff5 | different segmentation: same-shape task, all variants failed to engage | no |
| copy\|outside_vocabulary\|object-synthesis | 43 | NS-4 | 0a938d79 0e671a1a 0f63c0b9 | object synthesis: output objects with no input counterpart ('copy' deltas); only narrow synth_copy exists: needs copy/spawn-at-relational-position | no |
| structure\|unknown\|fold-unstable | 37 | UNDET | 045e512c 18447a8d 27a77e38 | fold programs disagree structurally across delta families; no census tag decides | unknown |
| matching\|unknown\|low-partial-fit | 35 | UNDET | 09c534e7 1478ab18 14b8e18c | matching stage with train fit < 0.5: not near enough to attribute | unknown |
| correspondence\|relational\|matching | 29 | NS-2 | 03560426 12422b43 1a244afd | explicit relational correspondence (role / shape-twin / positional matching) | unknown |
| selector\|relational\|predicate | 17 | NS-3 | 0b17323b 2a5f8217 2c0b0aff | relational selector predicate (selector search fails outright) | unknown |
| structural\|unknown\|low-fit | 14 | UNDET | 09629e4f 140c817e 28e73c20 | geocat acc < 0.6, no object parts | unknown |
| selector\|relational\|rule-partition | 10 | NS-3 | 342dd610 776ffc46 90347967 | same delta family per fold but objects split into different rules: grouping predicate unstable | unknown |
| parameter\|unknown\|low-partial-fit | 9 | UNDET | 0becf7df 1f642eb9 36fdfd69 | parameter stage with train fit < 0.5 | unknown |
| output_shape\|view_change\|fold-shape-mismatch | 7 | NS-5 | 28bf18c6 72ca375d 73ccf9c2 | output-spec/view must be derived, not induced per fold | unknown |
| eval_error\|unknown\|no-diff | 6 | UNDET | 27a28665 3befdf3e 3d31c5b3 | fold eval errors without program diff or induced map | unknown |
| structural\|partial\|grid:recolor_by_size_rank | 6 | NS-1 | 1b8318e3 50c07299 543a7ed5 | object-level residual rule on size-rank recolor | unknown |
| color\|relational\|derived-color | 5 | NS-3 | 009d5c81 0a2355a6 1d61978c | derived color: induced feature_map/color_map tables miss held-out keys: needs functional generalization (feature_affine or completed family) | unknown |
| multi\|relational\|multi-literal | 5 | NS-3 | 321b1fc6 4364c1c4 a61f2674 | several literal params each need a derived/relational form | unknown |
| copy\|outside_vocabulary\|param-search-fail | 3 | NS-3 | 11e1fe23 c074846d d492a647 | copy-delta parameter search fails: same synthesis gap as object-synthesis | no |
| correspondence\|relational\|context-instability | 3 | NS-2 | 4347f46a 64a7c07e d364b489 | identical program diverges on fold: segmentation/matching context unstable | unknown |
| structure\|outside_vocabulary\|fold-unstable | 3 | NS-4 | 18419cfa 57aa92db e5062a87 | fold structure unstable + census tags place needed rule outside vocabulary | no |

Long tail (< 3 tasks each): grow / translate / paint / composite / recolor
param-search-fail (8 tasks total), multi-slot UNDET (1), selector low-fit (1).

## 2. Cross-task clusters among NS-3/NS-4 (anti-unification candidates)

These are the CORA highest-value case: >= 3 tasks sharing one cluster_key at
program-near or abstraction-near level.

| Rank | Cluster | Tasks | Semantic delta (shared repair) |
|---|---|---|---|
| 1 | pattern\|outside_vocabulary\|extensional-pattern | 111 | `pattern: extensional(literal mask) -> generative(function of object features/geometry)` |
| 2 | copy\|outside_vocabulary\|object-synthesis (+ param-search twin) | 43 + 3 | `count/position: none -> spawn(copy_of(ref), at relational position)` |
| 3 | selector\|relational\|predicate (+ rule-partition twin) | 17 + 10 | `selector: literal/absent predicate -> relational grouping predicate` |
| 4 | color\|relational\|derived-color | 5 | `color: extensional map (missing held-out key) -> functional map (feature_affine / completed family)` |

Coverage: the top-3 abstractions (generative pattern derivation, relational
object synthesis, relational selector/grouping) cover 184 of 205 NS-3/NS-4
records (90%).

## 3. Ranked recommendation vs the queued expression-grammar round

The queued round (from `docs/V22_CENSUS_CANDIDATES.md`) targets POSITIONAL
COLOR (~45 extrapolated) and COLOR INVENTION (~39 extrapolated). The
measured table **confirms the root cause and amends the priority order**:

- **Coincides at the root**: 90% of parameter slots constant-class (v22
  census) is exactly what this compiler sees per-fold: literal parameters
  and literal patterns that do not survive LOO reinduction. Both analyses
  say: replace extensional values with derived expressions.
- **Amends the ranking**: at the *program* level, pure color-slot failures
  are small (5 decided tasks; 0 decided context-conditional-color tasks,
  though structural-tag coverage is only 40 tasks: see limitations). The
  census's positional-color counts came from *residual-cell* analysis; most
  of those tasks land here in the **extensional-pattern** family, because the
  stored program hides position-dependent color inside literal grow masks. A
  derived pattern must specify both cells *and* colors: so
  **pattern-as-function subsumes positional color**. Building conditional
  color expressions alone would leave the mask-derivation gap unsolved.
- **Extends it**: two families the queued round does not cover at all rank
  above color: **object synthesis** (46) and **relational
  selector/grouping** (27). Ray/line extension, the census's build-first
  pick, is now largely IN vocabulary (`ray_until_obstacle`,
  `ray_through_absorbed`, `line_periodic`, `ray_relational` exist in
  `generative.py`): the residual gap is the pattern/selector/synthesis
  triple, not more ray kinds.

**Recommended build order for the expression-language round** (smallest set
covering the most NS-3/NS-4):

1. **Generative pattern derivation** (pattern-as-function; subsumes
   positional color): 111 tasks.
2. **Relational object synthesis** (spawn/copy at relational position,
   derived count): 46 tasks.
3. **Relational selector/grouping predicates**: 27 tasks.
4. Functional map generalization (feature_affine completion; the measured
   remnant of "color invention"): 5 tasks.

Not in scope for the expression round but dominant overall: NS-5 view
families (292 tasks: 234 shape-change + 51 same-shape no-engagement + 7
fold-shape-mismatch): these feed Stage E's view language, and NS-0
near-copies (102) suggest a cheap "sparse-edit view" probe.

## 4. Honest limitations

- **UNDET = 103 / 824 (12.5%)**: 37 structure-unstable LOO records spanning
  different delta families, 45 low-partial-fit parts (train fit < 0.5: in
  the corpus but not "near"), 14 low-fit geocat, 6 eval-error-only, 1
  multi-slot. These were left undecided rather than guessed.
- **Structural-tag coverage is thin**: per-task structural tags exist for
  only 40 tasks (`outputs/structural_vocab_census.json`); the v22 census's
  80-task divergence sample kept only a histogram, not per-task rows. This
  is why the context-conditional-color family decided 0 tasks at program
  level; its members are counted inside extensional-pattern instead.
- **Census corpus mismatch**: `blocker_census_v14.json` per-task blockers
  come from the v14 run; used only as secondary evidence (1 task, 57aa92db,
  decided solely by it; 2 more by vocab-census tags).
- **Pixel residuals are approximate** where only per-pair train accuracy was
  stored: wrong-cell counts are reconstructed as `round((1-acc)*H*W)` per
  pair from ground-truth grid shapes; parts-backed LOO records use stored
  `cells_wrong` where present (often null in the artifact).
- **Corpora skipped**: `unified_harness_v10` (847 records, superseded config)
  and v9: same schema, older engine; using them would double-count tasks
  under stale diagnoses. `meta_m1_residual_patterns.json` (v8-era) was
  consulted but not merged for the same reason.
- **NS-5 for identity fallbacks is corpus-level evidence**: "no segmentation
  variant engaged" is the pipeline's own no-engagement diagnosis; individual
  records carry no program to confirm the needed view.
