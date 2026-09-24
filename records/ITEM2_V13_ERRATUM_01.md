# Erratum 1 to Item-2 protocol v1.3

Recorded 2026-09-24, after Phase A completed and **before any Phase B group
was generated, before the calibration artifact was committed, and before any
audit outcome existed**. It corrects an implementation defect in how the
frozen standardization is applied. It does not change the protocol, the
descriptor, the feature sets, the distances' definitions, the group law, any
threshold, any seed, `epsilon_demo`, the `q` formula, or any of G1 to G10.

The protocol document and manifest hashes are unchanged:
`66aa1c56...389d8f1e` and `9492f392...ab56de14`.

## The defect

The protocol says both distances are standardized by the Phase A constants. It
does not say what to do with a field that is constant across Phase A. My
implementation floored the standard deviation at 1e-9.

Phase A measured, over exactly 200 admitted calibration episodes:

- `d_demo`: 1 of 6 features constant, `same_shape_all`, always true.
- `d_frontier`: **13 of 42 descriptor fields constant**, being
  `exec_max_depth`, `op_bucket_3`, `op_bucket_9`, `op_bucket_12`,
  `op_bucket_14`, `outcome_exact`, `outcome_slot_fit_ok`,
  `outcome_typecheck_failed`, `outcome_typed`, `shape_mismatch`,
  `surface_min`, `surface_mean`, `surface_max`.

A field constant in calibration can still move in Phase B. With a divisor of
1e-9, a raw difference of one on such a field becomes a standardized
difference of one billion, which would swamp every other dimension. The
Euclidean distance would stop being a distance over the descriptor and become
a lookup on whichever constant field happened to move.

That would corrupt the identifiability audit in an uncontrolled direction. It
could manufacture separation or destroy it, depending on which fields moved,
and it would do so for reasons unrelated to the hypothesis.

## The correction

For any field whose Phase A standard deviation is below 1e-6, the divisor is
**1.0** rather than 1e-9. A raw difference of one then contributes one
standardized unit, which is a neutral scale: the field is neither amplified
nor discarded.

Flooring at 1.0 is preferred over dropping the field. Dropping would discard
variation that is real in Phase B merely because it was absent from
calibration, and the descriptor width is part of the recorded sample-size
justification.

The calibration artifact now records, for both distances, the raw standard
deviations, the effective divisors actually used, and the explicit list of
floored fields, so the correction is auditable rather than implicit.

## What was regenerated

Nothing. The same 200 Phase A episodes are reused unchanged. Only the
calibration constants are recomputed from them under the corrected floor. No
episode was regenerated, reselected or discarded, and no Phase B group existed
at any point during this correction.

## Why this is recorded rather than silently fixed

The same defect class was found by adversarial review in the v1.2 scorer
block, where constant features with a floored standard deviation made a
control inert and put a factor of a million on a dead weight. Finding it again
here, before it could touch a result, is the discipline working. Recording it
before generation is what makes the later verdict trustworthy.
