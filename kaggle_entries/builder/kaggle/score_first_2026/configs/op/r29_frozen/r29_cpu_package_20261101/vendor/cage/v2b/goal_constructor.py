"""CORA / CAGE v2: finite intermediate-goal construction in the frozen DSL.

The inverse views follow the tested R26 helper's all-demo D4 specification
propagation, but do not give every view a fresh budget.  Shape constraints apply
to a proposed resize's *intermediate* goal, rather than requiring its prefix to
already have the final output shape.  This adds search coverage, not semantics.
No query, task identifier, expected program, or teacher prediction enters fit.
"""
from __future__ import annotations

import copy
import math
import time

from ..dependencies import E, G
from .. import programs

ARMS = ('forward', 'inverse_fixed', 'inverse_diagnosed', 'inverse_library')
SUFFIXES = ('identity', 'hflip', 'vflip', 'r90', 'r180', 'r270', 'transpose', 'antitranspose')
INVERSE = {'identity': 'identity', 'hflip': 'hflip', 'vflip': 'vflip',
           'r90': 'r270', 'r180': 'r180', 'r270': 'r90',
           'transpose': 'transpose', 'antitranspose': 'antitranspose'}
DEFAULT_CAPS = dict(E.DEFAULT_CAPS, CPU_s=1.0, generated_states=512,
                    semantic_classes=128, primitive_executions=2048,
                    cell_work=2000000, selected_programs=1, max_depth=4,
                    library_seeds=16)
LOGICAL = ('generated_states', 'semantic_classes', 'primitive_executions', 'cell_work')


def _caps(caps):
    return E._limits(dict(DEFAULT_CAPS, **dict(caps or {})))


def _static_seeds(train, check):
    """Eight public mixed-family chains; output schema validated, values unused.

    Frozen BASE.static_programs calls valid_demos, then only _families(inp(),
    None); it does not inspect an output to select a seed or its parameters.
    """
    roots, seen = [], set()
    for ast in E.static_programs(train, check=check, max_programs=32):
        check()
        key = E.digest(ast)
        if E.structural_cost(ast) == 1 and key not in seen:
            seen.add(key)
            roots.append(ast)
    seeds = []
    for index in range(min(8, len(roots))):
        check()
        inner = roots[index]
        # Cycle through distinct public primitive families before repeats.
        outer = next((root for root in roots[index+1:] + roots[:index+1]
                      if root['op'] != inner['op']), roots[(index+1) % len(roots)])
        joined = copy.deepcopy(outer)
        joined['args'] = [copy.deepcopy(inner)]
        E.validate_ast(joined, DEFAULT_CAPS['max_depth'])
        seeds.append(joined)
    return seeds


def _prefixes(static, learned, check):
    """Interleaved existing root families and seeds; no final-shape filtering."""
    families = [('static', iter(static)), ('learned', iter(learned))]
    families += E.BASE._families(E.inp(), None)
    # The extension primitives remain available in the common forward stage;
    # inverse geometry composes the original public geometry/object families.
    while families:
        next_round = []
        for name, iterator in families:
            check()
            try:
                ast = next(iterator)
            except StopIteration:
                continue
            next_round.append((name, iterator))
            yield name, ast
        families = next_round


def _goal_order(outputs, goals, diagnosed, check):
    """Rank retained residual evidence; fixed computes and discards same scores."""
    scores = []
    for index, (suffix, goal) in enumerate(goals):
        check()
        shape_error, pixel_error = E.BASE._residual(outputs, goal)
        scores.append(((shape_error, pixel_error, index), suffix, goal))
    if diagnosed:
        scores.sort(key=lambda item: item[0])
    return scores


