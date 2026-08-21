# V22 Census: Failure Candidates for >200

Generated: 2026-08-17
V22 sealed: 181/1000 (18.1% CSR), unsolved: 819

## Failure-Stage Histogram (all 819 unsolved)

| Stage | Count | Description |
|---|---|---|
| no_engagement | 387 | Object engine cannot segment meaningfully |
| loo_fail:loo | 195 | Train-perfect program, LOO gate rejects |
| geocat_only | 104 | Only geocat layer engaged (structural strategies) |
| loo_fail:matching | 47 | Train-perfect but object matching fails on folds |
| partial_low:matching | 36 | Partial fit (<0.5), matching fails |
| partial_high:matching | 24 | Partial fit (>0.5), matching fails |
| partial_low:parameter | 10 | Partial fit, parameter search fails |
| partial_high:parameter | 10 | Partial fit (>0.5), parameter search fails |
| partial_high:selector | 5 | Partial fit, selector search fails |
| partial_low:selector | 1 | Partial fit, selector search fails |

## Program-Structure Analysis (290 LOO-fail tasks with programs)

The binding bottleneck is overwhelmingly confirmed at v22:

| Structural Blocker | Count | % | Note |
|---|---|---|---|
| Extensional pattern | 156 | 54% | Literal pixel patterns that need generative rules |
| Constant color param | 60 | 21% | Color needs to be derived from context |
| Constant params dominate | 568/633 | 90% | Of all parameter slots, 90% are constant class |
| Nearly zero relational | 1/290 | 0.3% | Only 1 task has ANY relational parameter |

Delta type distribution: grow 485, translate 36, delete 34, recolor 22,
keep 16, crop_to 14, reflect 6, composite 5, copy 5, rotate 5,
synth_copy 3, paint 2.

## Top-5 Named Candidates

### 1. POSITIONAL COLOR: color varies by position/neighborhood

- **Tasks in sample**: 15/80 LOO-fail analyzed
- **Extrapolated**: ~45 of 242 LOO-fail tasks
- **Category**: color/color_function_of_context
- **Exemplars**: 0a938d79, 0e671a1a, 0f63c0b9
- **Buildability**: Needs conditional color expressions (if-then or lookup
  over neighborhood features). LOW buildability -- requires new expression
  type in the parameter grammar.

### 2. COLOR INVENTION: output uses colors absent from input

- **Tasks in sample**: 13/80
- **Extrapolated**: ~39 of 242 LOO-fail tasks
- **Category**: color/novel_color_in_output
- **Exemplars**: 0e671a1a, 32e9702f, 4612dd53
- **Buildability**: Needs color-arithmetic or color-mapping expressions
  (complement, count-to-color). LOW buildability -- new expression type.

### 3. RAY/LINE EXTENSION: cells placed along rays/lines beyond object boundaries

- **Tasks in sample**: 11/80
- **Extrapolated**: ~33 of 242 LOO-fail tasks
- **Category**: position/extension_beyond_objects
- **Exemplars**: 0a938d79, 0e671a1a, 0f63c0b9
- **Buildability**: Partially covered by ray/line generators (R17). Gap:
  ray_until_obstacle, ray_through_absorbed, relational direction.
  HIGH buildability -- machinery exists, vocabulary extensions needed.

### 4. INTER-OBJECT CONNECTOR: bridge/line connecting objects

- **Tasks in sample**: 11/80
- **Extrapolated**: ~33 of 242 LOO-fail tasks
- **Category**: position/connector_between_objects
- **Exemplars**: 0a938d79, 0e671a1a, 0f63c0b9
- **Buildability**: CONNECT delta type exists but fires narrowly. Needs
  wider connector induction (L-path, Manhattan, diagonal).
  MEDIUM buildability -- delta type exists.

### 5. PATTERN-TO-RULE: literal pixel patterns need generative/relational rules

- **Tasks in sample**: 7/80
- **Extrapolated**: ~21 of 242 LOO-fail tasks
- **Category**: position/extensional_pattern
- **Exemplars**: 0e671a1a, 0f63c0b9, 4612dd53
- **Buildability**: Program stores literal patterns; needs generative mode
  that DERIVES pattern from object features (e.g., fill_interior +
  scale_to_container). Delta type exists (grow), needs new generator logic.
  MEDIUM buildability.

## Build-First Recommendation

**RAY/LINE EXTENSION** (#3, ~33 extrapolated tasks) is the build-first
target despite ranking 3rd by count, because:
1. It has HIGH buildability (ray/line machinery from R17 already exists)
2. RAY/EXTENSION and CONNECTOR (#4) share infrastructure, so building one
   partially addresses the other (combined ~66 tasks)
3. The top-2 candidates (POSITIONAL COLOR, COLOR INVENTION) both require
   NEW expression types -- a grammar extension that is the deepest
   architectural change and should be deferred until the easier wins are
   collected

However, the STRUCTURAL reality is that 90% of LOO-fail parameter slots are
constant class and the R1/R2 relational-expression bottleneck is confirmed
at v22 with even larger numbers. The path to >200 requires BOTH easier
delta/generator wins (ray/connector, ~60 tasks) AND the harder expression
grammar extension (color expressions, ~80 tasks). Neither alone reaches 200.

## 868de0fa Scheduling-Harm Diagnosis

**Mechanism**: The cheap-first variant-budget scheduling promotes a simpler,
shallower program (S3-only single-stage with constant-color fill_interior)
that is train-perfect but LOO-fails, instead of the deeper framed+composed
program (S3+S4 two-stage) that would certify under v21 flags. The v22
search exhausts budget on the promoted (non-certifiable) candidate before
exploring the deeper composition path.

**Specific trace**:
- OFF-CONTROL (v21 flags): `framed` program wrapping `composed` with 2
  stages (S3 + S4), each with fill_interior. The composition structure is
  fold-stable so it certifies.
- V22 (new flags): simple single-stage S3-only program with 2 rules (both
  grow/fill_interior with constant colors 2 and 7). Train-perfect but
  LOO-fails because constant colors are not subset-stable.

**Harm mechanism**: promotion-starvation. Variant-budget scheduling
allocates less time to S4, so the composition stage that depends on S4
never runs. The engine finds the simpler S3-only program first (cheap-first
ordering), and because it is train-perfect, no further search occurs.

**Remedy**: Composition-aware budget reservation: when a single-stage
program is train-perfect but LOO-fails with constant parameters, reserve
budget for a composition attempt before declaring failure. This is a
targeted fix for the one known harm case.
