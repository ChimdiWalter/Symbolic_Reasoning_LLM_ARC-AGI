"""Leave-one-solver-out ablation study for the portfolio."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.portfolio import PortfolioSolver


def make_local_rule_solver():
    from reasoning_project.local_rules import solve_task_local_rules
    def solver(train_pairs, test_inputs):
        if not all(inp.shape == out.shape for inp, out in train_pairs):
            return None
        result = solve_task_local_rules(train_pairs, test_inputs)
        if result is None:
            return None
        predictions, rule = result
        return predictions, {"strategy": rule.strategy_name, "n_rules": len(rule.mapping)}
    return solver


def make_rule_induction_solver():
    from reasoning_project.models import RuleInductionModel
    model = RuleInductionModel()
    def solver(train_pairs, test_inputs):
        class FakeExample:
            def __init__(self, ig, og):
                self.input_grid = ig.tolist()
                self.output_grid = og.tolist()
        fake_train = [FakeExample(inp, out) for inp, out in train_pairs]
        for strategy in model._STRATEGIES:
            rule = model._induce_rule(fake_train, strategy)
            if rule is None:
                continue
            train_ok = True
            for inp, out in train_pairs:
                pred = model._apply_rule(inp, rule, strategy)
                if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                    train_ok = False
                    break
            if train_ok:
                predictions = []
                for test_inp in test_inputs:
                    pred = model._apply_rule(test_inp, rule, strategy)
                    predictions.append(pred if pred is not None else test_inp.copy())
                return predictions, {"strategy": strategy}
        for gs in model._GRID_STRATEGIES:
            train_ok = True
            for inp, out in train_pairs:
                pred = model._apply_grid_strategy(inp, gs)
                if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                    train_ok = False
                    break
            if not train_ok:
                continue
            predictions = []
            for test_inp in test_inputs:
                pred = model._apply_grid_strategy(test_inp, gs)
                predictions.append(pred if pred is not None else test_inp.copy())
            return predictions, {"strategy": gs}
        return None
    return solver


def make_object_graph_solver():
    from reasoning_project.object_graph import solve_task_object_graph
    def solver(train_pairs, test_inputs):
        result = solve_task_object_graph(train_pairs, test_inputs)
        if result is None:
            return None
        return result
    return solver


def make_crop_extract_solver():
    from reasoning_project.crop_extract import solve_task_crop_extract
    def solver(train_pairs, test_inputs):
        return solve_task_crop_extract(train_pairs, test_inputs)
    return solver


def make_color_solver():
    from reasoning_project.color_solver import solve_task_color
    def solver(train_pairs, test_inputs):
        return solve_task_color(train_pairs, test_inputs)
    return solver


def make_dsl_solver():
    from reasoning_project.operators import candidate_programs, apply_program
    programs = None
    def solver(train_pairs, test_inputs):
        nonlocal programs
        if programs is None:
            programs = candidate_programs(2, list(range(1, 10)), profile="arc_expanded")
        for prog in programs:
            all_ok = True
            for inp, out in train_pairs:
                try:
                    pred = apply_program(inp, prog)
                except Exception:
                    all_ok = False
                    break
                if pred is None or not isinstance(pred, np.ndarray):
                    all_ok = False
                    break
                if pred.shape != out.shape or not np.array_equal(pred, out):
                    all_ok = False
                    break
            if all_ok:
                predictions = []
                for test_inp in test_inputs:
                    try:
                        predictions.append(apply_program(test_inp, prog))
                    except Exception:
                        predictions.append(test_inp.copy())
                return predictions, {"program": [str(s) for s in prog]}
        return None
    return solver


def make_abstract_program_solver():
    from reasoning_project.abstract_programs import solve_task_abstract_programs
    def solver(train_pairs, test_inputs):
        return solve_task_abstract_programs(train_pairs, test_inputs)
    return solver


def make_separator_decompose_solver():
    from reasoning_project.separator_decompose import solve_task_separator_decompose
    def solver(train_pairs, test_inputs):
        return solve_task_separator_decompose(train_pairs, test_inputs)
    return solver


def make_world_model_solver_factory(checkpoint_path, device="cpu"):
    def factory():
        from reasoning_project.neural.graph_network import load_world_model_checkpoint
        model = load_world_model_checkpoint(checkpoint_path, device)
        def solver(train_pairs, test_inputs):
            predictions = []
            for test_inp in test_inputs:
                if test_inp.shape[0] > 30 or test_inp.shape[1] > 30:
                    return None
                out_shapes = [out.shape for _, out in train_pairs]
                output_shape = out_shapes[0] if len(set(out_shapes)) == 1 else test_inp.shape
                pred = model.predict(test_inp, output_shape, device)
                predictions.append(pred)
            train_correct = sum(
                1 for inp, out in train_pairs
                if inp.shape[0] <= 30 and inp.shape[1] <= 30
                and np.array_equal(model.predict(inp, out.shape, device), out)
            )
            if train_correct == 0:
                return None
            return predictions, {"solver": "world_model", "train_correct": train_correct}
        return solver
    return factory


ALL_SOLVERS = {
    "local_rule": make_local_rule_solver,
    "rule_induction": make_rule_induction_solver,
    "object_graph": make_object_graph_solver,
    "crop_extract": make_crop_extract_solver,
    "color_solver": make_color_solver,
    "dsl": make_dsl_solver,
    "abstract_program": make_abstract_program_solver,
    "separator_decompose": make_separator_decompose_solver,
}


def run_ablation(tasks, solver_factories, output_dir):
    """Run full portfolio and each leave-one-out variant."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ablation_results = {}

    # Full portfolio
    full_solvers = {name: factory() for name, factory in solver_factories.items()}
    full_portfolio = PortfolioSolver(solvers=full_solvers, timeout_seconds=300)
    full_solved = run_portfolio_on_tasks(tasks, full_portfolio)
    ablation_results["full"] = full_solved
    print(f"Full: {len(full_solved)}/{len(tasks)}")

    # Leave-one-out
    for leave_out in solver_factories:
        remaining = {name: factory() for name, factory in solver_factories.items() if name != leave_out}
        portfolio = PortfolioSolver(solvers=remaining, timeout_seconds=300)
        solved = run_portfolio_on_tasks(tasks, portfolio)
        ablation_results[f"without_{leave_out}"] = solved
        contribution = len(full_solved) - len(solved)
        unique = full_solved - solved
        print(f"Without {leave_out}: {len(solved)}/{len(tasks)} (contribution: {contribution}, unique: {sorted(unique)[:3]}...)")

    summary = {}
    for config, solved_set in ablation_results.items():
        summary[config] = {
            "n_solved": len(solved_set),
            "solve_rate": round(len(solved_set) / len(tasks), 4),
            "solved_ids": sorted(solved_set),
        }

    full_set = ablation_results["full"]
    for leave_out in solver_factories:
        without_set = ablation_results[f"without_{leave_out}"]
        unique_contribution = sorted(full_set - without_set)
        summary[f"unique_contribution_{leave_out}"] = {
            "n_unique": len(unique_contribution),
            "task_ids": unique_contribution,
        }

    with open(output_dir / "ablation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {output_dir / 'ablation_summary.json'}")
    return summary


def run_portfolio_on_tasks(tasks, portfolio):
    solved = set()
    for task in tasks:
        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
        ]
        test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]
        test_outputs = [np.asarray(ex.output_grid, dtype=int) for ex in task.test]
        result = portfolio.solve(task.task_id, train_pairs, test_inputs, test_outputs)
        if result.solved:
            solved.add(task.task_id)
    return solved


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/ablation")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--world-model", default=None, help="World model checkpoint for ablation")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} tasks")

    solvers = dict(ALL_SOLVERS)
    wm_ckpt = args.world_model
    if wm_ckpt is None:
        default_ckpt = Path("outputs/neural/world_model_gpu/world_model/world_model_best.pt")
        if default_ckpt.exists():
            wm_ckpt = str(default_ckpt)
    if wm_ckpt:
        solvers["world_model"] = make_world_model_solver_factory(wm_ckpt, args.device)
        print(f"Including world model in ablation: {wm_ckpt}")

    t0 = time.time()
    run_ablation(tasks, solvers, args.output_dir)
    print(f"\nTotal time: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