def fit(train, *, arm='forward', library=None, caps=None, check=lambda: None):
    """Return one closed, all-retained-reverified program and carried budgets.

    All four arms have the same *total* ceilings. Inverse arms spend at most a
    quarter of their logical/CPU allowance on current forward search, then use
    remaining resources for backward goals. This is a mechanism comparison,
    not a guarantee of preserving forward coverage under a finite allowance.
    """
    started = time.process_time()
    limits = _caps(caps)
    E.valid_demos(train)
    if arm not in ARMS:
        raise E.Failure('GOAL_ABLATION_ARM')
    library = G.empty_library() if library is None else library
    G.validate_library(library)
    cost = dict.fromkeys(LOGICAL, 0)
    meter = {'primitive_executions': 0, 'cell_work': 0,
             'primitive_limit': limits['primitive_executions'], 'cell_limit': limits['cell_work']}
    external, stages = [], []
    selected, reason, materialized = None, 'FINITE_CONSTRUCTION_EXHAUSTED_UNKNOWN', {'expanded': []}
    reserved_child = False
    seen, semantics = set(), set()

    def bounded():
        try:
            check()
        except BaseException as error:
            external.append(error)
            raise
        if time.process_time()-started >= limits['CPU_s']:
            raise E.Budget('TOTAL_GOAL_FIT_CPU_CAP_UNKNOWN')

    def fresh(ast):
        bounded()
        if E.verify(ast, train, check=bounded, meter=meter):
            return programs.wrap(ast)
        return None

    def state(ast):
        bounded()
        if E.structural_cost(ast) > limits['max_depth']:
            return False
        key = E.digest(ast)
        if key in seen:
            return False
        if cost['generated_states'] >= limits['generated_states']:
            raise E.Budget('TOTAL_GOAL_GENERATION_CAP_UNKNOWN')
        seen.add(key)
        cost['generated_states'] += 1
        return True

    def semantic(outputs):
        signature = E.canonical(outputs)
        if signature in semantics:
            return False
        if cost['semantic_classes'] >= limits['semantic_classes']:
            raise E.Budget('TOTAL_GOAL_SEMANTIC_CAP_UNKNOWN')
        semantics.add(signature)
        cost['semantic_classes'] += 1
        return True

    try:
        bounded()
        static = [ast for ast in _static_seeds(train, bounded)
                  if E.structural_cost(ast) <= limits['max_depth']]
        # Same library decoding/materialization overhead in every arm. Its
        # expansions are admitted only in the fourth, explicitly learned arm.
        materialized = G.materialize(library, train=train, constructor=E,
                                     check=bounded, max_variants=min(8, limits['library_seeds']))
        learned = ([ast for ast in materialized['expanded']
                    if E.structural_cost(ast) <= limits['max_depth']]
                   if arm == 'inverse_library' else [])
        seeds = static + learned
        fraction = 1.0 if arm == 'forward' else 0.25
        child = dict(limits, CPU_s=min(limits['CPU_s']*fraction,
                                      limits['CPU_s']-(time.process_time()-started)))
        for key in LOGICAL:
            child[key] = max(1, int(limits[key]*fraction))
            cost[key] += child[key]
        reserved_child = True
        proposal = E.propose(train, library={'expanded': seeds}, caps=child, check=bounded)
        diagnostic = proposal['diagnosis']
        for key in ('generated_states', 'semantic_classes'):
            cost[key] -= child[key]-diagnostic['counts'].get(key, 0)
        for key in ('primitive_executions', 'cell_work'):
            cost[key] -= child[key]-diagnostic['meter'][key]
            meter[key] = cost[key]
        reserved_child = False
        stages.append({'kind': 'forward', 'diagnosis': diagnostic,
                       'proposal_sha256': proposal['proposal_sha256']})
        if proposal['programs']:
            selected = fresh(proposal['programs'][0])
            if selected:
                reason = 'EXACT_RETAINED_WITNESS_SEARCH_INCOMPLETE'
        if selected is None and arm != 'forward':
            goals = []
            for suffix in SUFFIXES:
                bounded()
                if suffix == 'identity':
                    transformed = copy.deepcopy(train)
                else:
                    inverse = E.node('d4', E.inp(), mode=INVERSE[suffix])
                    transformed = [{'input': copy.deepcopy(pair['input']),
                                    'output': E.execute(inverse, pair['output'], check=bounded, meter=meter)}
                                   for pair in train]
                goals.append((suffix, transformed))
            inverse_diagnosis = {'kind': 'intermediate_goal_search', 'prefixes': 0,
                                 'failed_prefixes': 0, 'resize_candidates': 0,
                                 'suffix_order_uses_retained_residuals': arm != 'inverse_fixed',
                                 'finite_goal_views': list(SUFFIXES), 'selected_suffix': None}
            stages.append(inverse_diagnosis)
            for family, prefix in _prefixes(static, learned, bounded):
                if not state(prefix):
                    continue
                inverse_diagnosis['prefixes'] += 1
                try:
                    outputs = [E.execute(prefix, pair['input'], check=bounded, meter=meter) for pair in train]
                except E.Failure as error:
                    if external and external[-1] is error:
                        raise
                    inverse_diagnosis['failed_prefixes'] += 1
                    continue
                if not semantic(outputs):
                    continue
                for _, suffix, goal in _goal_order(outputs, goals, arm != 'inverse_fixed', bounded):
                    bounded()
                    # Bare prefixes and shape-derived resizes are both checked.
                    # Only inferred *integer* factors in the unchanged DSL are
                    # admitted; no scaling assumption supplies expected pixels.
                    repairs = [None] + list(E.BASE._infer_resizes(outputs, goal))
                    for params in repairs:
                        bounded()
                        ast = prefix if params is None else E.node('resize', prefix, **params)
                        if suffix != 'identity':
                            ast = E.node('d4', ast, mode=suffix)
                        if not state(ast):
                            # The bare identity prefix was counted above, but
                            # still needs its retained-goal comparison once.
                            if not (params is None and suffix == 'identity'):
                                continue
                        if params is None:
                            trial = outputs
                        else:
                            inverse_diagnosis['resize_candidates'] += 1
                            try:
                                resize = E.node('resize', E.inp(), **params)
                                trial = [E.execute(resize, grid, check=bounded, meter=meter) for grid in outputs]
                            except E.Failure as error:
                                if external and external[-1] is error:
                                    raise
                                continue
                        # Count and charge every attempted suffix, including
                        # failures. Semantic signatures refer to actual final
                        # outputs, not differently oriented inverse goals.
                        if suffix == 'identity':
                            final_outputs = trial
                        else:
                            suffix_ast = E.node('d4', E.inp(), mode=suffix)
                            final_outputs = [E.execute(suffix_ast, grid, check=bounded, meter=meter)
                                             for grid in trial]
                        exact = all(grid == pair['output'] for grid, pair in zip(final_outputs, train))
                        if not exact:
                            semantic(final_outputs)
                            continue
                        selected = fresh(ast)
                        if selected:
                            inverse_diagnosis['selected_suffix'] = suffix
                            inverse_diagnosis['selected_prefix_family'] = family
                            reason = 'EXACT_RETAINED_INTERMEDIATE_GOAL_WITNESS_SEARCH_INCOMPLETE'
                            break
                    if selected:
                        break
                if selected:
                    break
    except E.Budget as error:
        if external and external[-1] is error:
            raise
        selected, reason = None, str(error)
    finally:
        if not reserved_child:
            cost['primitive_executions'] = meter['primitive_executions']
            cost['cell_work'] = meter['cell_work']
    attribution = (G.attribute_program(selected['body'], materialized)
                   if selected and arm == 'inverse_library' else None)
    cost['CPU_s'] = time.process_time()-started
    if cost['CPU_s'] >= limits['CPU_s'] or any(cost[k] > limits[k] for k in LOGICAL):
        selected, reason = None, 'TOTAL_GOAL_THROUGH_RETURN_OVERRUN_DISCARDED'
    return {'schema': 'CORA_CAGE_GOAL_V2', 'program': selected, 'retained_verified': selected is not None,
            'arm': arm, 'cost': cost, 'caps': limits,
            'diagnosis': {'reason': reason, 'stages': stages,
                          'library_sha256': library['library_sha256'],
                          'library_attribution': attribution if selected else None,
                          'logical_cost_status': ('CONSERVATIVE_CHILD_RESERVATION' if reserved_child else 'RETURNED_METERS'),
                          'query_or_teacher_received': False, 'inexpressibility_proven': False,
                          'new_primitive_semantics': False,
                          'work_metric': 'frozen DSL precharged primitive/cell proxy; comparisons and AST preparation charged to CPU',
                          'inverse_scope': 'eight exact D4 suffix goals and shape-derived resize over finite public prefixes'}}


