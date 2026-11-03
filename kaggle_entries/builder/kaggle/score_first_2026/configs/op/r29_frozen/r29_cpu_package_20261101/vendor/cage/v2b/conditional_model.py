"""CORA/CAGE bounded conditional-program search, version 2b.

The feature/emission language and typed executable model are the frozen R27
language. This constructor changes search: a bounded frontier of candidate
splits receives two-level lookahead and unsuccessful branches can be revisited.
It learns conditionals, not primitive semantics. No query participates in fit.

Compiled masks/cache entries save physical work; all mask construction and all
unsuccessful split/leaf evaluations are charged conservatively in scalar
predicate-work units. Callers share one task allowance by subtracting each
returned cost before calling predict, and supplying a whole-task check callback.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import time

_FROZEN = Path(__file__).resolve().parents[2] / 'experiments' / 'independent_synthesis_20261029' / 'round27' / 'learned_local_rules' / 'model.py'
# Path.parents[2] is the repository for cage/v2/conditional_model.py.
FROZEN_SHA256 = '110bcb0c19801d22fc27de7f38b34d1c7e7aca65afdbcb7d0b10980b00a3fbd6'
if hashlib.sha256(_FROZEN.read_bytes()).hexdigest() != FROZEN_SHA256:
    raise RuntimeError('FROZEN_R27_MODEL_CHANGED')
_spec = importlib.util.spec_from_file_location('_cora_cage_v2_frozen_model', _FROZEN)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

FEATURES, NUMERIC = M.FEATURES, M.NUMERIC
Failure, Abstention = M.Failure, M.Abstention
canonical, digest, valid_grid, validate_model = M.canonical, M.digest, M.valid_grid, M.validate_model
DEFAULT_CAPS = dict(M.DEFAULT_CAPS, CPU_s=1.0, beam_width=8, candidate_width=16, lookahead=2)
CONSTRUCTOR = 'bounded_beam_lazy_lookahead_v2b'


def _limits(caps):
    result = dict(DEFAULT_CAPS)
    supplied = dict(caps or {})
    if any(key not in result for key in supplied):
        raise Failure('UNKNOWN_CAP')
    result.update(supplied)
    core = M._limits({key: value for key, value in result.items() if key in M.DEFAULT_CAPS})
    if core['CPU_s'] > 1.0 or core['predicate_work'] > 2000000 or core['feature_cell_work'] > 2000000:
        raise Failure('SHARED_TASK_ALLOWANCE_EXTENSION')
    for key, maximum in (('beam_width', 8), ('candidate_width', 16), ('lookahead', 2)):
        if type(result[key]) is not int or not 1 <= result[key] <= maximum:
            raise Failure('BOUNDED_SEARCH_CAP_VALUE')
    core.update({key: result[key] for key in ('beam_width', 'candidate_width', 'lookahead')})
    return core


class _Search:
    def __init__(self, examples, emissions, budget):
        self.examples, self.emissions, self.budget = examples, emissions, budget
        self.n = len(examples)
        self.full = (1 << self.n) - 1
        self.demo_masks = {}
        self.leaf_cache, self.split_cache, self.solve_cache = {}, {}, {}
        self.predicates, self.mismatches = [], []
        self.stats = {'search_attempts': 0, 'candidate_evaluations': 0,
                      'split_partitions_considered': 0, 'leaf_evaluations': 0,
                      'lookahead_evaluations': 0, 'unresolved_leaves': 0}
        for i, (_, _, demo) in enumerate(examples):
            budget.guard()
            self.demo_masks[demo] = self.demo_masks.get(demo, 0) | (1 << i)
        for emission in emissions:
            budget.spend('predicate_work', self.n)
            mismatch = 0
            for i, (feature, target, _) in enumerate(examples):
                if M._emit(emission, feature) != target:
                    mismatch |= 1 << i
            self.mismatches.append(mismatch)
        for feature_index, name in enumerate(FEATURES):
            budget.guard()
            values = sorted({sample[0][feature_index] for sample in examples})
            choices = [('eq', value) for value in values]
            if name in NUMERIC:
                choices += [('le', value) for value in values[:-1]]
            for operation, value in choices:
                budget.spend('predicate_work', self.n)
                mask = 0
                for i, sample in enumerate(examples):
                    actual = sample[0][feature_index]
                    if actual == value if operation == 'eq' else actual <= value:
                        mask |= 1 << i
                self.predicates.append((feature_index, name, operation, value, mask))

    def support(self, mask):
        self.budget.guard()
        return (mask.bit_count() >= self.budget.limits['min_support'] and
                sum(bool(mask & demo) for demo in self.demo_masks.values()) >= self.budget.limits['min_demos'])

    def info(self, mask):
        return {'support': mask.bit_count(),
                'support_demos': sum(bool(mask & demo) for demo in self.demo_masks.values())}

    def leaf(self, mask):
        self.budget.guard()
        if mask not in self.leaf_cache:
            self.stats['leaf_evaluations'] += 1
            self.budget.spend('predicate_work', mask.bit_count() * len(self.emissions))
            ranked = [(mask.__and__(bad).bit_count(), 1 if spec['kind'] == 'feature' else 2,
                       i) for i, (bad, spec) in enumerate(zip(self.mismatches, self.emissions))]
            best = min(ranked)
            self.leaf_cache[mask] = (best[0], self.emissions[best[2]])
        return self.leaf_cache[mask]

    def splits(self, mask):
        self.budget.guard()
        if mask in self.split_cache:
            return self.split_cache[mask]
        candidates, seen = [], set()
        for index, name, operation, value, global_yes in self.predicates:
            self.budget.spend('predicate_work', mask.bit_count())
            self.stats['candidate_evaluations'] += 1
            yes, no = mask & global_yes, mask & ~global_yes
            # A duplicate or complementary partition has the same tree-search
            # alternatives; its attempted routing is nevertheless charged above.
            partition = min(yes, no)
            if partition in seen or not self.support(yes) or not self.support(no):
                continue
            seen.add(partition)
            self.stats['split_partitions_considered'] += 1
            error = self.leaf(yes)[0] + self.leaf(no)[0]
            values = sorted({self.examples[i][0][index] for i in range(self.n) if mask & (1 << i)})
            # The inference contract rejects unseen values in this node's context.
            predicate = {'feature': name, 'operation': operation, 'value': value,
                         'observed_values': values}
            key = (error, 0 if operation == 'eq' else 1, index, value)
            candidates.append((key, predicate, yes, no))
            # Zero is a proved lower bound for classification error. Both
            # supported children already have exact executable emissions, so
            # evaluating other partitions cannot improve feasibility. The
            # attempts and leaf/cache construction above remain fully charged.
            if error == 0:
                self.split_cache[mask] = [candidates[-1]]
                return self.split_cache[mask]
        candidates.sort(key=lambda item: item[0])
        self.split_cache[mask] = candidates[:self.budget.limits['candidate_width']]
        return self.split_cache[mask]

    def lower_estimate(self, mask, depth):
        self.budget.guard()
        error = self.leaf(mask)[0]
        if not error or depth >= self.budget.limits['max_depth']:
            return error
        options = self.splits(mask)
        return min(error, options[0][0][0]) if options else error

    def solve(self, mask, depth=0):
        self.budget.guard()
        key = mask, depth
        if key in self.solve_cache:
            return copy.deepcopy(self.solve_cache[key])
        self.stats['search_attempts'] += 1
        if not self.support(mask):
            return None
        error, emission = self.leaf(mask)
        if error == 0:
            node = dict(self.info(mask), kind='emit', type='Color', emission=copy.deepcopy(emission))
            self.solve_cache[key] = node
            return copy.deepcopy(node)
        if depth >= self.budget.limits['max_depth']:
            self.stats['unresolved_leaves'] += 1
            self.solve_cache[key] = None
            return None
        options = self.splits(mask)
        ranked = []
        for option in options[:self.budget.limits['beam_width']]:
            self.budget.guard()
            ordinary, predicate, yes_mask, no_mask = option
            if self.budget.limits['lookahead'] == 2:
                self.stats['lookahead_evaluations'] += 1
                estimate = self.lower_estimate(yes_mask, depth + 1) + self.lower_estimate(no_mask, depth + 1)
            else:
                estimate = ordinary[0]
            ranked.append(((estimate, *ordinary), predicate, yes_mask, no_mask))
            # Evaluate the frontier lazily. A zero two-level estimate is an
            # exact lower bound, so try that constructive witness immediately
            # rather than compiling every unrelated numerical child partition.
            # Failed recursion is still charged and the next frontier entry is
            # explored; no allowance or feature/emission language is enlarged.
            if estimate == 0:
                yes = self.solve(yes_mask, depth + 1)
                no = self.solve(no_mask, depth + 1) if yes is not None else None
                if yes is not None and no is not None:
                    node = dict(self.info(mask), kind='if', type='Color', predicate=copy.deepcopy(predicate), yes=yes, no=no)
                    if _nodes(node) <= self.budget.limits['max_nodes']:
                        self.solve_cache[key] = node
                        return copy.deepcopy(node)
        ranked.sort(key=lambda item: item[0])
        for _, predicate, yes_mask, no_mask in ranked[:self.budget.limits['beam_width']]:
            self.budget.guard()
            yes = self.solve(yes_mask, depth + 1)
            if yes is None:
                continue
            no = self.solve(no_mask, depth + 1)
            if no is None:
                continue
            node = dict(self.info(mask), kind='if', type='Color', predicate=copy.deepcopy(predicate), yes=yes, no=no)
            if _nodes(node) <= self.budget.limits['max_nodes']:
                self.solve_cache[key] = node
                return copy.deepcopy(node)
        self.stats['unresolved_leaves'] += 1
        self.solve_cache[key] = None
        return None


def _nodes(node):
    return 1 if node['kind'] == 'emit' else 1 + _nodes(node['yes']) + _nodes(node['no'])


def train(retained, caps=None, check=lambda: None):
    limits = _limits(caps)
    budget = M._Budget(limits, check)
    if type(retained) is not list or not 2 <= len(retained) <= 10:
        raise Failure('AT_LEAST_TWO_RETAINED_DEMOS_REQUIRED')
    examples, search, model = [], None, None
    reason = 'NO_EXACT_TREE_WITHIN_DECLARED_BEAM'
    try:
        colors = set()
        for pair in retained:
            budget.guard()
            if type(pair) is not dict or set(pair) != {'input', 'output'}:
                raise Failure('RETAINED_DEMO_FIELDS_ONLY')
            valid_grid(pair['input']); valid_grid(pair['output'])
            if (len(pair['input']), len(pair['input'][0])) != (len(pair['output']), len(pair['output'][0])):
                raise Failure('SAME_SHAPED_PAIRS_REQUIRED')
            features = M._features(pair['input'], budget)
            targets = [value for row in pair['output'] for value in row]
            if len(examples) + len(features) > limits['max_samples']:
                raise M._Limit('SAMPLE_CAP_UNKNOWN')
            identity = digest(pair)
            examples.extend((feature, target, identity) for feature, target in zip(features, targets))
            colors.update(targets)
        search = _Search(examples, M._emissions(colors), budget)
        tree = search.solve(search.full)
        if tree is not None:
            payload = {'schema': 'CORA_CONDITIONAL_COLOR_TREE_V1', 'features': list(FEATURES),
                       'background': 0, 'tree': tree, 'training_demo_sha256': digest(retained)}
            candidate = dict(payload, model_sha256=digest(payload))
            validate_model(candidate)
            for pair in retained:
                actual = M._apply_features(candidate, M._features(pair['input'], budget), budget)
                if actual != [color for row in pair['output'] for color in row]:
                    raise Failure('FRESH_REPLAY_DISAGREEMENT')
            model, reason = candidate, 'EXACT_ALL_DEMO_CONDITIONAL_PROGRAM'
    except M._Limit as error:
        if budget.external and budget.external[-1] is error:
            raise
        reason = str(error)
    elapsed = time.process_time() - budget.started
    if elapsed >= limits['CPU_s']:
        model, reason = None, 'THROUGH_RETURN_CPU_CAP_UNKNOWN'
    stats = search.stats if search else {}
    return {'model': model, 'status': 'VERIFIED_RETAINED_FIT' if model else 'UNKNOWN',
            'reason': reason, 'samples': len(examples),
            'constructed_nodes': _nodes(model['tree']) if model else 0,
            'unresolved_leaves': stats.get('unresolved_leaves', 0),
            'cost': dict(budget.used, CPU_s=elapsed), 'caps': limits,
            'query_or_task_id_received': False, 'primitive_semantics_learned': False,
            'learned_capability': 'conditional_Color_program_over_fixed_features',
            'constructor': CONSTRUCTOR, **stats}


def predict(model, grid, caps=None, check=lambda: None):
    # Frozen interpreter performs fresh features, hash/type checks, observed-value
    # checks, all-pixel execution, cancellation and through-return CPU checks.
    limits = _limits(caps)
    return M.predict(model, grid, {key: value for key, value in limits.items() if key in M.DEFAULT_CAPS}, check)
