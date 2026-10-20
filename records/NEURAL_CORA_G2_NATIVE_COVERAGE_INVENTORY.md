# Neural-CORA G2: native coverage inventory, what ncv2-g1 exposes and omits, and the parity evidence (20 October 2026)

**What this is.** An inventory of what native CORA v23 executes, read from its own registries
(`cora_neural_v2/inventory.py`: `native_inventory()`, `scan_action_params()`) and from its single executor
`render_program` (`geocat_arc/object_reasoning/actions.py:878`). Each construct is mapped to its ncv2-g1 op, with the
exact parity tests behind it.

Native CORA is unchanged: its aggregate sha256 is `18060dbc…`, equal to the v1 freeze. Nothing in this record is a
new primitive. **ncv2-g1 surfaces constructs native already implements.**

**Parity evidence:**

| suite | what it checks | result |
|---|---|---|
| `tests/test_neural_cora_v2_ast.py` (frozen with G2) | 32 programs, each against a hand-written native dict | 46 tests pass |
| `tests/test_neural_cora_v2_parity.py` (new) | 39 more programs, an inventory-coverage check, and the semantics in section 3 | 61 tests pass |
| `scripts/neural_cora_v2_parity_bench.py` | 71 programs on all 200 demonstration inputs of the 60 exposed dev60 tasks, AST-compiled vs hand-written native | 14,200 executions; **0 mismatches**; 4,247 changed outputs; 1,582 identical native EvalErrors; 25.8 CPU-s. Every program changes at least one real grid |

The benchmark reads demonstration inputs only, with no search, no fitting and no answers. It is parity evidence, not
G2.

## 1. How native executes an object program (from `render_program`)

1. Segment the input under the program's view (S1–S7).
2. For **each object, in segmentation order**, take the **first** rule whose selector matches; otherwise the
   default action.
3. Each action returns the object's output pieces, and they are appended to one canvas **in object order**.
   Later pieces paint over earlier ones.
4. Render per the output spec:
   - `same_as_input`;
   - `crop` (a region, or the region a `crop_to` action set);
   - `constant_shape` (H, W, a background colour).
5. A ComposedProgram (`seq`) re-segments each stage's output.
6. An expression that is undefined on an input raises EvalError, and the attempt fails.

## 2. Native constructs and their exposure in ncv2-g1

### 2a. Actions (native delta types)

| native delta (params read by its apply function) | ncv2-g1 op(s) | exposed | parity |
|---|---|---|---|
| keep, delete | `keep`, `delete`, defaults | yes | ast:default_delete, and_in_set |
| translate(vector) | `translate` + 10 vector forms | yes | ast + parity:translate_const, vector_to, gap_closing, reflect_across, … |
| recolor(color) | `recolor` + 7 colour forms | yes | ast:recolor_const, color_map, … |
| copy(targets, align / offsetNN / period / rayNN; **k, placement, keep_original**) | `copy_targets`, `copy_offsets`, `copy_period`, `copy_rays` | partly: **k-mode, placement and keep_original are not exposed** | ast:copy_* |
| move_to(position) | `move_to` | yes | parity:move_to |
| move_until_adjacent(direction, target) | `move_until_adjacent`, `move_until_adjacent_to` | yes | ast + parity |
| scale(factor) | `scale` | yes | ast:scale |
| reflect(axis, vector) | `reflect`, `reflect_shift` | yes | ast + parity |
| rotate(angle, vector) | `rotate`, `rotate_shift` | yes | ast + parity |
| paint(source) | `paint` | yes, including multicolour results | parity:paint_ref, paint_multicolour |
| copy_part(window, placement) | `copy_part` | yes | parity:copy_part |
| extract_part(source, transform_k, transform_flip, placement) | `extract_part` | yes | parity:extract_part |
| connect(target, color, **turn**) | `connect` | partly: **turn is not exposed** | ast:connect |
| fill_line(axis, color, extent) | `fill_line` | yes | ast:fill_line |
| crop_to(region, **tile_h, tile_w**) | `crop_to` + `crop_by_action` | partly: **tiling is not exposed** | ast:crop_by_action, parity:separator_block_self |
| composite(`i:delta:param` …) | `composite` (ordered; nested and parameterless parts rejected) | yes | ast:composite, binding_inlined; parity: order tests |
| **grow**(axis, color, conn, direction, hole_map, length, mode, pattern, vector) | — | **no**: many modes with mode-specific parameters | rejected (`test_not_exposed_constructs_are_rejected`) |
| **synth_copy**(color, placement, verb) | — | **no**: it depends on the frozen learned-verb asset | rejected |

### 2b. Expressions (native grammars)

| class | native ops | ncv2-g1 | not exposed |
|---|---|---|---|
| PredExpr | true, test, and2, in_set, relation_exists | all | — |
| RefExpr | self, nearest_object, nearest_object_of_color, container, contained, largest, unique, nearest_shape_twin, **matched_template** | all but one | matched_template (needs a correspondence-bound template) |
| ColorExpr | const, color_of, most_common_color, least_common_color, color_map, feature_map, feature_affine | all | — |
| VecExpr | const, vector_to, vector_to_border, gap_closing_vector, scaled_unit, step_toward, slide_vector, align_vector, mirror_vector, reflect_across | all | — |
| ScalarExpr | const, size, feature, count, hole_count | all | — |
| RegionExpr | bbox_self, bbox, grid_quadrant, separator_cell, separator_block_self | all | — |
| Axis, Angle, Direction, Align | const | all | — |
| FreeSlotExpr, GrowModeExpr, PatternExpr | library holes; grow-only | — | all three (ncv2 has its own typed holes) |

