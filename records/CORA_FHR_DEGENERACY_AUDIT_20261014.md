# CORA-FHR generator semantic-degeneracy audit (2026-10-14, DEVELOPMENT)

**Question** (user directive "FINAL SURGICAL INTEGRITY CHECK", item 2). D3's planted rule is
`union(ring(8)[part_minority], hull[part_minority])`, but `_shape()` gives each object one minority
cell. Does the planted rule collapse to `ring(8)[part_minority]`, the witness's constructed operator?

**Code and outputs.**
- `cora_fhr/degeneracy_audit.py`, which writes `outputs/cora_fhr/degeneracy_audit.json`.
- The test `tests/test_fhr.py::test_d3_planted_union_collapses_to_the_constructed_operator`, which
  passes.

## Verdict: CONFIRMED. D3 is semantically degenerate

**Proof.**
- `_shape(two_colour=True)` recolours exactly one cell. In a 2-cell object the 1–1 colour tie also
  gives a one-cell minority part.
- `hull` of one cell is that cell. It is occupied, so `finalize()` (`cells & free`) removes it.
- Hence `union(ring8, hull)[S] = ring8[S]` on every D3 object.

| check | result |
|---|---|
| stored dev corpus (`c4_dev_v2`): all 5 D3 tasks, 20 pairs including the tests, 31 objects | every object has 1 minority cell; planted = constructed on 31 of 31; the hull branch adds 0 cells; the planted rule reproduces 20 of 20 recorded outputs |
| generator test (300 fresh D3 scenes, at least 100 objects) | one minority cell and planted = constructed = recorded, on every object |
| canonical search over 60 pooled D3 instances | the first fitting expression is the single-step `ring(8)[part_minority]`, with 15 fitting expressions in all |
| 1,000 perturbed objects with 2–4 minority cells | constructed ≠ planted on **81** (k=2: 33/684; k=3: 33/247; k=4: 15/69). The hull adds a free cell outside the 8-ring, e.g. minority cells at (2,2) and (4,4) add (4,2) |

## Corrected witness claim (dev_D3_04)

**Preserved:**
- frozen CORA fails;
- CORA constructs `ring(8)[part_minority]`, absent from the native modes and from `cora_reach`
  (perturbation novelty: native 7/300, best reach setting 8/300);
- the native gate plus 3/3 fold-local rebuilds hold;
- the unseen test is correct;
- removing the extension removes the gain;
- the run is deterministic.

**Corrected:** this is construction of a missing **single-step composition** (a declared source × a
declared transform). It is **not** recovery of a nontrivial two-operation union. The task never required
the union.

**Generalization caveat:** on objects with several minority cells, the constructed operator and the
planted rule disagree on 8.1% of perturbations.

## Other families (pooled generator samples, about 60 instances per parameter setting; seeds 500000+, outside every split; the sealed final split was neither generated nor read)

| family | settings | verdict |
|---|---|---|
| D1, F1 | 4 + 4 | none |
| D2 | 4 | same-depth alias only: `shift(unit,d)[reflect(d)[self]]` = `reflect(d)[shift(unit,opp d)[self]]` |
| **D3** | 1 | **SEMANTIC COLLAPSE** to `ring(8)[part_minority]` |
| F2 | 4 | none (one same-depth alias) |
| F3, F5 | 4 + 4 | same-depth aliases (F5: shift and ring commute) |
| F4 | 28 | 19 none, 9 same-depth aliases |
| **S** | 1 | **SEMANTIC COLLAPSE**: `ring(8)[hull[self]]` = `ring(8)[bbox]`. This is definitional (bbox = hull of self). S is the reach-only control, so its role is unaffected; describe it as single-step |

**Consequences.**
- Same-depth aliases predict identically and do not trigger tie abstention.
- The four final families (F1, F2, F4, F5) show no collapse.
- The final split stays sealed and unmodified.
- D3 should be described as a single-step family wherever D3 complexity is cited.

Materials corrected in the same commit:
- the poster witness item and the abstract;
- explainer panel 8;
- paper section 8.20;
- the dev results record;
- the evidence record, section 16;
- the demo README scope note.

The demo's hash-pinned `data/task.json` keeps the planted string.
