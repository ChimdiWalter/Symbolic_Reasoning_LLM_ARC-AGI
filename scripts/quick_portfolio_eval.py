"""Quick portfolio eval: no DSL, all other solvers including fill_solver."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks, load_conceptarc_tasks
from reasoning_project.portfolio import PortfolioSolver


def make_solvers():
    from reasoning_project.local_rules import solve_task_local_rules
    from reasoning_project.models import RuleInductionModel
    from reasoning_project.object_graph import solve_task_object_graph
    from reasoning_project.crop_extract import solve_task_crop_extract
    from reasoning_project.color_solver import solve_task_color
    from reasoning_project.abstract_programs import solve_task_abstract_programs
    from reasoning_project.separator_decompose import solve_task_separator_decompose
    from reasoning_project.fill_solver import solve_task_fill

    def local_rule_solver(train_pairs, test_inputs):
        if not all(inp.shape == out.shape for inp, out in train_pairs):
            return None
        result = solve_task_local_rules(train_pairs, test_inputs)
        if result is None:
            return None
        predictions, rule = result
        return predictions, {"strategy": rule.strategy_name, "n_rules": len(rule.mapping)}

    ri_model = RuleInductionModel()
    def rule_induction_solver(train_pairs, test_inputs):
        class FakeExample:
            def __init__(self, ig, og):
                self.input_grid = ig.tolist()
                self.output_grid = og.tolist()
        fake_train = [FakeExample(inp, out) for inp, out in train_pairs]
        for strategy in ri_model._STRATEGIES:
            rule = ri_model._induce_rule(fake_train, strategy)
            if rule is None:
                continue
            train_ok = True
            for inp, out in train_pairs:
                pred = ri_model._apply_rule(inp, rule, strategy)
                if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                    train_ok = False
                    break
            if train_ok:
                predictions = []
                for test_inp in test_inputs:
                    pred = ri_model._apply_rule(test_inp, rule, strategy)
                    predictions.append(pred if pred is not None else test_inp.copy())
                return predictions, {"strategy": strategy, "n_rules": len(rule)}
        for gs in ri_model._GRID_STRATEGIES:
            train_ok = True
            for inp, out in train_pairs:
                pred = ri_model._apply_grid_strategy(inp, gs)
                if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                    train_ok = False
                    break
            if not train_ok:
                continue
            predictions = []
            for test_inp in test_inputs:
                pred = ri_model._apply_grid_strategy(test_inp, gs)
                predictions.append(pred if pred is not None else test_inp.copy())
            return predictions, {"strategy": gs}
        return None

    return {
        "local_rule": local_rule_solver,
        "rule_induction": rule_induction_solver,
        "object_graph": lambda tp, ti: solve_task_object_graph(tp, ti),
        "crop_extract": lambda tp, ti: solve_task_crop_extract(tp, ti),
        "color_solver": lambda tp, ti: solve_task_color(tp, ti),
        "abstract_program": lambda tp, ti: solve_task_abstract_programs(tp, ti),
        "separator_decompose": lambda tp, ti: solve_task_separator_decompose(tp, ti),
        "fill_solver": lambda tp, ti: solve_task_fill(tp, ti),
    }


def eval_benchmark(tasks, solvers, label):
    portfolio = PortfolioSolver(solvers=solvers, timeout_seconds=300, mode="collect_all")
    solved = []
    contributions = {}
    t0 = time.time()

    for i, task in enumerate(tasks):
        if i % 100 == 0:
            print(f"  [{label}] {i}/{len(tasks)} ({time.time()-t0:.0f}s, solved={len(solved)})", flush=True)

        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
        ]
        test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]
        test_outputs = [
            np.asarray(ex.output_grid, dtype=int) for ex in task.test
            if ex.output_grid is not None
        ]
        if not test_outputs:
            test_outputs = None

        result = portfolio.solve(task.task_id, train_pairs, test_inputs, test_outputs)
        if result.solved:
            solved.append((task.task_id, result.solver_used))
            contributions[result.solver_used] = contributions.get(result.solver_used, 0) + 1

    elapsed = time.time() - t0
    print(f"\n=== {label} Results ===")
    print(f"  Solved: {len(solved)}/{len(tasks)} ({len(solved)/len(tasks):.1%})")
    print(f"  Elapsed: {elapsed:.0f}s")
    print(f"  Contributions: {contributions}")
    return solved, contributions


def main():
    print("Loading tasks...")
    arc_tasks = load_arc_tasks("data/arc")
    carc_tasks = load_conceptarc_tasks("data/conceptarc")
    print(f"Loaded {len(arc_tasks)} ARC, {len(carc_tasks)} ConceptARC tasks")

    solvers = make_solvers()
    print(f"Solvers: {list(solvers.keys())}")

    arc_solved, arc_contrib = eval_benchmark(arc_tasks, solvers, "ARC")
    carc_solved, carc_contrib = eval_benchmark(carc_tasks, solvers, "ConceptARC")

    # Save results
    output_dir = Path("outputs/portfolio_v9_no_dsl")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "arc": {
            "solved": len(arc_solved),
            "total": len(arc_tasks),
            "rate": round(len(arc_solved) / len(arc_tasks), 4),
            "contributions": arc_contrib,
            "solved_tasks": [(tid, solver) for tid, solver in arc_solved],
        },
        "conceptarc": {
            "solved": len(carc_solved),
            "total": len(carc_tasks),
            "rate": round(len(carc_solved) / len(carc_tasks), 4),
            "contributions": carc_contrib,
            "solved_tasks": [(tid, solver) for tid, solver in carc_solved],
        },
    }
    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {output_dir / 'results.json'}")


if __name__ == "__main__":
    main()
