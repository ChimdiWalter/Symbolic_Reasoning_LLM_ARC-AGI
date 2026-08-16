# Structural Vocabulary Candidates

Generated: 2026-08-13 07:22
Sample: 40 tasks (29 LOO-fail + 11 vocab-blocked)

## Raw Cluster Histogram (co-occurring tags)

| Rank | Category | Subcategory | Tasks | Exemplars |
|------|----------|-------------|-------|-----------|
| 1 | conditional | neighborhood_conditional | 32 | 692cd3b6, 95755ff2, 5c0a986e |
| 2 | position | connector_between_objects | 26 | 692cd3b6, 95755ff2, 575b1a71 |
| 3 | color | color_function_of_context | 25 | 692cd3b6, 95755ff2, 5c0a986e |
| 4 | count | varying_object_count | 23 | 95755ff2, e21a174a, 575b1a71 |
| 5 | position | extensional_pattern | 15 | 95755ff2, 5c0a986e, 575b1a71 |
| 6 | color | novel_color_in_output | 14 | 692cd3b6, 575b1a71, 292dd178 |
| 7 | position | extension_beyond_objects | 14 | 692cd3b6, 95755ff2, 5c0a986e |
| 8 | shape | shape_hash_selector | 11 | 95755ff2, 5c0a986e, 575b1a71 |
| 9 | color | constant_color_param | 8 | 54d82841, 31adaf00, fcc82909 |
| 10 | position | rectangular_fill | 5 | 692cd3b6, fc754716, d56f2372 |
| 11 | shape | symmetric_divergence_v | 4 | e21a174a, fc754716, 9b30e358 |
| 12 | shape | symmetric_divergence_h | 3 | 95755ff2, fc754716, 9bebae7a |
| 13 | position | full_col_divergence | 1 | fc754716 |
| 14 | position | full_row_divergence | 1 | fc754716 |

NOTE: Heavy co-occurrence inflates the top rows. The "neighborhood_conditional"
tag fires on 80% of tasks because most divergent cells have varying local
context. The PRIMARY BLOCKER analysis below deduplicates by assigning
each task to its root structural cause.

## Primary Blocker Histogram (de-duplicated)

Each task assigned to its single highest-priority structural gap.

| Rank | Primary Blocker | Tasks | % | Exemplars |
|------|-----------------|-------|---|-----------|
| 1 | extensional_pattern | 15 | 43% | 95755ff2, 5c0a986e, 575b1a71 |
| 2 | connector_between_objects | 9 | 26% | 292dd178, 465b7d93, 321b1fc6 |
| 3 | extension_beyond_objects | 6 | 17% | 692cd3b6, d56f2372, 41e4d17e |
| 4 | no_divergence | 5 | 14% | 0ca9ddb6, 4c5c2cf0, 2c0b0aff |
| 5 | color_function_of_context | 2 | 6% | e21a174a, f3e62deb |
| 6 | full_row_divergence | 1 | 3% | fc754716 |
| 7 | constant_color_param | 1 | 3% | 54d82841 |
| 8 | shape_hash_selector | 1 | 3% | fea12743 |

(Denominator for %: 35 tasks with real divergence)

## Top 5 Named Candidates

### 1. EXTENSIONAL PATTERN (15 tasks, 43%)

The program stores a literal pixel-by-pixel pattern (e.g., grow with mode=pattern
containing 4-30 hardcoded cell coordinates). The pattern is correct for the
training pairs it was induced on, but cannot generalize because the cell
positions are absolute, not derived from scene structure.

- **Root cause**: No generative mode that DERIVES the pattern from object
  properties (shape, size, relative position). The program falls back to
  memorizing pixel coordinates.
- **Exemplars**: 95755ff2 (12-cell pattern, shape_hash selector),
  5c0a986e (4-cell pattern, extension)
- **Buildability**: MEDIUM. The `grow` delta type exists and the generator
  framework (R17) can host new modes. Needs: pattern-generation logic that
  computes fill regions from object features (e.g., `fill_interior` relative
  to a bounding container, `scale_and_stamp` relative to an anchor).
  Expressible as a new generator mode within current program shapes.

### 2. INTER-OBJECT CONNECTOR (9 tasks, 26%)

