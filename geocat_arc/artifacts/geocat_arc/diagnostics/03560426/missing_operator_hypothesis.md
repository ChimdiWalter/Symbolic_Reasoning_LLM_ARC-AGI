# Missing Operator Hypothesis: 03560426

## Best Program

- Program: `Program(segment -> filter -> render)`
- Score: 0.7917
- Operators: ['segment', 'filter', 'render']

## Score Breakdown

- Pair 0: cell_accuracy=0.8000, cells_changed=20/100
- Pair 1: cell_accuracy=0.8500, cells_changed=15/100
- Pair 2: cell_accuracy=0.8000, cells_changed=20/100

## Object-Level Errors

- Pair 0: target_objs=3, pred_objs=0, missing=3, extra=0, mismatched=0
- Pair 1: target_objs=4, pred_objs=0, missing=4, extra=0, mismatched=0
- Pair 2: target_objs=3, pred_objs=0, missing=3, extra=0, mismatched=0

## Cross-Example Consistency

- Mean accuracy: 0.8167
- Std: 0.0236
- Spread: 0.0500
- Consistency score: 0.9764

## Pairwise Fitting Risk

- Risk level: low

## LOO-CV Validation

- Mean held-out accuracy: 0.8167
- Mean train score: 0.7917
- Generalization gap: -0.0250
- Pairwise fitting risk: False

## Failure Hypotheses (ranked by confidence)

### wrong_object_binding (confidence: 0.50)

10 target objects not present in prediction


## Transformation Analysis

- movement_present_in_all_pairs

### Per-Pair Details

- Pair 0: in_objs=3, out_objs=3, changed=42, moved=3, recolored=0, added=0, removed=0, new_colors=[], identity_acc=0.580
- Pair 1: in_objs=4, out_objs=4, changed=33, moved=4, recolored=0, added=0, removed=0, new_colors=[], identity_acc=0.670
- Pair 2: in_objs=3, out_objs=3, changed=39, moved=3, recolored=0, added=0, removed=0, new_colors=[], identity_acc=0.610
