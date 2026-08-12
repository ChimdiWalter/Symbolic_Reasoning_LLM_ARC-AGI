"""Trace the 12 property-sufficient tasks through the ACTUAL solver pipeline.

For each task, trace every stage and report exactly where/why it fails:
  1. Object extraction
  2. Kept/removed classification
  3. Property discrimination (gap-analysis style vs solver-style)
  4. Evidence threshold
  5. LOO validation
  6. Reconstruction
  7. Prediction emission
  8. Full AdaptiveReasoningLoop result
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    BOOLEAN_PROPERTIES,
    DERIVED_PREDICATES,
    GridDomainAdapter,
    StructuralReasoner,
    ReasoningMemory,
    _all_property_names,
    _classify_kept_removed,
    _extract_objects_with_properties,
    _get_property_value,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop

PROPERTY_SUFFICIENT_12 = [
    "03560426", "05f2a901", "0e206a2e", "184a9768",
    "1a07d186", "1caeab9d", "2c737e39", "305b1341",
    "56dc2b01", "6855a6e4", "6a1e5592", "73c3b0d8",
]


def load_arc_tasks(root: str):
    tasks = {}
    challenges_path = os.path.join(root, "arc-agi_training_challenges.json")
    solutions_path = os.path.join(root, "arc-agi_training_solutions.json")
    with open(challenges_path) as f:
        challenges = json.load(f)
    solutions = {}
    if os.path.isfile(solutions_path):
        with open(solutions_path) as f:
            solutions = json.load(f)
    for task_id in challenges:
        data = challenges[task_id]
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in data["train"]
        ]
        test_outputs = []
        if task_id in solutions:
            test_outputs = [np.array(o) for o in solutions[task_id]]
        elif data["test"] and "output" in data["test"][0]:
            test_outputs = [np.array(ex["output"]) for ex in data["test"]]
        test_inputs = [np.array(ex["input"]) for ex in data["test"]]
        tasks[task_id] = {
            "task_id": task_id,
            "train_pairs": train_pairs,
            "test_inputs": test_inputs,
            "test_outputs": test_outputs,
        }
    return tasks


def trace_single_task(task_data, adapter):
    """Trace a single task through every pipeline stage. Returns a dict."""
    tid = task_data["task_id"]
    train_pairs = task_data["train_pairs"]
    test_inputs = task_data["test_inputs"]
    test_outputs = task_data["test_outputs"]
    all_props = _all_property_names()

    trace = {
        "task_id": tid,
        "n_train": len(train_pairs),
        "failure_class": "unknown",
    }

    # ── Stage 1: Object extraction ──
    per_pair_info = []
    for i, (inp, out) in enumerate(train_pairs):
        objects = adapter.extract_objects(inp)
        cls = _classify_kept_removed(objects, inp, out)
        same_shape = inp.shape == out.shape
        info = {
            "pair_idx": i,
            "inp_shape": list(inp.shape),
            "out_shape": list(out.shape),
            "same_shape": same_shape,
            "n_objects": len(objects),
            "classify_result": "ok" if cls is not None else "None",
            "kept_count": len(cls[0]) if cls else 0,
            "removed_count": len(cls[1]) if cls else 0,
            "object_details": [],
        }
        for j, obj in enumerate(objects):
            info["object_details"].append({
                "idx": j,
                "color": obj["primary_color"],
                "area": obj["area"],
                "bbox": list(obj["bbox"]),
                "is_kept": j in cls[0] if cls else None,
            })
        per_pair_info.append(info)
    trace["per_pair"] = per_pair_info

    n_objects_per_pair = [p["n_objects"] for p in per_pair_info]
    trace["n_objects_mean"] = float(np.mean(n_objects_per_pair)) if n_objects_per_pair else 0
    trace["all_same_shape"] = all(p["same_shape"] for p in per_pair_info)
    n_none_classify = sum(1 for p in per_pair_info if p["classify_result"] == "None")
    n_ok_classify = sum(1 for p in per_pair_info if p["classify_result"] == "ok")
    trace["n_none_classify"] = n_none_classify
    trace["n_ok_classify"] = n_ok_classify

    # ── Stage 2: Gap-analysis-style property check (lenient) ──
    gap_best_prop = None
    gap_best_score = 0.0
    for prop in all_props:
        n_consistent = 0
        n_classifiable = 0
        for inp, out in train_pairs:
            objects = adapter.extract_objects(inp)
            cls = _classify_kept_removed(objects, inp, out)
            if cls is None:
                continue
            n_classifiable += 1
            kept, removed = cls
            kept_vals = [_get_property_value(objects[k], prop) for k in kept]
            removed_vals = [_get_property_value(objects[r], prop) for r in removed]
            if kept_vals and removed_vals:
                if all(kept_vals) and not any(removed_vals):
                    n_consistent += 1
                elif not any(kept_vals) and all(removed_vals):
                    n_consistent += 1
        if n_classifiable > 0:
            score = n_consistent / n_classifiable
            if score > gap_best_score:
                gap_best_score = score
                gap_best_prop = prop
    trace["gap_best_prop"] = gap_best_prop
    trace["gap_best_score"] = gap_best_score

    # ── Stage 3: Solver-style property check (now tolerates None pairs) ──
    solver_prop = None
    solver_keep = None
    solver_prop_failure_reason = None
    candidates = {p: {"true_keeps": True, "false_keeps": True} for p in all_props}
    solver_n_classifiable = 0
    for inp, out in train_pairs:
        objects = adapter.extract_objects(inp)
        result = adapter.classify_kept_removed(objects, inp, out)
        if result is None:
            continue
        solver_n_classifiable += 1
        kept_idx, removed_idx = result
        for prop in list(candidates.keys()):
            kept_vals = [adapter.get_property(objects[k], prop) for k in kept_idx]
            removed_vals = [adapter.get_property(objects[r], prop) for r in removed_idx]
            if not (all(kept_vals) and not any(removed_vals)):
                candidates[prop]["true_keeps"] = False
            if not (all(not v for v in kept_vals) and all(removed_vals)):
                candidates[prop]["false_keeps"] = False
            if not candidates[prop]["true_keeps"] and not candidates[prop]["false_keeps"]:
                del candidates[prop]

    solver_classify_ok = solver_n_classifiable > 0
    trace["solver_classify_all_ok"] = solver_classify_ok
    trace["solver_n_classifiable"] = solver_n_classifiable
    if not solver_classify_ok:
        solver_prop_failure_reason = "no classifiable pairs (all returned None)"

    if solver_classify_ok:
        # Evidence threshold check
        prop_evidence = {}
        for prop in list(candidates.keys()):
            n_true = n_false = 0
            for inp, out in train_pairs:
                for obj in adapter.extract_objects(inp):
                    if adapter.get_property(obj, prop):
                        n_true += 1
                    else:
                        n_false += 1
            prop_evidence[prop] = (n_true, n_false)

        surviving_candidates = []
        evidence_rejected = []
        for prop in all_props:
            if prop not in candidates:
                continue
            n_true, n_false = prop_evidence.get(prop, (0, 0))
            if n_true < 2 or n_false < 2:
                evidence_rejected.append((prop, n_true, n_false))
                continue
            keep = None
            if candidates[prop]["true_keeps"]:
                keep = True
            elif candidates[prop]["false_keeps"]:
                keep = False
            if keep is not None:
                surviving_candidates.append((prop, keep, n_true, n_false))

        trace["n_candidates_before_evidence"] = len(candidates)
        trace["n_evidence_rejected"] = len(evidence_rejected)
        trace["evidence_rejected_details"] = [
            {"prop": p, "n_true": nt, "n_false": nf}
            for p, nt, nf in evidence_rejected
        ]
        trace["n_surviving_candidates"] = len(surviving_candidates)
        trace["surviving_candidates"] = [
            {"prop": p, "keep_when_true": k, "n_true": nt, "n_false": nf}
            for p, k, nt, nf in surviving_candidates
        ]

        if surviving_candidates:
            solver_prop, solver_keep = surviving_candidates[0][0], surviving_candidates[0][1]
        else:
            solver_prop_failure_reason = (
                f"evidence_threshold: {len(evidence_rejected)} candidates rejected "
                f"(n_true<2 or n_false<2), 0 surviving"
            )
    trace["solver_prop"] = solver_prop
    trace["solver_keep"] = solver_keep
    trace["solver_prop_failure_reason"] = solver_prop_failure_reason

    # ── Stage 4: min_train check ──
    min_train = 2
    trace["passes_min_train"] = len(train_pairs) >= min_train
    if len(train_pairs) < min_train:
        trace["failure_class"] = "min_train_too_few"
        if solver_prop_failure_reason is None:
            trace["solver_prop_failure_reason"] = f"min_train={min_train}, have {len(train_pairs)}"

    # ── Stage 5: LOO validation (uses SAME property, not re-find) ──
    loo_pass = None
    loo_failure_detail = None
    recon_diffs = []
    if solver_prop is not None and len(train_pairs) >= min_train:
        loo_pass = True
        for hold_out in range(len(train_pairs)):
            held_inp, held_out_scene = train_pairs[hold_out]
            objects = adapter.extract_objects(held_inp)
            if len(objects) < 2:
                loo_pass = False
                loo_failure_detail = f"hold_out={hold_out}: <2 objects in held-out input"
                break
            keep_mask = [adapter.get_property(o, solver_prop) == solver_keep for o in objects]
            if all(keep_mask) or not any(keep_mask):
                loo_pass = False
                loo_failure_detail = f"hold_out={hold_out}: all/none match property={solver_prop}"
                break
            pred = adapter.reconstruct_filtered(held_inp, objects, keep_mask)
            if pred is None:
                loo_pass = False
                loo_failure_detail = f"hold_out={hold_out}: reconstruct_filtered returned None"
                break
            if not adapter.scenes_equal(pred, held_out_scene):
                loo_pass = False
                diff_mask = pred != held_out_scene
                n_diff = int(diff_mask.sum())
                diff_positions = list(zip(*np.where(diff_mask)))[:10]
                diff_info = {
                    "hold_out": hold_out,
                    "n_diff_pixels": n_diff,
                    "total_pixels": int(pred.size),
                    "diff_pct": round(100 * n_diff / max(pred.size, 1), 1),
                    "sample_diffs": [
                        {"pos": [int(r), int(c)],
                         "pred": int(pred[r, c]),
                         "expected": int(held_out_scene[r, c])}
                        for r, c in diff_positions
                    ],
                }
                recon_diffs.append(diff_info)
                loo_failure_detail = (
                    f"hold_out={hold_out}: reconstruction != expected, "
                    f"{n_diff}/{pred.size} pixels differ ({diff_info['diff_pct']}%)"
                )
                break

    trace["loo_pass"] = loo_pass
    trace["loo_failure_detail"] = loo_failure_detail
    trace["recon_diffs"] = recon_diffs

    # ── Stage 6: Reconstruction on test ──
    test_recon_ok = None
    test_recon_detail = None
    if loo_pass is True and solver_prop is not None:
        test_recon_ok = True
        for ti_idx, test_inp in enumerate(test_inputs):
            objects = adapter.extract_objects(test_inp)
            if len(objects) < 2:
                test_recon_ok = False
                test_recon_detail = f"test[{ti_idx}]: <2 objects"
                break
            keep_mask = [adapter.get_property(o, solver_prop) == solver_keep for o in objects]
            if all(keep_mask) or not any(keep_mask):
                test_recon_ok = False
                test_recon_detail = f"test[{ti_idx}]: all/none match prop={solver_prop}"
                break
            pred = adapter.reconstruct_filtered(test_inp, objects, keep_mask)
            if pred is None:
                test_recon_ok = False
                test_recon_detail = f"test[{ti_idx}]: reconstruct returned None"
                break
            if test_outputs and ti_idx < len(test_outputs):
                if not adapter.scenes_equal(pred, test_outputs[ti_idx]):
                    test_recon_ok = False
                    test_recon_detail = f"test[{ti_idx}]: prediction != ground truth"
                    break

    trace["test_recon_ok"] = test_recon_ok
    trace["test_recon_detail"] = test_recon_detail

    # ── Stage 7: StructuralReasoner.solve() ──
    reasoner = StructuralReasoner(adapter, min_train=2)
    solver_result = reasoner.solve(train_pairs, test_inputs)
    trace["structural_reasoner_solved"] = solver_result is not None
    if solver_result is not None:
        preds, meta = solver_result
        trace["structural_reasoner_strategy"] = meta.get("strategy")
        trace["structural_reasoner_property"] = meta.get("property")
        # Check against ground truth
        if test_outputs:
            correct = all(
                adapter.scenes_equal(p, gt)
                for p, gt in zip(preds, test_outputs)
            )
            trace["structural_reasoner_correct"] = correct
        else:
            trace["structural_reasoner_correct"] = None

    # ── Stage 8: AdaptiveReasoningLoop.solve() ──
    loop = AdaptiveReasoningLoop(max_iterations=8, timeout_seconds=60.0)
    loop_result = loop.solve(train_pairs, test_inputs, task_id=tid)
    trace["loop_solved"] = loop_result.solved
    trace["loop_views_tried"] = loop_result.views_tried
    trace["loop_iterations"] = loop_result.iterations_used
    if loop_result.solved and loop_result.predictions is not None:
        trace["loop_strategy"] = (loop_result.hypothesis or {}).get("strategy")
        trace["loop_view"] = (loop_result.hypothesis or {}).get("view")
        if test_outputs:
            correct = all(
                adapter.scenes_equal(p, gt)
                for p, gt in zip(loop_result.predictions, test_outputs)
            )
            trace["loop_correct"] = correct

    # ── Classify failure ──
    if trace.get("loop_solved"):
        trace["failure_class"] = "SOLVED" if trace.get("loop_correct", False) else "solved_but_wrong"
    elif trace.get("structural_reasoner_solved"):
        trace["failure_class"] = "reasoner_solved_loop_missed"
    elif not trace["all_same_shape"]:
        trace["failure_class"] = "different_shapes"
    elif trace["n_none_classify"] > 0 and trace.get("solver_classify_all_ok") is False:
        trace["failure_class"] = "perception_classify_none"
    elif not trace["passes_min_train"]:
        trace["failure_class"] = "min_train_too_few"
    elif solver_prop is None and trace.get("n_evidence_rejected", 0) > 0:
        trace["failure_class"] = "evidence_threshold_rejects"
    elif solver_prop is None:
        trace["failure_class"] = "no_discriminative_prop_in_solver"
    elif loo_pass is False:
        trace["failure_class"] = "loo_rejects"
    elif test_recon_ok is False:
        trace["failure_class"] = "reconstruction_fails"
    else:
        trace["failure_class"] = "unknown_pipeline_gap"

    return trace


def write_csv(traces, out_path):
    fields = [
        "task_id", "failure_class", "n_train", "n_objects_mean", "all_same_shape",
        "n_none_classify", "n_ok_classify",
        "gap_best_prop", "gap_best_score",
        "solver_classify_all_ok", "solver_prop", "solver_keep",
        "passes_min_train",
        "n_candidates_before_evidence", "n_evidence_rejected", "n_surviving_candidates",
        "loo_pass", "loo_failure_detail",
        "test_recon_ok", "test_recon_detail",
        "structural_reasoner_solved", "structural_reasoner_strategy",
        "structural_reasoner_correct",
        "loop_solved", "loop_views_tried", "loop_iterations", "loop_correct",
        "solver_prop_failure_reason",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for t in traces:
            row = {}
            for field in fields:
                val = t.get(field)
                if isinstance(val, list):
                    val = str(val)
                row[field] = val
            writer.writerow(row)


def write_report(traces, out_path):
    lines = ["# Property-Sufficient 12: Detailed Trace Report\n"]
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Task | Failure Class | Gap Prop | Gap Score | Solver Prop | LOO | Recon | Solved |")
    lines.append("|------|--------------|----------|-----------|-------------|-----|-------|--------|")
    for t in traces:
        lines.append(
            f"| {t['task_id']} | {t['failure_class']} | "
            f"{t.get('gap_best_prop', '-')} | {t.get('gap_best_score', '-')} | "
            f"{t.get('solver_prop', '-')} | {t.get('loo_pass', '-')} | "
            f"{t.get('test_recon_ok', '-')} | {t.get('loop_solved', False)} |"
        )

    # Failure class distribution
    from collections import Counter
    fc = Counter(t["failure_class"] for t in traces)
    lines.append("\n## Failure Class Distribution\n")
    for cls, cnt in fc.most_common():
        lines.append(f"- **{cls}**: {cnt}")

    # Per-task details
    lines.append("\n## Per-Task Details\n")
    for t in traces:
        lines.append(f"### {t['task_id']}\n")
        lines.append(f"- **Failure class**: {t['failure_class']}")
        lines.append(f"- **Train pairs**: {t['n_train']}")
        lines.append(f"- **Avg objects/pair**: {t.get('n_objects_mean', '?'):.1f}")
        lines.append(f"- **All same shape**: {t['all_same_shape']}")
        lines.append(f"- **Classify None count**: {t['n_none_classify']} / {t['n_train']}")
        lines.append(f"- **Gap analysis**: prop={t.get('gap_best_prop')}, score={t.get('gap_best_score')}")
        lines.append(f"- **Solver classify all ok**: {t.get('solver_classify_all_ok')}")
        lines.append(f"- **Solver prop**: {t.get('solver_prop')}, keep={t.get('solver_keep')}")
        if t.get('solver_prop_failure_reason'):
            lines.append(f"- **Solver prop failure**: {t['solver_prop_failure_reason']}")
        lines.append(f"- **Passes min_train=3**: {t.get('passes_min_train')}")
        if t.get('n_candidates_before_evidence') is not None:
            lines.append(f"- **Candidates before evidence filter**: {t['n_candidates_before_evidence']}")
            lines.append(f"- **Evidence-rejected**: {t['n_evidence_rejected']}")
            lines.append(f"- **Surviving candidates**: {t['n_surviving_candidates']}")
            if t.get('evidence_rejected_details'):
                for rej in t['evidence_rejected_details'][:5]:
                    lines.append(f"  - {rej['prop']}: n_true={rej['n_true']}, n_false={rej['n_false']}")
            if t.get('surviving_candidates'):
                for cand in t['surviving_candidates'][:5]:
                    lines.append(f"  - SURVIVES: {cand['prop']}, keep={cand['keep_when_true']}, n_true={cand['n_true']}, n_false={cand['n_false']}")
        lines.append(f"- **LOO pass**: {t.get('loo_pass')}")
        if t.get('loo_failure_detail'):
            lines.append(f"  - Detail: {t['loo_failure_detail']}")
        if t.get('recon_diffs'):
            for rd in t['recon_diffs']:
                lines.append(f"  - **Reconstruction diff** (pair {rd['hold_out']}): "
                             f"{rd['n_diff_pixels']}/{rd['total_pixels']} pixels differ "
                             f"({rd['diff_pct']}%)")
                for sd in rd.get('sample_diffs', [])[:5]:
                    lines.append(f"    - [{sd['pos'][0]},{sd['pos'][1]}]: "
                                 f"pred={sd['pred']}, expected={sd['expected']}")
        lines.append(f"- **Test reconstruction ok**: {t.get('test_recon_ok')}")
        if t.get('test_recon_detail'):
            lines.append(f"  - Detail: {t['test_recon_detail']}")
        lines.append(f"- **StructuralReasoner solved**: {t.get('structural_reasoner_solved')}")
        if t.get('structural_reasoner_solved'):
            lines.append(f"  - Strategy: {t.get('structural_reasoner_strategy')}")
            lines.append(f"  - Correct: {t.get('structural_reasoner_correct')}")
        lines.append(f"- **AdaptiveLoop solved**: {t.get('loop_solved')}")
        if t.get('loop_solved'):
            lines.append(f"  - Strategy: {t.get('loop_strategy')}")
            lines.append(f"  - View: {t.get('loop_view')}")
            lines.append(f"  - Correct: {t.get('loop_correct')}")
        lines.append(f"- **Loop views tried**: {t.get('loop_views_tried')}")
        lines.append(f"- **Loop iterations**: {t.get('loop_iterations')}")

        # Per-pair object details
        for p in t.get("per_pair", []):
            lines.append(f"\n  **Train pair {p['pair_idx']}**: "
                         f"inp={p['inp_shape']}, out={p['out_shape']}, "
                         f"objects={p['n_objects']}, "
                         f"classify={p['classify_result']} "
                         f"(kept={p['kept_count']}, removed={p['removed_count']})")
            for od in p["object_details"][:10]:
                kept_str = "KEPT" if od["is_kept"] else ("REMOVED" if od["is_kept"] is False else "?")
                lines.append(f"    obj[{od['idx']}]: color={od['color']}, area={od['area']}, "
                             f"bbox={od['bbox']}, {kept_str}")
        lines.append("")

    # Bugs found and fixed
    lines.append("\n## Bugs Found and Fixed\n")
    lines.append("1. **LOO property-switching** (FIXED): LOO re-found the property on the subset, "
                 "which could pick a different property that didn't work on the held-out pair. "
                 "Now uses the same property found on all pairs.")
    lines.append("2. **Fatal None classification** (FIXED): `_find_discriminative_property` aborted "
                 "if any pair returned None from `classify_kept_removed`. Now skips None pairs.")
    lines.append("3. **min_train=3 too strict** (FIXED): Tasks with 2 training pairs were rejected. "
                 "Lowered default to 2.")
    lines.append("4. **Reconstruction gap** (NOT A BUG): The gap analysis only checks property "
                 "discrimination, but the solver must also reconstruct (zero out removed objects) "
                 "and match exactly. Many tasks that discriminate objects do more than just zeroing.")
    lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/property_gap_analysis")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading ARC tasks...", flush=True)
    all_tasks = load_arc_tasks(args.arc_root)
    print(f"Loaded {len(all_tasks)} tasks", flush=True)

    adapter = GridDomainAdapter()
    traces = []

    for tid in PROPERTY_SUFFICIENT_12:
        if tid not in all_tasks:
            print(f"  SKIP {tid}: not found in dataset")
            continue
        print(f"  Tracing {tid}...", end=" ", flush=True)
        t0 = time.time()
        trace = trace_single_task(all_tasks[tid], adapter)
        elapsed = time.time() - t0
        print(f"{trace['failure_class']} ({elapsed:.1f}s)")
        traces.append(trace)

    csv_path = os.path.join(args.output_dir, "property_sufficient_12_trace.csv")
    write_csv(traces, csv_path)
    print(f"\nCSV: {csv_path}")

    report_path = os.path.join(args.output_dir, "property_sufficient_12_report.md")
    write_report(traces, report_path)
    print(f"Report: {report_path}")

    # Write failures JSON (serializable subset)
    failures_path = os.path.join(args.output_dir, "property_sufficient_12_failures.json")
    failures_data = []
    for t in traces:
        entry = {k: v for k, v in t.items()
                 if k != "per_pair" and not isinstance(v, np.ndarray)}
        failures_data.append(entry)
    with open(failures_path, "w") as f:
        json.dump(failures_data, f, indent=2, default=str)
    print(f"Failures JSON: {failures_path}")

    # Summary
    solved = sum(1 for t in traces if t.get("loop_solved"))
    print(f"\nSolved: {solved}/{len(traces)}")
    from collections import Counter
    fc = Counter(t["failure_class"] for t in traces)
    for cls, cnt in fc.most_common():
        print(f"  {cls}: {cnt}")


if __name__ == "__main__":
    main()
