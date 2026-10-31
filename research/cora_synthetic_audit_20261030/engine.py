"""R16 causal scheduling audit, using unchanged R11 executable semantics."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
HERE = Path(__file__).resolve().parent

def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(v):
    return hashlib.sha256(canonical(v)).hexdigest()

def pinned(name, module_name, pin):
    raw = (HERE / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('PINNED_CODE_CHANGED:' + name)
    spec = importlib.util.spec_from_file_location(module_name, HERE / name)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(HERE / name), 'exec'), module.__dict__)
    return module

PINS = json.loads((HERE / 'COPIED_PINS.json').read_text())
D = pinned('r11_domains.py', '_r16_domains', PINS['r11_domains.py'])
_sentinel = object(); _old = sys.modules.get('domains', _sentinel)
try:
    sys.modules['domains'] = D
    C = pinned('r11_core.py', '_r16_core', PINS['r11_core.py'])
finally:
    if _old is _sentinel:
        del sys.modules['domains']
    else:
        sys.modules['domains'] = _old

PRIMARY = ('lambda0', 'lambda_plus', 'lambda_minus', 'expanded_control', 'shuffled_call_prior')
FAILURE = ('failure_authentic', 'failure_blind', 'failure_shuffled', 'failure_static', 'failure_extra_search')
ARMS = PRIMARY + ('base_reference',) + FAILURE

def all_nodes(v):
    if isinstance(v, dict):
        if 'op' in v:
            yield v
        for x in v.values():
            yield from all_nodes(x)
    elif isinstance(v, list):
        for x in v:
            yield from all_nodes(x)

def syntax_cost(ast):
    return sum(n['op'] != 'input' for n in all_nodes(ast))

def freeze_universe(library, check):
    """No held-task data. Same unique expanded ASTs and representative labels."""
    pool = C.extended_universe('grid', library)
    full = pool + [C.unary('grid', role, ast) for ast in pool for role in ('mark', 'repeat', 'select')]
    groups = {}
    for ast in full:
        check(); expanded = C.expand(ast, library)
        if C.count(expanded) <= 5:
            groups.setdefault(canonical(expanded), []).append(ast)
    rows = []
    for key in sorted(groups):
        check(); reps = groups[key]
        representative = min(reps, key=lambda a: (syntax_cost(a), canonical(a)))
        expanded = json.loads(key)
        rows.append({'expanded': expanded, 'expanded_AST_sha256': digest(expanded),
            'representative': representative, 'representative_sha256': digest(representative),
            'expanded_primitive_nodes': C.count(expanded),
            'legacy_call_feature': sum(n['op'] == 'call' for n in C.walk(representative)),
            'true_recursive_call_count': sum(n['op'] == 'call' for n in all_nodes(representative)),
            'alias_count_before_dedup': len(reps)})
    strata = {}
    for index, row in enumerate(rows):
        strata.setdefault(row['expanded_primitive_nodes'], []).append(index)
    labels = [r['legacy_call_feature'] for r in rows]; shuffled = labels[:]; diagnostics = []
    for size, ids in sorted(strata.items()):
        values = [labels[i] for i in ids]; moved = values[1:] + values[:1]
        for index, label in zip(ids, moved):
            shuffled[index] = label
        diagnostics.append({'expanded_nodes': size, 'candidate_count': len(ids),
            'original_labels': values, 'permuted_labels': moved,
            'labels_changed': sum(a != b for a, b in zip(values, moved))})
    for row, label in zip(rows, shuffled):
        row['shuffled_call_feature'] = label
    return rows, {'canonical_expanded_universe_sha256': digest([r['expanded'] for r in rows]),
        'representative_map_sha256': digest(rows), 'candidate_count': len(rows),
        'raw_candidate_count': len(full), 'strata': diagnostics,
        'effective_shuffled_label_changes': sum(x['labels_changed'] for x in diagnostics),
        'feature_limitation': 'Exact legacy C.walk feature intentionally misses nested call bindings; true recursive calls separately reported.',
        'semantics_limit': 'Dedup identical expanded AST bytes, not a proof of arbitrary functional equivalence.'}

def rows_for_base():
    seen = {}
    for ast in C.base_universe('grid'):
        seen[canonical(ast)] = {'expanded': ast, 'expanded_AST_sha256': digest(ast),
            'representative': ast, 'representative_sha256': digest(ast),
            'expanded_primitive_nodes': C.count(ast), 'legacy_call_feature': 0,
            'true_recursive_call_count': 0, 'shuffled_call_feature': 0}
    return [seen[k] for k in sorted(seen)]

def order(task, rows, weights, lam, shuffled, check):
    context = C.context(task); scores = []
    for index, row in enumerate(rows):
        check(); features = C.features(row['expanded'], 'grid', context, {'rules': []})
        score = sum(w * x for w, x in zip(weights, features))
        label = row['shuffled_call_feature'] if shuffled else row['legacy_call_feature']
        scores.append((-score - lam * label, row['expanded_primitive_nodes'], canonical(row['expanded']), index))
    return [s[-1] for s in sorted(scores)]

def failure_payload(trace):
    fits = {r['expanded_AST_sha256'] for r in trace['rows'] if r['exact']}
    return {'kind': 'NO_EXACT_FIT_IN_BOUNDED_PREFIX' if not fits else
            'MULTIPLE_EXPANDED_AST_FITS' if len(fits) > 1 else 'ONE_EXPANDED_AST_FIT',
        'alternate': len(fits) != 1, 'distinct_expanded_fits': len(fits),
        'prefix_validations': len(trace['rows']), 'prefix_requested_validations':12,
        'prefix_search_status':trace.get('status','BOUNDED_PREFIX_UNIVERSE_UNKNOWN'),
        'prefix_universe_UNKNOWN':trace.get('UNKNOWN',True),
        'planned12_prefix_complete':len(trace['rows'])==12, 'bounded_not_absence': True,
        'failure_kinds': trace['failure_kinds']}

def static_alternate(task):
    # Input-only authored heuristic, deliberately distinct from execution evidence.
    for pair in task['demos']:
        raw = pair['input']; components = D.groups('grid', raw, 'mono4'); colors = D.groups('grid', raw, 'color')
        if max(map(len, colors), default=0) > max(map(len, components), default=0):
            return True
    return False

def run_search(task, rows, weights, check, *, lam=0., shuffled=False, cap=24,
               primitive_cap=192, cpu_cap=.12, action='none', payload=None):
    begin = time.process_time(); ordering = order(task, rows, weights, lam, shuffled, check)
    receipts = []; spent = 0; failures = {}; stop_reason = 'FINITE_UNIVERSE_COMPLETE'
    stage = 0; offset = 0; alternate = None; action_executed = False
    while stage < (2 if action != 'none' else 1):
        view = 'mono4' if stage == 0 or not alternate else 'color'
        local_cap = 12 if action != 'none' else cap
        for index in ordering[offset:]:
            check()
            if len(receipts) >= cap:
                stop_reason = 'VALIDATION_CAP_UNKNOWN'; break
            if time.process_time() - begin >= cpu_cap:
                stop_reason = 'CPU_CAP_UNKNOWN'; break
            if action != 'none' and len(receipts) >= (stage + 1) * local_cap:
                break
            row = rows[index]; upper = row['expanded_primitive_nodes'] * len(task['demos'])
            if spent + upper > primitive_cap:
                stop_reason = 'PRIMITIVE_CAP_UNKNOWN'; break
            exact = True; output_hashes = []; statuses = []; complete_candidate = True
            for pair in task['demos']:
                check(); output, receipt = C.execute(pair['input'], row['expanded'], 'grid', view)
                spent += receipt['primitive_executions']; exact = exact and output == pair['output']
                output_hashes.append(digest(output)); statuses.append(receipt['status'])
                if receipt['status'] != 'EXECUTED':
                    kind = receipt['failure_kind']; failures[kind] = failures.get(kind, 0) + 1
                if time.process_time() - begin >= cpu_cap:
                    stop_reason = 'CPU_CAP_UNKNOWN'; complete_candidate = False; break
            if not complete_candidate:
                break
            receipts.append({'index': index, 'expanded_AST_sha256': row['expanded_AST_sha256'],
                'view': view, 'exact': exact, 'output_sha256s': output_hashes, 'statuses': statuses,
                'validation': len(receipts) + 1, 'cumulative_primitives': spent,
                'cumulative_CPU_s': time.process_time() - begin,
                'legacy_call_feature': row['legacy_call_feature'],
                'true_recursive_call_count': row['true_recursive_call_count']})
        if action == 'none' or stage == 1:
            break
        if len(receipts) != 12:
            break
        own = failure_payload({'rows': receipts, 'failure_kinds': failures})
        if action == 'authentic': alternate = own['alternate']
        elif action == 'blind': alternate = True
        elif action == 'shuffled': alternate = payload['alternate']
        elif action == 'static': alternate = static_alternate(task)
        elif action == 'extra_search': alternate = False
        else: raise ValueError('UNKNOWN_EXECUTABLE_ACTION')
        action_executed = True; stage = 1; offset = 0 if alternate else 12
    if len(receipts) < len(rows) or action != 'none':
        if stop_reason == 'FINITE_UNIVERSE_COMPLETE': stop_reason = 'VALIDATION_CAP_UNKNOWN'
    return {'rows': receipts, 'order': ordering, 'order_sha256': digest(ordering),
        'candidate_universe_sha256': digest([r['expanded'] for r in rows]),
        'candidate_count': len(rows), 'validations': len(receipts), 'primitive_executions': spent,
        'actual_CPU_s': time.process_time() - begin, 'status': stop_reason,
        'UNKNOWN': stop_reason != 'FINITE_UNIVERSE_COMPLETE', 'failure_kinds': failures,
        'action': action, 'action_executed': action_executed, 'alternate_view': alternate,
        'lambda': lam, 'shuffled_call_labels': shuffled,
        'borrowed_evidence': payload if action == 'shuffled' else None}

def matched_prefix(traces):
    validations = min(t['validations'] for t in traces.values())
    primitive = min(t['primitive_executions'] for t in traces.values())
    cpu = min(t['actual_CPU_s'] for t in traces.values())
    feasible = {}
    for name, trace in traces.items():
        count = 0
        for row in trace['rows']:
            if row['validation'] > validations or row['cumulative_primitives'] > primitive or row['cumulative_CPU_s'] > cpu:
                break
            count += 1
        feasible[name] = count
    common = min(feasible.values())
    return {'common_validation_prefix_length': common, 'validation_ceiling': validations,
        'expanded_primitive_ceiling': primitive, 'measured_CPU_ceiling_s': cpu,
        'per_arm_feasible_prefix': feasible,
        'interpretation': 'All arms use exact same prefix LENGTH; actual primitive/CPU remain <=common ceilings. Timing cannot change lambda0/control choices independently.'}

def choices(trace, rows, prefix=None):
    selected = []
    for receipt in trace['rows'][:prefix]:
        if receipt['exact']:
            row = rows[receipt['index']]
            selected.append({'expanded': row['expanded'], 'representative': row['representative'],
                'expanded_AST_sha256': row['expanded_AST_sha256'], 'view': receipt['view'],
                'legacy_call_feature': row['legacy_call_feature'],
                'true_recursive_call_count': row['true_recursive_call_count']})
            if len(selected) == 2: break
    return selected
