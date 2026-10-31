"""Authored development synthetic compositions; independent target specification.

No target AST, learned library, call body or solver trace is used by targets.
Training contains only single completion; held outer compositions are new to
that training set. Generator authors know earlier CORA results: not blind data.
"""
import copy
import engine as E

SPECS = [{'index': 800+i, 'family': 'completion_repeat' if i < 4 else 'selection_completion_mark',
          'parameter': 'h' if i % 2 == 0 else 'v'} for i in range(8)]

def input_grid(spec, demo=None):
    seed = (250000 + spec['index'] * 37 + demo if demo is not None else 350000 + spec['index'] * 41)
    return E.D.grid_input(seed, spec['family'] == 'selection_completion_mark')

def target(raw, family, parameter):
    g = copy.deepcopy(raw)
    if family == 'selection_completion_mark':
        counts = {c: sum(row.count(c) for row in g) for c in sorted({c for row in g for c in row if c})}
        best = max(counts.values()); winners = [c for c in counts if counts[c] == best]
        if len(winners) != 1: raise ValueError('AUTHORED_TARGET_TIE')
        color = winners[0]; g = [[v if v == color else 0 for v in row] for row in g]
    h, w = len(g), len(g[0]); before = copy.deepcopy(g)
    for r in range(h):
        for c in range(w):
            reflected = before[r][w-1-c] if parameter == 'h' else before[h-1-r][c]
            if before[r][c] and reflected and before[r][c] != reflected:
                raise ValueError('AUTHORED_TARGET_OVERLAY_CONFLICT')
            g[r][c] = before[r][c] or reflected
    if family == 'completion_repeat':
        return [row * 2 for row in g] * 2
    if family == 'selection_completion_mark':
        return [[2 if v else 0 for v in row] for row in g]
    raise ValueError('UNKNOWN_AUTHORED_COMPOSITION')

def training():
    return [E.D.make_task('grid', i, 'single_completion', 'h' if i % 2 == 0 else 'v') for i in range(400, 412)]

def retained_tasks():
    return [{'id': 'synthetic_' + str(s['index']), 'domain': 'grid',
        'demos': [{'input': input_grid(s,j), 'output': target(input_grid(s,j), s['family'], s['parameter'])}
            for j in range(2)]} for s in SPECS]
