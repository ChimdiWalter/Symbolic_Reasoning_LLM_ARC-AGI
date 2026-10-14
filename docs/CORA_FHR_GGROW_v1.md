# G-grow v1: the declared grammar for constructed growth operators (CORA-FHR)

**Status: SPECIFICATION, frozen with the protocol**
(`records/CORA_FHR_PROTOCOL_20261014.md`). Not yet implemented. Any change
after the freeze needs a dated amendment, written before any final-split
run.

## 1. What an operator is

A growth operator maps one object of a scene to the cells it adds:

```
op : (O, G) -> A
  O = the object's cells, with their colours (as native segmented and matched it)
  G = the scene's input grid
  A = op(O, G), with the result restricted to in-grid background cells of G that are not in O
```

**Colour is not part of the operator.** As in `cora_reach`, every instance
must add cells of one colour. Native's own colour-expression candidates
(`inducer._action_candidates`) then decide how that colour is derived.

**Derived quantities** come from O only. Nothing is learned from the
demonstrations as a constant.
- the bounding box (r0, c0, r1, c1), with height h and width w;
- the centre cell: floor of the bbox midpoint;
- for a multicolour object, its minority colour (fewest cells, ties broken by
  the lower colour index) and its majority colour;
- the background: native's `growth.grid_background` of G.

**No cell literal can appear.** Every parameter comes from a finite symbolic
domain: a direction, a stop rule, an axis, a connectivity, or a size-derived
vector. This is `cora_reach`'s "not a cache" condition, true by construction.

## 2. Primitives

### Sources (O, G) → cell set: 10

| id | name | cells |
|---|---|---|
| S1 | `self` | O |
| S2 | `part_minority` | cells of O with its minority colour (empty if single-coloured) |
| S3 | `part_majority` | cells of O with its majority colour |
| S4–S7 | `edge(d)`, d ∈ {N, S, E, W} | cells of O extremal in direction d |
| S8 | `corners` | the 4 bbox corner cells |
| S9 | `centre` | the centre cell |
| S10 | `bbox` | every cell of the bbox |

### Unary transforms, cell set → cell set: 50

| id | name | parameters | count |
|---|---|---|---|
| U1 | `shift(v)` | v ∈ unit(8 directions) ∪ size(N, S, E, W) = (∓h, 0), (0, ±w) ∪ size_gap(N, S, E, W) = (∓(h+1), 0), (0, ±(w+1)) | 16 |
| U2 | `ray(d, stop)` | d ∈ 8 directions; stop ∈ {border, obstacle}; obstacle = the last background cell before a non-background cell not in O | 16 |
| U3 | `reflect(axis)` | outward across a bbox edge (N, S, E, W), or within the bbox about its centre line (H, V) | 6 |
| U4 | `ring(conn)` | conn ∈ {4, 8}: the set's 1-cell neighbourhood minus the set | 2 |
| U5 | `hull` | the bbox of the set, filled | 1 |
| U6 | `interior` | background cells of the set's bbox not 4-connected to the bbox border | 1 |
| U7 | `repeat(v)` | v ∈ size ∪ size_gap (8): iterate `shift(v)` while any shifted cell is in-grid | 8 |

### Binary combinator: 1

`union(X, Y)` of two depth-1 expressions over the **same** source.

## 3. Expressions, bounds and canonical order

| class | form | count |
|---|---|---|
| depth 1 | `U(S)` | 10 × 50 = 500 |
| depth 2 | `U2(U1(S))` | 10 × 50 × 50 = 25,000 |
| union | `union(U_a(S), U_b(S))`, a < b | 10 × C(50, 2) = 12,250 |
| **total, before deduplication** | | **37,750** |

There is no deeper nesting, no unions of depth-2 terms and no unions across
sources.

**Canonical order.** Class (depth 1, then depth 2, then union); then source
id; then transform ids in table order; then parameters in table order. This
is the order of proposal, Occam-first.

**Deduplication.** Expressions are deduplicated by observational
equivalence on the instances being explained. Of the expressions producing
identical added-cell sets on every instance, only the canonically first is
kept. Evaluation is bottom-up: depth-1 results are cached per instance, and
an expression is rejected at the first instance it fails.

**Semantics are total.** An expression that leaves the grid or produces the
empty set is evaluated, not raised. An empty added set never explains an
instance that adds cells.

## 4. The frozen baseline B, and the novelty classes

**B, what frozen CORA can already do**, has two parts:
- **B_native:** the 11 derived GROW modes that native v23 detects under the
  sealed flags, with their own parameter search. These are `growth.GROW_MODES`
  minus the constant `pattern` and minus `fill_holes`, whose detection is
  gated by `ARC_EXPR_GRAMMAR`, which is off natively (`growth.py`, around line
  765). B_native
  explains an instance exactly when native's `detect_grow`, with nothing
  installed, returns a mode other than `pattern`.
- **B_reach:** the frozen `cora_reach` grammar of 9 families and 210
  settings (`cora_reach/construct.py` GRAMMAR).

**Instances.** By definition, every instance FHR explains is one where
native fell back to the constant `pattern`. So no constructed operator is a
renaming of a native mode on its own evidence (reach's separation
condition (i)).

**Novelty class of a constructed operator, on the task's training
instances:**

| class | condition | counts as capability growth? |
|---|---|---|
| AVAILABLE_REACH | some B_reach setting produces the same added cells on every instance | **no** (selection from the existing constructor's grammar) |
| NEW_COMPOSITION | no B_native mode and no B_reach setting explains the instances; built from G-grow primitives | **yes**, as compositional growth (claim level L2) |
| NEW_PRIMITIVE | — | **not claimable here**; G-grow adds no primitive whose semantics lies outside B's geometric vocabulary |

Several G-grow primitives restate B's own primitives (ray, ring ≈ halo,
interior ≈ fill_interior, reflect ≈ mirror, hull ≈ bbox_fill, shift and
repeat ≈ copies). The grammar's new content is which combinations can be
expressed.

## 5. Instance sources by arm (protocol section 4)

| arm | where the instances come from |
|---|---|
| E authentic | native's own `pattern` fallbacks during an identity-frame induction on the demonstrations (`cora_reach/instances.py`, unchanged); grouped per segmentation variant |
| C failure-blind | the demonstrations alone (the `cora_reach.measure.demo_only_propose` rule): objects are the 8-connected non-background components of each input; the operator's added cells, unioned over all objects, must equal exactly the cells that turn from background to non-background, on every demonstration that adds cells |
| D shuffled | arm E's instances from a donor task (the next key in sorted order, cyclic), explained in this task's reasoner |

Limits are those of `cora_reach`, all arms:
- SUPPORT_DEMOS = 2: the instances must come from at least 2
  demonstrations;
- MAX_INSTANCES = 64;
- MAX_PROPOSALS = 8.

## 6. Extension form

An extension has this canonical JSON form:
`{"format": "cora_fhr_ggrow", "version": 1, "expr": <canonical expression>, "name": "fx_" + sha256(body)[:16]}`

- **Loading** rebuilds it from the expression and requires identical bytes,
  as `cora_reach.growth_ext.load`.
- **Rendering** is the G-grow evaluator.
- **Installation** goes through an adapted copy of `cora_reach/bridge.py`
  (same five overlay points, same identity-checked restore). `cora_reach` is
  not mutated, and `geocat_arc` is not edited.
