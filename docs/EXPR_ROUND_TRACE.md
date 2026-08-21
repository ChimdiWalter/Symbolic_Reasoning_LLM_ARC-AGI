# Expression-Grammar Round: TRACE (family #1: pattern-as-function)

Date: 2026-08-20. Phase: TRACE-FIRST (CORA invention round 1, target family
`pattern|outside_vocabulary|extensional-pattern`, 111 tasks). ANALYSIS ONLY -
no engine edits. Script: `scripts/expr_trace_v1.py` (deterministic, no LLMs).
Artifacts: `outputs/expr_round_trace/trace_results.jsonl` (per-task checker
verdicts), `trace_summary.json`, `classification_final.json`. All findings
below were written to those artifacts BEFORE the design section was drafted.

Lockbox discipline (v1.0.0 manifest): only Experience-split tasks were opened.
Promotion/lockbox members of the family were counted by id only and never
read, rendered, or diffed.

## 1. Working set

| | count |
|---|---|
| Family total (ns_dataset cluster) | **111** |
| In Experience split (analyzed) | **69** |
| In Promotion split (ids only, excluded) | 21 |
| In Lockbox split (ids only, excluded) | 21 |

Structure of the 69: all are same-shape tasks (input and output grids equal
size in every train pair), 2-5 train pairs, max grid dim 4-29. All 69 have
object-layer parts in `outputs/unified_harness_v22/object/near_solve_parts/`.

**Stored-program baseline (the diagnosis, measured):** all 69 stored
near-solve programs reach `train_fit_pixels = 1.0` and all 69 fail at
`failure_stage = loo`. Together they carry **196 const-pattern grow rules
holding 7,629 literal mask cells** (single masks up to 448 cells, e.g.
7b6016b9), keyed by `shape_sig`/`color` selectors. The pattern content is
memorized per fold; nothing derives it, so LOO reinduction diverges. This is
the family's defining failure, confirmed task-by-task.

## 2. Exemplars (12, spread across structural sub-shapes)

Selection rationale: cover every major sub-shape found by the checker battery
plus manual rendering: region fills (object-hole / panel / connected
component), keyed stamps, template stamps, periodic completion (repair and
extension), size-derived generative shapes, count-derived repetition,
pairwise-relational patterns, symmetry completion, and one honest
out-of-family reject. All grid renders and diffs used train pairs only.

| Task | Pairs | Stored program (all fit=1.0, all LOO-fail) | True pattern as a function |
|---|---|---|---|
| 00dbd492 | 4 | 4 rules, 2 const masks (32+57 cells) on shape_sig | fill enclosed holes of each square; **color = f(object size)** (area/hw/hole_area all consistent, keys repeat across pairs) |
| 7b6016b9 | 3 | 3 const masks totalling 1,262 cells (!) on color | fill each bg connected component; **color = f(touches_border)** (loop interiors 2, outside 3): fold-coverable |
| 272f95fa | 2 | 2 const masks (72+140 cells) on shape_sig | fill separator panels; **color = f(panel position class)** (center/left/right/top/bottom): fold-coverable |
| 0ca9ddb6 | 3 | 2 rules, 1 const mask on color | fixed local stamp **keyed by object color** (2→corner 4s, 1→plus of 7s, 8→nothing); keys repeat, unknown-key default no-op → LOO-viable |
| 39e1d7f9 | 3 | 3 const masks (48/99/54) | **copy of an in-grid template object** stamped with color bijection (17 id+recolor, 3 id events) |
| 8eb1be9a | 2 | 2 const masks (54+100) on color | **periodic repair/extension**: output invariant under translation (3,0); every changed cell derivable from a clean orbit member of the input |
| 05269061 | 3 | 3 const masks (37/38/43) | **diagonal wallpaper extension**: lattice vectors (0,3)+(3,0)/(1,-1); whole grid derived from the seed band |
| c97c0139 | 2 | 3 const masks (32/84/8) on relational selectors | **pyramid/diamond off each bar, size = f(bar length), orientation = f(bar axis)**: size-derived generative shape |
| fcc82909 | 3 | 3 const masks (16/10/10) | block of 3s directly below each object, width = object width, **height = number of distinct colors in the object**: count-derived repetition |
| 5ad8a7c0 | 5 | 3 rules, 2 const masks (4+4) on shape_sig | **connect same-color dot pairs**: fill the segment between aligned dots: pairwise-relational, not per-object |
| 2bcee788 | 4 | 4 const masks (~96 cells each) on color | **mirror-completion** of the partial shape across its marked axis + global bg recolor to 3 |
| 4093f84a | 3 | 3 const masks (7/9/11) on shape_sig | HONEST REJECT: dots **move** to rest against the wall (input cells vacated). Movement, not pattern derivation: misfiled into this family by the compiler |

