# Missing Operator Hypothesis: 009d5c81

## Best Program

- Program: `Program(segment -> filter -> render)`
- Score: 0.8577
- Operators: ['segment', 'filter', 'render']

## Score Breakdown

- Pair 0: cell_accuracy=0.8418, cells_changed=31/196
- Pair 1: cell_accuracy=0.9286, cells_changed=14/196
- Pair 2: cell_accuracy=0.8776, cells_changed=24/196
- Pair 3: cell_accuracy=0.9184, cells_changed=16/196
- Pair 4: cell_accuracy=0.8469, cells_changed=30/196

## Object-Level Errors

- Pair 0: target_objs=1, pred_objs=0, missing=1, extra=0, mismatched=0
- Pair 1: target_objs=6, pred_objs=0, missing=6, extra=0, mismatched=0
- Pair 2: target_objs=1, pred_objs=0, missing=1, extra=0, mismatched=0
- Pair 3: target_objs=7, pred_objs=0, missing=7, extra=0, mismatched=0
- Pair 4: target_objs=1, pred_objs=0, missing=1, extra=0, mismatched=0

## Cross-Example Consistency

- Mean accuracy: 0.8827
- Std: 0.0356
- Spread: 0.0867
- Consistency score: 0.9644

## Pairwise Fitting Risk

- Risk level: low

## LOO-CV Validation

- Mean held-out accuracy: 0.8827
- Mean train score: 0.8577
- Generalization gap: -0.0250
- Pairwise fitting risk: False

## Failure Hypotheses (ranked by confidence)

### wrong_object_binding (confidence: 0.50)

16 target objects not present in prediction


## Transformation Analysis

- recoloring_present_in_all_pairs
- objects_removed_in_all_pairs
- mostly_identity_small_changes

### Per-Pair Details

- Pair 0: in_objs=3, out_objs=1, changed=37, moved=0, recolored=1, added=0, removed=2, new_colors=[7], identity_acc=0.811
- Pair 1: in_objs=9, out_objs=6, changed=20, moved=0, recolored=6, added=0, removed=3, new_colors=[3], identity_acc=0.898
- Pair 2: in_objs=2, out_objs=1, changed=29, moved=0, recolored=1, added=0, removed=1, new_colors=[2], identity_acc=0.852
- Pair 3: in_objs=10, out_objs=7, changed=22, moved=0, recolored=7, added=0, removed=3, new_colors=[3], identity_acc=0.888
- Pair 4: in_objs=2, out_objs=1, changed=35, moved=0, recolored=1, added=0, removed=1, new_colors=[2], identity_acc=0.821
