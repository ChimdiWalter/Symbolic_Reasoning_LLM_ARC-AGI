"""R29 constructors with full-fit and fresh leave-one-out acceptance.

No filesystem dataset access, IDs, hidden outputs or query labels are accepted.
The optional backend seam is solely for authored unit tests; worker uses Backend.
"""
import copy
import hashlib
import json
import time

ARMS = ('forward', 'inverse_diagnosed', 'conditional_beam')
GOAL_CAPS = {'CPU_s': 1.0, 'generated_states': 512, 'semantic_classes': 128,
             'primitive_executions': 2048, 'cell_work': 2000000,
             'selected_programs': 1, 'max_depth': 4, 'library_seeds': 16}
BEAM_CAPS = {'CPU_s': 1.0, 'max_depth': 4, 'max_nodes': 31, 'min_support': 2,
             'min_demos': 2, 'max_samples': 9000, 'predicate_work': 2000000,
             'feature_cell_work': 2000000}

class ClockTimeout(BaseException):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class Backend:
    def __init__(self):
        # No data loading; isolated worker already pins exact package bytes.
        from cage.v2b import goal_constructor, conditional_model
        self.goal, self.beam = goal_constructor, conditional_model

    def fit(self, arm, retained, check):
        started = time.process_time()
        def bounded():
            check()
            if time.process_time() - started >= 1.0:
                raise ClockTimeout('METHOD_FIT_REPLAY_QUERY_CPU_CAP')
        if arm != 'conditional_beam':
            fit = self.goal.fit(copy.deepcopy(retained), arm=arm, caps=GOAL_CAPS, check=bounded)
            accepted = fit['program'] is not None and fit.get('retained_verified') is True
            reason = fit['diagnosis']['reason']
            identity = fit['program']['program_sha256'] if accepted else None
        else:
            if len(retained) < 2 or any((len(p['input']), len(p['input'][0])) != (len(p['output']), len(p['output'][0])) for p in retained):
                return None, {'reason': 'CONDITIONAL_LANGUAGE_OR_SUPPORT_UNSUPPORTED'}
            fit = self.beam.train(copy.deepcopy(retained), caps=BEAM_CAPS, check=bounded)
            accepted = fit['model'] is not None and fit.get('status') == 'VERIFIED_RETAINED_FIT'
            reason = fit['reason']
            identity = fit['model']['model_sha256'] if accepted else None
        bounded()
        if 'CPU' in reason or 'OVERRUN' in reason:
            raise ClockTimeout('CONSTRUCTOR_CPU_TIMEOUT')
        receipt = {'arm': arm, 'reason': reason, 'program_or_model_sha256': identity,
                   'retained_sha256': digest(retained), 'retained_count': len(retained),
                   'cost': copy.deepcopy(fit['cost'])}
        if not accepted:
            return None, receipt
        return {'arm': arm, 'fit': fit, 'CPU_s': time.process_time()-started,
                'cost': copy.deepcopy(fit['cost'])}, receipt

    def predict(self, state, query, check):
        started, before = time.process_time(), state['CPU_s']
        def bounded():
            check()
            if before >= 1.0 or before + (time.process_time()-started) >= 1.0:
                raise ClockTimeout('METHOD_FIT_REPLAY_QUERY_CPU_CAP')
        bounded()
        if state['arm'] != 'conditional_beam':
            state['fit']['cost']['CPU_s'] = before
            answer = self.goal.predict(state['fit'], copy.deepcopy(query), check=bounded)
            reason, prediction = answer['reason'], answer['prediction']
            state['cost'] = copy.deepcopy(answer['cost'])
        else:
            cost = state['cost']
            caps = dict(BEAM_CAPS, CPU_s=1.0-before-(time.process_time()-started),
                        predicate_work=BEAM_CAPS['predicate_work']-cost['predicate_work'],
                        feature_cell_work=BEAM_CAPS['feature_cell_work']-cost['feature_cell_work'])
            if caps['CPU_s'] <= 0:
                raise ClockTimeout('CONDITIONAL_CUMULATIVE_CPU_CAP')
            if min(caps['predicate_work'], caps['feature_cell_work']) <= 0:
                return None
            answer = self.beam.predict(state['fit']['model'], copy.deepcopy(query), caps=caps, check=bounded)
            reason, prediction = answer['reason'], answer['prediction']
            for key in ('predicate_work', 'feature_cell_work'):
                cost[key] += answer['cost'][key]
        bounded()
        state['CPU_s'] = before + (time.process_time()-started)
        state['cost']['CPU_s'] = state['CPU_s']
        if 'CPU' in reason or 'OVERRUN' in reason:
            raise ClockTimeout('QUERY_CPU_TIMEOUT')
        return prediction


