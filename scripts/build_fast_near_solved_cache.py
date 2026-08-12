"""Fast Phase 1 cache builder: staged filtering to avoid running full adaptive loop on every task.

Pipeline:
    1. Run static StructuralReasoner on all tasks (~1-3s/task)
    2. Mark solved tasks
    3. For unsolved: compute lightweight object/property/relation traces
    4. Classify failure type and operator-gap evidence
    5. Run adaptive loop ONLY on high-value candidates (optional)

Outputs:
    outputs/cache_fast/solved_tasks.json
    outputs/cache_fast/unsolved_tasks.json
    outputs/cache_fast/near_solved_states.jsonl
    outputs/cache_fast/object_traces.jsonl
    outputs/cache_fast/operator_gap_traces.jsonl
    outputs/cache_fast/failure_clusters.json
    outputs/cache_fast/cache_summary.md
    outputs/cache_fast/status.json

Usage:
    python3.11 scripts/build_fast_near_solved_cache.py \\
        --max-tasks 1000 --static-first --adaptive-on-candidates-only \\
        --timeout 10 --output-dir outputs/cache_fast
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _all_property_names,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
    _find_discriminative_property,
)
from reasoning_project.manifold_memory import (
    ManifoldPoint,
    MemoryManifold,
    _signature_to_embedding,
    encode_task_signature,
)
from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedTaskState,
    NearSolvedStatus,
    RepairAction,
    save_near_solved_cache,
)


def load_arc_tasks(arc_root: str) -> List[Dict]:
    tasks = []
    challenges_path = os.path.join(arc_root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(arc_root, "arc-agi_training_solutions.json")
    if not os.path.isfile(challenges_path):
        print(f"[ERROR] No challenges at {challenges_path}")
        return tasks
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions = {}
    if os.path.isfile(solutions_path):
        with open(solutions_path) as f:
            solutions = json.load(f)
    for task_id in sorted(challenges.keys()):
        data = challenges[task_id]
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["train"]
        ]
        test_inputs = [np.array(ex["input"]) for ex in data["test"]]
        test_outputs = []
        if task_id in solutions:
            test_outputs = [np.array(o) for o in solutions[task_id]]
        elif data["test"] and "output" in data["test"][0]:
            test_outputs = [np.array(ex["output"]) for ex in data["test"]]
        tasks.append({
            "task_id": task_id,
            "train_pairs": train_pairs,
            "test_inputs": test_inputs,
            "test_outputs": test_outputs,
        })
    return tasks


def compute_object_trace(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    """Lightweight object/property/relation trace without running the full reasoner."""
    trace: Dict[str, Any] = {
        "n_pairs": len(train_pairs),
        "same_size": all(i.shape == o.shape for i, o in train_pairs),
        "size_changes": [],
        "object_counts_in": [],
        "object_counts_out": [],
        "has_classification": [],
        "discriminative_property": None,
        "disc_keep_when_true": None,
        "disc_score": 0.0,
        "reconstruction_match": False,
        "reconstruction_similarity": 0.0,
        "all_objects_all_pairs": [],
    }

    for inp, out in train_pairs:
        trace["size_changes"].append(inp.shape != out.shape)
        objects_in = _extract_objects_with_properties(inp)
        trace["object_counts_in"].append(len(objects_in))
        out_objects = _extract_objects_with_properties(out)
        trace["object_counts_out"].append(len(out_objects))

        kr = _classify_kept_removed(objects_in, inp, out)
        trace["has_classification"].append(kr is not None)

    if trace["same_size"] and all(trace["has_classification"]):
        disc = _find_discriminative_property(train_pairs)
        if disc is not None:
            prop_name, keep_when_true = disc
            trace["discriminative_property"] = prop_name
            trace["disc_keep_when_true"] = keep_when_true
            trace["disc_score"] = 1.0

            match_count = 0
            total_sim = 0.0
            for inp, out in train_pairs:
                objects = _extract_objects_with_properties(inp)
                keep_mask = []
                for obj in objects:
                    val = obj.get(prop_name, False)
                    if isinstance(val, (int, float)):
                        val = bool(val)
                    keep_mask.append(val == keep_when_true)
                pred = np.zeros_like(inp)
                for obj, keep in zip(objects, keep_mask):
                    if keep:
                        pred[obj["mask"]] = inp[obj["mask"]]
                if np.array_equal(pred, out):
                    match_count += 1
                n_total = max(out.size, 1)
                sim = float(np.sum(pred == out)) / n_total
                total_sim += sim

            trace["reconstruction_match"] = match_count == len(train_pairs)
            trace["reconstruction_similarity"] = total_sim / max(len(train_pairs), 1)

    return trace


def classify_failure(trace: Dict[str, Any]) -> str:
    """Classify the failure type from an object trace."""
    if not trace["same_size"]:
        return "size_change"
    if not any(trace["has_classification"]):
        return "no_classification"
    if not all(trace["has_classification"]):
        return "partial_classification"
    if trace["discriminative_property"] is None:
        return "no_discrimination"
    if trace["reconstruction_match"]:
        return "solved_by_filter"
    return "property_found_reconstruction_fails"


def classify_operator_gap(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    trace: Dict[str, Any],
) -> Dict[str, Any]:
    """For tasks where property discriminates but reconstruction fails,
    classify what operator is missing."""
    gap: Dict[str, Any] = {
        "has_gap": False,
        "operator_family": "unknown",
        "evidence": {},
    }

    prop_name = trace.get("discriminative_property")
    keep_when_true = trace.get("disc_keep_when_true")
    if prop_name is None:
        return gap

    gap["has_gap"] = True

    displacement_vectors = []
    color_changes = []
    fill_patterns = []
    kept_objects_present_in_output = 0
    removed_objects_present_in_output = 0
    total_removed = 0

    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        kr = _classify_kept_removed(objects, inp, out)
        if kr is None:
            gap["has_gap"] = False
            return gap
        kept_idx, removed_idx = kr
        total_removed += len(removed_idx)

        for ri in removed_idx:
            obj = objects[ri]
            out_region = out[obj["mask"]]
            if np.any(out_region != 0):
                removed_objects_present_in_output += 1

                in_colors = set(inp[obj["mask"]].tolist()) - {0}
                out_colors = set(out_region.tolist()) - {0}
                if in_colors != out_colors:
                    color_changes.append({
                        "from": sorted(in_colors),
                        "to": sorted(out_colors),
                    })

        for ki in kept_idx:
            obj = objects[ki]
            out_region = out[obj["mask"]]
            if np.array_equal(inp[obj["mask"]], out_region):
                kept_objects_present_in_output += 1

        out_objects = _extract_objects_with_properties(out)
        if len(out_objects) != len(objects):
            for out_obj in out_objects:
                matched = False
                for in_obj in objects:
                    if (abs(out_obj["center_r"] - in_obj["center_r"]) < 1 and
                            abs(out_obj["center_c"] - in_obj["center_c"]) < 1):
                        matched = True
                        break
                if not matched:
                    for in_obj in [objects[ri] for ri in removed_idx]:
                        dr = out_obj["center_r"] - in_obj["center_r"]
                        dc = out_obj["center_c"] - in_obj["center_c"]
                        if abs(dr) > 0.5 or abs(dc) > 0.5:
                            displacement_vectors.append((dr, dc))

    if total_removed == 0:
        gap["has_gap"] = False
        return gap

    removed_present_ratio = removed_objects_present_in_output / max(total_removed, 1)
    gap["evidence"] = {
        "removed_present_in_output_ratio": removed_present_ratio,
        "displacement_vectors": displacement_vectors[:10],
        "color_changes": color_changes[:10],
        "n_kept": kept_objects_present_in_output,
        "n_removed_total": total_removed,
        "n_removed_present": removed_objects_present_in_output,
    }

    if displacement_vectors:
        gap["operator_family"] = "copy_to_position"
    elif removed_present_ratio > 0.5 and color_changes:
        gap["operator_family"] = "object_match_transfer_color"
    elif removed_present_ratio > 0.5:
        gap["operator_family"] = "region_fill_from_boundary"
    else:
        gap["operator_family"] = "unknown"

    return gap


def build_near_solved_state_fast(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    trace: Dict[str, Any],
    failure_type: str,
    operator_gap: Dict[str, Any],
) -> NearSolvedTaskState:
    """Build a NearSolvedTaskState from fast trace data (no adaptive loop)."""
    sig = encode_task_signature(train_pairs)
    emb = _signature_to_embedding(sig)
    point = ManifoldPoint(embedding=emb, task_signature=sig, domain="grid")

    hypothesis = None
    train_fit = 0.0
    if trace["discriminative_property"]:
        hypothesis = {
            "strategy": "discriminative_filter",
            "property": trace["discriminative_property"],
            "keep_when_true": trace["disc_keep_when_true"],
        }
        train_fit = trace["reconstruction_similarity"]

    repairs = _propose_repairs_from_trace(failure_type, trace, operator_gap)
    missing_cap = _guess_capability(failure_type, operator_gap)

    topo_sig = {
        "n_objects": max(trace["object_counts_in"]) if trace["object_counts_in"] else 0,
        "same_size": trace["same_size"],
        "has_classification": all(trace["has_classification"]),
        "has_discrimination": trace["discriminative_property"] is not None,
        "operator_gap_family": operator_gap.get("operator_family", "unknown"),
    }

    return NearSolvedTaskState(
        task_id=task_id,
        manifold_point=point,
        active_chart="static_fast",
        best_hypothesis=hypothesis,
        hypothesis_score=train_fit,
        train_fit=train_fit,
        train_fit_detail=[],
        loo_passed=False,
        failure_type=failure_type,
        failed_examples=[],
        error_signature={
            "failure_type": failure_type,
            "operator_gap": operator_gap.get("operator_family", "none"),
            "reconstruction_similarity": trace["reconstruction_similarity"],
        },
        retrieved_success_anchors=[],
        retrieved_failure_anchors=[],
        proposed_repairs=repairs,
        missing_capability_guess=missing_cap,
        views_tried=["color_cc"],
        iterations_used=1,
        suspected_next_chart=None,
        topology_signature=topo_sig,
    )


def _propose_repairs_from_trace(
    failure_type: str, trace: Dict, operator_gap: Dict,
) -> List[RepairAction]:
    repairs = []
    if failure_type == "property_found_reconstruction_fails":
        family = operator_gap.get("operator_family", "unknown")
        repairs.append(RepairAction(
            action_type="invent_operator",
            description=f"Invent {family} operator from failure trace",
            priority=0.95,
        ))
        repairs.append(RepairAction(
            action_type="try_alternative_reconstruction",
            description="Try fill_removed_constant / marker_projection / nearest_kept_color",
            priority=0.8,
        ))
    elif failure_type == "no_discrimination":
        repairs.append(RepairAction(
            action_type="add_conjunction",
            description="Try compound predicate (p1 ∧ p2) search",
            priority=0.9,
        ))
        repairs.append(RepairAction(
            action_type="add_spatial_property",
            description="Add spatial-rank or positional predicates",
            priority=0.7,
        ))
    elif failure_type == "no_classification":
        repairs.append(RepairAction(
            action_type="change_decomposition",
            description="Try per-color or monochrome object extraction",
            priority=0.9,
        ))
    elif failure_type == "size_change":
        repairs.append(RepairAction(
            action_type="try_crop_extract",
            description="Task changes grid size: try crop/extract/separator",
            priority=0.9,
        ))
    if not repairs:
        repairs.append(RepairAction(
            action_type="synthesize_adapter",
            description="Use AdapterGenesis for novel approach",
            priority=0.3,
        ))
    return repairs


def _guess_capability(failure_type: str, operator_gap: Dict) -> str:
    if failure_type == "property_found_reconstruction_fails":
        return f"operator:{operator_gap.get('operator_family', 'unknown')}"
    if failure_type == "no_discrimination":
        return "richer_property_language"
    if failure_type == "no_classification":
        return "object_decomposition"
    if failure_type == "size_change":
        return "size_transform"
    if failure_type == "partial_classification":
        return "mixed_classification"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(
        description="Fast Phase 1 cache builder with staged filtering")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/cache_fast")
    parser.add_argument("--max-tasks", type=int, default=0,
                        help="Max tasks (0 = all)")
    parser.add_argument("--static-first", action="store_true",
                        help="Run static reasoner first (fast pass)")
    parser.add_argument("--adaptive-on-candidates-only", action="store_true",
                        help="Only run adaptive loop on high-value candidates")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="Per-task timeout for adaptive loop (seconds)")
    parser.add_argument("--adaptive-max", type=int, default=50,
                        help="Max tasks to run adaptive loop on")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("=" * 60)
    print("FAST NEAR-SOLVED CACHE BUILDER")
    print("=" * 60)

    status = {
        "status": "running",
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "args": vars(args),
    }
    with open(out_dir / "status.json", "w") as f:
        json.dump(status, f, indent=2)

    # Load tasks
    tasks = load_arc_tasks(args.arc_root)
    if args.max_tasks > 0:
        tasks = tasks[:args.max_tasks]
    print(f"Loaded {len(tasks)} ARC tasks\n", flush=True)

    # Stage 1: Static reasoner pass
    print("=== Stage 1: Static StructuralReasoner pass ===", flush=True)
    solved_ids = []
    unsolved_tasks = []
    memory = ReasoningMemory()
    adapter = GridDomainAdapter()
    stage1_t0 = time.time()

    for i, task in enumerate(tasks):
        tid = task["task_id"]
        tp = task["train_pairs"]
        ti = task["test_inputs"]
        to = task["test_outputs"]

        if len(tp) < 2:
            unsolved_tasks.append(task)
            continue

        reasoner = StructuralReasoner(adapter, memory=memory, min_train=2)
        result = reasoner.solve(tp, ti)

        if result is not None and to:
            preds, meta = result
            correct = all(np.array_equal(p, t) for p, t in zip(preds, to))
            if correct:
                solved_ids.append(tid)
                continue

        unsolved_tasks.append(task)

        if (i + 1) % 100 == 0:
            elapsed = time.time() - stage1_t0
            print(f"  {i+1}/{len(tasks)} | solved={len(solved_ids)} "
                  f"unsolved={len(unsolved_tasks)} | {elapsed:.0f}s", flush=True)

    stage1_elapsed = time.time() - stage1_t0
    print(f"\nStage 1 complete: {len(solved_ids)} solved, "
          f"{len(unsolved_tasks)} unsolved in {stage1_elapsed:.0f}s "
          f"({stage1_elapsed/max(len(tasks),1):.1f}s/task)\n", flush=True)

    # Stage 2: Object/property traces for unsolved tasks
    print("=== Stage 2: Compute object/property/failure traces ===", flush=True)
    object_traces = []
    operator_gap_traces = []
    near_solved_states = []
    failure_type_counts: Dict[str, int] = Counter()
    operator_family_counts: Dict[str, int] = Counter()
    stage2_t0 = time.time()

    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)

    for i, task in enumerate(unsolved_tasks):
        tid = task["task_id"]
        tp = task["train_pairs"]

        trace = compute_object_trace(tp)
        trace["task_id"] = tid
        failure_type = classify_failure(trace)
        failure_type_counts[failure_type] += 1

        operator_gap: Dict[str, Any] = {"has_gap": False, "operator_family": "unknown"}
        if failure_type == "property_found_reconstruction_fails":
            operator_gap = classify_operator_gap(tp, trace)
            if operator_gap["has_gap"]:
                operator_family_counts[operator_gap["operator_family"]] += 1
                gap_record = {
                    "task_id": tid,
                    "best_property": trace["discriminative_property"],
                    "property_discrimination_score": trace["disc_score"],
                    "reconstruction_similarity": trace["reconstruction_similarity"],
                    "operator_family": operator_gap["operator_family"],
                    "evidence": operator_gap["evidence"],
                    "failure_type": failure_type,
                }
                operator_gap_traces.append(gap_record)

        trace_record = {
            "task_id": tid,
            "same_size": trace["same_size"],
            "n_pairs": trace["n_pairs"],
            "object_counts_in": trace["object_counts_in"],
            "object_counts_out": trace["object_counts_out"],
            "has_classification": trace["has_classification"],
            "discriminative_property": trace["discriminative_property"],
            "disc_score": trace["disc_score"],
            "reconstruction_similarity": trace["reconstruction_similarity"],
            "failure_type": failure_type,
            "operator_gap_family": operator_gap.get("operator_family", "none"),
        }
        object_traces.append(trace_record)

        state = build_near_solved_state_fast(
            tid, tp, trace, failure_type, operator_gap,
        )
        ns_mem.store_partial(state)
        near_solved_states.append(state)

        if (i + 1) % 100 == 0:
            elapsed = time.time() - stage2_t0
            print(f"  {i+1}/{len(unsolved_tasks)} traced | {elapsed:.0f}s", flush=True)

    stage2_elapsed = time.time() - stage2_t0
    print(f"\nStage 2 complete: {len(unsolved_tasks)} tasks traced in "
          f"{stage2_elapsed:.0f}s ({stage2_elapsed/max(len(unsolved_tasks),1):.1f}s/task)\n",
          flush=True)

    # Stage 3 (optional): Run adaptive loop on high-value candidates
    adaptive_count = 0
    if args.adaptive_on_candidates_only:
        candidates = [
            t for t, tr in zip(unsolved_tasks, object_traces)
            if tr["failure_type"] in (
                "property_found_reconstruction_fails",
                "no_discrimination",
            )
        ]
        candidates = candidates[:args.adaptive_max]
        if candidates:
            print(f"=== Stage 3: Adaptive loop on {len(candidates)} candidates ===",
                  flush=True)
            stage3_t0 = time.time()
            from reasoning_project.adaptive_loop import AdaptiveReasoningLoop

            for i, task in enumerate(candidates):
                tid = task["task_id"]
                tp = task["train_pairs"]
                ti = task["test_inputs"]
                to = task["test_outputs"]

                loop = AdaptiveReasoningLoop(
                    max_iterations=3,
                    timeout_seconds=args.timeout,
                    memory=memory,
                    manifold=manifold,
                    near_solved_memory=ns_mem,
                )
                loop_result = loop.solve(tp, ti, task_id=tid)
                adaptive_count += 1

                if hasattr(loop_result, "predictions") and loop_result.predictions and to:
                    correct = all(
                        np.array_equal(p, t)
                        for p, t in zip(loop_result.predictions, to)
                    )
                    if correct and tid not in solved_ids:
                        solved_ids.append(tid)

                if (i + 1) % 20 == 0:
                    elapsed = time.time() - stage3_t0
                    print(f"  {i+1}/{len(candidates)} adaptive | {elapsed:.0f}s",
                          flush=True)

            stage3_elapsed = time.time() - stage3_t0
            print(f"\nStage 3 complete: {len(candidates)} tasks in {stage3_elapsed:.0f}s\n",
                  flush=True)

    # Build failure clusters
    failure_clusters: Dict[str, List[str]] = defaultdict(list)
    for tr in object_traces:
        failure_clusters[tr["failure_type"]].append(tr["task_id"])

    operator_gap_clusters: Dict[str, List[str]] = defaultdict(list)
    for gap in operator_gap_traces:
        operator_gap_clusters[gap["operator_family"]].append(gap["task_id"])

    # Write outputs
    print("=== Writing outputs ===", flush=True)

    with open(out_dir / "solved_tasks.json", "w") as f:
        json.dump({"solved": sorted(solved_ids)}, f, indent=2)

    unsolved_ids = [t["task_id"] for t in unsolved_tasks if t["task_id"] not in solved_ids]
    with open(out_dir / "unsolved_tasks.json", "w") as f:
        json.dump({"unsolved": sorted(unsolved_ids)}, f, indent=2)

    with open(out_dir / "near_solved_states.jsonl", "w") as f:
        from reasoning_project.near_solved_memory import _state_to_json
        for state in near_solved_states:
            f.write(json.dumps(_state_to_json(state)) + "\n")

    with open(out_dir / "object_traces.jsonl", "w") as f:
        for tr in object_traces:
            f.write(json.dumps(tr) + "\n")

    with open(out_dir / "operator_gap_traces.jsonl", "w") as f:
        for gap in operator_gap_traces:
            gap_safe = dict(gap)
            ev = gap_safe.get("evidence", {})
            if "displacement_vectors" in ev:
                ev["displacement_vectors"] = [
                    [float(x) for x in v] for v in ev["displacement_vectors"]
                ]
            f.write(json.dumps(gap_safe) + "\n")

    clusters_out = {
        "failure_clusters": {k: sorted(v) for k, v in failure_clusters.items()},
        "operator_gap_clusters": {k: sorted(v) for k, v in operator_gap_clusters.items()},
        "failure_type_counts": dict(failure_type_counts),
        "operator_family_counts": dict(operator_family_counts),
    }
    with open(out_dir / "failure_clusters.json", "w") as f:
        json.dump(clusters_out, f, indent=2)

    total_elapsed = time.time() - t0
    status = {
        "status": "complete",
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_tasks": len(tasks),
        "solved_static": len(solved_ids) - adaptive_count,
        "solved_adaptive": adaptive_count,
        "solved_total": len(solved_ids),
        "unsolved": len(unsolved_ids),
        "near_solved_states": len(near_solved_states),
        "operator_gap_traces": len(operator_gap_traces),
        "adaptive_tasks_run": adaptive_count,
        "failure_type_counts": dict(failure_type_counts),
        "operator_family_counts": dict(operator_family_counts),
        "stage1_seconds": stage1_elapsed,
        "stage2_seconds": stage2_elapsed,
        "total_seconds": total_elapsed,
    }
    with open(out_dir / "status.json", "w") as f:
        json.dump(status, f, indent=2)
    with open(out_dir / "phase1_status.json", "w") as f:
        json.dump(status, f, indent=2)

    # Write summary
    lines = [
        "# Fast Near-Solved Cache Summary\n",
        f"- Total tasks: {len(tasks)}",
        f"- Solved (static): {len(solved_ids)}",
        f"- Unsolved: {len(unsolved_ids)}",
        f"- Near-solved states: {len(near_solved_states)}",
        f"- Operator gap traces: {len(operator_gap_traces)}",
        f"- Adaptive loop ran on: {adaptive_count} tasks",
        f"- Total time: {total_elapsed:.0f}s ({total_elapsed/max(len(tasks),1):.1f}s/task)",
        "",
        "## Failure Type Distribution\n",
    ]
    for ftype, count in sorted(failure_type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {ftype}: {count}")
    lines.append("")
    lines.append("## Operator Gap Families\n")
    for family, count in sorted(operator_family_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {family}: {count}")
    lines.append("")
    lines.append(f"## Timing\n")
    lines.append(f"- Stage 1 (static solve): {stage1_elapsed:.0f}s "
                 f"({stage1_elapsed/max(len(tasks),1):.1f}s/task)")
    lines.append(f"- Stage 2 (trace computation): {stage2_elapsed:.0f}s "
                 f"({stage2_elapsed/max(len(unsolved_tasks),1):.1f}s/task)")
    lines.append(f"- Total: {total_elapsed:.0f}s")

    with open(out_dir / "cache_summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nDone in {total_elapsed:.0f}s")
    print(f"  Solved: {len(solved_ids)}, Unsolved: {len(unsolved_ids)}")
    print(f"  Near-solved states: {len(near_solved_states)}")
    print(f"  Operator gap traces: {len(operator_gap_traces)}")
    print(f"  Failure types: {dict(failure_type_counts)}")
    print(f"  Operator families: {dict(operator_family_counts)}")
    print(f"\nOutputs: {out_dir}")


if __name__ == "__main__":
    main()
