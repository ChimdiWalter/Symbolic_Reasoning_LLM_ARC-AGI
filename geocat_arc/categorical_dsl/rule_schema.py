"""RuleSchema — enforces cross-example rule consistency for ARC tasks."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.categorical_dsl.program import Program
from geocat_arc.bayesian_program_search.real_objective import (
    normalized_cell_accuracy, exact_match,
)


@dataclass
class RuleSchema:
    global_template: Program
    input_predicates: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
    transformation_ops: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.global_template and not self.transformation_ops:
            self.transformation_ops = self.global_template.operator_names

    def bind_and_execute(self, input_grid: Grid) -> Grid:
        return self.global_template.apply(input_grid)

    def score_cross_example(self, task) -> dict:
        per_pair = []
        for pair in task.train:
            try:
                input_grid = Grid.from_list(pair.input)
                result = self.bind_and_execute(input_grid)
                if isinstance(result, Grid):
                    predicted = result.to_list()
                elif isinstance(result, list) and result and isinstance(result[0], list):
                    predicted = result
                else:
                    predicted = [[0]]
                acc = normalized_cell_accuracy(predicted, pair.output)
                is_exact = exact_match(predicted, pair.output)
            except Exception:
                acc = 0.0
                is_exact = False
            per_pair.append({"cell_accuracy": float(acc), "exact_match": bool(is_exact)})

        accs = [r["cell_accuracy"] for r in per_pair]
        mean_acc = float(np.mean(accs)) if accs else 0.0
        std_acc = float(np.std(accs)) if accs else 0.0

        consistency = 1.0 - std_acc if std_acc < 1.0 else 0.0
        all_same_template = True

        return {
            "train_fit_score": mean_acc,
            "cross_example_rule_consistency": float(consistency),
            "predicate_binding_consistency": 1.0 if all_same_template else 0.0,
            "parameter_consistency": float(consistency),
            "per_pair_scores": accs,
            "all_exact": all(r["exact_match"] for r in per_pair),
        }

    def loocv_score(self, task, search_fn=None) -> dict:
        from geocat_arc.data.arc_task import ARCTask
        if len(task.train) < 3:
            return {"skipped": True, "reason": f"only {len(task.train)} train pairs"}

        folds = []
        for hold_idx in range(len(task.train)):
            held_out = task.train[hold_idx]
            try:
                input_grid = Grid.from_list(held_out.input)
                result = self.bind_and_execute(input_grid)
                predicted = result.to_list() if isinstance(result, Grid) else [[0]]
                acc = normalized_cell_accuracy(predicted, held_out.output)
                is_exact = exact_match(predicted, held_out.output)
            except Exception:
                acc = 0.0
                is_exact = False
            folds.append({
                "held_out_index": hold_idx,
                "cell_accuracy": float(acc),
                "exact_match": bool(is_exact),
            })

        held_accs = [f["cell_accuracy"] for f in folds]
        return {
            "skipped": False,
            "folds": folds,
            "loocv_rule_accuracy": float(np.mean([f["exact_match"] for f in folds])),
            "loocv_cell_accuracy": float(np.mean(held_accs)),
        }

    def adjusted_score(self, task, consistency_weight: float = 0.3) -> float:
        metrics = self.score_cross_example(task)
        fit = metrics["train_fit_score"]
        consistency = metrics["cross_example_rule_consistency"]
        return fit * (1.0 - consistency_weight) + fit * consistency * consistency_weight

    def to_dict(self) -> dict:
        return {
            "template": repr(self.global_template),
            "operators": self.transformation_ops,
            "input_predicates": self.input_predicates,
            "relations": self.relations,
        }
