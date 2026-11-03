"""CORA R25: finite demo-constrained typed program construction.

No task IDs, query grids, neural predictions, file I/O or held-out answers enter
propose(). Closed programs are independently replayed on every retained demo.
Search failure returns UNKNOWN, never an assertion that no program exists.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import heapq
import itertools
import json
import math
import time

SCHEMA = 'CORA_R25_PROPOSAL_V1'
ACTIONS = ('rebind', 'change_representation', 'revise_fragment', 'compose', 'library', 'abstain')
BACKGROUNDS = ('zero', 'mode', 'border')
D4 = ('identity', 'hflip', 'vflip', 'r90', 'r180', 'r270', 'transpose', 'antitranspose')
OP_PARAMETER_DOMAINS = {
    'input': {},
    'd4': {'mode': D4},
    'crop': {'background': BACKGROUNDS},
    'object': {'background': BACKGROUNDS, 'connectivity': (4, 8),
               'color_mode': ('mono', 'foreground'),
               'selector': ('largest', 'smallest', 'top', 'bottom', 'left', 'right'),
               'output': ('crop', 'canvas')},
    'recolor': {'mapping': None},
    'resize': {'mode': ('scale', 'tile', 'reduce', 'untile'),
               'row_factor': tuple(range(1, 6)), 'col_factor': tuple(range(1, 6))},
    'shift': {'background': BACKGROUNDS, 'dr': tuple(range(-29, 30)), 'dc': tuple(range(-29, 30))},
    'pack': {'background': BACKGROUNDS, 'direction': ('left', 'right', 'up', 'down')},
    'fill_bbox': {'background': BACKGROUNDS, 'color': ('foreground_mode',)},
    'complete_symmetry': {'background': BACKGROUNDS, 'axis': ('horizontal', 'vertical', 'both')},
    'fill_holes': {'background': BACKGROUNDS, 'color': ('foreground_mode',)},
}
DEFAULT_CAPS = {'CPU_s': 0.5, 'generated_states': 512, 'semantic_classes': 128,
                'primitive_executions': 10000, 'cell_work': 2000000,
                'selected_programs': 4, 'max_depth': 4, 'library_seeds': 16}
EVIDENCE_FEATURES = ('shape_error', 'pixel_error', 'palette_error', 'ink_error',
                     'bbox_error', 'component_error', 'retained_error', 'type_error',
                     'ambiguity', 'search_usage')


class Failure(ValueError):
    """An executable primitive's explicit precondition failed."""


