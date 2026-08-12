"""Cross-benchmark ablation: ARC + ConceptARC x collect_all vs first_hit.

Produces the clean ablation story for the paper:
- Multi-proposer collect-all beats first-hit cascade on both benchmarks
- Per-concept-group breakdown on ConceptARC shows generalization
- World model contribution (with/without) if checkpoint available
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks, load_conceptarc_tasks
from reasoning_project.portfolio import PortfolioSolver, WorldModelReranker, compute_task_features


def make_solvers(skip_dsl=False, wm_checkpoint=None, device="cpu"):
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

    solvers = {
        "local_rule": local_rule_solver,
        "rule_induction": rule_induction_solver,
        "object_graph": lambda tp, ti: solve_task_object_graph(tp, ti),
        "crop_extract": lambda tp, ti: solve_task_crop_extract(tp, ti),
        "color_solver": lambda tp, ti: solve_task_color(tp, ti),
        "abstract_program": lambda tp, ti: solve_task_abstract_programs(tp, ti),
        "separator_decompose": lambda tp, ti: solve_task_separator_decompose(tp, ti),
        "fill_solver": lambda tp, ti: solve_task_fill(tp, ti),
    }

    if not skip_dsl:
        from reasoning_project.operators import candidate_programs, apply_program
        programs = None
        def dsl_solver(train_pairs, test_inputs):
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
        solvers["dsl"] = dsl_solver

    reranker = None
    if wm_checkpoint:
        try:
            from reasoning_project.neural.graph_network import load_world_model_checkpoint
            model = load_world_model_checkpoint(wm_checkpoint, device)
            def wm_solver(train_pairs, test_inputs):
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
                train_correct = sum(
                    1 for inp, out in train_pairs
                    if inp.shape[0] <= 30 and inp.shape[1] <= 30
                    and np.array_equal(model.predict(inp, out.shape, device), out)
                )
                if train_correct == 0:
                    return None
                return predictions, {"solver": "world_model", "train_correct": train_correct}
            solvers["world_model"] = wm_solver
            reranker = WorldModelReranker(model, device)
            print(f"World model loaded from {wm_checkpoint}")
        except Exception as e:
            print(f"Warning: could not load world model: {e}")

    return solvers, reranker


def run_benchmark(tasks, solvers, reranker, mode, no_rerank=False, timeout=300):
    portfolio = PortfolioSolver(
        solvers=solvers,
        timeout_seconds=timeout,
        reranker=None if no_rerank else reranker,
        mode=mode,
    )

    solved = []
    solver_contributions = {}
    per_task = []
    concept_groups = {}
    t0 = time.time()

    for i, task in enumerate(tasks):
        if i % 50 == 0:
            print(f"  [{mode}] {i}/{len(tasks)} ({time.time()-t0:.0f}s, solved={len(solved)})", flush=True)

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
            solved.append(task.task_id)
            solver_contributions[result.solver_used] = solver_contributions.get(result.solver_used, 0) + 1

        concept_group = task.metadata.get("concept_group", "arc_training")
        if concept_group not in concept_groups:
            concept_groups[concept_group] = {"total": 0, "solved": 0, "tasks": []}
        concept_groups[concept_group]["total"] += 1
        if result.solved:
            concept_groups[concept_group]["solved"] += 1
        concept_groups[concept_group]["tasks"].append(task.task_id)

        per_task.append({
            "task_id": task.task_id,
            "solved": result.solved,
            "solver_used": result.solver_used,
            "confidence": round(result.confidence, 4),
            "elapsed": round(result.elapsed_seconds, 3),
            "routing_reason": result.routing_reason,
            "concept_group": concept_group,
        })

    elapsed = time.time() - t0

    for cg in concept_groups:
        t = concept_groups[cg]["total"]
        s = concept_groups[cg]["solved"]
        concept_groups[cg]["solve_rate"] = round(s / t, 4) if t > 0 else 0.0

    return {
        "mode": mode,
        "total_tasks": len(tasks),
        "solved": len(solved),
        "solve_rate": round(len(solved) / len(tasks), 4) if tasks else 0.0,
        "elapsed_seconds": round(elapsed, 1),
        "solver_contributions": solver_contributions,
        "solved_ids": solved,
        "per_concept_group": concept_groups,
    }, per_task


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cross-benchmark ablation: ARC + ConceptARC x collect_all vs first_hit")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--conceptarc-root", default="data/conceptarc")
    parser.add_argument("--output-dir", default="outputs/cross_benchmark_ablation")
    parser.add_argument("--skip-dsl", action="store_true")
    parser.add_argument("--skip-arc", action="store_true", help="Skip ARC benchmark (ConceptARC only)")
    parser.add_argument("--max-arc-tasks", type=int, default=None)
    parser.add_argument("--world-model", default=None)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    solvers, reranker = make_solvers(
        skip_dsl=args.skip_dsl,
        wm_checkpoint=args.world_model,
        device=args.device,
    )
    print(f"Solvers: {list(solvers.keys())}")

    results = {}

    # --- ConceptARC ---
    print("\n=== ConceptARC Benchmark ===")
    carc_tasks = load_conceptarc_tasks(args.conceptarc_root)
    print(f"Loaded {len(carc_tasks)} ConceptARC tasks")

    for mode in ["collect_all", "first_hit"]:
        print(f"\n--- ConceptARC / {mode} ---")
        summary, per_task = run_benchmark(
            carc_tasks, solvers, reranker, mode, no_rerank=args.no_rerank
        )
        results[f"conceptarc_{mode}"] = summary
        with open(output_dir / f"conceptarc_{mode}_per_task.json", "w") as f:
            json.dump(per_task, f, indent=2)
        print(f"  ConceptARC/{mode}: {summary['solved']}/{summary['total_tasks']} ({summary['solve_rate']:.1%})")

    # --- ARC ---
    if not args.skip_arc:
        print("\n=== ARC Training Benchmark ===")
        arc_tasks = load_arc_tasks(args.arc_root, max_tasks=args.max_arc_tasks)
        print(f"Loaded {len(arc_tasks)} ARC tasks")

        for mode in ["collect_all", "first_hit"]:
            print(f"\n--- ARC / {mode} ---")
            summary, per_task = run_benchmark(
                arc_tasks, solvers, reranker, mode, no_rerank=args.no_rerank
            )
            results[f"arc_{mode}"] = summary
            with open(output_dir / f"arc_{mode}_per_task.json", "w") as f:
                json.dump(per_task, f, indent=2)
            print(f"  ARC/{mode}: {summary['solved']}/{summary['total_tasks']} ({summary['solve_rate']:.1%})")

    # --- Comparison summary ---
    print("\n=== Ablation Summary ===")
    comparison = {}
    for benchmark in ["conceptarc", "arc"]:
        ca_key = f"{benchmark}_collect_all"
        fh_key = f"{benchmark}_first_hit"
        if ca_key in results and fh_key in results:
            ca = results[ca_key]
            fh = results[fh_key]
            delta = ca["solved"] - fh["solved"]
            comparison[benchmark] = {
                "collect_all_solved": ca["solved"],
                "first_hit_solved": fh["solved"],
                "collect_all_rate": ca["solve_rate"],
                "first_hit_rate": fh["solve_rate"],
                "delta_solved": delta,
                "delta_rate": round(ca["solve_rate"] - fh["solve_rate"], 4),
                "collect_all_contributions": ca["solver_contributions"],
                "first_hit_contributions": fh["solver_contributions"],
            }
            if benchmark == "conceptarc":
                ca_groups = ca.get("per_concept_group", {})
                fh_groups = fh.get("per_concept_group", {})
                group_comparison = {}
                for group in sorted(set(list(ca_groups.keys()) + list(fh_groups.keys()))):
                    ca_g = ca_groups.get(group, {"solved": 0, "total": 0})
                    fh_g = fh_groups.get(group, {"solved": 0, "total": 0})
                    group_comparison[group] = {
                        "collect_all": f"{ca_g['solved']}/{ca_g['total']}",
                        "first_hit": f"{fh_g['solved']}/{fh_g['total']}",
                        "delta": ca_g["solved"] - fh_g["solved"],
                    }
                comparison[f"{benchmark}_by_concept"] = group_comparison

            print(f"  {benchmark}: collect_all={ca['solved']}, first_hit={fh['solved']}, delta=+{delta}")

    results["comparison"] = comparison

    with open(output_dir / "summary.json", "w") as f:
        json.dump(results, f, indent=2)

    # Write markdown report
    md_lines = ["# Cross-Benchmark Ablation: collect_all vs first_hit\n"]
    md_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n")
    md_lines.append(f"Solvers: {list(solvers.keys())}\n")

    md_lines.append("\n## Results Overview\n")
    md_lines.append("| Benchmark | Mode | Solved | Total | Rate |")
    md_lines.append("|---|---|---|---|---|")
    for key in ["conceptarc_collect_all", "conceptarc_first_hit", "arc_collect_all", "arc_first_hit"]:
        if key in results:
            r = results[key]
            md_lines.append(f"| {key} | {r['mode']} | {r['solved']} | {r['total_tasks']} | {r['solve_rate']:.1%} |")

    if "conceptarc" in comparison:
        c = comparison["conceptarc"]
        md_lines.append(f"\n## ConceptARC Delta: +{c['delta_solved']} tasks ({c['delta_rate']:+.1%})\n")
        md_lines.append("### Solver Contributions\n")
        md_lines.append("| Solver | collect_all | first_hit |")
        md_lines.append("|---|---|---|")
        all_solvers = sorted(set(
            list(c["collect_all_contributions"].keys()) + list(c["first_hit_contributions"].keys())
        ))
        for s in all_solvers:
            md_lines.append(f"| {s} | {c['collect_all_contributions'].get(s, 0)} | {c['first_hit_contributions'].get(s, 0)} |")

    if "conceptarc_by_concept" in comparison:
        md_lines.append("\n### Per Concept Group\n")
        md_lines.append("| Concept Group | collect_all | first_hit | Delta |")
        md_lines.append("|---|---|---|---|")
        for group, data in sorted(comparison["conceptarc_by_concept"].items()):
            md_lines.append(f"| {group} | {data['collect_all']} | {data['first_hit']} | {data['delta']:+d} |")

    if "arc" in comparison:
        c = comparison["arc"]
        md_lines.append(f"\n## ARC Delta: +{c['delta_solved']} tasks ({c['delta_rate']:+.1%})\n")

    with open(output_dir / "ablation_report.md", "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nWrote {output_dir / 'summary.json'}")
    print(f"Wrote {output_dir / 'ablation_report.md'}")


if __name__ == "__main__":
    main()
