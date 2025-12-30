# make_auto_shape_hints.py
import json, numpy as np, collections

def arr(x):
    return np.array(x['output'] if isinstance(x,dict) and 'output' in x else x, int)

ch = json.load(open('data/arc-agi_evaluation_challenges.json'))
hints = {}
for tid, spec in ch.items():
    ys = [arr(p['output']) for p in spec.get('train',[])]
    if not ys: continue
    shapes = [(y.shape[0], y.shape[1]) for y in ys]
    (mh, mw), _ = collections.Counter(shapes).most_common(1)[0]
    hints[tid] = {"target_shape":[int(mh), int(mw)]}

json.dump(hints, open('llm_hints_auto_shapes.json','w'))
print('Wrote llm_hints_auto_shapes.json with', len(hints), 'tasks')