`test_every_exposed_action_and_expression_op_has_a_parity_case` enforces that every exposed op appears in a parity
case.

### 2c. Relations, features, program classes, output modes

- **Relations (12 native, all accepted by g1):**
  - parity-exercised: adjacent, inside, contains, left_of, right_of, above, below, same_color, same_shape,
    same_shape_normalized (equal up to rotation: it fires on a rotated twin where same_shape does not), same_size;
  - **overlaps** is accepted but not exercised. Objects of one segmentation never share cells, so no change was
    observed.
- **Features:** 36 registered native features, all usable in `test`, with names checked by the type checker.
  Exercised: color, size, size_rank, is_multicolor, touches_border, has_hole, is_line. The others are reachable but
  not individually parity-tested.
- **Program classes:**
  - object and composed: exposed;
  - reduction (pixel rules, symmetry completion, counting), framed (dihedral frames), overlay, generative,
    computed_pattern, erase_patch: **not exposed**.
  - On dev60, native's demonstration-fitting programs came from object or composed programs on 30 tasks, reduction
    on 3 and generative on 2 (G2 protocol §2).
- **Output modes:** same_as_input, crop and constant_shape are exposed. The spec's `fill` (a ColorExpr frame) is
  **not exposed**.

## 3. The addendum's checklist

| requirement | status in ncv2-g1 | evidence |
|---|---|---|
| object selection; views | 7 native views; exact view-equivalence collapse in search | ast, search tests |
| part selection; local vs whole-object | **part operations** via `copy_part` / `extract_part` over bbox windows. **No part-level selector**: native ObjectProgram selects whole objects of a view | parity:copy_part, extract_part |
| references: nearest, matching colour / shape / size | `nearest(PRED)`, `nearest_of_color`, `unique(test color/size …)`, `shape_twin`, same_* relations | ast + parity |
| containment, adjacency | `container`, `contained`; `exists inside / contains / adjacent`; `move_until_adjacent` | ast + parity |
| relative position | `exists left_of / right_of / above / below`; `vector_to`, `align_to`, `gap_closing` | parity |
| symmetry | `mirror`, `reflect_across`, `reflect`. **Grid-level symmetry completion is a native ReductionProgram, not exposed** | parity |
| component correspondences | `shape_twin` only. **matched_template is not exposed** | parity:shape_twin |
| guard (WHERE) vs operation (WHAT) | the guard compiles into the selector only; the same action under two guards acts on exactly the guarded objects | `test_guard_is_where_and_action_is_what` |
| movement, copy, connect, reflect, rotate, crop, scale, delete, paint, recolour | all exposed (copy without k / placement; connect without turn) | ast + parity |
| **grow** | **not exposed** | rejected by the type checker |
| multicolour outputs | `paint` from a multicolour source (view S3) gives one object two colours | `test_multicolour_output_via_paint` |
| output dimensions | crop (region; crop_by_action) and constant_shape give exact sizes | `test_output_dimensions` |
| overlap and occlusion | **characterized**: drawing follows native object order, so a later object occludes an earlier one, whichever moved; a copy draws with its source object | `test_occlusion_follows_native_object_order` (7 cases) |
| ordered actions | composite parts apply in order, and a later part's expressions see the earlier part's result | `test_composite_parts_apply_in_order_on_the_transformed_object` |
| first-match / branch precedence | an object matching two rules gets the first rule's action | `test_first_match_precedence` |
| default action | applies to every unmatched object | `test_default_action_applies_to_unmatched_objects` |
| named multi-step functions | typed, hygienic macros (sugar over native ops); `seq` stages re-segment the previous output | ast:macro; `test_stages_resegment_the_previous_output` |
| expression composition | nested references and `rule_with` binding (exact substitution) | ast:binding_inlined, color_of_ref, … |
| bounded loops / recursion | **not exposed**. Native has no general loop; bounded repetition exists only as copy_period / copy_rays and `seq` | `(repeat …)` rejected |

**Semantic facts worth knowing** (they affect any generator or neural proposer):
1. Occlusion follows object order, not colour or motion.
2. `most_common_color` and `least_common_color` count **objects** per colour, not cells, and ties go to the smaller
   colour (`expressions.py:558`).
3. In a render region, `self` evaluates against native's grid anchor. On the test grid GD, `(crop (bbox (self)))`
   crops to the frame's 3×3 box.

## 4. What parity does and does not show

**It shows:**
- the typed AST compiles to exactly the native program a researcher would write;
- that program runs identically on hand-built and real ARC grids, failures included.

**It does not show:**
- that ncv2-g1 can express real tasks: G2 (frozen, awaiting authorization) measures demonstration-fit reach and
  correct predictions;
- that search finds what the language can express: the G2 exhaustive single-rule diagnostic separates the two for
  single rules.

## 5. Next exposure increments

Proposed only. Each needs a new grammar version, its own parity tests, and none starts before G2 runs:
1. grow modes;
2. copy k-mode, placement and keep_original;
3. connect turn;
4. crop_to tiling;
5. the spec fill;
6. matched_template, which needs a correspondence binding;
7. native program classes: reduction (symmetry completion, pixel rules, counting), framed, overlay and generative.
   The dev60 native fits suggest these matter on 5 of 35 fitted tasks.
