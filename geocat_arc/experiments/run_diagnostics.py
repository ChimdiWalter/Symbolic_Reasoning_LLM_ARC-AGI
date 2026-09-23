"""Detailed failure diagnostics for top-scoring tasks.

Generates per-task diagnostic artifacts:
  - best_program.txt
  - predicted_outputs.json
  - target_outputs.json
  - diff_maps.json
  - object_error_summary.json
  - relation_error_summary.json
  - missing_operator_hypothesis.md
  - shared_rule_hypothesis.md
  - cross_example_consistency.json
  - pairwise_fitting_risk.json
  - loocv_rule_validation.json
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import numpy as np

from geocat_arc.data.arc_loader import load_task
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import extract_objects
from geocat_arc.perception.relations import build_relation_graph
from geocat_arc.perception.matching import match_objects
from geocat_arc.perception.change_detection import detect_changes
from geocat_arc.bayesian_program_search.search_loop import bayesian_search
from geocat_arc.bayesian_program_search.real_objective import (
    evaluate_program, normalized_cell_accuracy, exact_match,
)
from geocat_arc.neuro_cognitive.predictive_error import compute_prediction_error

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "geocat_arc" / "diagnostics"
TARGET_TASKS = ["045e512c", "009d5c81", "03560426", "00d62c1b", "00dbd492"]


def _serialize_grid(grid):
    if isinstance(grid, Grid):
        return grid.to_list()
    return grid


def _diff_map(predicted, target):
    pred = np.array(predicted, dtype=np.int32)
    tgt = np.array(target, dtype=np.int32)
    if pred.shape != tgt.shape:
        return {"shape_mismatch": True, "pred_shape": list(pred.shape), "tgt_shape": list(tgt.shape)}
    diff = (pred != tgt).astype(int).tolist()
    changed = int(np.sum(pred != tgt))
    total = int(tgt.size)
    return {
        "diff": diff,
        "cells_changed": changed,
        "total_cells": total,
        "cell_accuracy": float((total - changed) / total) if total > 0 else 0.0,
    }


def _object_error_summary(predicted, target):
    pred_grid = Grid.from_list(predicted) if isinstance(predicted, list) else predicted
    tgt_grid = Grid.from_list(target) if isinstance(target, list) else target

    pred_objs = extract_objects(pred_grid)
    tgt_objs = extract_objects(tgt_grid)

    matches = match_objects(tgt_objs, pred_objs)
    matched_tgt_ids = {m[0].id for m in matches}
    matched_pred_ids = {m[1].id for m in matches}

    missing_objects = [
        {"id": o.id, "color": o.color, "size": o.size, "bbox": list(o.bounding_box)}
        for o in tgt_objs if o.id not in matched_tgt_ids
    ]
    extra_objects = [
        {"id": o.id, "color": o.color, "size": o.size, "bbox": list(o.bounding_box)}
        for o in pred_objs if o.id not in matched_pred_ids
    ]
    mismatched = []
    for tgt_obj, pred_obj, sim in matches:
        if tgt_obj.color != pred_obj.color or tgt_obj.shape_signature != pred_obj.shape_signature:
            mismatched.append({
                "tgt_id": tgt_obj.id, "pred_id": pred_obj.id,
                "similarity": float(sim),
                "color_match": tgt_obj.color == pred_obj.color,
                "shape_match": tgt_obj.shape_signature == pred_obj.shape_signature,
                "size_match": tgt_obj.size == pred_obj.size,
                "tgt_color": tgt_obj.color, "pred_color": pred_obj.color,
                "tgt_size": tgt_obj.size, "pred_size": pred_obj.size,
            })

    return {
        "target_object_count": len(tgt_objs),
        "predicted_object_count": len(pred_objs),
        "matched_count": len(matches),
        "missing_objects": missing_objects,
        "extra_objects": extra_objects,
        "mismatched_objects": mismatched,
    }


def _relation_error_summary(predicted, target):
    pred_grid = Grid.from_list(predicted) if isinstance(predicted, list) else predicted
    tgt_grid = Grid.from_list(target) if isinstance(target, list) else target

    pred_objs = extract_objects(pred_grid)
    tgt_objs = extract_objects(tgt_grid)

    pred_rels = build_relation_graph(pred_objs)
    tgt_rels = build_relation_graph(tgt_objs)

    pred_rel_set = {(r.source_id, r.target_id, r.relation_type) for r in pred_rels}
    tgt_rel_set = {(r.source_id, r.target_id, r.relation_type) for r in tgt_rels}

    pred_rel_types = {}
    tgt_rel_types = {}
    for r in pred_rels:
        pred_rel_types[r.relation_type] = pred_rel_types.get(r.relation_type, 0) + 1
    for r in tgt_rels:
        tgt_rel_types[r.relation_type] = tgt_rel_types.get(r.relation_type, 0) + 1

    return {
        "target_relation_count": len(tgt_rels),
        "predicted_relation_count": len(pred_rels),
        "target_relation_types": tgt_rel_types,
        "predicted_relation_types": pred_rel_types,
    }


def _cross_example_consistency(task, program):
    per_pair_results = []
    for i, pair in enumerate(task.train):
        try:
            input_grid = Grid.from_list(pair.input)
            result = program.apply(input_grid)
            predicted = _serialize_grid(result)
            acc = normalized_cell_accuracy(predicted, pair.output)
            is_exact = exact_match(predicted, pair.output)
        except Exception as e:
            acc = 0.0
            is_exact = False
            predicted = None

        per_pair_results.append({
            "pair_index": i,
            "cell_accuracy": float(acc),
            "exact_match": bool(is_exact),
        })

    accuracies = [r["cell_accuracy"] for r in per_pair_results]
    mean_acc = float(np.mean(accuracies)) if accuracies else 0.0
    std_acc = float(np.std(accuracies)) if accuracies else 0.0
    min_acc = float(min(accuracies)) if accuracies else 0.0
    max_acc = float(max(accuracies)) if accuracies else 0.0

    return {
        "per_pair_results": per_pair_results,
        "mean_accuracy": mean_acc,
        "std_accuracy": std_acc,
        "min_accuracy": min_acc,
        "max_accuracy": max_acc,
        "accuracy_spread": float(max_acc - min_acc),
        "all_exact": all(r["exact_match"] for r in per_pair_results),
        "program_template": repr(program),
        "operator_sequence": program.operator_names if hasattr(program, 'operator_names') else [],
        "consistency_score": 1.0 - std_acc if std_acc < 1.0 else 0.0,
    }


def _loocv_validation(task, max_search_iters=20):
    if len(task.train) < 3:
        return {"skipped": True, "reason": f"only {len(task.train)} train pairs, need >= 3"}

    results = []
    for held_out_idx in range(len(task.train)):
        from geocat_arc.data.arc_task import ARCTask, GridPair
        train_subset = [p for i, p in enumerate(task.train) if i != held_out_idx]
        held_out = task.train[held_out_idx]

        subset_task = ARCTask(
            task_id=f"{task.task_id}_loo_{held_out_idx}",
            train=train_subset,
            test=[held_out],
        )

        best_prog, best_score, trace = bayesian_search(subset_task, max_iterations=max_search_iters)

        try:
            input_grid = Grid.from_list(held_out.input)
            result = best_prog.apply(input_grid) if best_prog else None
            predicted = _serialize_grid(result) if result else [[0]]
            held_out_acc = normalized_cell_accuracy(predicted, held_out.output)
            held_out_exact = exact_match(predicted, held_out.output)
        except Exception:
            held_out_acc = 0.0
            held_out_exact = False

        results.append({
            "held_out_index": held_out_idx,
            "train_score": float(best_score),
            "held_out_cell_accuracy": float(held_out_acc),
            "held_out_exact_match": bool(held_out_exact),
            "program": repr(best_prog) if best_prog else "none",
        })

    held_out_accs = [r["held_out_cell_accuracy"] for r in results]
    train_scores = [r["train_score"] for r in results]

    return {
        "skipped": False,
        "folds": results,
        "mean_held_out_accuracy": float(np.mean(held_out_accs)),
        "mean_train_score": float(np.mean(train_scores)),
        "generalization_gap": float(np.mean(train_scores) - np.mean(held_out_accs)),
        "pairwise_fitting_risk": float(np.mean(train_scores) - np.mean(held_out_accs)) > 0.3,
    }


def _pairwise_fitting_risk(task, program, cross_consistency):
    spread = cross_consistency["accuracy_spread"]
    std = cross_consistency["std_accuracy"]
    mean = cross_consistency["mean_accuracy"]

    risk_factors = []
    if spread > 0.3:
        risk_factors.append(f"high accuracy spread across pairs: {spread:.3f}")
    if std > 0.15:
        risk_factors.append(f"high std across pairs: {std:.3f}")
    if mean > 0.5 and spread > 0.2:
        risk_factors.append("decent mean but inconsistent — may be fitting some pairs better")

    per_pair = cross_consistency["per_pair_results"]
    exact_count = sum(1 for r in per_pair if r["exact_match"])
    if 0 < exact_count < len(per_pair):
        risk_factors.append(f"only {exact_count}/{len(per_pair)} exact matches — possible per-pair fitting")

    return {
        "risk_level": "high" if len(risk_factors) >= 2 else "medium" if risk_factors else "low",
        "risk_factors": risk_factors,
        "accuracy_spread": float(spread),
        "accuracy_std": float(std),
        "exact_match_fraction": float(exact_count / len(per_pair)) if per_pair else 0.0,
    }


def _classify_failure(task, program, diffs, obj_summaries, rel_summaries, cross_consistency):
    total_cell_acc = np.mean([d.get("cell_accuracy", 0) for d in diffs if "cell_accuracy" in d])

    total_missing_objs = sum(len(s["missing_objects"]) for s in obj_summaries)
    total_extra_objs = sum(len(s["extra_objects"]) for s in obj_summaries)
    total_mismatched = sum(len(s["mismatched_objects"]) for s in obj_summaries)

    ops_used = set(program.operator_names) if program and hasattr(program, 'operator_names') else set()

    hypotheses = []

    if total_cell_acc < 0.3:
        hypotheses.append({
            "type": "missing_operator",
            "confidence": 0.8,
            "evidence": f"very low cell accuracy ({total_cell_acc:.3f}) — current operators cannot approximate the transformation",
        })
    elif total_cell_acc < 0.6:
        hypotheses.append({
            "type": "missing_operator",
            "confidence": 0.6,
            "evidence": f"moderate cell accuracy ({total_cell_acc:.3f}) — partial match suggests some operators work but key transformation missing",
        })

    if total_missing_objs > 0:
        hypotheses.append({
            "type": "wrong_object_binding",
            "confidence": 0.5,
            "evidence": f"{total_missing_objs} target objects not present in prediction",
        })

    if total_extra_objs > 0:
        hypotheses.append({
            "type": "perception_failure",
            "confidence": 0.4,
            "evidence": f"{total_extra_objs} extra objects in prediction not in target",
        })

    color_mismatches = sum(
        1 for s in obj_summaries for m in s["mismatched_objects"] if not m["color_match"]
    )
    if color_mismatches > 0:
        hypotheses.append({
            "type": "wrong_parameter",
            "confidence": 0.6,
            "evidence": f"{color_mismatches} objects have wrong color — possible missing conditional_recolor or wrong color binding",
        })

    shape_mismatches = sum(
        1 for s in obj_summaries for m in s["mismatched_objects"] if not m["shape_match"]
    )
    if shape_mismatches > 0:
        hypotheses.append({
            "type": "missing_operator",
            "confidence": 0.7,
            "evidence": f"{shape_mismatches} objects have wrong shape — may need spatial transformation operator",
        })

    if len(ops_used) <= 2 and total_cell_acc < 0.8:
        hypotheses.append({
            "type": "insufficient_search_depth",
            "confidence": 0.5,
            "evidence": f"only {len(ops_used)} unique operators used — deeper programs may help",
        })

    consistency = cross_consistency.get("consistency_score", 0)
    if consistency < 0.7:
        hypotheses.append({
            "type": "insufficient_cross_example_rule_induction",
            "confidence": 0.6,
            "evidence": f"cross-example consistency score {consistency:.3f} — program may not generalize",
        })

    if not hypotheses:
        hypotheses.append({
            "type": "insufficient_candidate_generation",
            "confidence": 0.5,
            "evidence": "no specific failure pattern detected — likely need more diverse candidates",
        })

    hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
    return hypotheses


def _analyze_task_transformation(task):
    analyses = []
    for i, pair in enumerate(task.train):
        in_grid = Grid.from_list(pair.input)
        out_grid = Grid.from_list(pair.output)
        in_objs = extract_objects(in_grid)
        out_objs = extract_objects(out_grid)
        changes = detect_changes(in_grid, out_grid)

        in_colors = in_grid.colors_used
        out_colors = out_grid.colors_used
        new_colors = out_colors - in_colors
        removed_colors = in_colors - out_colors

        analyses.append({
            "pair_index": i,
            "input_objects": len(in_objs),
            "output_objects": len(out_objs),
            "cells_changed": changes.num_cells_changed,
            "cell_accuracy_if_identity": float(changes.cell_accuracy),
            "objects_added": len(changes.objects_added),
            "objects_removed": len(changes.objects_removed),
            "objects_moved": len(changes.objects_moved),
            "objects_recolored": len(changes.objects_recolored),
            "new_colors": sorted(new_colors),
            "removed_colors": sorted(removed_colors),
            "same_shape": len(pair.input) == len(pair.output) and len(pair.input[0]) == len(pair.output[0]),
        })

    obj_counts_in = [a["input_objects"] for a in analyses]
    obj_counts_out = [a["output_objects"] for a in analyses]
    cells_changed = [a["cells_changed"] for a in analyses]

    shared_patterns = []
    if all(a["objects_recolored"] > 0 for a in analyses):
        shared_patterns.append("recoloring_present_in_all_pairs")
    if all(a["objects_moved"] > 0 for a in analyses):
        shared_patterns.append("movement_present_in_all_pairs")
    if all(a["objects_added"] > 0 for a in analyses):
        shared_patterns.append("objects_added_in_all_pairs")
    if all(a["objects_removed"] > 0 for a in analyses):
        shared_patterns.append("objects_removed_in_all_pairs")
    if all(a["cell_accuracy_if_identity"] > 0.8 for a in analyses):
        shared_patterns.append("mostly_identity_small_changes")
    if len(set(a["input_objects"] for a in analyses)) == 1:
        shared_patterns.append("consistent_input_object_count")
    if len(set(a["output_objects"] for a in analyses)) == 1:
        shared_patterns.append("consistent_output_object_count")

    return {
        "per_pair_analysis": analyses,
        "shared_patterns": shared_patterns,
        "mean_cells_changed": float(np.mean(cells_changed)),
        "mean_identity_accuracy": float(np.mean([a["cell_accuracy_if_identity"] for a in analyses])),
    }


def run_diagnostic(task_id: str, max_search_iters: int = 20, max_loocv_iters: int = 15):
    task = load_task(task_id)
    out_dir = ARTIFACTS_DIR / task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{task_id}] Running search ({max_search_iters} iters)...")
    best_prog, best_score, trace = bayesian_search(task, max_iterations=max_search_iters)

    with open(out_dir / "best_program.txt", "w") as f:
        f.write(f"Program: {repr(best_prog)}\n")
        f.write(f"Score: {float(best_score)}\n")
        f.write(f"Operators: {best_prog.operator_names if best_prog else 'none'}\n")
        f.write(f"Depth: {best_prog.depth if best_prog else 0}\n")
        f.write(f"Cost: {best_prog.total_cost if best_prog else 0}\n")
        if best_prog:
            f.write(f"\nProgram dict:\n{json.dumps(best_prog.to_dict(), indent=2)}\n")

    predicted_outputs = []
    target_outputs = []
    diffs = []
    obj_summaries = []
    rel_summaries = []

    for i, pair in enumerate(task.train):
        try:
            input_grid = Grid.from_list(pair.input)
            result = best_prog.apply(input_grid) if best_prog else input_grid
            predicted = _serialize_grid(result)
        except Exception as e:
            predicted = pair.input

        predicted_outputs.append(predicted)
        target_outputs.append(pair.output)
        diffs.append(_diff_map(predicted, pair.output))
        obj_summaries.append(_object_error_summary(predicted, pair.output))
        rel_summaries.append(_relation_error_summary(predicted, pair.output))

    with open(out_dir / "predicted_outputs.json", "w") as f:
        json.dump(predicted_outputs, f)
    with open(out_dir / "target_outputs.json", "w") as f:
        json.dump(target_outputs, f)
    with open(out_dir / "diff_maps.json", "w") as f:
        json.dump(diffs, f, indent=2)
    with open(out_dir / "object_error_summary.json", "w") as f:
        json.dump(obj_summaries, f, indent=2)
    with open(out_dir / "relation_error_summary.json", "w") as f:
        json.dump(rel_summaries, f, indent=2)

    print(f"[{task_id}] Cross-example consistency...")
    cross_consistency = _cross_example_consistency(task, best_prog) if best_prog else {}
    with open(out_dir / "cross_example_consistency.json", "w") as f:
        json.dump(cross_consistency, f, indent=2)

    print(f"[{task_id}] Pairwise fitting risk...")
    pairwise_risk = _pairwise_fitting_risk(task, best_prog, cross_consistency) if cross_consistency else {}
    with open(out_dir / "pairwise_fitting_risk.json", "w") as f:
        json.dump(pairwise_risk, f, indent=2)

    print(f"[{task_id}] LOO-CV validation...")
    loocv = _loocv_validation(task, max_search_iters=max_loocv_iters)
    with open(out_dir / "loocv_rule_validation.json", "w") as f:
        json.dump(loocv, f, indent=2)

    print(f"[{task_id}] Analyzing transformation patterns...")
    transformation_analysis = _analyze_task_transformation(task)

    failure_hypotheses = _classify_failure(
        task, best_prog, diffs, obj_summaries, rel_summaries, cross_consistency
    )

    with open(out_dir / "missing_operator_hypothesis.md", "w") as f:
        f.write(f"# Missing Operator Hypothesis: {task_id}\n\n")
        f.write(f"## Best Program\n\n")
        f.write(f"- Program: `{repr(best_prog)}`\n")
        f.write(f"- Score: {float(best_score):.4f}\n")
        f.write(f"- Operators: {best_prog.operator_names if best_prog else 'none'}\n\n")

        f.write(f"## Score Breakdown\n\n")
        for i, d in enumerate(diffs):
            acc = d.get("cell_accuracy", 0)
            changed = d.get("cells_changed", "?")
            total = d.get("total_cells", "?")
            f.write(f"- Pair {i}: cell_accuracy={acc:.4f}, cells_changed={changed}/{total}\n")

        f.write(f"\n## Object-Level Errors\n\n")
        for i, s in enumerate(obj_summaries):
            f.write(f"- Pair {i}: target_objs={s['target_object_count']}, pred_objs={s['predicted_object_count']}, ")
            f.write(f"missing={len(s['missing_objects'])}, extra={len(s['extra_objects'])}, ")
            f.write(f"mismatched={len(s['mismatched_objects'])}\n")

        f.write(f"\n## Cross-Example Consistency\n\n")
        if cross_consistency:
            f.write(f"- Mean accuracy: {cross_consistency.get('mean_accuracy', 0):.4f}\n")
            f.write(f"- Std: {cross_consistency.get('std_accuracy', 0):.4f}\n")
            f.write(f"- Spread: {cross_consistency.get('accuracy_spread', 0):.4f}\n")
            f.write(f"- Consistency score: {cross_consistency.get('consistency_score', 0):.4f}\n")

        f.write(f"\n## Pairwise Fitting Risk\n\n")
        if pairwise_risk:
            f.write(f"- Risk level: {pairwise_risk.get('risk_level', 'unknown')}\n")
            for rf in pairwise_risk.get("risk_factors", []):
                f.write(f"- {rf}\n")

        f.write(f"\n## LOO-CV Validation\n\n")
        if loocv.get("skipped"):
            f.write(f"- Skipped: {loocv['reason']}\n")
        else:
            f.write(f"- Mean held-out accuracy: {loocv.get('mean_held_out_accuracy', 0):.4f}\n")
            f.write(f"- Mean train score: {loocv.get('mean_train_score', 0):.4f}\n")
            f.write(f"- Generalization gap: {loocv.get('generalization_gap', 0):.4f}\n")
            f.write(f"- Pairwise fitting risk: {loocv.get('pairwise_fitting_risk', False)}\n")

        f.write(f"\n## Failure Hypotheses (ranked by confidence)\n\n")
        for h in failure_hypotheses:
            f.write(f"### {h['type']} (confidence: {h['confidence']:.2f})\n\n")
            f.write(f"{h['evidence']}\n\n")

        f.write(f"\n## Transformation Analysis\n\n")
        for p in transformation_analysis.get("shared_patterns", []):
            f.write(f"- {p}\n")
        f.write(f"\n### Per-Pair Details\n\n")
        for a in transformation_analysis.get("per_pair_analysis", []):
            f.write(f"- Pair {a['pair_index']}: in_objs={a['input_objects']}, out_objs={a['output_objects']}, ")
            f.write(f"changed={a['cells_changed']}, moved={a['objects_moved']}, recolored={a['objects_recolored']}, ")
            f.write(f"added={a['objects_added']}, removed={a['objects_removed']}, ")
            f.write(f"new_colors={a['new_colors']}, identity_acc={a['cell_accuracy_if_identity']:.3f}\n")

    with open(out_dir / "shared_rule_hypothesis.md", "w") as f:
        f.write(f"# Shared Rule Hypothesis: {task_id}\n\n")
        f.write(f"## Transformation Patterns Shared Across All Train Pairs\n\n")
        patterns = transformation_analysis.get("shared_patterns", [])
        if patterns:
            for p in patterns:
                f.write(f"- {p}\n")
        else:
            f.write("- No consistent shared patterns detected\n")
        f.write(f"\n## Identity Accuracy (how much changes)\n\n")
        f.write(f"- Mean: {transformation_analysis['mean_identity_accuracy']:.3f}\n")
        f.write(f"- Mean cells changed: {transformation_analysis['mean_cells_changed']:.1f}\n")
        f.write(f"\n## Per-Pair Object Flow\n\n")
        for a in transformation_analysis["per_pair_analysis"]:
            f.write(f"### Pair {a['pair_index']}\n\n")
            f.write(f"- Input: {a['input_objects']} objects\n")
            f.write(f"- Output: {a['output_objects']} objects\n")
            f.write(f"- Objects added: {a['objects_added']}\n")
            f.write(f"- Objects removed: {a['objects_removed']}\n")
            f.write(f"- Objects moved: {a['objects_moved']}\n")
            f.write(f"- Objects recolored: {a['objects_recolored']}\n")
            f.write(f"- New colors introduced: {a['new_colors']}\n")
            f.write(f"- Colors removed: {a['removed_colors']}\n\n")

    print(f"[{task_id}] Done. Artifacts in {out_dir}/")
    return {
        "task_id": task_id,
        "best_score": float(best_score),
        "failure_hypotheses": failure_hypotheses,
        "cross_consistency": cross_consistency,
        "loocv": loocv,
        "pairwise_risk": pairwise_risk,
    }


if __name__ == "__main__":
    results = []
    for tid in TARGET_TASKS:
        result = run_diagnostic(tid, max_search_iters=20, max_loocv_iters=15)
        results.append(result)

    summary_dir = ARTIFACTS_DIR.parent
    with open(summary_dir / "diagnostic_summary.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n=== DIAGNOSTIC SUMMARY ===")
    for r in results:
        top_hyp = r["failure_hypotheses"][0] if r["failure_hypotheses"] else {"type": "unknown", "confidence": 0}
        print(f"{r['task_id']}: score={r['best_score']:.4f}, "
              f"top_failure={top_hyp['type']} ({top_hyp['confidence']:.2f}), "
              f"consistency={r.get('cross_consistency', {}).get('consistency_score', 0):.3f}")
