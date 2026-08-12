"""Integrated evaluation: world model + JEPA + DSL + all solvers → H1-H5 hypothesis testing.

Runs the full neuro-symbolic pipeline and produces hypothesis-level evidence:
  H1 (structural transfer): portfolio + world model vs symbolic-only on ARC
  H2 (falsification): world model reranking reduces false-positive rate
  H3 (path repair): world model score recovery after grid corruption
  H4 (compression selection): world model agreement correlates with program simplicity
  H5 (integrated scientist): full pipeline (JEPA + world model + symbolic) vs partial stacks
"""
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.local_rules import solve_task_local_rules
from reasoning_project.portfolio import PortfolioSolver, WorldModelReranker
from reasoning_project.analogy import (
    compute_task_signature,
    find_analogous_tasks,
    transfer_solution,
)


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


def make_world_model_solver(checkpoint_path, device="cpu"):
    from reasoning_project.neural.graph_network import load_world_model_checkpoint
    model = load_world_model_checkpoint(checkpoint_path, device)

    def solver(train_pairs, test_inputs):
        predictions = []
        for test_inp in test_inputs:
            if test_inp.shape[0] > 30 or test_inp.shape[1] > 30:
                return None
            out_shapes = [out.shape for _, out in train_pairs]
            output_shape = out_shapes[0] if len(set(out_shapes)) == 1 else test_inp.shape
            pred = model.predict(test_inp, output_shape, device, train_pairs=train_pairs)
            predictions.append(pred)
        train_correct = 0
        for i, (inp, out) in enumerate(train_pairs):
            if inp.shape[0] > 30 or inp.shape[1] > 30:
                continue
            context = [p for j, p in enumerate(train_pairs) if j != i]
            pred = model.predict(inp, out.shape, device, train_pairs=context if context else None)
            if np.array_equal(pred, out):
                train_correct += 1
        if train_correct == 0:
            return None
        return predictions, {
            "solver": "world_model",
            "train_correct": train_correct,
            "train_total": len(train_pairs),
        }
    return solver


def run_config(tasks, solvers, reranker=None, label=""):
    """Run a portfolio configuration and return solved set + per-task details."""
    portfolio = PortfolioSolver(solvers=solvers, timeout_seconds=300, reranker=reranker)
    solved = set()
    per_task = []
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
        per_task.append({
            "task_id": task.task_id,
            "solved": result.solved,
            "solver_used": result.solver_used,
            "confidence": round(result.confidence, 4),
            "reranked": result.reranker_info is not None,
        })
    return solved, per_task


def evaluate_h3_path_repair(tasks, world_model, device, n_samples=50):
    """H3: Does world model scoring recover after grid corruption?"""
    rng = np.random.default_rng(42)
    results = []
    for task in tasks[:n_samples]:
        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
            if np.asarray(ex.input_grid).shape[0] <= 30 and np.asarray(ex.input_grid).shape[1] <= 30
            and np.asarray(ex.output_grid).shape[0] <= 30 and np.asarray(ex.output_grid).shape[1] <= 30
        ]
        for ex in task.train[:1]:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if inp.shape[0] > 30 or inp.shape[1] > 30:
                continue
            if out.shape[0] > 30 or out.shape[1] > 30:
                continue
            context = [p for p in train_pairs if not (np.array_equal(p[0], inp) and np.array_equal(p[1], out))]
            clean_score = world_model.score_candidate(inp, out, device, train_pairs=context or None)

            corrupted = inp.copy()
            n_corrupt = max(1, int(0.1 * corrupted.size))
            flat = corrupted.flatten()
            indices = rng.choice(len(flat), size=n_corrupt, replace=False)
            flat[indices] = rng.integers(0, 10, size=n_corrupt)
            corrupted = flat.reshape(inp.shape)
            corrupt_score = world_model.score_candidate(corrupted, out, device, train_pairs=context or None)

            results.append({
                "task_id": task.task_id,
                "clean_score": round(clean_score, 4),
                "corrupt_score": round(corrupt_score, 4),
                "score_drop": round(clean_score - corrupt_score, 4),
                "recovered": clean_score > corrupt_score,
            })

    n_recovered = sum(r["recovered"] for r in results)
    return {
        "n_evaluated": len(results),
        "n_recovered": n_recovered,
        "recovery_rate": round(n_recovered / max(1, len(results)), 4),
        "mean_clean_score": round(float(np.mean([r["clean_score"] for r in results])), 4) if results else 0,
        "mean_corrupt_score": round(float(np.mean([r["corrupt_score"] for r in results])), 4) if results else 0,
        "mean_score_drop": round(float(np.mean([r["score_drop"] for r in results])), 4) if results else 0,
        "details": results,
    }