def predict(result, grid, *, check=lambda: None):
    """Execute one query, mutating cumulative cost for subsequent query calls.

    Inter-task wall/CPU elapsed since fit is deliberately not charged. Only this
    task's fit and prediction calls consume its predeclared total CPU allowance.
    No expected query output or answer is accepted.
    """
    started = time.process_time()
    if type(result) is not dict or result.get('schema') != 'CORA_CAGE_GOAL_V2':
        raise E.Failure('GOAL_RESULT_SCHEMA')
    limits = _caps(result['caps'])
    E.valid_grid(grid)
    cost = result['cost']
    if type(cost) is not dict or set(cost) != set(LOGICAL) | {'CPU_s'}:
        raise E.Failure('GOAL_RESULT_COST')
    if any(type(cost[key]) is not int or cost[key] < 0 or cost[key] > limits[key] for key in LOGICAL):
        raise E.Failure('GOAL_RESULT_LOGICAL_COST')
    if (type(cost['CPU_s']) not in (int, float) or not math.isfinite(cost['CPU_s'])
            or not 0 <= cost['CPU_s']):
        raise E.Failure('GOAL_RESULT_CPU_COST')
    before = cost['CPU_s']
    meter = {'primitive_executions': cost['primitive_executions'], 'cell_work': cost['cell_work'],
             'primitive_limit': limits['primitive_executions'], 'cell_limit': limits['cell_work']}
    external = []
    prediction, reason = None, 'NO_EXACT_RETAINED_PROGRAM_UNKNOWN'

    def bounded():
        try:
            check()
        except BaseException as error:
            external.append(error)
            raise
        # Check the carried cost separately. Left-associated (before + now) -
        # started can round below before when a coarse CPU clock has not ticked.
        # Already exhausted fit allowances must never permit a query call.
        if before >= limits['CPU_s'] or before+(time.process_time()-started) >= limits['CPU_s']:
            raise E.Budget('TOTAL_GOAL_FIT_PLUS_QUERY_CPU_CAP_UNKNOWN')

    try:
        bounded()
        if result['program'] is not None:
            programs.validate(result['program'])
            if result['program']['kind'] != 'dsl' or not result.get('retained_verified'):
                raise E.Failure('GOAL_CLOSED_DSL_REQUIRED')
            prediction = E.execute(result['program']['body'], grid, check=bounded, meter=meter)
            reason = 'CLOSED_PROGRAM_EXECUTED_QUERY_CORRECTNESS_UNKNOWN'
        bounded()
    except (E.Budget, E.Failure) as error:
        if external and external[-1] is error:
            raise
        prediction, reason = None, str(error)
    finally:
        cost['primitive_executions'] = meter['primitive_executions']
        cost['cell_work'] = meter['cell_work']
        cost['CPU_s'] = before+(time.process_time()-started)
    response = {'prediction': prediction, 'status': 'EXECUTED' if prediction is not None else 'ABSTAIN',
                'reason': reason, 'cost': copy.deepcopy(cost), 'query_correctness_known': False}
    # Include response construction/cost copying before the final snapshot.
    # A supervisor must still charge the small Python return/assignment tail.
    cost['CPU_s'] = before+(time.process_time()-started)
    response['cost']['CPU_s'] = cost['CPU_s']
    if cost['CPU_s'] >= limits['CPU_s'] or any(cost[k] > limits[k] for k in LOGICAL):
        response.update(prediction=None, status='ABSTAIN',
                        reason='TOTAL_GOAL_FIT_PLUS_QUERY_OVERRUN_DISCARDED')
    return response
