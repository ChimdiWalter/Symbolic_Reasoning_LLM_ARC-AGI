"""Ablation-based importance estimation."""
from __future__ import annotations


def estimate_importance(
    program,
    task,
    score_fn,
) -> dict[str, float]:
    original_score = score_fn(program, task)
    importance = {}

    if not hasattr(program, 'steps'):
        return importance

    for i, step in enumerate(program.steps):
        op_name = step.morphism.name

        ablated_steps = program.steps[:i] + program.steps[i+1:]
        if not ablated_steps:
            importance[op_name] = original_score
            continue

        from geocat_arc.categorical_dsl.program import Program
        ablated = Program(ablated_steps)
        try:
            ablated_score = score_fn(ablated, task)
        except Exception:
            ablated_score = 0.0

        importance[op_name] = max(0.0, original_score - ablated_score)

    return importance
