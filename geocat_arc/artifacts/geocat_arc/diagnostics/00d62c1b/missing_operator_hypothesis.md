# Missing Operator Hypothesis: 00d62c1b

## Best Program

- Program: `Program(segment -> render)`
- Score: 0.7663
- Operators: ['segment', 'render']

## Score Breakdown

- Pair 0: cell_accuracy=0.9400, cells_changed=6/100
- Pair 1: cell_accuracy=0.9900, cells_changed=1/100
- Pair 2: cell_accuracy=0.9100, cells_changed=9/100
- Pair 3: cell_accuracy=0.0000, cells_changed=?/?
- Pair 4: cell_accuracy=0.0000, cells_changed=?/?

## Object-Level Errors

- Pair 0: target_objs=8, pred_objs=5, missing=3, extra=0, mismatched=0
- Pair 1: target_objs=10, pred_objs=9, missing=1, extra=0, mismatched=0
- Pair 2: target_objs=13, pred_objs=11, missing=2, extra=0, mismatched=0
- Pair 3: target_objs=19, pred_objs=6, missing=13, extra=0, mismatched=1
- Pair 4: target_objs=8, pred_objs=6, missing=2, extra=0, mismatched=0

## Cross-Example Consistency

- Mean accuracy: 0.7863
- Std: 0.3207
- Spread: 0.8431
- Consistency score: 0.6793

## Pairwise Fitting Risk

- Risk level: high
- high accuracy spread across pairs: 0.843
- high std across pairs: 0.321
- decent mean but inconsistent — may be fitting some pairs better

## LOO-CV Validation

- Mean held-out accuracy: 0.7863
- Mean train score: 0.7663
- Generalization gap: -0.0200
- Pairwise fitting risk: False

## Failure Hypotheses (ranked by confidence)

### missing_operator (confidence: 0.70)

1 objects have wrong shape — may need spatial transformation operator

### insufficient_cross_example_rule_induction (confidence: 0.60)

cross-example consistency score 0.679 — program may not generalize

### wrong_object_binding (confidence: 0.50)

21 target objects not present in prediction


## Transformation Analysis

- objects_added_in_all_pairs
- mostly_identity_small_changes

### Per-Pair Details

- Pair 0: in_objs=5, out_objs=8, changed=6, moved=0, recolored=0, added=3, removed=0, new_colors=[4], identity_acc=0.940
- Pair 1: in_objs=9, out_objs=10, changed=1, moved=0, recolored=0, added=1, removed=0, new_colors=[4], identity_acc=0.990
- Pair 2: in_objs=11, out_objs=13, changed=9, moved=0, recolored=0, added=2, removed=0, new_colors=[4], identity_acc=0.910
- Pair 3: in_objs=14, out_objs=19, changed=31, moved=0, recolored=0, added=5, removed=0, new_colors=[4], identity_acc=0.922
- Pair 4: in_objs=6, out_objs=8, changed=2, moved=0, recolored=0, added=2, removed=0, new_colors=[4], identity_acc=0.944