def solve(task, check, backend=None):
    """Each accepted arm must pass full replay and *every* fresh LOO fold."""
    check()
    train, queries = task['train'], task['test']
    predictions = [None] * len(queries)
    report = {'status': 'ABSTAIN', 'reason': 'NO_FULL_AND_LOO_VERIFIED_METHOD',
              'selected_arm': None, 'selected_arms': [None] * len(queries),
              'arms': [], 'fit_invocations': 0, 'LOO_fits_cache_reused': False,
              'test_answers_received': False, 'query_values_used_in_fit': False}
    if len(train) < 2:
        report.update(status='INSUFFICIENT_VALIDATION_EVIDENCE', reason='FEWER_THAN_TWO_DEMONSTRATIONS')
        return predictions, report
    backend = Backend() if backend is None else backend
    for arm in ARMS:
        check()
        arm_report = {'arm': arm, 'accepted': False, 'full_replay_exact': False, 'folds': []}
        report['arms'].append(arm_report)
        report['fit_invocations'] += 1
        full, receipt = backend.fit(arm, copy.deepcopy(train), check)
        arm_report['full_fit'] = receipt
        if full is None:
            continue
        full_exact = True
        for pair in train:
            check()
            if backend.predict(full, copy.deepcopy(pair['input']), check) != pair['output']:
                full_exact = False
                break
        arm_report['full_replay_exact'] = full_exact
        if not full_exact:
            continue
        all_folds_exact = True
        for held_index, held in enumerate(train):
            check()
            retained = [copy.deepcopy(pair) for index, pair in enumerate(train) if index != held_index]
            # New synth invocation and new model every fold. No state/model is
            # passed from full-fit or another fold; imported code may be cached.
            report['fit_invocations'] += 1
            fold, fold_receipt = backend.fit(arm, retained, check)
            row = {'held_index': held_index, 'fresh_fit_invocation': report['fit_invocations'],
                   'fit': fold_receipt, 'held_exact': False}
            arm_report['folds'].append(row)
            if fold is not None:
                # Verify retained inputs independently even though constructor
                # already exact-checks them; then execute the excluded input.
                retained_exact = all(backend.predict(fold, copy.deepcopy(p['input']), check) == p['output'] for p in retained)
                if retained_exact:
                    row['held_exact'] = backend.predict(fold, copy.deepcopy(held['input']), check) == held['output']
            if not row['held_exact']:
                all_folds_exact = False
                break
        arm_report['accepted'] = all_folds_exact and len(arm_report['folds']) == len(train)
        if not arm_report['accepted']:
            continue
        for index, query in enumerate(queries):
            check()
            if predictions[index] is None:
                value = backend.predict(full, copy.deepcopy(query['input']), check)
                if value is not None:
                    predictions[index] = copy.deepcopy(value)
                    report['selected_arms'][index] = arm
        arm_report['full_cost_after_queries'] = copy.deepcopy(full.get('cost', {}))
        if all(value is not None for value in predictions):
            break
    check()
    if any(value is not None for value in predictions):
        report.update(status='ACCEPTED_FULL_AND_FRESH_LOO', reason='EXECUTED_VERIFIED_PROGRAM',
                      selected_arm=next(a for a in report['selected_arms'] if a is not None))
    return predictions, report