Wrong cells lie between or adjacent to multiple input objects. The program
needs to draw connecting structures (lines, bridges, L-paths, Manhattan
paths) between object pairs, but the current `CONNECT` delta type fires
too narrowly (only straight axis-aligned segments between directly
adjacent objects).

- **Root cause**: Connector induction explores only straight lines. Tasks
  need L-shaped paths, diagonal connectors, Manhattan routing, or
  flood-fill between object boundaries.
- **Exemplars**: 292dd178 (33 wrong cells, connector between 2 objects),
  465b7d93 (23 wrong cells)
- **Buildability**: MEDIUM-HIGH. The `CONNECT` delta type and infrastructure
  exist. Needs: L-path/Manhattan connector induction, boundary-to-boundary
  flood fill. Expressible as new connector subtypes within current delta vocabulary.

### 3. RAY/LINE EXTENSION (6 tasks, 17%)

Wrong cells extend beyond object boundaries along rays or lines. The program
needs to emit geometric structures (rays, lines, halos) that project outward
from objects, but current ray generators are insufficient (missing relational
direction, obstacle-conditional stopping, color absorption).

- **Root cause**: The R17 ray vocabulary covers basic 4-directional rays and
  row/col lines. Tasks need: rays with relational direction (toward/away from
  another object), rays that stop at obstacles, rays that change color at
  obstacles, bounded extensions.
- **Exemplars**: 692cd3b6 (268 wrong cells, extension + connector),
  d56f2372 (16 wrong cells)
- **Buildability**: HIGH. Ray/line generator framework exists (R17/R17b).
  The R17b ledger already names specific gaps: ray_until_obstacle,
  ray_through_absorbed, relational direction. These are vocabulary
  extensions to existing machinery.

### 4. POSITIONAL COLOR (2 tasks, 6%)

Wrong cells need different colors depending on their position or local
context, but the program uses a fixed color constant. No novel color
invention -- the needed colors exist in the input but selection depends
on spatial relationships.

- **Root cause**: Color expressions are limited to constants and simple
  feature lookups. Tasks need conditional color (if neighbor has color X,
  use Y) or positional color (color = f(row, col, nearby_object_color)).
- **Exemplars**: e21a174a (6 wrong cells, translate-based),
  f3e62deb (16 wrong cells)
- **Buildability**: LOW. Needs new expression types (conditional color,
  neighborhood-dependent color). Not expressible in current expression
  vocabulary without a new expression class.

### 5. ROW-SPAN FILL (1 task, 3%)

Entire row(s) need to be filled with a computed color. Existing row_line
generators (R17b) exist but don't fire on this task, likely because the
fill is conditional on row content.

- **Exemplar**: fc754716
- **Buildability**: MEDIUM. row_line generator exists. Needs conditional
  activation (which rows to fill based on content).

## Build-First Recommendation

**EXTENSIONAL PATTERN** (15 tasks, 43% of divergent tasks).

This is the single largest cluster and the most actionable:
- The infrastructure exists: `grow` delta type, generator framework, R17
  machinery for composite rendering.
- The gap is specific: programs memorize pixel coordinates instead of
  deriving them from scene structure (object containment, relative position,
  size ratios).
- Buildable as new generator modes within the existing framework.
- Expected to unlock the most tasks per engineering hour.

Second priority: INTER-OBJECT CONNECTOR (9 tasks). The `CONNECT` delta type
already exists; wider connector induction (L-path, Manhattan) is a contained
extension. Combined with extensional_pattern, these two cover 69% of
divergent tasks.

## Honest Caveats

1. **Sample bias**: 40/269 tasks sampled. The proportions may shift at full scale.
2. **Co-occurrence**: Most tasks have multiple structural gaps. Fixing one
   (e.g., extensional_pattern) may expose the next (e.g., connector).
3. **The "no_divergence" group** (5 tasks): These LOO-fail tasks had no
   stored fold-program divergence data. Their structural gap is real but
   not diagnosed here.
4. **The "conditional" signal**: The raw histogram shows 80% conditional,
   but this is a SYMPTOM, not a cause. Most divergences appear conditional
   because wrong cells have varying local context. The primary blocker
   analysis correctly filters this out.
