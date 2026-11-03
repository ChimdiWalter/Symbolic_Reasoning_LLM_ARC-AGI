"""CORA R26: bounded executable grammar extension over frozen R25.

Only retained demonstrations enter construction. New mechanisms are modular
period completion, panel mask algebra, relational object alignment, and axis
aggregation. An exact retained witness is evidence of fit, not generalization.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import heapq
import importlib.util
import itertools
import math
from pathlib import Path
import time

_BASE_PATH = Path(__file__).resolve().parents[2] / 'round25' / 'diagnosis_constructor' / 'engine.py'
BASE_SHA256 = '009788d7071929240a5231032eaeb3e783b1313e92aea14a9a81043dccb56559'
if hashlib.sha256(_BASE_PATH.read_bytes()).hexdigest() != BASE_SHA256:
    raise RuntimeError('FROZEN_R25_DEPENDENCY_HASH')
_spec = importlib.util.spec_from_file_location('_cora_r26_frozen_r25', _BASE_PATH)
BASE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BASE)

Failure, Budget = BASE.Failure, BASE.Budget
canonical, digest = BASE.canonical, BASE.digest
valid_grid, valid_demos = BASE.valid_grid, BASE.valid_demos
node, inp, input_ast = BASE.node, BASE.inp, BASE.inp
structural_cost = BASE.structural_cost
BACKGROUNDS, D4, ACTIONS = BASE.BACKGROUNDS, BASE.D4, BASE.ACTIONS
EVIDENCE_FEATURES = BASE.EVIDENCE_FEATURES
DEFAULT_CAPS = dict(BASE.DEFAULT_CAPS)
SCHEMA = 'CORA_R26_COVERAGE_PROPOSAL_V1'
EXTENSION_DOMAINS = {
    'periodic_complete': {'background': BACKGROUNDS, 'row_period': tuple(range(1, 16)),
                          'col_period': tuple(range(1, 16))},
    'panel_boolean': {'background': BACKGROUNDS, 'axis': ('rows', 'columns'), 'gap': (0, 1),
                      'combine': ('union', 'intersection', 'xor', 'left_minus_right', 'right_minus_left'),
                      'color': tuple(range(10))},
    'align_objects': {'background': BACKGROUNDS, 'connectivity': (4, 8),
                      'color_mode': ('mono', 'foreground'), 'anchor': ('largest', 'smallest'),
                      'edge': ('top', 'bottom', 'left', 'right')},
    'axis_aggregate': {'background': BACKGROUNDS, 'axis': ('rows', 'columns'),
                       'statistic': ('foreground_mode', 'foreground_count', 'color_count'),
                       'color': tuple(range(10))},
}
OP_PARAMETER_DOMAINS = dict(BASE.OP_PARAMETER_DOMAINS, **EXTENSION_DOMAINS)


def validate_ast(ast, max_depth=12, _depth=0):
    if type(max_depth) is not int or max_depth < 0 or _depth > max_depth:
        raise Failure('AST_DEPTH')
    if type(ast) is not dict or set(ast) != {'op', 'type', 'args', 'params'}:
        raise Failure('AST_SCHEMA')
    op, args, params = ast['op'], ast['args'], ast['params']
    if ast['type'] != 'Grid' or type(op) is not str or op not in OP_PARAMETER_DOMAINS:
        raise Failure('AST_TYPE_OR_OPERATION')
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
                    type(v) is not int or not 0 <= v <= 9 for k, v in value.items()):
                raise Failure('AST_PALETTE')
        elif not any(type(value) is type(item) and value == item for item in domain):
            raise Failure('AST_PARAMETER_DOMAIN')
    for child in args:
        validate_ast(child, max_depth, _depth + 1)


def lower_plain(ast, library=None):
    validate_ast(ast)
    return copy.deepcopy(ast)


def _components(grid, bg, connectivity, color_mode, check):
    """Linear grid scan and flood fill; no quadratic repeated minimum selection."""
    h, w = len(grid), len(grid[0])
    seen, out = set(), []
    directions = ((-1, 0), (0, -1), (0, 1), (1, 0)) if connectivity == 4 else tuple(
        (dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
    for r in range(h):
        check()
        for c in range(w):
            if grid[r][c] == bg or (r, c) in seen:
                continue
            seen.add((r, c))
            todo, component = [(r, c)], []
            while todo:
                check()
                x, y = todo.pop()
                component.append((x, y))
                for dr, dc in directions:
                    a, b = x + dr, y + dc
                    if (0 <= a < h and 0 <= b < w and (a, b) not in seen and
                            grid[a][b] != bg and
                            (color_mode == 'foreground' or grid[a][b] == grid[x][y])):
                        seen.add((a, b))
                        todo.append((a, b))
            out.append(component)
    return out


def _extension(op, grid, p, check):
    h, w = len(grid), len(grid[0])
    bg = BASE.background(grid, p['background'])
    if op == 'periodic_complete':
        rp, cp = p['row_period'], p['col_period']
        if rp > h or cp > w:
            raise Failure('PERIOD_EXCEEDS_GRID')
        residues = {}
        for r, row in enumerate(grid):
            check()
            for c, value in enumerate(row):
                if value == bg:
                    continue
                key = r % rp, c % cp
                if key in residues and residues[key] != value:
                    raise Failure('PERIODIC_COLOR_CONFLICT')
                residues[key] = value
        if not residues:
            raise Failure('NO_PERIODIC_EVIDENCE')
        return [[residues.get((r % rp, c % cp), bg) for c in range(w)] for r in range(h)]
    if op == 'panel_boolean':
        axis, gap = p['axis'], p['gap']
        size = h if axis == 'rows' else w
        if size <= gap or (size-gap) % 2:
            raise Failure('PANEL_EQUAL_HALVES')
        half = (size-gap) // 2
        if gap:
            separator = grid[half] if axis == 'rows' else [row[half] for row in grid]
            if len(set(separator)) != 1:
                raise Failure('PANEL_SEPARATOR_NOT_CONSTANT')
        if axis == 'rows':
            left, right = grid[:half], grid[half+gap:]
        else:
            left = [row[:half] for row in grid]
            right = [row[half+gap:] for row in grid]
        out = []
        for arow, brow in zip(left, right):
            check()
            values = []
            for a, b in zip(arow, brow):
                x, y = a != bg, b != bg
                selected = {'union': x or y, 'intersection': x and y, 'xor': x != y,
                            'left_minus_right': x and not y,
                            'right_minus_left': y and not x}[p['combine']]
                values.append(p['color'] if selected else bg)
            out.append(values)
        return out
    if op == 'align_objects':
        components = _components(grid, bg, p['connectivity'], p['color_mode'], check)
        if len(components) < 2:
            raise Failure('ALIGN_NEEDS_MULTIPLE_OBJECTS')
        size = (max if p['anchor'] == 'largest' else min)(len(obj) for obj in components)
        anchors = [obj for obj in components if len(obj) == size]
        if len(anchors) != 1:
            raise Failure('AMBIGUOUS_OBJECT_ANCHOR')
        anchor = anchors[0]
        edge_index = {'top': 0, 'left': 1, 'bottom': 2, 'right': 3}[p['edge']]
        target = BASE._bounds(anchor)[edge_index]
        out = [[bg] * w for _ in range(h)]
        occupied = set()
        for obj in components:
            check()
            delta = target - BASE._bounds(obj)[edge_index]
            dr, dc = (delta, 0) if p['edge'] in ('top', 'bottom') else (0, delta)
            for r, c in obj:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < h and 0 <= nc < w):
                    raise Failure('ALIGN_CLIPS_OBJECT')
                if (nr, nc) in occupied:
                    raise Failure('ALIGN_OBJECT_COLLISION')
                occupied.add((nr, nc))
                out[nr][nc] = grid[r][c]
        return out
    if op == 'axis_aggregate':
        rows = grid if p['axis'] == 'rows' else [list(column) for column in zip(*grid)]
        values = []
        for row in rows:
            check()
            foreground = [v for v in row if v != bg]
            if p['statistic'] == 'foreground_mode':
                value = BASE._unique_mode(foreground) if foreground else bg
            elif p['statistic'] == 'foreground_count':
                value = len(foreground)
            else:
                value = sum(v == p['color'] for v in row)
            if not 0 <= value <= 9:
                raise Failure('AGGREGATE_COUNT_EXCEEDS_COLOR_DOMAIN')
            values.append(value)
        return [[value] for value in values] if p['axis'] == 'rows' else [values]
    raise Failure('UNKNOWN_EXTENSION')


def execute(program, raw, library=None, check=lambda: None, meter=None):
    """Pure mixed-grammar interpreter with precharged conservative work units.

    Every attempted non-input primitive is charged before execution, including
    explicit precondition failures. Original work units count maximum read/write
    cell capacity, as in R25; extensions also debit their extra scans. This is a
    finite work proxy, not instruction counting. CPU must be metered separately.
    External check exceptions propagate.
    """
    check()
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
        # Original operations use a fixed 1800-cell budget as R25 does. New
        # operations include scans/neighbor tests/output in their upper bound.
        n = len(grid)*len(grid[0])
        charge = (24*n + 1800 if ast['op'] == 'align_objects' else
                  8*n + 1800 if ast['op'] in EXTENSION_DOMAINS else 1800)
        if meter.get('primitive_limit') is not None and meter['primitive_executions'] + 1 > meter['primitive_limit']:
            raise Budget('PRIMITIVE_CAP_UNKNOWN')
        if meter.get('cell_limit') is not None and meter['cell_work'] + charge > meter['cell_limit']:
            raise Budget('CELL_WORK_CAP_UNKNOWN')
        meter['primitive_executions'] += 1
        meter['cell_work'] += charge
        out = (_extension(ast['op'], grid, ast['params'], check) if ast['op'] in EXTENSION_DOMAINS else
               BASE._primitive(ast['op'], grid, ast['params'], check))
        valid_grid(out)
        check()
        return out
    return run(program)


def predict(program, query, library=None, check=lambda: None):
    return execute(program, query, library=library, check=check)


def verify(program, train, check=lambda: None, meter=None):
    valid_demos(train)
    validate_ast(program)
    return all(execute(program, pair['input'], check=check, meter=meter) == pair['output'] for pair in train)


def _extension_families(seed, outputs, train, check):
    """Finite candidate constraints from all visible demos; no query or IDs."""
    def periodic():
        if any(BASE._shape(g) != BASE._shape(p['output']) for g, p in zip(outputs, train)):
            return
        targets = [p['output'] for p in train]
        mh, mw = min(len(g) for g in targets), min(len(g[0]) for g in targets)
        for rp, cp in itertools.product(range(1, min(15, mh)+1), range(1, min(15, mw)+1)):
            check()
            if all(all(g[r][c] == g[r % rp][c % cp] for r in range(len(g)) for c in range(len(g[0])))
                   for g in targets):
                for role in BACKGROUNDS:
                    yield node('periodic_complete', seed, background=role, row_period=rp, col_period=cp)
    def panel():
        for axis, gap, role in itertools.product(('columns', 'rows'), (0, 1), BACKGROUNDS):
            check()
            if not all((len(g), (len(g[0])-gap)//2) == BASE._shape(p['output']) and
                       len(g[0]) > gap and (len(g[0])-gap) % 2 == 0
                       if axis == 'columns' else
                       ((len(g)-gap)//2, len(g[0])) == BASE._shape(p['output']) and
                       len(g) > gap and (len(g)-gap) % 2 == 0 for g, p in zip(outputs, train)):
                continue
            colors = set(range(10))
            try:
                for grid, pair in zip(outputs, train):
                    bg = BASE.background(grid, role)
                    colors &= set(v for row in pair['output'] for v in row if v != bg)
            except Failure:
                continue
            for combine, color in itertools.product(EXTENSION_DOMAINS['panel_boolean']['combine'], sorted(colors)):
                yield node('panel_boolean', seed, background=role, axis=axis, gap=gap, combine=combine, color=color)
    def align():
        if any(BASE._shape(g) != BASE._shape(p['output']) for g, p in zip(outputs, train)):
            return
        for edge, anchor, role, cm, conn in itertools.product(
                ('top', 'bottom', 'left', 'right'), ('largest', 'smallest'), BACKGROUNDS,
                ('foreground', 'mono'), (4, 8)):
            yield node('align_objects', seed, background=role, connectivity=conn,
                       color_mode=cm, anchor=anchor, edge=edge)
    def aggregate():
        for axis, statistic, role in itertools.product(('rows', 'columns'),
                EXTENSION_DOMAINS['axis_aggregate']['statistic'], BACKGROUNDS):
            if not all((len(g), 1) == BASE._shape(p['output']) if axis == 'rows' else
                       (1, len(g[0])) == BASE._shape(p['output']) for g, p in zip(outputs, train)):
                continue
            for color in (range(10) if statistic == 'color_count' else (0,)):
                yield node('axis_aggregate', seed, background=role, axis=axis, statistic=statistic, color=color)
    return [('periodic', periodic()), ('panel', panel()), ('alignment', align()), ('aggregate', aggregate())]


def _limits(caps):
    values = dict(DEFAULT_CAPS)
    supplied = dict(caps or {})
    for alias, target in (('executions', 'primitive_executions'), ('max_programs', 'selected_programs'),
                          ('generated', 'generated_states')):
        if alias in supplied:
            if target in supplied:
                raise Failure('DUPLICATE_CAP_ALIAS')
            supplied[target] = supplied.pop(alias)
    if any(k not in values for k in supplied):
        raise Failure('UNKNOWN_CAP')
    values.update(supplied)
    if any((type(v) not in (int, float) if k == 'CPU_s' else type(v) is not int) or
           not math.isfinite(v) or v <= 0 for k, v in values.items()):
        raise Failure('CAP_VALUE')
    return values


def static_programs(train, caps=None, check=lambda: None, max_programs=16):
    """R25 input-only static seed API; no learned/extension bodies supplied."""
    return BASE.static_programs(train, caps=caps, check=check, max_programs=max_programs)


def propose(train, library=None, caps=None, check=lambda: None,
            diagnosis='authentic', revision_action=None, seed_AST=None):
    start = time.process_time()
    check()
    valid_demos(train)
    if diagnosis not in ('authentic', 'blind') or revision_action not in (None,) + ACTIONS:
        raise Failure('DIAGNOSIS_OR_ACTION')
    limits = _limits(caps)
    meter = {'primitive_executions': 0, 'cell_work': 0,
             'primitive_limit': limits['primitive_executions'], 'cell_limit': limits['cell_work']}
    counts, family_counts = collections.Counter(), {}
    selected, records, seen, evaluated, semantics = [], [], set(), set(), {}
    pending, serial, best_error = [], 0, 1.0
    external_cancellation = []
    status, reason = 'COMPLETE_FINITE_SEARCH', None
    seed = inp() if seed_AST is None else copy.deepcopy(seed_AST)
    validate_ast(seed, limits['max_depth'])
    raw_library = library or {}
    if type(raw_library) is not dict:
        raise Failure('LIBRARY_SCHEMA')
    seeds = raw_library.get('expanded', list(raw_library.values())) if raw_library else []
    if type(seeds) is not list:
        raise Failure('LIBRARY_EXPANDED_SCHEMA')
    seeds = [copy.deepcopy(ast) for ast in seeds[:limits['library_seeds']]]
    for ast in seeds:
        validate_ast(ast, limits['max_depth'])

    def bounded():
        try:
            check()
        except BaseException as error:
            # A caller may itself use the exported Budget type for cancellation.
            # Preserve that exception rather than treating it as internal UNKNOWN.
            external_cancellation.append(error)
            raise
        if time.process_time() - start >= limits['CPU_s']:
            raise Budget('CPU_CAP_UNKNOWN')

    def queue(ast, family, priority):
        nonlocal serial
        if structural_cost(ast) > limits['max_depth']:
            return
        key = digest(ast)
        if key in seen:
            counts['syntactic_duplicates'] += 1
            return
        if counts['generated_states'] >= limits['generated_states']:
            raise Budget('GENERATION_CAP_UNKNOWN')
        seen.add(key)
        counts['generated_states'] += 1
        serial += 1
        heapq.heappush(pending, ((priority if diagnosis == 'authentic' else (0,)), serial, ast, family))

    def repairs(ast, outputs):
        shape_error, error = BASE._residual(outputs, train)
        mapping = BASE._palette_map(outputs, train)
        if mapping is not None and any(int(k) != v for k, v in mapping.items()):
            queue(node('recolor', ast, mapping=mapping), 'rebind_palette', (0, error, structural_cost(ast)))
        elif mapping is None and not shape_error:
            counts['palette_inconsistent'] += 1
        for params in BASE._infer_resizes(outputs, train):
            queue(node('resize', ast, **params), 'rebind_resize', (1, error, structural_cost(ast)))
        for params in BASE._infer_shifts(outputs, train):
            queue(node('shift', ast, **params), 'rebind_shift', (1, error, structural_cost(ast)))
        if structural_cost(ast) < limits['max_depth'] and ast['op'] not in ('d4', 'recolor'):
            for mode in D4[1:]:
                swapped = mode in ('r90', 'r270', 'transpose', 'antitranspose')
                if all((BASE._shape(g)[::-1] if swapped else BASE._shape(g)) == BASE._shape(p['output'])
                       for g, p in zip(outputs, train)):
                    queue(node('d4', ast, mode=mode), 'compose_geometry', (2, error, structural_cost(ast)))
        if revision_action in ('compose', 'library') and structural_cost(ast) <= 2:
            for role in BACKGROUNDS:
                queue(node('crop', ast, background=role), 'compose_crop', (2, error, structural_cost(ast)))

    def evaluate(ast, family):
        nonlocal best_error
        bounded()
        key = digest(ast)
        if key in evaluated:
            return
        evaluated.add(key)
        stats = family_counts.setdefault(family, collections.Counter())
        stats['executed'] += 1
        try:
            outputs = [execute(ast, pair['input'], check=bounded, meter=meter) for pair in train]
        except Failure as error:
            if external_cancellation and external_cancellation[-1] is error:
                raise
            stats['precondition_failure'] += 1
            counts['primitive_failures'] += 1
            counts['ambiguity_failures'] += 'AMBIGUOUS' in str(error)
            return
        shape_errors, error = BASE._residual(outputs, train)
        best_error = min(best_error, error)
        if not shape_errors and error == 0:
            if not verify(ast, train, check=bounded, meter=meter):
                raise Failure('INDEPENDENT_REPLAY_DISAGREEMENT')
            selected.append(copy.deepcopy(ast))
            records.append({'program_sha256': digest(ast), 'structural_cost': structural_cost(ast),
                            'retained_count': len(train), 'exact_reverified': True, 'family': family})
            stats['exact_fit'] += 1
            counts['exact_fit'] += 1
            return
        signature = canonical(outputs)
        cost, previous = structural_cost(ast), semantics.get(signature)
        if previous is not None and previous <= cost:
            counts['semantic_duplicates'] += 1
            return
        if previous is None:
            if counts['semantic_classes'] >= limits['semantic_classes']:
                raise Budget('SEMANTIC_CLASS_CAP_UNKNOWN')
            counts['semantic_classes'] += 1
        semantics[signature] = cost
        counts['shape_mismatch'] += bool(shape_errors)
        counts['same_shape_residual'] += bool(not shape_errors and error)
        repairs(ast, outputs)

    try:
        if revision_action != 'abstain':
            # Every original and new family gets one root turn per round. Guidance
            # changes ordering but cannot erase the ordinary grammar coverage floor.
            families = BASE._families(seed, None)
            seed_outputs = [execute(seed, pair['input'], check=bounded, meter=meter) for pair in train]
            families += _extension_families(seed, seed_outputs, train, bounded)
            if seeds:
                families.append(('library_seed', iter(seeds)))
            preferred = {'rebind': ('identity',), 'change_representation': ('crop', 'object', 'panel', 'aggregate'),
                         'revise_fragment': ('periodic', 'alignment', 'geometry', 'pack', 'bbox', 'symmetry', 'holes'),
                         'compose': ('identity', 'periodic', 'panel', 'alignment', 'aggregate'),
                         'library': ('library_seed',)}.get(revision_action, ())
            if diagnosis == 'authentic' and preferred:
                families.sort(key=lambda item: item[0] not in preferred)
            round_number = 0
            while families or pending:
                bounded()
                next_round = []
                for family, iterator in families:
                    bounded()
                    try:
                        ast = next(iterator)
                    except StopIteration:
                        continue
                    next_round.append((family, iterator))
                    key = digest(ast)
                    if key not in seen:
                        if counts['generated_states'] >= limits['generated_states']:
                            raise Budget('GENERATION_CAP_UNKNOWN')
                        seen.add(key)
                        counts['generated_states'] += 1
                    evaluate(ast, family)
                    if selected:
                        break
                families = next_round
                if not selected and round_number:
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
        if external_cancellation and external_cancellation[-1] is error:
            raise
        status, reason = 'UNKNOWN', str(error)
    used = time.process_time() - start
    if used >= limits['CPU_s']:
        status, reason = 'UNKNOWN', 'CPU_CAP_UNKNOWN'
        selected, records = [], []
        counts['over_budget_witnesses_discarded'] += 1
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
    receipt = {'schema': 'CORA_R26_DIAGNOSIS_V1', 'mode': diagnosis, 'revision_action': revision_action,
               'guidance_preserves_static_family_floor': True, 'status': status, 'stop_reason': reason,
               'floor_semantics': 'interleaved_root_turns_no_equal_complete_coverage_guarantee_under_caps',
               'counts': dict(counts), 'families': {k: dict(v) for k, v in family_counts.items()},
               'best_retained_pixel_error': best_error, 'next_capability_requests': requests,
               'meter': meter, 'work_unit_semantics': 'precharged_cell_capacity_and_extension_scan_proxy',
               'CPU_s': used, 'caps': limits, 'frozen_base_sha256': BASE_SHA256}
    result = {'schema': SCHEMA, 'programs': selected, 'program_records': records, 'diagnosis': receipt}
    result['proposal_sha256'] = digest(result)
    return result


def get_failure_evidence(train, seed_AST=None, caps=None, check=lambda: None):
    """R25's ten generic residual features, using the new typed interpreter."""
    valid_demos(train)
    seed = inp() if seed_AST is None else seed_AST
    accumulated = [0.0] * len(EVIDENCE_FEATURES)
    external_cancellation = []
    def caller_check():
        try:
            check()
        except BaseException as error:
            external_cancellation.append(error)
            raise
    for pair in train:
        caller_check()
        target = pair['output']
        try:
            out = execute(seed, pair['input'], check=caller_check)
        except Failure as error:
            if external_cancellation and external_cancellation[-1] is error:
                raise
            accumulated[6] += 1
            accumulated[7] += 1
            continue
        accumulated[0] += BASE._shape(out) != BASE._shape(target)
        accumulated[1] += BASE._residual([out], [pair])[1]
        a, b = {v for row in out for v in row}, {v for row in target for v in row}
        accumulated[2] += len(a ^ b) / max(1, len(a | b))
        points, desired = BASE._points(out, 0), BASE._points(target, 0)
        accumulated[3] += abs(len(points)-len(desired)) / max(1, len(out)*len(out[0]), len(target)*len(target[0]))
        try:
            accumulated[4] += sum(abs(x-y) for x, y in zip(BASE._bounds(points), BASE._bounds(desired))) / 116.0
        except Failure:
            accumulated[4] += bool(points) != bool(desired)
        old = _components(out, 0, 4, 'foreground', caller_check)
        new = _components(target, 0, 4, 'foreground', caller_check)
        accumulated[5] += abs(len(old)-len(new)) / max(1, len(old), len(new))
        accumulated[6] += out != target
        for grid in (out, target):
            count = collections.Counter(v for row in grid for v in row)
            accumulated[8] += (sum(n == max(count.values()) for n in count.values()) > 1) / 2.0
        accumulated[9] += min(1.0, structural_cost(seed) / float((caps or {}).get('max_depth', DEFAULT_CAPS['max_depth'])))
    return {'schema': 'CORA_R26_EVIDENCE_V1', 'feature_names': list(EVIDENCE_FEATURES),
            'features': [min(1.0, max(0.0, value / len(train))) for value in accumulated],
            'retained_count': len(train), 'seed_sha256': digest(seed)}
