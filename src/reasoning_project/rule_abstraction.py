"""Rule Abstraction — learns abstract rules from concrete context→output mappings.

Instead of memorizing {(0,1,0,1): 3, (0,1,0,2): 3, ...}, discovers the
abstract rule: "if neighbor_count > 2: output = 3". Generalizes to unseen
test contexts.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.operator_genesis import SynthesizedOperator


@dataclass
class AbstractRule:
    condition: str
    output_color: int
    predicate: Callable[[tuple], bool]
    coverage: float


def abstract_from_mapping(
    mapping: Dict[tuple, int],
    context_name: str,
) -> List[AbstractRule]:
    """Find abstract rules that explain a context→output mapping."""
    if not mapping:
        return []

    rules = []
    by_output = defaultdict(list)
    for ctx, out_color in mapping.items():
        by_output[out_color].append(ctx)

    # For each output color, find what's common in its contexts
    for out_color, contexts in by_output.items():
        if not contexts:
            continue

        ctx_len = len(contexts[0]) if contexts else 0
        total_in_mapping = len(mapping)
        coverage = len(contexts) / max(total_in_mapping, 1)

        # Strategy A: single element discriminates
        for pos in range(ctx_len):
            vals_for_this_output = set(ctx[pos] for ctx in contexts)
            vals_for_other = set()
            for oc, ocs in by_output.items():
                if oc != out_color:
                    for ctx in ocs:
                        if pos < len(ctx):
                            vals_for_other.add(ctx[pos])

            unique_vals = vals_for_this_output - vals_for_other
            if unique_vals and len(unique_vals) <= 3:
                for val in unique_vals:
                    def make_pred(p, v):
                        def pred(ctx, _p=p, _v=v):
                            return len(ctx) > _p and ctx[_p] == _v
                        return pred
                    rules.append(AbstractRule(
                        condition=f"ctx[{pos}]=={val}",
                        output_color=out_color,
                        predicate=make_pred(pos, val),
                        coverage=coverage,
                    ))

        # Strategy B: threshold on numeric elements
        for pos in range(ctx_len):
            try:
                this_vals = [ctx[pos] for ctx in contexts
                             if isinstance(ctx[pos], (int, float))]
                other_vals = []
                for oc, ocs in by_output.items():
                    if oc != out_color:
                        for ctx in ocs:
                            if pos < len(ctx) and isinstance(ctx[pos], (int, float)):
                                other_vals.append(ctx[pos])

                if not this_vals or not other_vals:
                    continue

                min_this = min(this_vals)
                max_other = max(other_vals) if other_vals else float('-inf')
                max_this = max(this_vals)
                min_other = min(other_vals) if other_vals else float('inf')

                if min_this > max_other:
                    threshold = (min_this + max_other) / 2
                    def make_gt(p, t):
                        def pred(ctx, _p=p, _t=t):
                            return len(ctx) > _p and isinstance(ctx[_p], (int, float)) and ctx[_p] > _t
                        return pred
                    rules.append(AbstractRule(
                        condition=f"ctx[{pos}]>{threshold:.1f}",
                        output_color=out_color,
                        predicate=make_gt(pos, threshold),
                        coverage=coverage,
                    ))

                if max_this < min_other:
                    threshold = (max_this + min_other) / 2
                    def make_lt(p, t):
                        def pred(ctx, _p=p, _t=t):
                            return len(ctx) > _p and isinstance(ctx[_p], (int, float)) and ctx[_p] < _t
                        return pred
                    rules.append(AbstractRule(
                        condition=f"ctx[{pos}]<{threshold:.1f}",
                        output_color=out_color,
                        predicate=make_lt(pos, threshold),
                        coverage=coverage,
                    ))
            except (TypeError, ValueError):
                continue

        # Strategy C: output = context element (copy rule)
        for pos in range(ctx_len):
            if all(isinstance(ctx[pos], int) and ctx[pos] == out_color
                   for ctx in contexts):
                def make_copy(p):
                    def pred(ctx, _p=p):
                        return len(ctx) > _p
                    return pred
                rules.append(AbstractRule(
                    condition=f"output=ctx[{pos}]",
                    output_color=out_color,
                    predicate=make_copy(pos),
                    coverage=coverage,
                ))

        # Strategy D: boolean element (True/False)
        for pos in range(ctx_len):
            if all(isinstance(ctx[pos], bool) for ctx in contexts):
                val = contexts[0][pos]
                if all(ctx[pos] == val for ctx in contexts):
                    other_have_same = any(
                        any(ctx[pos] == val for ctx in ocs)
                        for oc, ocs in by_output.items() if oc != out_color
                    )
                    if not other_have_same:
                        def make_bool(p, v):
                            def pred(ctx, _p=p, _v=v):
                                return len(ctx) > _p and ctx[_p] == _v
                            return pred
                        rules.append(AbstractRule(
                            condition=f"ctx[{pos}]=={'True' if val else 'False'}",
                            output_color=out_color,
                            predicate=make_bool(pos, val),
                            coverage=coverage,
                        ))

    rules.sort(key=lambda r: -r.coverage)
    return rules


def build_abstract_rule_fn(
    rules: List[AbstractRule],
    fallback_mapping: Dict[tuple, int],
    context_fn: Callable,
) -> Callable:
    """Build function that applies abstract rules with exact-mapping fallback."""
    def fn(grid, _rules=rules, _fb=fallback_mapping, _cf=context_fn):
        H, W = grid.shape
        out = np.zeros_like(grid)
        for r in range(H):
            for c in range(W):
                ctx = _cf(grid, r, c)
                # Try exact mapping first
                if ctx in _fb:
                    out[r, c] = _fb[ctx]
                    continue
                # Try abstract rules
                matched = False
                for rule in _rules:
                    try:
                        if rule.predicate(ctx):
                            out[r, c] = rule.output_color
                            matched = True
                            break
                    except Exception:
                        continue
                if not matched:
                    out[r, c] = grid[r, c]
        return out
    return fn


def generalize_context_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    context_fn: Callable,
    context_name: str,
) -> Optional[SynthesizedOperator]:
    """End-to-end: build exact mapping → abstract → generalize → verify."""
    # Build exact mapping from training data
    mapping = {}
    is_identity = True
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        H, W = inp.shape
        for r in range(H):
            for c in range(W):
                ctx = context_fn(inp, r, c)
                expected = int(out[r, c])
                if ctx in mapping:
                    if mapping[ctx] != expected:
                        return None
                else:
                    mapping[ctx] = expected
                if expected != int(inp[r, c]):
                    is_identity = False

    if is_identity or not mapping:
        return None

    # Abstract the mapping
    rules = abstract_from_mapping(mapping, context_name)

    # Build generalized function
    fn = build_abstract_rule_fn(rules, mapping, context_fn)

    # Verify on training data
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if not np.array_equal(pred, out):
                return None
        except Exception:
            return None

    return SynthesizedOperator(
        operator_id=f"abstract_{context_name}_{uuid.uuid4().hex[:8]}",
        operator_family=f"abstracted_{context_name}",
        parameters={"context": context_name, "n_rules": len(rules),
                     "mapping_size": len(mapping)},
        preconditions=[],
        execute=fn,
        explanation=f"[Abstracted] {context_name} with {len(rules)} abstract rules + {len(mapping)} exact entries",
        source_failure_signature={},
    )
