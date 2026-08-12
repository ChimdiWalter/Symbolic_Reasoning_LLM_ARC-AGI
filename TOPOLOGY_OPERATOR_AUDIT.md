# Topology Operator Audit

Generated artifact: `outputs/exactness/topology_operator_audit.md`.

The implemented exact topology audit uses a finite, color-insensitive support topology:

- support mask: exact nonzero mask,
- component count: number of 4-connected components in the binary support,
- hole count: number of enclosed background regions in the binary support.

Current finite domain:

- all binary 3x3 grids,
- selected colored 3x3 probes designed to expose color-dependent selector failures.

## Current Classification Counts

From `outputs/exactness/exactness_report.md`:

- `topology_preserving_under_support_mask_definition`: 7 operator instances.
- `topology_preserving_for_component_and_hole_counts_only`: 5 operator instances.
- `conditionally_topology_preserving_not_on_full_bounded_domain`: 10 operator instances.
- `not_topology_preserving_on_bounded_domain`: 9 operator instances.

## Examples Of Exact Bounded Findings

- `identity`, recoloring-only operators, and `mark_contained_objects` instances preserve the exact support-mask topology on the audited finite domain.
- Reflections and rotations preserve component count and hole count but do not preserve the literal support mask because they move support.
- Translation and copy-to-corner operators are conditional: they may preserve topology when no clipping/overlap occurs, but fail on the full audited domain.
- Counting, selector, adjacency, and distractor-removal operators have explicit finite counterexamples in `outputs/exactness/topology_operator_audit.json`.

## Boundary

This is not a broad topological theorem. It is an exhaustive finite check over the declared operator instances and finite grid domain.