def evaluate_h4_compression_agreement(tasks, world_model, device, dsl_solver):
    """H4: Does world model score correlate with program simplicity?"""
    results = []
    for task in tasks[:100]:
        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
        ]
        test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]

        dsl_result = dsl_solver(train_pairs, test_inputs)
        if dsl_result is None:
            continue

        predictions, meta = dsl_result
        prog_steps = len(meta.get("program", []))

        for test_inp, pred in zip(test_inputs, predictions):
            if test_inp.shape[0] > 30 or test_inp.shape[1] > 30:
                continue
            wm_score = world_model.score_candidate(test_inp, pred, device, train_pairs=train_pairs)
            results.append({
                "task_id": task.task_id,
                "wm_score": round(wm_score, 4),
                "program_length": prog_steps,
            })

    if len(results) < 3:
        return {"n_evaluated": len(results), "correlation": 0.0, "verdict": "insufficient_data"}

    scores = np.array([r["wm_score"] for r in results])
    lengths = np.array([r["program_length"] for r in results])
    if np.std(scores) < 1e-8 or np.std(lengths) < 1e-8:
        corr = 0.0
    else:
        corr = float(np.corrcoef(scores, -lengths)[0, 1])

    return {
        "n_evaluated": len(results),
        "correlation_wm_vs_neg_length": round(corr, 4),
        "verdict": "supported" if corr > 0.1 else "inconclusive",
        "details": results[:20],
    }


