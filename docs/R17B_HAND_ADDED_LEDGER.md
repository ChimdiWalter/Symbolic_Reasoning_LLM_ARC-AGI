# R17b Hand-Added Ledger (Stage-2 E10 ground truth)

Ground truth for the E10 rediscovery experiment: every generator mode
hand-added in R17b, the exemplar trace that motivated it, and exact
parameterization. Stage 2's miner must rediscover these BLIND from
residual data alone.

## Modes added

### 1. intersection_color (GenerativeProgram field)

- **Exemplar**: 23581191
- **Trace**: Two single-cell objects (color 8 at varying positions,
  color 7 at varying positions) each emit a cross_line (full row +
  column) with their own color. At the TWO cells where the cross_lines
  intersect (where 8's row meets 7's column and vice versa), the output
  color is 2 — a CONSTANT not derived from either source color by any
  arithmetic rule (8+7=15, 8-7=1, 8^7=15, min=7, max=8; none = 2).
  Color 2 is consistent across both training pairs.
- **Residual motivating it**: per-color cross_line program with any
  painter's order produces EITHER 7 or 8 at the two intersection cells,
  never 2. The residual is exactly 2 cells per pair, always at the
  cross-line overlap, always needing color 2.
- **Parameterization**: `GenerativeProgram.intersection_color: int` —
  after all generators paint, cells painted by generators from objects
  of DIFFERENT source colors get repainted with this value.
- **Date**: 2026-08-07

### 2. ray_through_absorbed (generator kind)

- **Exemplar**: 05a7bcf2
- **Trace**: Each color-4 object emits a ray toward a color-8 wall
  (vertical or horizontal). The ray uses the source color (4) for cells
  between the object and the wall, then absorbs the wall's color (8) and
  continues to the grid border. Additional task mechanics (source
  recolor 4->3, color-2 boundary pushed to grid edge, relational
  direction perpendicular to wall) are NOT captured by this mode.
- **Residual motivating it**: existing ray modes either stop at the
  obstacle (ray_until_obstacle) or go to the border with a fixed color
  (ray). Neither produces the two-segment color pattern. The absorbed
  mode captures the color-transition at the obstacle.
- **Parameterization**: `{"kind": "ray_through_absorbed", "direction":
  str, "color": int, "bg": int}` — ray from source cells in direction,
  using `color` until first non-bg cell (obstacle), then using the
  obstacle's color from that point to the grid border.
- **Note**: 05a7bcf2 is NOT fully solvable with this mode alone. The
  full task requires relational direction (perpendicular to wall, which
  varies between training pairs) and a boundary-push mechanism. This
  mode is nevertheless a well-motivated vocabulary item with a clear
  exemplar trace.
- **Date**: 2026-08-07

## Modes NOT added (trace-first rule)

### 05a7bcf2 — relational direction + boundary push

- **Status**: not yet nameable
- **Why**: the ray direction is relational (perpendicular to the 8-wall,
  varying between pairs: right for vertical wall, down for horizontal).
  The generative framework uses fixed direction parameters per program.
  The 2-boundary push (shifting boundary cells to the grid edge, count
  preserved per line) has no generator equivalent. Both would require
  structural framework extensions, not vocabulary items.

### Trace-first sweep residuals (32 unsolved fused tasks)

Sweep date: 2026-08-07. 32 unsolved tasks (excluding 178fcbfb solved,
05a7bcf2 and 23581191 analyzed above). Zero additional inducer solves.
7 tasks at 100% per-object partial coverage (generators exist for each
object individually but the assembler fails to combine them).

**Top 5 closest tasks, with nameable-mode analysis:**

1. **0e671a1a** (100% coverage, 4 pairs): Three single-cell dots
   (colors 4, 3, 2) produce L-shaped paths (Manhattan path) connecting
   pairs with color 5. Requires RELATIONAL DESTINATION (each path goes
   to another dot). Not a per-object generator -- per-object generators
   propose cross_line which is too broad. Not yet nameable: the path
   destination is relational, varying per pair.

2. **508bd3b6** (100% coverage, 3 pairs): Diagonal dots (color 8)
   with a rectangular wall (color 2). Output adds diagonal ray segments
   (color 3) that BOUNCE off the wall. Requires DIAGONAL DIRECTIONS
   (45-degree), which the current _UNIT vocabulary does not include.
   Not yet nameable: needs non-cardinal direction support.

3. **6ffe8f07** (100% coverage, 4 pairs): Rectangular objects (colors
   1, 2, 8) where the central 8-object emits cross_line-like extensions
   (color 4) that STOP at the edges of other rectangular objects. This
   is a BOUNDED CROSS_LINE (cross_line + ray_until_obstacle hybrid).
   Borderline nameable but the stopping rule depends on the combined
   footprint of other objects, not a single obstacle. Not added under
   trace-first: requires obstacle-set-aware stopping.

4. **a2fd1cf0** (100% coverage, 3 pairs): Two single-cell dots (colors
   2 and 3) connected by L-shaped path (color 8). Same mechanism as
   0e671a1a but 2 dots instead of 3. Not yet nameable: relational
   destination.

5. **a64e4611** (100% coverage, 3 pairs): Large grids with scattered
   non-zero cells. A contiguous rectangular void (all-0 region) is
   filled with color 3. Not a per-object generator at all -- it's a
   GRID-LEVEL void detection + fill. Not yet nameable within the
   generative framework.

**Additional 100%-coverage tasks (d4a91cb9, e7639916)**: similar
L-path or fill patterns. No clearly nameable per-object generator
emerged from any of the 32 tasks.
