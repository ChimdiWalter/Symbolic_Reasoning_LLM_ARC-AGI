"""Run portfolio solver on ARC tasks, combining DSL + local rules + CEGIS + world model."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.local_rules import solve_task_local_rules, STRATEGY_REGISTRY
from reasoning_project.portfolio import PortfolioSolver, WorldModelReranker, compute_task_features


def make_local_rule_solver():
    def solver(train_pairs, test_inputs):
        if not all(inp.shape == out.shape for inp, out in train_pairs):
            return None
        result = solve_task_local_rules(train_pairs, test_inputs)
        if result is None:
            return None
        predictions, rule = result
        return predictions, {"strategy": rule.strategy_name, "n_rules": len(rule.mapping)}
    return solver


def make_dsl_solver(max_depth=2, dsl_profile="arc_expanded", colors=None):
    if colors is None:
        colors = list(range(1, 10))

    from reasoning_project.operators import candidate_programs, apply_program

    programs = None

    def solver(train_pairs, test_inputs):
        nonlocal programs
        if programs is None:
            programs = candidate_programs(max_depth, colors, profile=dsl_profile)

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


def make_rule_induction_solver():
    """Use the RuleInductionModel's strategies directly."""
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
                return predictions, {"strategy": strategy, "n_rules": len(rule)}

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
        predictions, metadata = result
        return predictions, metadata
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


def make_abstract_program_solver():
    """Create a solver using abstract program induction (H1/H4 strengthener)."""
    from reasoning_project.abstract_programs import solve_task_abstract_programs

    def solver(train_pairs, test_inputs):
        return solve_task_abstract_programs(train_pairs, test_inputs)
    return solver


def make_separator_decompose_solver():
    from reasoning_project.separator_decompose import solve_task_separator_decompose

    def solver(train_pairs, test_inputs):
        return solve_task_separator_decompose(train_pairs, test_inputs)
    return solver


def make_fill_solver():
    from reasoning_project.fill_solver import solve_task_fill

    def solver(train_pairs, test_inputs):
        return solve_task_fill(train_pairs, test_inputs)
    return solver


def make_relation_solver():
    from reasoning_project.relation_solver import solve_task_relation

    def solver(train_pairs, test_inputs):
        return solve_task_relation(train_pairs, test_inputs)
    return solver


def make_reasoning_engine_solver(memory_path=None):
    from reasoning_project.reasoning_engine import (
        GridDomainAdapter, StructuralReasoner, ReasoningMemory,
    )

    adapter = GridDomainAdapter()
    memory = ReasoningMemory()
    if memory_path and Path(memory_path).exists():
        with open(memory_path) as f:
            memory = ReasoningMemory.from_dict(json.load(f))

    reasoner = StructuralReasoner(adapter, memory=memory)

    def solver(train_pairs, test_inputs):
        return reasoner.solve(train_pairs, test_inputs)

    solver._reasoner = reasoner
    solver._memory_path = memory_path
    return solver


def make_world_model_solver(checkpoint_path, device="cpu"):
    """Create a solver that uses the trained world model for direct prediction."""
    from reasoning_project.neural.graph_network import load_world_model_checkpoint

    model = load_world_model_checkpoint(checkpoint_path, device)

    def solver(train_pairs, test_inputs):
        predictions = []
        for test_inp in test_inputs:
            if test_inp.shape[0] > 30 or test_inp.shape[1] > 30:
                return None
            out_shapes = [out.shape for _, out in train_pairs]
            if len(set(out_shapes)) == 1:
                output_shape = out_shapes[0]
            else:
                output_shape = test_inp.shape
            pred = model.predict(test_inp, output_shape, device)
            predictions.append(pred)

        train_correct = 0
        for inp, out in train_pairs:
            if inp.shape[0] > 30 or inp.shape[1] > 30:
                continue
            pred = model.predict(inp, out.shape, device)
            if np.array_equal(pred, out):
                train_correct += 1

        if train_correct == 0:
            return None

        return predictions, {
            "solver": "world_model",
            "train_correct": train_correct,
            "train_total": len(train_pairs),
            "train_accuracy": round(train_correct / len(train_pairs), 4),
        }

    return solver


