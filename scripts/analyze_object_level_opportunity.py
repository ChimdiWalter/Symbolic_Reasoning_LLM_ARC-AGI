"""How many unsolved same-shape tasks are object-level tasks?

For each unsolved same-shape task, extract objects from input and output of
every train pair and classify the edit at object granularity:
  - object_preserved: every output object's shape signature exists among input
    object signatures (objects moved / recolored / copied / deleted)
  - object_recolor_only: object cells identical, only colors change
  - object_motion: signatures preserved but positions differ
  - object_new_shapes: output contains shapes not present in input (drawing,
    line-growing, completion)
"""
import json
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, '/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project')
from geocat_arc.data.arc_loader import load_tasks
from geocat_arc.perception.objects import Grid, extract_objects

ROOT = '/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project'

with open(f'{ROOT}/outputs/failure_landscape_2026_07_02.json') as f:
    fl = json.load(f)
union = set(fl['union_ids'])
same_shape_unsolved = set()
for cat in ('same_shape_sparse_edit', 'same_shape_moderate_edit', 'same_shape_heavy_edit'):
    same_shape_unsolved.update(fl['unsolved_by_category'].get(cat, []))

tasks = {t.task_id: t for t in load_tasks(split='training')}


def norm_sig(obj):
    """Shape signature normalized (bbox mask), ignoring color."""
    return obj.shape_signature


def classify_pair(inp, out):
    gi, go = Grid(np.array(inp, dtype=np.int32)), Grid(np.array(out, dtype=np.int32))
    try:
        oi = extract_objects(gi)
        oo = extract_objects(go)
    except Exception:
        return 'perception_error'
    if len(oi) > 60 or len(oo) > 60:
        return 'too_many_objects'
    if not oo:
        return 'output_empty'
    in_sigs = Counter(norm_sig(o) for o in oi)
    out_sigs = Counter(norm_sig(o) for o in oo)
    preserved = all(in_sigs[s] >= c or s in in_sigs for s, c in out_sigs.items())
    all_present = all(s in in_sigs for s in out_sigs)
    if all_present:
        # same cells exactly? then recolor-only
        in_cells = {frozenset(o.cells) for o in oi}
        out_cells = {frozenset(o.cells) for o in oo}
        if out_cells <= in_cells or {(o.color, o.cells) for o in oi} == {(o.color, o.cells) for o in oo}:
            same_positions = {o.cells for o in oo} <= {o.cells for o in oi}
            return 'object_recolor_or_delete' if same_positions else 'object_motion_or_copy'
        same_positions = {o.cells for o in oo} <= {o.cells for o in oi}
        return 'object_recolor_or_delete' if same_positions else 'object_motion_or_copy'
    # partial: how many output objects have novel shapes?
    novel = sum(c for s, c in out_sigs.items() if s not in in_sigs)
    total = sum(out_sigs.values())
    if novel / total <= 0.34:
        return 'mostly_preserved_some_new'
    return 'object_new_shapes'


task_class = {}
for tid in sorted(same_shape_unsolved):
    task = tasks[tid]
    pair_classes = [classify_pair(p.input, p.output) for p in task.train]
    cnt = Counter(pair_classes)
    # task class = unanimous class if consistent, else mixed
    if len(cnt) == 1:
        task_class[tid] = pair_classes[0]
    else:
        task_class[tid] = 'mixed:' + cnt.most_common(1)[0][0]

summary = Counter(task_class.values())
print(f'Unsolved same-shape tasks analyzed: {len(task_class)}')
for cls, n in summary.most_common():
    print(f'  {cls:38s} {n:4d}')

# aggregate: object-level tractable = unanimous recolor/motion/mostly-preserved
tractable = {t for t, c in task_class.items() if c in (
    'object_recolor_or_delete', 'object_motion_or_copy', 'mostly_preserved_some_new')
    or c.startswith('mixed:object_') or c == 'mixed:mostly_preserved_some_new'}
print(f'\nObject-level tractable (objects preserved +/- recolor/move/copy): {len(tractable)}')

with open(f'{ROOT}/outputs/object_level_opportunity_2026_07_02.json', 'w') as f:
    json.dump({'task_class': task_class, 'tractable': sorted(tractable)}, f)
print('Saved to outputs/object_level_opportunity_2026_07_02.json')