class Budget(TimeoutError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def valid_grid(grid):
    if type(grid) is not list or not 1 <= len(grid) <= 30:
        raise Failure('GRID_HEIGHT')
    if type(grid[0]) is not list or not 1 <= len(grid[0]) <= 30:
        raise Failure('GRID_WIDTH')
    width = len(grid[0])
    if any(type(row) is not list or len(row) != width or
           any(type(v) is not int or not 0 <= v <= 9 for v in row) for row in grid):
        raise Failure('GRID_CELLS')
    return grid


def valid_demos(train):
    if type(train) is not list or not 1 <= len(train) <= 10:
        raise Failure('TRAIN_SCHEMA')
    for pair in train:
        if type(pair) is not dict or set(pair) != {'input', 'output'}:
            raise Failure('TRAIN_FIELDS')
        valid_grid(pair['input'])
        valid_grid(pair['output'])


def inp():
    return {'op': 'input', 'type': 'Grid', 'args': [], 'params': {}}


input_ast = inp


def node(op, child=None, **params):
    return {'op': op, 'type': 'Grid', 'args': [] if child is None else [copy.deepcopy(child)],
            'params': copy.deepcopy(params)}


def structural_cost(ast):
    """Explicit primitive count; every library seed is already expanded."""
    return (ast['op'] != 'input') + sum(structural_cost(c) for c in ast.get('args', []))


def lower_plain(ast, library=None):
    validate_ast(ast)
    return copy.deepcopy(ast)


def validate_ast(ast, max_depth=12, _depth=0):
    if _depth > max_depth or type(ast) is not dict or set(ast) != {'op', 'type', 'args', 'params'}:
        raise Failure('AST_SCHEMA_OR_DEPTH')
    op = ast['op']
    if ast['type'] != 'Grid' or op not in OP_PARAMETER_DOMAINS:
        raise Failure('AST_TYPE_OR_OPERATION')
    args, params = ast['args'], ast['params']
    if type(args) is not list or len(args) != (0 if op == 'input' else 1) or type(params) is not dict:
        raise Failure('AST_ARITY')
    domains = OP_PARAMETER_DOMAINS[op]
    if set(params) != set(domains):
        raise Failure('AST_PARAMETER_FIELDS')
    for key, domain in domains.items():
        value = params[key]
        if op == 'recolor':
            if type(value) is not dict or not value or any(
                type(k) is not str or k not in tuple(str(c) for c in range(10)) or
                type(v) is not int or not 0 <= v <= 9 for k, v in value.items()
            ):
                raise Failure('AST_PALETTE')
        elif not any(type(value) is type(admitted) and value == admitted for admitted in domain):
            raise Failure('AST_PARAMETER_DOMAIN')
    for child in args:
        validate_ast(child, max_depth, _depth + 1)


def _unique_mode(values):
    counts = collections.Counter(values)
    if not counts:
        raise Failure('EMPTY_ROLE')
    maximum = max(counts.values())
    winners = [v for v, n in counts.items() if n == maximum]
    if len(winners) != 1:
        raise Failure('AMBIGUOUS_COLOR_ROLE')
    return winners[0]


def background(grid, role):
    if role == 'zero':
        return 0
    if role == 'mode':
        return _unique_mode(v for row in grid for v in row)
    if role == 'border':
        return _unique_mode(v for r, row in enumerate(grid) for c, v in enumerate(row)
                            if r in (0, len(grid)-1) or c in (0, len(row)-1))
    raise Failure('UNKNOWN_BACKGROUND_ROLE')


def _points(grid, bg):
    return [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != bg]


def _bounds(points):
    if not points:
        raise Failure('EMPTY_FOREGROUND')
    return min(r for r, _ in points), min(c for _, c in points), max(r for r, _ in points), max(c for _, c in points)


def _components(grid, bg, connectivity=4, color_mode='foreground', check=lambda: None):
    remaining = set(_points(grid, bg))
    offsets = ((-1, 0), (0, -1), (0, 1), (1, 0)) if connectivity == 4 else tuple(
        (r, c) for r in (-1, 0, 1) for c in (-1, 0, 1) if r or c)
    components = []
    while remaining:
        check()
        start = min(remaining)
        remaining.remove(start)
        component, todo = [start], [start]
        while todo:
            r, c = todo.pop()
            for dr, dc in offsets:
                q = r + dr, c + dc
                if q in remaining and (color_mode == 'foreground' or grid[q[0]][q[1]] == grid[r][c]):
                    remaining.remove(q)
                    component.append(q)
                    todo.append(q)
        components.append(component)
    return components


def _d4(grid, mode):
    if mode == 'identity':
        return [row[:] for row in grid]
    if mode == 'hflip':
        return [row[::-1] for row in grid]
    if mode == 'vflip':
        return grid[::-1]
    if mode == 'r90':
        return [list(row) for row in zip(*grid[::-1])]
    if mode == 'r180':
        return [row[::-1] for row in grid[::-1]]
    if mode == 'r270':
        return [list(row) for row in zip(*grid)][::-1]
    if mode == 'transpose':
        return [list(row) for row in zip(*grid)]
    if mode == 'antitranspose':
        return [list(row)[::-1] for row in zip(*grid)][::-1]
    raise Failure('D4_MODE')


def _primitive(op, grid, p, check):
    if op == 'd4':
        return _d4(grid, p['mode'])
    if op == 'recolor':
        return [[p['mapping'].get(str(v), v) for v in row] for row in grid]
    if op == 'resize':
        a, b, mode = p['row_factor'], p['col_factor'], p['mode']
        h, w = len(grid), len(grid[0])
        if mode in ('scale', 'tile'):
            if h * a > 30 or w * b > 30:
                raise Failure('RESIZE_GRID_BOUND')
            if mode == 'scale':
                return [[v for v in row for _ in range(b)] for row in grid for _ in range(a)]
            return [row * b for _ in range(a) for row in grid]
        if h % a or w % b:
            raise Failure('REDUCE_DIVISIBILITY')
        nh, nw = h // a, w // b
        if mode == 'reduce':
            out = [[grid[r*a][c*b] for c in range(nw)] for r in range(nh)]
            if any(grid[r][c] != out[r//a][c//b] for r in range(h) for c in range(w)):
                raise Failure('NONCONSTANT_SCALE_BLOCK')
            return out
        out = [row[:nw] for row in grid[:nh]]
        if any(grid[r][c] != out[r % nh][c % nw] for r in range(h) for c in range(w)):
            raise Failure('NONREPEATED_TILE')
        return out
    bg = background(grid, p['background'])
    points = _points(grid, bg)
    h, w = len(grid), len(grid[0])
    if op == 'crop':
        r0, c0, r1, c1 = _bounds(points)
        return [row[c0:c1+1] for row in grid[r0:r1+1]]
    if op == 'object':
        components = _components(grid, bg, p['connectivity'], p['color_mode'], check)
        if not components:
            raise Failure('NO_OBJECT')
        def key(component):
            r0, c0, r1, c1 = _bounds(component)
            return {'largest': -len(component), 'smallest': len(component),
                    'top': r0, 'bottom': -r1, 'left': c0, 'right': -c1}[p['selector']]
        best = min(key(component) for component in components)
        winners = [component for component in components if key(component) == best]
        if len(winners) != 1:
            raise Failure('AMBIGUOUS_OBJECT_ROLE')
        chosen = winners[0]
        if p['output'] == 'canvas':
            out = [[bg] * w for _ in range(h)]
            for r, c in chosen:
                out[r][c] = grid[r][c]
            return out
        r0, c0, r1, c1 = _bounds(chosen)
        out = [[bg] * (c1-c0+1) for _ in range(r1-r0+1)]
        for r, c in chosen:
            out[r-r0][c-c0] = grid[r][c]
        return out
    if op == 'shift':
        out = [[bg] * w for _ in range(h)]
        for r, c in points:
            nr, nc = r + p['dr'], c + p['dc']
            if not (0 <= nr < h and 0 <= nc < w):
                raise Failure('SHIFT_CLIPS_FOREGROUND')
            out[nr][nc] = grid[r][c]
        return out
    if op == 'pack':
        direction = p['direction']
        if direction in ('left', 'right'):
            out = []
            for row in grid:
                values = [v for v in row if v != bg]
                blanks = [bg] * (w-len(values))
                out.append(values + blanks if direction == 'left' else blanks + values)
            return out
        transposed = [list(row) for row in zip(*grid)]
        packed = _primitive('pack', transposed, {'background': 'zero' if bg == 0 else p['background'],
                              'direction': 'left' if direction == 'up' else 'right'}, check)
        # A border role can change under a transpose only if border membership changes;
        # transpose preserves border membership, hence this re-evaluation is identical.
        return [list(row) for row in zip(*packed)]
    if op in ('fill_bbox', 'fill_holes'):
        color = _unique_mode(grid[r][c] for r, c in points)
        out = [row[:] for row in grid]
        if op == 'fill_bbox':
            r0, c0, r1, c1 = _bounds(points)
            for r in range(r0, r1+1):
                for c in range(c0, c1+1):
                    if out[r][c] == bg:
                        out[r][c] = color
            return out
        outside = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row)
                   if v == bg and (r in (0, h-1) or c in (0, w-1))}
        todo = list(outside)
        while todo:
            r, c = todo.pop()
            for dr, dc in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                q = r+dr, c+dc
                if 0 <= q[0] < h and 0 <= q[1] < w and grid[q[0]][q[1]] == bg and q not in outside:
                    outside.add(q)
                    todo.append(q)
        for r, row in enumerate(out):
            for c, value in enumerate(row):
                if value == bg and (r, c) not in outside:
                    out[r][c] = color
        return out
    if op == 'complete_symmetry':
        out = [row[:] for row in grid]
        modes = {'horizontal': ('hflip',), 'vertical': ('vflip',), 'both': ('hflip', 'vflip', 'r180')}[p['axis']]
        for mode in modes:
            reflected = _d4(grid, mode)
            for r in range(h):
                for c in range(w):
                    value = reflected[r][c]
                    if value != bg:
                        if out[r][c] not in (bg, value):
                            raise Failure('SYMMETRY_COLOR_CONFLICT')
                        out[r][c] = value
        return out
    raise Failure('UNKNOWN_PRIMITIVE')


def execute(program, raw, library=None, check=lambda: None, meter=None):
    """Typed pure interpreter. Library bodies must be expanded before this call."""
    validate_ast(program)
    valid_grid(raw)
    meter = {} if meter is None else meter
    meter.setdefault('primitive_executions', 0)
    meter.setdefault('cell_work', 0)
    def run(ast):
        check()
        if ast['op'] == 'input':
            return [row[:] for row in raw]
        grid = run(ast['args'][0])
        check()
        if meter.get('primitive_limit') is not None and meter['primitive_executions'] >= meter['primitive_limit']:
            raise Budget('PRIMITIVE_CAP_UNKNOWN')
        # Every admitted primitive reads and emits at most 30x30 cells.
        if meter.get('cell_limit') is not None and meter['cell_work'] + 1800 > meter['cell_limit']:
            raise Budget('CELL_WORK_CAP_UNKNOWN')
        meter['primitive_executions'] += 1
        out = _primitive(ast['op'], grid, ast['params'], check)
        valid_grid(out)
        meter['cell_work'] += len(grid)*len(grid[0]) + len(out)*len(out[0])
        check()
        return out
    return run(program)


def predict(program, query, library=None, check=lambda: None):
    return execute(program, query, library=library, check=check)


def verify(program, train, check=lambda: None, meter=None):
    valid_demos(train)
    validate_ast(program)
    return all(execute(program, pair['input'], check=check, meter=meter) == pair['output'] for pair in train)


def _shape(grid):
    return len(grid), len(grid[0])


def _palette_map(outputs, train):
    mapping = {}
    for grid, pair in zip(outputs, train):
        if _shape(grid) != _shape(pair['output']):
            return None
        for old_row, new_row in zip(grid, pair['output']):
            for old, new in zip(old_row, new_row):
                if str(old) in mapping and mapping[str(old)] != new:
                    return None
                mapping[str(old)] = new
    return mapping


def _infer_resizes(outputs, train):
    for mode in ('scale', 'tile', 'reduce', 'untile'):
        factors = []
        for grid, pair in zip(outputs, train):
            h, w = _shape(grid)
            oh, ow = _shape(pair['output'])
            big, small = ((oh, ow), (h, w)) if mode in ('scale', 'tile') else ((h, w), (oh, ow))
            if big[0] % small[0] or big[1] % small[1]:
                break
            factors.append((big[0] // small[0], big[1] // small[1]))
        if len(factors) == len(train) and len(set(factors)) == 1:
            a, b = factors[0]
            if 1 <= a <= 5 and 1 <= b <= 5 and (a, b) != (1, 1):
                yield {'mode': mode, 'row_factor': a, 'col_factor': b}


def _infer_shifts(outputs, train):
    for role in BACKGROUNDS:
        values = []
        try:
            for grid, pair in zip(outputs, train):
                target = pair['output']
                if _shape(grid) != _shape(target):
                    break
                # Infer displacement from bounding boxes, then verify actual cell behavior.
                old = _bounds(_points(grid, background(grid, role)))
                new = _bounds(_points(target, background(target, role)))
                if (old[2]-old[0], old[3]-old[1]) != (new[2]-new[0], new[3]-new[1]):
                    break
                values.append((new[0]-old[0], new[1]-old[1]))
            if len(values) == len(train) and len(set(values)) == 1 and values[0] != (0, 0):
                dr, dc = values[0]
                yield {'background': role, 'dr': dr, 'dc': dc}
        except Failure:
            continue


def _families(seed, action):
    def geometry():
        for mode in D4[1:]:
            yield node('d4', seed, mode=mode)
    def crop():
        for role in BACKGROUNDS:
            yield node('crop', seed, background=role)
    def objects():
        # Round-robin over selectors before changing segmentation, not a large object-root block.
        for output, selector, color_mode, connectivity, role in itertools.product(
                ('crop', 'canvas'), ('largest', 'smallest', 'top', 'bottom', 'left', 'right'),
                ('foreground', 'mono'), (4, 8), BACKGROUNDS):
            yield node('object', seed, background=role, connectivity=connectivity,
                       color_mode=color_mode, selector=selector, output=output)
    def pack():
        for direction, role in itertools.product(('left', 'right', 'up', 'down'), BACKGROUNDS):
            yield node('pack', seed, background=role, direction=direction)
    def bbox():
        for role in BACKGROUNDS:
            yield node('fill_bbox', seed, background=role, color='foreground_mode')
    def symmetry():
        for axis, role in itertools.product(('horizontal', 'vertical', 'both'), BACKGROUNDS):
            yield node('complete_symmetry', seed, background=role, axis=axis)
    def holes():
        for role in BACKGROUNDS:
            yield node('fill_holes', seed, background=role, color='foreground_mode')
    definitions = [('identity', iter([seed])), ('geometry', geometry()), ('crop', crop()),
                   ('object', objects()), ('pack', pack()), ('bbox', bbox()),
                   ('symmetry', symmetry()), ('holes', holes())]
    if action == 'rebind':
        return [('identity', iter([seed]))]
    if action == 'change_representation':
        return [(name, it) for name, it in definitions if name in ('crop', 'object')]
    if action == 'revise_fragment':
        return [(name, it) for name, it in definitions if name in ('geometry', 'pack', 'bbox', 'symmetry', 'holes')]
    if action in ('compose', 'library'):
        return [('identity', iter([seed]))]
    return definitions


def static_programs(train, caps=None, check=lambda: None, max_programs=16):
    """No demonstration outputs are used to form these matched static seed programs."""
    valid_demos(train)
    families, out = _families(inp(), None), []
    while families and len(out) < max_programs:
        next_round = []
        for name, iterator in families:
            check()
            try:
                out.append(next(iterator))
                next_round.append((name, iterator))
            except StopIteration:
                pass
            if len(out) >= max_programs:
                break
        families = next_round
    return out


def _residual(outputs, train):
    shape_errors = sum(_shape(grid) != _shape(pair['output']) for grid, pair in zip(outputs, train))
    pixels, total = 0, 0
    for grid, pair in zip(outputs, train):
        target = pair['output']
        total += max(len(grid)*len(grid[0]), len(target)*len(target[0]))
        if _shape(grid) == _shape(target):
            pixels += sum(v != target[r][c] for r, row in enumerate(grid) for c, v in enumerate(row))
        else:
            pixels += max(len(grid)*len(grid[0]), len(target)*len(target[0]))
    return shape_errors, pixels / max(1, total)


def _expanded_seeds(library, limit):
    if type(library) is not dict:
        raise Failure('LIBRARY_SCHEMA')
    if not library:
        return []
    if 'expanded' in library:
        seeds = library['expanded']
        if type(seeds) is not list:
            raise Failure('LIBRARY_EXPANDED_SCHEMA')
    else:
        seeds = list(library.values())
    out = []
    for ast in seeds[:limit]:
        validate_ast(ast)
        out.append(copy.deepcopy(ast))
    return out


def propose(train, library=None, caps=None, check=lambda: None,
            diagnosis='authentic', revision_action=None, seed_AST=None):
    """Construct closed programs only from retained demonstrations.

    Diagnosis acts through measured residuals and actual bounded candidate branches.
    It does not select a task ID, intended task family or hidden answer. The blind
    control uses the same primitives and inferred parameters, with FIFO repair order.
    """
    valid_demos(train)
    if diagnosis not in ('authentic', 'blind') or revision_action not in (None,) + ACTIONS:
        raise Failure('DIAGNOSIS_OR_ACTION')
    limits = dict(DEFAULT_CAPS)
    if caps:
        caps = dict(caps)
        for alias, target in (('executions', 'primitive_executions'), ('max_programs', 'selected_programs'), ('generated', 'generated_states')):
            if alias in caps:
                if target in caps:
                    raise Failure('DUPLICATE_CAP_ALIAS')
                caps[target] = caps.pop(alias)
        if any(k not in limits for k in caps):
            raise Failure('UNKNOWN_CAP')
        limits.update(caps)
    if any((type(v) not in (int, float) if k == 'CPU_s' else type(v) is not int) or not math.isfinite(v) or v <= 0 for k, v in limits.items()):
        raise Failure('CAP_VALUE')
    start = time.process_time()
    meter = {'primitive_executions': 0, 'cell_work': 0,
             'primitive_limit': limits['primitive_executions'], 'cell_limit': limits['cell_work']}
    counts = collections.Counter()
    family_counts = {}
    selected, selected_records, seen_ast, seen_semantics = [], [], set(), {}
    evaluated_ast = set()
    pending, serial = [], 0
    best_error = 1.0
    seed = inp() if seed_AST is None else copy.deepcopy(seed_AST)
    validate_ast(seed, limits['max_depth'])
    seeds = _expanded_seeds(library or {}, int(limits['library_seeds']))
    status = 'COMPLETE_FINITE_SEARCH'
    reason = None

    def bounded():
        check()
        if time.process_time() - start >= limits['CPU_s']:
            raise Budget('CPU_CAP_UNKNOWN')
        if meter['primitive_executions'] > limits['primitive_executions']:
            raise Budget('PRIMITIVE_CAP_UNKNOWN')
        if meter['cell_work'] > limits['cell_work']:
            raise Budget('CELL_WORK_CAP_UNKNOWN')

    def push(ast, family, priority):
        nonlocal serial
        if structural_cost(ast) > limits['max_depth']:
            return
        key = digest(ast)
        if key in seen_ast:
            counts['syntactic_duplicates'] += 1
            return
        if counts['generated_states'] >= limits['generated_states']:
            raise Budget('GENERATION_CAP_UNKNOWN')
        seen_ast.add(key)
        counts['generated_states'] += 1
        serial += 1
        heapq.heappush(pending, ((priority if diagnosis == 'authentic' else (0,)), serial, ast, family))

    def repairs(ast, outputs, family):
        shape_errors, pixel_error = _residual(outputs, train)
        # Palette fitting is a shared exact constraint solver, including static/library seeds.
        mapping = _palette_map(outputs, train)
        if mapping is not None:
            if any(int(k) != v for k, v in mapping.items()):
                push(node('recolor', ast, mapping=mapping), 'rebind_palette', (0, pixel_error, structural_cost(ast)))
        elif not shape_errors:
            counts['palette_inconsistent'] += 1
        if revision_action == 'change_representation':
            return
        for params in _infer_resizes(outputs, train):
            push(node('resize', ast, **params), 'rebind_resize', (1, pixel_error, structural_cost(ast)))
        for params in _infer_shifts(outputs, train):
            push(node('shift', ast, **params), 'rebind_shift', (1, pixel_error, structural_cost(ast)))
        if revision_action == 'rebind':
            return
        if structural_cost(ast) < limits['max_depth'] and ast['op'] not in ('d4', 'recolor'):
            # Shape constraints eliminate incompatible symmetry roots before execution.
            for mode in D4[1:]:
                swapped = mode in ('r90', 'r270', 'transpose', 'antitranspose')
                if all((_shape(g)[::-1] if swapped else _shape(g)) == _shape(p['output'])
                       for g, p in zip(outputs, train)):
                    push(node('d4', ast, mode=mode), 'compose_geometry', (2, pixel_error, structural_cost(ast)))
        if revision_action in ('compose', 'library') and structural_cost(ast) <= 2:
            for role in BACKGROUNDS:
                push(node('crop', ast, background=role), 'compose_crop', (2, pixel_error, structural_cost(ast)))

    def evaluate(ast, family):
        nonlocal best_error
        bounded()
        ast_key = digest(ast)
        if ast_key in evaluated_ast:
            counts['queued_already_executed'] += 1
            return
        evaluated_ast.add(ast_key)
        stats = family_counts.setdefault(family, collections.Counter())
        stats['executed'] += 1
        outputs = []
        try:
            for pair in train:
                outputs.append(execute(ast, pair['input'], check=bounded, meter=meter))
        except Failure as error:
            counts['primitive_failures'] += 1
            stats['precondition_failure'] += 1
            if 'AMBIGUOUS' in str(error):
                counts['ambiguity_failures'] += 1
            return
        shape_errors, error = _residual(outputs, train)
        best_error = min(best_error, error)
        if not shape_errors and error == 0:
            # An exact closed witness is checked before any semantic pruning.
            # Replay is fresh and charged to the same primitive/cell/CPU meter.
            if not verify(ast, train, check=bounded, meter=meter):
                raise Failure('INDEPENDENT_REPLAY_DISAGREEMENT')
            selected.append(copy.deepcopy(ast))
            selected_records.append({'program_sha256': digest(ast), 'structural_cost': structural_cost(ast),
                                     'retained_count': len(train), 'exact_reverified': True, 'family': family})
            stats['exact_fit'] += 1
            counts['exact_fit'] += 1
            return
        signature = tuple(tuple(tuple(row) for row in grid) for grid in outputs)
        cost = structural_cost(ast)
        previous_cost = seen_semantics.get(signature)
        if previous_cost is not None and previous_cost <= cost:
            counts['semantic_duplicates'] += 1
            stats['semantic_duplicate'] += 1
            return
        if previous_cost is None:
            if counts['semantic_classes'] >= limits['semantic_classes']:
                raise Budget('SEMANTIC_CLASS_CAP_UNKNOWN')
            counts['semantic_classes'] += 1
            stats['new_semantic_class'] += 1
        else:
            counts['cheaper_semantic_representative'] += 1
        # Retain depth room when a cheaper representative arrives later.
        # Equal retained behavior is still not a proof of equal query behavior.
        seen_semantics[signature] = cost
        counts['shape_mismatch'] += bool(shape_errors)
        counts['same_shape_residual'] += bool(not shape_errors and error)
        repairs(ast, outputs, family)

    try:
        if revision_action != 'abstain':
            for ast in (seeds if revision_action in (None, 'library') else []):
                push(ast, 'library_seed', (-1, structural_cost(ast), 0))
            families = [] if revision_action == 'library' else _families(seed, revision_action)
            # First complete round gives each primitive family a root validation.
            # Pending repairs are interleaved afterwards, so no root can monopolize search.
            round_number = 0
            while families or pending:
                bounded()
                next_round = []
                for family, iterator in families:
                    try:
                        ast = next(iterator)
                        next_round.append((family, iterator))
                        key = digest(ast)
                        if key not in seen_ast:
                            if counts['generated_states'] >= limits['generated_states']:
                                raise Budget('GENERATION_CAP_UNKNOWN')
                            seen_ast.add(key)
                            counts['generated_states'] += 1
                            evaluate(ast, family)
                        else:
                            counts['syntactic_duplicates'] += 1
                            # A pending repair cannot suppress a family's fair root validation.
                            if key not in evaluated_ast:
                                evaluate(ast, family)
                    except StopIteration:
                        pass
                    if selected:
                        break
                families = next_round
                if selected:
                    status, reason = 'UNKNOWN', 'EXACT_WITNESS_FOUND_SEARCH_INCOMPLETE'
                    break
                if round_number:
                    for _ in range(3):
                        if not pending:
                            break
                        _, _, ast, family = heapq.heappop(pending)
                        evaluate(ast, family)
                        if selected:
                            break
                round_number += 1
                if selected:
                    status, reason = 'UNKNOWN', 'EXACT_WITNESS_FOUND_SEARCH_INCOMPLETE'
                    break
        else:
            reason = 'EXPLICIT_ABSTENTION'
    except Budget as error:
        status, reason = 'UNKNOWN', str(error)
    # This internal sample excludes receipt serialization; the outer protocol must
    # measure actual through-return CPU and reject any over-return witness.
    used = time.process_time() - start
    if used >= limits['CPU_s']:
        status, reason = 'UNKNOWN', 'CPU_CAP_UNKNOWN'
        selected, selected_records = [], []
        counts['over_budget_witnesses_discarded'] = 1
    requests = []
    if not selected:
        if counts['shape_mismatch']:
            requests.append('representation_or_output_extent')
        if counts['palette_inconsistent']:
            requests.append('conditional_color_or_object_relation')
        if counts['ambiguity_failures']:
            requests.append('relational_object_disambiguation')
        if counts['same_shape_residual']:
            requests.append('additional_composition_or_local_rule')
    diagnosis_record = {'schema': 'CORA_R25_DIAGNOSIS_V1', 'mode': diagnosis,
                        'revision_action': revision_action, 'status': status, 'stop_reason': reason,
                        'counts': dict(counts), 'families': {k: dict(v) for k, v in family_counts.items()},
                        'best_retained_pixel_error': best_error, 'next_capability_requests': requests,
                        'meter': meter, 'CPU_s': used, 'caps': limits}
    result = {'schema': SCHEMA, 'programs': selected, 'program_records': selected_records,
              'diagnosis': diagnosis_record}
    result['proposal_sha256'] = digest(result)
    return result


def get_failure_evidence(train, seed_AST=None, caps=None, check=lambda: None):
    """Observed retained execution residuals, normalized and shared across actions.

    No intended-family label is an input. The caller can supervise a revision model
    using subsequently executed action outcomes; this function never trains itself.
    """
    valid_demos(train)
    seed = inp() if seed_AST is None else seed_AST
    accumulated = [0.0] * len(EVIDENCE_FEATURES)
    for pair in train:
        check()
        target = pair['output']
        try:
            out = execute(seed, pair['input'], check=check)
        except Failure:
            accumulated[7] += 1
            accumulated[6] += 1
            continue
        equal_shape = _shape(out) == _shape(target)
        accumulated[0] += not equal_shape
        accumulated[1] += _residual([out], [pair])[1]
        p, q = set(v for row in out for v in row), set(v for row in target for v in row)
        accumulated[2] += len(p ^ q) / max(1, len(p | q))
        bg_out = background(out, 'zero')
        bg_target = background(target, 'zero')
        points, desired = _points(out, bg_out), _points(target, bg_target)
        accumulated[3] += abs(len(points)-len(desired)) / max(1, len(out)*len(out[0]), len(target)*len(target[0]))
        try:
            a, b = _bounds(points), _bounds(desired)
            accumulated[4] += sum(abs(x-y) for x, y in zip(a, b)) / 116.0
        except Failure:
            accumulated[4] += bool(points) != bool(desired)
        old_components = _components(out, bg_out, check=check)
        new_components = _components(target, bg_target, check=check)
        accumulated[5] += abs(len(old_components)-len(new_components)) / max(1, len(old_components), len(new_components))
        accumulated[6] += out != target
        for grid in (out, target):
            count = collections.Counter(v for row in grid for v in row)
            maximum = max(count.values())
            accumulated[8] += (sum(n == maximum for n in count.values()) > 1) / 2.0
        accumulated[9] += min(1.0, structural_cost(seed) / float((caps or {}).get('max_depth', DEFAULT_CAPS['max_depth'])))
    values = [min(1.0, max(0.0, v/len(train))) for v in accumulated]
    return {'schema': 'CORA_R25_EVIDENCE_V1', 'feature_names': list(EVIDENCE_FEATURES),
            'features': values, 'retained_count': len(train), 'seed_sha256': digest(seed)}
