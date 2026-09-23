# Missing Operator Hypothesis: 00dbd492

## Best Program

- Program: `Program(segment -> render)`
- Score: 0.7556
- Operators: ['segment', 'render']

## Score Breakdown

- Pair 0: cell_accuracy=0.7511, cells_changed=56/225
- Pair 1: cell_accuracy=0.0000, cells_changed=?/?
- Pair 2: cell_accuracy=0.0000, cells_changed=?/?
- Pair 3: cell_accuracy=0.0000, cells_changed=?/?

## Object-Level Errors

- Pair 0: target_objs=6, pred_objs=4, missing=2, extra=0, mismatched=0
- Pair 1: target_objs=3, pred_objs=2, missing=1, extra=0, mismatched=0
- Pair 2: target_objs=6, pred_objs=4, missing=2, extra=0, mismatched=0
- Pair 3: target_objs=3, pred_objs=2, missing=1, extra=0, mismatched=0

## Cross-Example Consistency

- Mean accuracy: 0.7756
- Std: 0.0518
- Spread: 0.1330
- Consistency score: 0.9482

## Pairwise Fitting Risk

- Risk level: low

## LOO-CV Validation

- Mean held-out accuracy: 0.6384
- Mean train score: 0.7124
- Generalization gap: 0.0740
- Pairwise fitting risk: False

## Failure Hypotheses (ranked by confidence)

### wrong_object_binding (confidence: 0.50)

6 target objects not present in prediction

### insufficient_search_depth (confidence: 0.50)

only 2 unique operators used — deeper programs may help


## Transformation Analysis

- objects_added_in_all_pairs

### Per-Pair Details

- Pair 0: in_objs=4, out_objs=6, changed=56, moved=0, recolored=0, added=2, removed=0, new_colors=[3, 8], identity_acc=0.751
- Pair 1: in_objs=2, out_objs=3, changed=24, moved=0, recolored=0, added=1, removed=0, new_colors=[4], identity_acc=0.704
- Pair 2: in_objs=4, out_objs=6, changed=32, moved=0, recolored=0, added=2, removed=0, new_colors=[4, 8], identity_acc=0.811
- Pair 3: in_objs=2, out_objs=3, changed=8, moved=0, recolored=0, added=1, removed=0, new_colors=[8], identity_acc=0.837