## 3. Functional-form classification of all 69 (from checker battery + renders)

Checkers requiring EXACT reproduction of the ground-truth changed-cell set
(cells and colors) on ALL train pairs:

| Family | n | Tasks (abbrev) | LOO-derivable mechanism? |
|---|---|---|---|
| REGION_FILL, checker-verified | 6 | 00dbd492 272f95fa e9c9d9a1 7b6016b9 83302e8f e73095fd | yes: region computed per input, color = f(region feature), feature→color maps fold-coverable |
| REGION_FILL variants (selector / ordinal / legend / band / bbox / outline) | 15 | 941d9a10 a8d7556c 575b1a71 aa18de87 62ab2642 8fbca751 60b61512 1bfc4729 7447852a b7fb29bc 99306f82 94414823 5adee1b2 928ad970 2bee17df | yes in principle; needs region selectors (size predicate), ordinal color sequences, legend color-maps, distance-bands, bbox/bbox-complement regions |
| TEMPLATE_STAMP, checker-verified (D4 + color bijection) | 3 | 39e1d7f9 7e0986d6 fe45cba4 | yes: template is an in-grid object, per-input |
| TEMPLATE_STAMP variants (panel copy, marker anchor, self-mirror/rot) | 8 | 9f27f097 8e5a5113 1e32b0e9 7df24a62 88207623 93b581b8 760b3cac f35d900a | yes in principle; needs panel-as-template, marker anchors, self-as-template |
| PERIODIC_EXTEND, checker-verified | 2 | 05269061 8eb1be9a | yes: lattice derived per input |
| SEQUENCE_EXTEND_1D (line/row sequences, cyclic legends) | 5 | e21d9049 bd4472b8 8403a5d5 62b74c02 a57f2f04 | yes in principle; 1D periodic extension along lines/inside regions |
| SYMMETRY_COMPLETE (+recolor) | 2 | 1b60fb0c 2bcee788 | yes in principle; symmetry closure with recolor of completed cells |
| KEYED_STAMP f(color)→literal stamp, LOO-viable | 1 | 0ca9ddb6 | yes, but only 1 task: COINCIDENCE-RISK as a primitive |
| SIZE_DERIVED_SHAPE (ramp/pyramid/dilate/count-derived) | 6 | c97c0139 a65b410d 0962bcdd fcc82909 1f0c79e5 3bd67248 | needs shape constructors parameterized by object size/orientation/color-count |
| RAY_PROJECTION (apex/corner/marker rays, beams) | 4 | 25d487eb ec883f72 6bcdb01e 78e78cff | partially in vocabulary already (ray_* in generative.py); anchor/direction derivation missing |
| CONNECT_RELATIONAL (pair connect, between-fill, midpoint, separator line, cluster halo) | 7 | 5ad8a7c0 d6ad076f e9614598 22233c11 770cc55f da2b0fe3 b27ca6d3 | pairwise object relations: overlaps the relational-selector family (#3) |
| OUTSIDE: path/dynamics (pathfinding, bouncing) | 4 | 2dd70a9a bf89d739 aa300dc3 f9a67cb5 | no: not expressible as an object-feature pattern function; reject honestly |
| OUTSIDE: movement (gravity/move-to-contact) | 2 | 4093f84a 67c52801 | no: these are translate deltas misfiled as grow-pattern |
| UNCLEAR | 4 | 4cd1b7b2 95755ff2 7e02026e 712bf12e | left undecided rather than guessed |

## 4. Falsification results (exact, all pairs, all exemplars per form)

Per-task verdicts are in `outputs/expr_round_trace/trace_results.jsonl`.

**Form A: REGION_FILL(region, color=f(region_feature))**: VERIFIED.
Exact pass on all pairs of 6 tasks (≥2-task bar met):
- 00dbd492: INTERIOR_FILL passes (both segmentations); color fn consistent under area / hw / hole_area / hole-shape, repeated keys across pairs.
- 272f95fa, e9c9d9a1: REGION_FILL_PANELS passes; `panel_pos_class → color` fold-coverable in both.
- 7b6016b9: REGION_FILL_CONNECTED passes; `touches_border → color`, fold-coverable, 2 keys.
- 83302e8f: REGION_FILL_CONNECTED passes; `is_rect → color`, fold-coverable.
- e73095fd: REGION_FILL_CONNECTED passes; `rect_hw → color` (fold coverage marginal: feature choice needs the enclosure predicate, listed as variant work).
Fail (honest): 941d9a10 (color is ordinal along a diagonal walk, not a panel-index function), a8d7556c (only holes above a size threshold filled: needs region selector), b7fb29bc/99306f82 (multicolor = distance-band fill), 83302e8f-style predicate needed elsewhere. These fails are what the variant list in §3 itemizes.

**Form B: TEMPLATE_STAMP(in-grid template, D4 transform + color bijection)**: VERIFIED.
Exact pass on all pairs of 3 tasks: 39e1d7f9 (id+recolor ×17, id ×3), 7e0986d6 (id+recolor ×28), fe45cba4 (id ×2, id+recolor ×2). Plain TEMPLATE_COPY (no transform) already passes fe45cba4/7e0986d6/39e1d7f9: the bijection extension is what 39e1d7f9 needs. Fail (honest): 9f27f097, 8e5a5113, 88207623: the template is a panel or an adjacent-merged object, not a clean segmented object; classified as variants, not counted as verified.

**Form C: PERIODIC_EXTEND (translation-lattice closure, orbit-derivable from input)**: VERIFIED.
Exact pass on all pairs of 2 tasks: 8eb1be9a (vector (3,0); also passes the stricter PERIODIC_REPAIR), 05269061 (vector pairs (0,3)+(3,0)/(1,-1)). Fail (honest): 62b74c02 (tiling is edge-anchored with a mirrored right boundary: not pure translation), e21d9049/bd4472b8 (sequences live on 1D lines, grid-global invariance fails) → SEQUENCE_EXTEND_1D variant family.

**Form D: KEYED_STAMP (literal relative stamp = f(object key)): REJECTED as the general repair.**
This form is the closest formalization of what the stored programs already do.
Extensionally it passes 44/69 tasks (REL_STAMP checker, best key). But graded
for LOO evidence:
- **34/44 passes are VACUOUS**: every key occurs once, the "function" is a per-object memo. COINCIDENCE-RISK by construction.
- 6/44 have repeated keys but fold-breaking non-empty stamps (0962bcdd 25d487eb 99306f82 9f27f097 bd4472b8 ec883f72): LOO reinduction still fails, matching the recorded engine failure.
- **Exactly 1/44 (0ca9ddb6) is LOO-viable** (repeated keys, all fold-breaking keys have empty stamps, "unknown key → no-op" default). Single task ⇒ COINCIDENCE-RISK as a primitive; keep only as a degenerate case of Form B (template = stored key-indexed stamp) or a tiny FeatureMap production.
This is the central measured finding: **replacing const masks with keyed literal masks would fix ~1 task. The pattern content must be computed per input (region / template / lattice), not looked up.**

Strict HALO and BBOX_OUTLINE ring forms: 0/69 exact passes: outline events in
this family always come with legends, selectors, or derived boxes; falsified
as standalone forms.

## 5. Verified forms ranked by task coverage

| Rank | Verified form | Exact now (Experience) | Reachable with listed variant extensions | Extrapolated on 111 |
|---|---|---|---|---|
| 1 | REGION_FILL + color=f(region feature) | 6 | +15 = 21 | ~34 |
| 2 | TEMPLATE_STAMP (D4 + bijection, anchors) | 3 | +8 = 11 | ~18 |
| 3 | PERIODIC/SEQUENCE/SYMMETRY EXTEND | 2 | +7 = 9 | ~14 |
|: | KEYED_STAMP literal | 1 | 1 | coincidence-risk |
|: | SIZE_DERIVED_SHAPE / RAY / CONNECT | 0 verified | 17 characterized | later rounds (overlap w/ synthesis + selector families) |
|: | OUTSIDE + UNCLEAR |: | 10 | honest rejects |

Verified-exact coverage today: 12/69 (17%). Reachable with the three verified
forms plus their itemized variants: 41/69 (59%). The remaining 28 split into
size-derived/ray/connect (17, shared with families #2 and #3 of the round) and
rejects/unclear (10, and 0ca9ddb6 counted above).

## 6. DESIGN RECOMMENDATION (typed grammar productions: NOT generator modes)

The three verified forms all share one property the current DSL lacks: the
pattern is **computed from the input at apply time** (region decomposition,
in-grid template, lattice closure), so LOO reinduction is stable by
construction. Recommended typed productions for PatternExpr (replacing
const-only):

New types: `Region`, `Template`, `Xform`, `Lattice`, `FeatureMap[K→Color]`.

```
PatternExpr := FillRegion(RegionExpr, ColorExpr)
             | StampTemplate(TemplateExpr, XformExpr, AnchorExpr)
             | ExtendLattice(LatticeExpr, DomainExpr)

RegionExpr  := ObjectHoles(Obj)                      -- 00dbd492, a8d7556c(+size pred)
             | PanelAt(PanelIndexExpr) | PanelsWhere(PanelPred)   -- 272f95fa, e9c9d9a1
             | BgComponentsWhere(RegionPred)         -- 7b6016b9, 83302e8f, e73095fd
             | BBoxOf(Obj) | BBoxComplement(Obj)     -- 60b61512, 8fbca751
             | DistanceBand(Region, IntExpr)         -- b7fb29bc, 99306f82

RegionPred  := touches_border | is_rect(h,w) | area cmp k | enclosed
ColorExpr   += FeatureMap(RegionFeature | ObjFeature → Color)   -- induced as a
               TABLE but certified only when every fold's keys are covered by
               the remaining pairs (fold-coverability is a certificate field,
               measured here to be the exact discriminator)
             | LegendMap(legend_obj)                 -- 5adee1b2, 99306f82

TemplateExpr := ObjWithRole(unique-shape | unique-color | marked | self)
XformExpr    := D4 element × ColorBijection(induced per stamp)
AnchorExpr   := marker positions | panel origins | offset f(obj.h, obj.w)

LatticeExpr  := translation vectors derived per input (validated by
                orbit-consistency on the input, as in the checker)
DomainExpr   := whole grid | Region
```

CORA discipline (plan idea #6): these are grammar PRODUCTIONS to be composed
and searched with **semantic dedup before any depth increase**: two candidate
programs are equivalent iff they induce the same changed-cell function on the
train inputs (the trace checkers are exactly this evaluator; reuse them as the
e-graph's semantic hash). Do NOT add `region_fill` / `template_stamp` as new
hand-written generator modes with their own literal parameters: that
reproduces the extensional failure one level up (the measured fate of Form D).

Falsification protocol for the build phase: a production is accepted only via
the unchanged LOO gate on Experience tasks, then earns transfer status on
Promotion tasks per `docs/LOCKBOX_PROTOCOL.md`. The 21 Promotion members of
this family remain unopened until then.

Honest limits of this trace: 4 tasks UNCLEAR (left undecided); 6 tasks are
movement/path deltas misfiled into the family (compiler mislabel, worth a
compiler fix note); manual family assignments for the 47 non-checker-verified
tasks are characterizations from renders, not certified fits: only the 12
checker-verified tasks carry exact all-pair evidence.