def load_reranker(checkpoint_path, device="cpu"):
    """Load world model and wrap it as a reranker."""
    from reasoning_project.neural.graph_network import load_world_model_checkpoint
    model = load_world_model_checkpoint(checkpoint_path, device)
    return WorldModelReranker(model, device)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/portfolio_arc")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--skip-dsl", action="store_true", help="Skip DSL solver (fast mode)")
    parser.add_argument("--world-model", default=None,
                        help="Path to world model checkpoint for neural solver + reranking")
    parser.add_argument("--no-rerank", action="store_true",
                        help="Disable world model reranking even if checkpoint provided")
    parser.add_argument("--device", default=None)
    parser.add_argument("--reasoning-memory", default=None,
                        help="Path to reasoning engine memory JSON (loaded/saved)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} tasks")

    device = args.device or "cpu"
    wm_checkpoint = args.world_model
    if wm_checkpoint is None:
        default_ckpt = Path("outputs/neural/world_model_gpu/world_model/world_model_best.pt")
        if default_ckpt.exists():
            wm_checkpoint = str(default_ckpt)
            print(f"Auto-detected world model checkpoint: {wm_checkpoint}")

    solvers = {
        "local_rule": make_local_rule_solver(),
        "rule_induction": make_rule_induction_solver(),
        "object_graph": make_object_graph_solver(),
        "crop_extract": make_crop_extract_solver(),
        "color_solver": make_color_solver(),
        "abstract_program": make_abstract_program_solver(),
        "separator_decompose": make_separator_decompose_solver(),
        "fill_solver": make_fill_solver(),
        "relation_solver": make_relation_solver(),
        "reasoning_engine": make_reasoning_engine_solver(
            memory_path=args.reasoning_memory or str(output_dir / "reasoning_memory.json"),
        ),
    }
    if not args.skip_dsl:
        solvers["dsl"] = make_dsl_solver()

    reranker = None
    if wm_checkpoint:
        try:
            solvers["world_model"] = make_world_model_solver(wm_checkpoint, device)
            print(f"World model solver loaded from {wm_checkpoint}")
            if not args.no_rerank:
                reranker = load_reranker(wm_checkpoint, device)
                print("World model reranker enabled")
        except Exception as e:
            print(f"Warning: could not load world model: {e}")

    portfolio = PortfolioSolver(solvers=solvers, timeout_seconds=300, reranker=reranker)

    solved = []
    solver_contributions = {}
    reranked_count = 0
    per_task = []
    t0 = time.time()

    for i, task in enumerate(tasks):
        if i % 50 == 0:
            print(f"  {i}/{len(tasks)} ({time.time()-t0:.0f}s, solved={len(solved)})", flush=True)

        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
        ]
        test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]
        test_outputs = [np.asarray(ex.output_grid, dtype=int) for ex in task.test]

        result = portfolio.solve(task.task_id, train_pairs, test_inputs, test_outputs)

        if result.solved:
            solved.append(task.task_id)
            solver_contributions[result.solver_used] = solver_contributions.get(result.solver_used, 0) + 1
        if result.reranker_info is not None:
            reranked_count += 1

        entry = {
            "task_id": task.task_id,
            "solved": result.solved,
            "solver_used": result.solver_used,
            "confidence": round(result.confidence, 4),
            "elapsed": round(result.elapsed_seconds, 3),
            "routing_reason": result.routing_reason,
        }
        if result.solved and result.solver_used in result.all_solver_results:
            meta = result.all_solver_results[result.solver_used].get("metadata", {})
            if meta:
                entry["metadata"] = meta
        if result.reranker_info:
            entry["reranker"] = result.reranker_info
        per_task.append(entry)

    elapsed = time.time() - t0
    print(f"\nPortfolio solved {len(solved)}/{len(tasks)} in {elapsed:.0f}s")
    print(f"Solver contributions: {solver_contributions}")
    if reranked_count > 0:
        print(f"Tasks reranked by world model: {reranked_count}")
    for tid in solved:
        entry = next(p for p in per_task if p["task_id"] == tid)
        print(f"  {tid}: {entry['solver_used']} ({entry['elapsed']:.3f}s)")

    summary = {
        "total_tasks": len(tasks),
        "solved": len(solved),
        "solve_rate": round(len(solved) / len(tasks), 4),
        "elapsed_seconds": round(elapsed, 1),
        "solver_contributions": solver_contributions,
        "solved_ids": solved,
        "solvers_available": list(solvers.keys()),
        "world_model_checkpoint": wm_checkpoint,
        "reranker_enabled": reranker is not None,
        "tasks_reranked": reranked_count,
    }
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    with open(output_dir / "per_task.json", "w") as f:
        json.dump(per_task, f, indent=2)

    # Save reasoning engine memory
    re_solver = solvers.get("reasoning_engine")
    if re_solver and hasattr(re_solver, "_reasoner"):
        mem = re_solver._reasoner.memory
        mem_path = re_solver._memory_path or str(output_dir / "reasoning_memory.json")
        with open(mem_path, "w") as f:
            json.dump(mem.to_dict(), f, indent=2)
        print(f"Saved reasoning memory: {len(mem.learned_predicates)} predicates, "
              f"{len(mem.episodes)} episodes → {mem_path}")

    print(f"\nWrote {output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