def compute_jepa_world_model_complementarity(tasks, world_model, device):
    """Measure how JEPA grid embeddings and world model slots differ in what they capture."""
    try:
        from reasoning_project.neural.grid_encoder import build_grid_encoder
        encoder = build_grid_encoder(use_torch=False)
    except Exception:
        return {"status": "skipped", "reason": "grid encoder unavailable"}

    results = []
    for task in tasks[:50]:
        train_pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
            if np.asarray(ex.input_grid).shape[0] <= 30 and np.asarray(ex.input_grid).shape[1] <= 30
            and np.asarray(ex.output_grid).shape[0] <= 30 and np.asarray(ex.output_grid).shape[1] <= 30
        ]
        for ex in task.train[:1]:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if inp.shape[0] > 30 or inp.shape[1] > 30:
                continue
            if out.shape[0] > 30 or out.shape[1] > 30:
                continue

            jepa_enc = encoder.encode_grid(inp)
            context = [p for p in train_pairs if not (np.array_equal(p[0], inp) and np.array_equal(p[1], out))]
            wm_score = world_model.score_candidate(inp, out, device, train_pairs=context or None)

            results.append({
                "task_id": task.task_id,
                "jepa_dim": len(jepa_enc.grid_latent.flatten()),
                "wm_pixel_agreement": round(wm_score, 4),
            })

    return {
        "n_evaluated": len(results),
        "mean_wm_agreement": round(float(np.mean([r["wm_pixel_agreement"] for r in results])), 4) if results else 0,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/integrated_eval")
    parser.add_argument("--world-model", default=None)
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--skip-dsl", action="store_true")
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

    world_model = None
    reranker = None
    if wm_checkpoint:
        try:
            from reasoning_project.neural.graph_network import load_world_model_checkpoint
            world_model = load_world_model_checkpoint(wm_checkpoint, device)
            reranker = WorldModelReranker(world_model, device)
            print(f"Loaded world model from {wm_checkpoint}")
        except Exception as e:
            print(f"Warning: world model unavailable: {e}")

    t0 = time.time()

    # === Configuration A: symbolic-only ===
    print("\n--- Config A: Symbolic Only ---")
    symbolic_solvers = {
        "local_rule": make_local_rule_solver(),
        "rule_induction": make_rule_induction_solver(),
        "object_graph": make_object_graph_solver(),
        "crop_extract": make_crop_extract_solver(),
        "color_solver": make_color_solver(),
        "abstract_program": make_abstract_program_solver(),
        "separator_decompose": make_separator_decompose_solver(),
    }
    dsl_solver = None
    if not args.skip_dsl:
        dsl_solver = make_dsl_solver()
        symbolic_solvers["dsl"] = dsl_solver
    solved_symbolic, per_task_symbolic = run_config(tasks, symbolic_solvers, label="symbolic")
    print(f"  Solved: {len(solved_symbolic)}/{len(tasks)}")

    # === Configuration B: symbolic + world model solver ===
    solved_with_wm = solved_symbolic
    per_task_with_wm = per_task_symbolic
    if world_model and wm_checkpoint:
        print("\n--- Config B: Symbolic + World Model Solver ---")
        solvers_b = dict(symbolic_solvers)
        solvers_b["world_model"] = make_world_model_solver(wm_checkpoint, device)
        solved_with_wm, per_task_with_wm = run_config(tasks, solvers_b, label="sym+wm")
        print(f"  Solved: {len(solved_with_wm)}/{len(tasks)}")
        wm_unique = solved_with_wm - solved_symbolic
        print(f"  World model unique contribution: {len(wm_unique)} tasks")

    # === Configuration C: symbolic + world model solver + reranker ===
    solved_full = solved_with_wm
    per_task_full = per_task_with_wm
    if reranker and wm_checkpoint:
        print("\n--- Config C: Full Pipeline (Symbolic + WM Solver + Reranker) ---")
        solvers_c = dict(symbolic_solvers)
        solvers_c["world_model"] = make_world_model_solver(wm_checkpoint, device)
        solved_full, per_task_full = run_config(tasks, solvers_c, reranker=reranker, label="full")
        print(f"  Solved: {len(solved_full)}/{len(tasks)}")

    # === Hypothesis Evaluation ===
    hypotheses = {}

    # H1: Structural Transfer — does the combined portfolio outperform any single solver?
    print("\n--- H1: Structural Transfer ---")
    h1_evidence = {
        "symbolic_only": len(solved_symbolic),
        "with_world_model": len(solved_with_wm),
        "full_pipeline": len(solved_full),
        "total_tasks": len(tasks),
        "wm_unique_tasks": sorted(solved_with_wm - solved_symbolic) if world_model else [],
        "reranker_delta": len(solved_full) - len(solved_with_wm),
    }
    if len(solved_full) > len(solved_symbolic):
        h1_evidence["verdict"] = "supported"
    elif len(solved_full) == len(solved_symbolic) and len(solved_full) > 0:
        h1_evidence["verdict"] = "weakly_supported"
    else:
        h1_evidence["verdict"] = "inconclusive"
    hypotheses["H1_structural_transfer"] = h1_evidence
    print(f"  Symbolic: {h1_evidence['symbolic_only']}, +WM: {h1_evidence['with_world_model']}, Full: {h1_evidence['full_pipeline']}")
    print(f"  Verdict: {h1_evidence['verdict']}")

    # H2: Falsification via reranking — does world model reranking reduce false positives?
    print("\n--- H2: Falsification (Reranking) ---")
    if reranker:
        false_pos_before = sum(
            1 for pt in per_task_with_wm if not pt["solved"] and pt["solver_used"] != "none"
        )
        false_pos_after = sum(
            1 for pt in per_task_full if not pt["solved"] and pt["solver_used"] != "none"
        )
        h2_evidence = {
            "false_positives_without_reranker": false_pos_before,
            "false_positives_with_reranker": false_pos_after,
            "reduction": false_pos_before - false_pos_after,
            "verdict": "supported" if false_pos_after < false_pos_before else "inconclusive",
        }
    else:
        h2_evidence = {"verdict": "not_tested", "reason": "no_world_model"}
    hypotheses["H2_falsification"] = h2_evidence
    print(f"  {h2_evidence}")

    # H3: Path Repair — world model distinguishes clean vs corrupted inputs
    print("\n--- H3: Path Repair ---")
    if world_model:
        h3_evidence = evaluate_h3_path_repair(tasks, world_model, device)
        if h3_evidence["recovery_rate"] > 0.5:
            h3_evidence["verdict"] = "supported"
        elif h3_evidence["recovery_rate"] > 0.3:
            h3_evidence["verdict"] = "weakly_supported"
        else:
            h3_evidence["verdict"] = "inconclusive"
        del h3_evidence["details"]
    else:
        h3_evidence = {"verdict": "not_tested", "reason": "no_world_model"}
    hypotheses["H3_path_repair"] = h3_evidence
    print(f"  {h3_evidence}")

    # H4: Compression Selection — world model agreement correlates with program simplicity
    print("\n--- H4: Compression Selection ---")
    if world_model and dsl_solver:
        h4_evidence = evaluate_h4_compression_agreement(tasks, world_model, device, dsl_solver)
        del h4_evidence["details"]
    else:
        h4_evidence = {"verdict": "not_tested", "reason": "no_world_model_or_dsl"}
    hypotheses["H4_compression_selection"] = h4_evidence
    print(f"  {h4_evidence}")

    # H5: Integrated Scientist — full pipeline >= all partial stacks
    print("\n--- H5: Integrated Scientist ---")
    h5_evidence = {
        "symbolic_only": len(solved_symbolic),
        "full_pipeline": len(solved_full),
        "improvement": len(solved_full) - len(solved_symbolic),
        "improvement_pct": round(100 * (len(solved_full) - len(solved_symbolic)) / max(1, len(solved_symbolic)), 2),
    }
    if len(solved_full) > len(solved_symbolic):
        h5_evidence["verdict"] = "supported"
    elif len(solved_full) == len(solved_symbolic):
        h5_evidence["verdict"] = "inconclusive"
    else:
        h5_evidence["verdict"] = "not_supported"
    hypotheses["H5_integrated_scientist"] = h5_evidence
    print(f"  {h5_evidence}")

    # H6: Analogical Transfer — can solved task structure transfer to unsolved tasks?
    print("\n--- H6: Analogical Transfer ---")
    h6_evidence = {"verdict": "not_tested", "reason": "no_solved_tasks"}
    if solved_full:
        # Compute signatures for solved tasks
        solved_signatures = {}
        solved_train_data = {}
        solved_predictions_data = {}
        for task in tasks:
            if task.task_id in solved_full:
                train_pairs = [
                    (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
                    for ex in task.train
                ]
                sig = compute_task_signature(train_pairs)
                solved_signatures[task.task_id] = sig
                solved_train_data[task.task_id] = train_pairs
                # Store known outputs as stand-in predictions
                test_outputs = [np.asarray(ex.output_grid, dtype=int) for ex in task.test]
                solved_predictions_data[task.task_id] = test_outputs

        # Try analogical transfer on unsolved tasks
        transfer_successes = 0
        transfer_attempts = 0
        transfer_details = []
        for task in tasks:
            if task.task_id in solved_full:
                continue
            train_pairs = [
                (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
                for ex in task.train
            ]
            test_inputs = [np.asarray(ex.input_grid, dtype=int) for ex in task.test]
            test_outputs = [np.asarray(ex.output_grid, dtype=int) for ex in task.test]

            target_sig = compute_task_signature(train_pairs)
            analogues = find_analogous_tasks(target_sig, solved_signatures, threshold=0.7)

            for src_id, sim in analogues[:3]:  # Try top 3 analogues
                transfer_attempts += 1
                src_train = solved_train_data[src_id]
                src_preds = solved_predictions_data.get(src_id, [])

                result = transfer_solution(src_train, src_preds, train_pairs, test_inputs)
                if result is not None:
                    # Check if transfer produced correct outputs
                    all_correct = True
                    for pred, expected in zip(result, test_outputs):
                        if pred.shape != expected.shape or not np.array_equal(pred, expected):
                            all_correct = False
                            break
                    if all_correct:
                        transfer_successes += 1
                        transfer_details.append({
                            "target_task": task.task_id,
                            "source_task": src_id,
                            "similarity": round(sim, 4),
                        })
                        break  # Task solved, move on

        h6_evidence = {
            "n_solved_tasks": len(solved_full),
            "n_unsolved_tasks": len(tasks) - len(solved_full),
            "transfer_attempts": transfer_attempts,
            "transfer_successes": transfer_successes,
            "additional_tasks_solved": transfer_successes,
            "details": transfer_details[:10],
        }
        if transfer_successes > 0:
            h6_evidence["verdict"] = "supported"
        elif transfer_attempts > 0:
            h6_evidence["verdict"] = "inconclusive"
        else:
            h6_evidence["verdict"] = "not_tested"
    hypotheses["H6_analogical_transfer"] = h6_evidence
    print(f"  {h6_evidence}")

    # JEPA complementarity analysis
    print("\n--- JEPA + World Model Complementarity ---")
    jepa_complementarity = {}
    if world_model:
        jepa_complementarity = compute_jepa_world_model_complementarity(tasks, world_model, device)
    print(f"  {jepa_complementarity}")

    elapsed = time.time() - t0

    # === Write results ===
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tasks": len(tasks),
        "elapsed_seconds": round(elapsed, 1),
        "world_model_checkpoint": wm_checkpoint,
        "device": device,
        "configurations": {
            "symbolic_only": {"solved": len(solved_symbolic), "rate": round(len(solved_symbolic) / len(tasks), 4)},
            "with_world_model": {"solved": len(solved_with_wm), "rate": round(len(solved_with_wm) / len(tasks), 4)},
            "full_pipeline": {"solved": len(solved_full), "rate": round(len(solved_full) / len(tasks), 4)},
        },
        "hypotheses": hypotheses,
        "jepa_complementarity": jepa_complementarity,
    }

    with open(output_dir / "integrated_eval.json", "w") as f:
        json.dump(report, f, indent=2, cls=_NumpyEncoder)

    with open(output_dir / "per_task_full.json", "w") as f:
        json.dump(per_task_full, f, indent=2, cls=_NumpyEncoder)

    print(f"\n{'='*60}")
    print(f"INTEGRATED EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Tasks: {len(tasks)}")
    print(f"Symbolic only: {len(solved_symbolic)} ({len(solved_symbolic)/len(tasks)*100:.1f}%)")
    print(f"+ World Model: {len(solved_with_wm)} ({len(solved_with_wm)/len(tasks)*100:.1f}%)")
    print(f"Full Pipeline:  {len(solved_full)} ({len(solved_full)/len(tasks)*100:.1f}%)")
    print(f"\nHypothesis Verdicts:")
    for hname, hdata in hypotheses.items():
        print(f"  {hname}: {hdata.get('verdict', 'unknown')}")
    print(f"\nElapsed: {elapsed:.0f}s")
    print(f"Wrote {output_dir / 'integrated_eval.json'}")


if __name__ == "__main__":
    main()
