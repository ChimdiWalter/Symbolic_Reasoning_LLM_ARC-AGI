"""A bounded learned conditional Color program over a fixed pixel feature DSL.

The constructor learns a serializable decision tree from retained grid pairs.
No sklearn, task IDs, absolute row/column keys, grid lookup table, generated
Python, query inputs or answers enter training. The language is engineered;
learning a new conditional program is not invention of new primitive semantics.
Conceptual predecessors in the user's read-only Reasoning_Project code are
concept_grammar.py (SHA256 0a9ad226fc00c2edaf8f709b652ce79768e99a137f155feb05009b80f0f1fb8e)
and composable_reasoner.py (bf99d4bbaeeaa05ef29b7e83ae0dada1cdd20b7fc4dd867f17e53d832d166210).
This implementation is independently authored and imports neither file.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import math
import time

FEATURES = ('center', 'north', 'south', 'west', 'east', 'row_foreground_count',
            'column_foreground_count', 'border_distance', 'component_area',
            'component_height', 'component_width')
NUMERIC = frozenset(FEATURES[5:])
DEFAULT_CAPS = {'CPU_s': 2.0, 'max_depth': 4, 'max_nodes': 31,
                'min_support': 2, 'min_demos': 2, 'max_samples': 9000,
                'predicate_work': 2000000, 'feature_cell_work': 2000000}


class Failure(ValueError):
    pass


class Abstention(ValueError):
    pass


class _Limit(TimeoutError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def valid_grid(grid):
    if (type(grid) is not list or not 1 <= len(grid) <= 30 or type(grid[0]) is not list
            or not 1 <= len(grid[0]) <= 30 or any(type(row) is not list or len(row) != len(grid[0])
                or any(type(value) is not int or not 0 <= value <= 9 for value in row) for row in grid)):
        raise Failure('GRID_SCHEMA')


def _limits(caps):
    result = dict(DEFAULT_CAPS)
    supplied = dict(caps or {})
    if any(key not in result for key in supplied):
        raise Failure('UNKNOWN_CAP')
    result.update(supplied)
    for key, value in result.items():
        good_type = type(value) in (int, float) if key == 'CPU_s' else type(value) is int
        if not good_type or not math.isfinite(value) or value <= 0:
            raise Failure('CAP_VALUE')
    if result['max_depth'] > 4 or result['max_nodes'] > 31 or result['min_support'] < 2 or result['min_demos'] < 2:
        raise Failure('DECLARED_LANGUAGE_OR_SUPPORT_BOUND')
    return result


class _Budget:
    def __init__(self, limits, check):
        self.limits, self.check, self.started = limits, check, time.process_time()
        self.used = {'predicate_work': 0, 'feature_cell_work': 0}
        self.external = []

    def guard(self):
        try:
            self.check()
        except BaseException as error:
            self.external.append(error)
            raise
        if time.process_time() - self.started >= self.limits['CPU_s']:
            raise _Limit('CPU_CAP_UNKNOWN')

    def spend(self, name, value):
        self.guard()
        if self.used[name] + value > self.limits[name]:
            raise _Limit(name.upper() + '_CAP_UNKNOWN')
        self.used[name] += value


def _features(grid, budget):
    valid_grid(grid)
    h, w = len(grid), len(grid[0])
    budget.spend('feature_cell_work', 64 * h * w)
    area, height, width = {}, {}, {}
    seen = set()
    for r in range(h):
        budget.guard()
        for c in range(w):
            if not grid[r][c] or (r, c) in seen:
                continue
            todo, component = [(r, c)], []
            seen.add((r, c))
            while todo:
                budget.guard()
                point = todo.pop()
                component.append(point)
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = point[0] + dr, point[1] + dc
                    if 0 <= nr < h and 0 <= nc < w and grid[nr][nc] and (nr, nc) not in seen:
                        seen.add((nr, nc)); todo.append((nr, nc))
            bh = max(p[0] for p in component) - min(p[0] for p in component) + 1
            bw = max(p[1] for p in component) - min(p[1] for p in component) + 1
            for point in component:
                area[point], height[point], width[point] = len(component), bh, bw
    rows = [sum(value != 0 for value in row) for row in grid]
    cols = [sum(grid[r][c] != 0 for r in range(h)) for c in range(w)]
    result = []
    for r in range(h):
        budget.guard()
        for c in range(w):
            neighbors = [grid[r + dr][c + dc] if 0 <= r + dr < h and 0 <= c + dc < w else 10
                         for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))]
            result.append((grid[r][c], *neighbors, rows[r], cols[c],
                           min(r, c, h - 1 - r, w - 1 - c), area.get((r, c), 0),
                           height.get((r, c), 0), width.get((r, c), 0)))
    return result


def _emissions(colors):
    return ([{'kind': 'feature', 'feature': feature} for feature in FEATURES[:5]]
            + [{'kind': 'constant', 'color': color} for color in sorted(colors)])


def _emit(spec, feature):
    return feature[FEATURES.index(spec['feature'])] if spec['kind'] == 'feature' else spec['color']


def _fit_emit(indices, examples, emissions, budget):
    best = None
    for order, spec in enumerate(emissions):
        budget.spend('predicate_work', len(indices))
        errors = sum(_emit(spec, examples[i][0]) != examples[i][1] for i in indices)
        # Copy/neighborhood roles cost less than a literal color; stable ties
        # favor copy, making unchanged behavior a compact executable rule.
        key = (errors, 1 if spec['kind'] == 'feature' else 2, order)
        if best is None or key < best[0]:
            best = (key, spec)
    return best[0][0], copy.deepcopy(best[1])


def _support(indices, examples, limits):
    return (len(indices) >= limits['min_support'] and
            len({examples[i][2] for i in indices}) >= limits['min_demos'])


def _construct(indices, examples, emissions, budget, depth, state):
    budget.guard()
    if state['nodes'] >= budget.limits['max_nodes']:
        raise _Limit('NODE_CAP_UNKNOWN')
    state['nodes'] += 1
    if not _support(indices, examples, budget.limits):
        return None
    error, emission = _fit_emit(indices, examples, emissions, budget)
    info = {'support': len(indices), 'support_demos': len({examples[i][2] for i in indices})}
    if error == 0:
        return dict(info, kind='emit', type='Color', emission=emission)
    if depth >= budget.limits['max_depth']:
        state['unresolved_leaves'] += 1
        return None
    best = None
    for feature_index, name in enumerate(FEATURES):
        budget.guard()
        values = sorted({examples[i][0][feature_index] for i in indices})
        predicates = [('eq', value) for value in values]
        if name in NUMERIC:
            predicates += [('le', value) for value in values[:-1]]
        for operation, value in predicates:
            budget.spend('predicate_work', len(indices))
            yes = [i for i in indices if (examples[i][0][feature_index] == value if operation == 'eq'
                                         else examples[i][0][feature_index] <= value)]
            yes_set = set(yes)
            no = [i for i in indices if i not in yes_set]
            if not _support(yes, examples, budget.limits) or not _support(no, examples, budget.limits):
                continue
            left_error, _ = _fit_emit(yes, examples, emissions, budget)
            right_error, _ = _fit_emit(no, examples, emissions, budget)
            key = (left_error + right_error, 0 if operation == 'eq' else 1, feature_index, value)
            if best is None or key < best[0]:
                best = (key, name, operation, value, values, yes, no)
    if best is None:
        state['unresolved_leaves'] += 1
        return None
    _, name, operation, value, values, yes_indices, no_indices = best
    yes = _construct(yes_indices, examples, emissions, budget, depth + 1, state)
    no = _construct(no_indices, examples, emissions, budget, depth + 1, state)
    if yes is None or no is None:
        return None
    return dict(info, kind='if', type='Color',
                predicate={'feature': name, 'operation': operation, 'value': value,
                           'observed_values': values}, yes=yes, no=no)


def validate_model(model):
    if type(model) is not dict or set(model) != {'schema', 'features', 'background', 'tree', 'training_demo_sha256', 'model_sha256'}:
        raise Failure('MODEL_SCHEMA')
    if (model['schema'] != 'CORA_CONDITIONAL_COLOR_TREE_V1' or model['features'] != list(FEATURES)
            or type(model['background']) is not int or model['background'] != 0):
        raise Failure('MODEL_FEATURE_CONTRACT')
    if type(model['training_demo_sha256']) is not str or len(model['training_demo_sha256']) != 64:
        raise Failure('MODEL_PROVENANCE')
    count = 0
    def walk(node, depth):
        nonlocal count
        count += 1
        if depth > 4 or count > 31 or type(node) is not dict or node.get('type') != 'Color':
            raise Failure('TREE_TYPE_OR_SIZE')
        if (type(node.get('support')) is not int or node['support'] < 2 or
                type(node.get('support_demos')) is not int or node['support_demos'] < 2):
            raise Failure('TREE_SUPPORT')
        if node.get('kind') == 'emit':
            if set(node) != {'kind', 'type', 'emission', 'support', 'support_demos'}:
                raise Failure('EMIT_FIELDS')
            spec = node['emission']
            if type(spec) is not dict:
                raise Failure('EMISSION_SCHEMA')
            if spec.get('kind') == 'feature':
                if set(spec) != {'kind', 'feature'} or spec['feature'] not in FEATURES[:5]:
                    raise Failure('EMISSION_FEATURE')
            elif spec.get('kind') == 'constant':
                if set(spec) != {'kind', 'color'} or type(spec['color']) is not int or not 0 <= spec['color'] <= 9:
                    raise Failure('EMISSION_COLOR')
            else:
                raise Failure('EMISSION_KIND')
        elif node.get('kind') == 'if':
            if set(node) != {'kind', 'type', 'predicate', 'yes', 'no', 'support', 'support_demos'}:
                raise Failure('IF_FIELDS')
            pred = node['predicate']
            if (type(pred) is not dict or set(pred) != {'feature', 'operation', 'value', 'observed_values'}
                    or pred['feature'] not in FEATURES or pred['operation'] not in ('eq', 'le')
                    or pred['operation'] == 'le' and pred['feature'] not in NUMERIC
                    or type(pred['value']) is not int or type(pred['observed_values']) is not list
                    or not pred['observed_values'] or any(type(v) is not int for v in pred['observed_values'])
                    or pred['observed_values'] != sorted(set(pred['observed_values']))
                    or pred['value'] not in pred['observed_values']):
                raise Failure('PREDICATE_SCHEMA')
            walk(node['yes'], depth + 1); walk(node['no'], depth + 1)
        else:
            raise Failure('TREE_KIND')
    walk(model['tree'], 0)
    payload = {key: value for key, value in model.items() if key != 'model_sha256'}
    if digest(payload) != model['model_sha256']:
        raise Failure('MODEL_HASH')
    return count


def _apply_features(model, features, budget):
    values = []
    for feature in features:
        budget.guard()
        node = model['tree']
        while node['kind'] == 'if':
            budget.spend('predicate_work', 1)
            pred = node['predicate']; value = feature[FEATURES.index(pred['feature'])]
            if value not in pred['observed_values']:
                raise Abstention('UNSEEN_ROUTING_FEATURE_VALUE')
            truth = value == pred['value'] if pred['operation'] == 'eq' else value <= pred['value']
            node = node['yes'] if truth else node['no']
        budget.spend('predicate_work', 1)
        color = _emit(node['emission'], feature)
        if not 0 <= color <= 9:
            raise Abstention('UNOBSERVED_BOUNDARY_EMISSION')
        values.append(color)
    return values


def predict(model, grid, caps=None, check=lambda: None):
    limits = _limits(caps); budget = _Budget(limits, check)
    validate_model(model)
    prediction, reason = None, 'PREDICTED_ALL_PIXELS'
    try:
        features = _features(grid, budget)
        values = _apply_features(model, features, budget)
        prediction = [values[r * len(grid[0]):(r + 1) * len(grid[0])] for r in range(len(grid))]
    except (Abstention, _Limit) as error:
        if budget.external and budget.external[-1] is error:
            raise
        reason = str(error)
    elapsed = time.process_time() - budget.started
    if elapsed >= limits['CPU_s']:
        prediction, reason = None, 'THROUGH_RETURN_CPU_CAP_UNKNOWN'
    return {'prediction': prediction, 'status': 'PREDICTED' if prediction is not None else 'ABSTAINED',
            'reason': reason, 'model_sha256': model['model_sha256'],
            'cost': dict(budget.used, CPU_s=elapsed), 'query_truth_received': False}


def train(retained, caps=None, check=lambda: None):
    limits = _limits(caps); budget = _Budget(limits, check)
    if type(retained) is not list or not 2 <= len(retained) <= 10:
        raise Failure('AT_LEAST_TWO_RETAINED_DEMOS_REQUIRED')
    examples, emissions, state, model = [], None, {'nodes': 0, 'unresolved_leaves': 0}, None
    reason = 'NO_EXACT_TREE_WITHIN_DECLARED_SEARCH'
    try:
        colors = set()
        for pair in retained:
            budget.guard()
            if type(pair) is not dict or set(pair) != {'input', 'output'}:
                raise Failure('RETAINED_DEMO_FIELDS_ONLY')
            valid_grid(pair['input']); valid_grid(pair['output'])
            if (len(pair['input']), len(pair['input'][0])) != (len(pair['output']), len(pair['output'][0])):
                raise Failure('SAME_SHAPED_PAIRS_REQUIRED')
            features = _features(pair['input'], budget)
            targets = [value for row in pair['output'] for value in row]
            if len(examples) + len(features) > limits['max_samples']:
                raise _Limit('SAMPLE_CAP_UNKNOWN')
            # A duplicate pair does not manufacture independent leaf support.
            demo_identity = digest(pair)
            examples.extend((feature, target, demo_identity) for feature, target in zip(features, targets))
            colors.update(targets)
        emissions = _emissions(colors)
        tree = _construct(list(range(len(examples))), examples, emissions, budget, 0, state)
        if tree is not None:
            payload = {'schema': 'CORA_CONDITIONAL_COLOR_TREE_V1', 'features': list(FEATURES),
                       'background': 0, 'tree': tree, 'training_demo_sha256': digest(retained)}
            candidate = dict(payload, model_sha256=digest(payload))
            validate_model(candidate)
            # Fresh feature extraction/execution for every retained pair shares
            # the original training budget; a fitted table is not a verifier.
            for pair in retained:
                actual = _apply_features(candidate, _features(pair['input'], budget), budget)
                desired = [value for row in pair['output'] for value in row]
                if actual != desired:
                    raise Failure('FRESH_REPLAY_DISAGREEMENT')
            model, reason = candidate, 'EXACT_ALL_DEMO_CONDITIONAL_PROGRAM'
    except _Limit as error:
        if budget.external and budget.external[-1] is error:
            raise
        reason = str(error)
    elapsed = time.process_time() - budget.started
    if elapsed >= limits['CPU_s']:
        model, reason = None, 'THROUGH_RETURN_CPU_CAP_UNKNOWN'
    return {'model': model, 'status': 'VERIFIED_RETAINED_FIT' if model else 'UNKNOWN',
            'reason': reason, 'samples': len(examples), 'constructed_nodes': state['nodes'],
            'unresolved_leaves': state['unresolved_leaves'], 'cost': dict(budget.used, CPU_s=elapsed),
            'caps': limits, 'query_or_task_id_received': False, 'primitive_semantics_learned': False,
            'learned_capability': 'conditional_Color_program_over_fixed_features'}
