"""Failure-landscape analysis: what do the unsolved ARC training tasks require?

Computes the union of solved IDs (pipeline v6b + GeoCat engine run live),
then categorizes every unsolved task by structural requirements.
"""
import json
import sys
import time
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, '/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project')
from geocat_arc.data.arc_loader import load_tasks
from geocat_arc.reasoning.reasoning_engine import ReasoningEngine

ROOT = '/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project'

with open(f'{ROOT}/outputs/full_novel_reasoning_pipeline_v2/cortical_v6b_2026_06_30/results.json') as f:
    v6b = json.load(f)
pipeline_ids = {s['task_id'] for s in v6b['solved']}

tasks = load_tasks(split='training')
engine = ReasoningEngine()

geocat_ids = set()
t0 = time.time()
for task in tasks:
    train_pairs = [(np.array(p.input, dtype=np.int32), np.array(p.output, dtype=np.int32))
                   for p in task.train]
    result = engine.solve(task.task_id, train_pairs)
    if result.solution and result.solution.is_exact:
        geocat_ids.add(task.task_id)
print(f'GeoCat run: {len(geocat_ids)} solved in {time.time()-t0:.0f}s', flush=True)

union = pipeline_ids | geocat_ids
print(f'Pipeline: {len(pipeline_ids)}, GeoCat: {len(geocat_ids)}, union: {len(union)}')


def categorize(task):
    """Structural category of a task from its train pairs."""
    shapes_in = [np.array(p.input).shape for p in task.train]
    shapes_out = [np.array(p.output).shape for p in task.train]
    same_shape = all(si == so for si, so in zip(shapes_in, shapes_out))
    if same_shape:
        # how far is output from input?
        fracs = []
        for p in task.train:
            i, o = np.array(p.input), np.array(p.output)
            fracs.append((i != o).mean())
        mean_frac = float(np.mean(fracs))
        if mean_frac < 0.10:
            return 'same_shape_sparse_edit', mean_frac
        elif mean_frac < 0.35:
            return 'same_shape_moderate_edit', mean_frac
        else:
            return 'same_shape_heavy_edit', mean_frac
    # shape-changing
    smaller = all(so[0] * so[1] < si[0] * si[1] for si, so in zip(shapes_in, shapes_out))
    larger = all(so[0] * so[1] > si[0] * si[1] for si, so in zip(shapes_in, shapes_out))
    const_out = len(set(shapes_out)) == 1
    int_scale = all(so[0] % si[0] == 0 and so[1] % si[1] == 0 for si, so in zip(shapes_in, shapes_out) if si[0] and si[1])
    int_down = all(si[0] % so[0] == 0 and si[1] % so[1] == 0 for si, so in zip(shapes_in, shapes_out) if so[0] and so[1])
    if smaller:
        return ('shrink_const_out' if const_out else ('shrink_int_factor' if int_down else 'shrink_var')), None
    if larger:
        return ('grow_int_factor' if int_scale else ('grow_const_out' if const_out else 'grow_var')), None
    return 'shape_change_mixed', None


cats_unsolved = Counter()
cats_solved = Counter()
sparse_edit_fracs = []
unsolved_detail = defaultdict(list)

for task in tasks:
    cat, frac = categorize(task)
    if task.task_id in union:
        cats_solved[cat] += 1
    else:
        cats_unsolved[cat] += 1
        unsolved_detail[cat].append(task.task_id)
        if cat == 'same_shape_sparse_edit' and frac is not None:
            sparse_edit_fracs.append(frac)

print('\n=== Category breakdown: UNSOLVED (n=%d) vs solved (n=%d) ===' % (
    sum(cats_unsolved.values()), sum(cats_solved.values())))
allcats = sorted(set(cats_unsolved) | set(cats_solved),
                 key=lambda c: -cats_unsolved[c])
for c in allcats:
    u, s = cats_unsolved[c], cats_solved[c]
    tot = u + s
    print(f'  {c:28s} unsolved={u:4d}  solved={s:3d}  solve-rate={s/tot*100:4.1f}%')

out = {
    'pipeline_ids': sorted(pipeline_ids),
    'geocat_ids': sorted(geocat_ids),
    'union_ids': sorted(union),
    'unsolved_by_category': {k: v for k, v in unsolved_detail.items()},
}
with open(f'{ROOT}/outputs/failure_landscape_2026_07_02.json', 'w') as f:
    json.dump(out, f)
print(f'\nSaved to outputs/failure_landscape_2026_07_02.json')
