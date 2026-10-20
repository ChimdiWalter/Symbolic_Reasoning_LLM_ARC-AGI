# The three-space coverage matrix (20 October 2026)

**Source:** `records/NEURAL_CORA_V2G2_COVERAGE_MATRIX.json`, built by
`scripts/neural_cora_v2g2_coverage_matrix.py`. The JSON lists every construct with these fields: `native`,
`g1_compile`, `g1_generate`, `g2_compile`, `g2_generate`, `limitation`, plus the parameter domains.

**How "generate" is measured:** each generator runs on the probe tasks (the DEV synthetic families with seeds 1–2,
plus ncv2-g1's own search-test tasks), every candidate is compiled to a native dict, and the constructs inside are
collected.

| space | constructs |
|---|---|
| native CORA executes | 186 |
| ncv2-g1 compiles | 120 |
| ncv2-g1 generates | 64 |
| **ncv2-g2 compiles** | **172** |
| **ncv2-g2 generates** | **102** |

## Native constructs ncv2-g2 does not compile (14)

| constructs | reason |
|---|---|
| `delta:grow` | many mode-specific parameters; its generator vocabulary is reachable through the generative class |
| `delta:synth_copy`, `generator:learned_generator` | depend on frozen learned assets |
| `expr:RefExpr.matched_template` | needs a correspondence-bound template |
| `generator:ray_relational` | an untyped relational payload |
| `FreeSlotExpr` and the `GrowModeExpr` / `PatternExpr` grow-pattern expressions (5) | library holes and grow internals |
| the framed, overlay, computed_pattern and erase_patch program classes | not exposed yet |

## Compiled by ncv2-g2 but not generated on the probes (70)

**(a) Template gaps in the generator:**
- 9 relations as guards: above, below, left_of, right_of, overlaps, same_color, same_shape, same_shape_normalized,
  same_size;
- 23 features as selectors;
- the scalar expressions (`size`, `feature`, `count`, `hole_count`, `scaled_unit`);
- `and`, `in_set`, `self`, `reflect_across`, `feature_affine`, `separator_block_self`, `copy_part`;
- **staged `seq` programs (`class:composed`)**.

**(b) Task-triggered native-inducer outputs that these probes did not trigger:**
- equal-split panel modes and some separator modes;
- the `neighbor_pattern` pixel rule;
- 12 generator kinds (cavity_leak, line_periodic, periodic_*, ray_until_obstacle, …);
- 2 generator selector keys.

These come from native's own inducers when a task's demonstrations call for them, so on other tasks they can be
generated.

## Native certificates (EXPOSED ENGINEERING fixtures, demonstrations only)

- 6 of 6 round-trip exactly.
- 5 of 6 are structurally inside ncv2-g2's candidate set for their own tasks.
- The exception is k553a7e98f13d, whose S2 `feature_map` over `aligned_col_count` is not proposed. That task is solved
  by another program.
