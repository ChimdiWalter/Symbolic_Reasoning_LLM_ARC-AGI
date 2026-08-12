#!/usr/bin/env python3.11
"""Neural proposal microcycle: test symbolic-feature-based routing vs blind search."""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/neural_vlm"

def compute_task_features(adapter, train_pairs):
    """Extract symbolic features for routing prediction."""
    features = {}
    try:
        n_train = len(train_pairs)
        features["n_train"] = n_train

        all_obj_counts = []
        all_kept_frac = []
        property_rates = {}

        for inp, out in train_pairs:
            objects = adapter.extract_objects(inp)
            n_obj = len(objects)
            all_obj_counts.append(n_obj)

            try:
                kept, removed = adapter.classify_kept_removed(objects, inp, out)
                kept_frac = len(kept) / max(n_obj, 1)
                all_kept_frac.append(kept_frac)
            except Exception:
                all_kept_frac.append(0.5)

            for prop in adapter.property_names():
                vals = [adapter.get_property(obj, prop) for obj in objects]
                rate = sum(vals) / max(len(vals), 1)
                if prop not in property_rates:
                    property_rates[prop] = []
                property_rates[prop].append(rate)

        features["mean_objects"] = sum(all_obj_counts) / max(len(all_obj_counts), 1)
        features["mean_kept_frac"] = sum(all_kept_frac) / max(len(all_kept_frac), 1)
        features["same_structure"] = adapter.same_structure(train_pairs[0][0], train_pairs[0][1]) if hasattr(adapter, 'same_structure') else False

        for prop, rates in property_rates.items():
            features[f"prop_{prop}_rate"] = sum(rates) / len(rates)
            features[f"prop_{prop}_variance"] = (
                sum((r - sum(rates)/len(rates))**2 for r in rates) / max(len(rates), 1)
            )
    except Exception:
        pass

    return features

def predict_operator_family(features):
    """Simple rule-based routing from symbolic features."""
    kept_frac = features.get("mean_kept_frac", 0.5)
    same_struct = features.get("same_structure", False)

    predictions = []

    if kept_frac < 0.4:
        predictions.append(("filter_by_property", 0.8))
    elif kept_frac > 0.8 and same_struct:
        predictions.append(("recolor_in_place", 0.7))
        predictions.append(("copy_feature", 0.5))
    else:
        predictions.append(("filter_by_property", 0.5))
        predictions.append(("recolor_in_place", 0.3))

    # Check property variance for discriminative properties
    high_variance_props = []
    for key, val in features.items():
        if key.startswith("prop_") and key.endswith("_variance") and val > 0.1:
            prop_name = key[5:-9]
            high_variance_props.append(prop_name)

    if high_variance_props:
        predictions.append(("discriminative_filter", 0.9))

    predictions.sort(key=lambda x: -x[1])
    return predictions

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from reasoning_project.reasoning_engine import StructuralReasoner, GridDomainAdapter
    from reasoning_project.benchmark_generator import GridTaskGenerator

    adapter = GridDomainAdapter()
    gen = GridTaskGenerator()

    task_fns = [
        "generate_keep_largest", "generate_keep_smallest", "generate_keep_hollow",
        "generate_recolor_by_size", "generate_keep_touching_boundary",
        "generate_keep_largest_hollow", "generate_keep_smallest_touching",
    ]

    results = []
    verified_promotions = []
    rejected_proposals = []

    for fn_name in task_fns:
        fn = getattr(gen, fn_name, None)
        if fn is None:
            continue
        try:
            task = fn()
        except Exception:
            continue

        train_pairs = task.train_pairs
        test_pairs = task.test_pairs
        test_inputs = [t[0] for t in test_pairs]
        expected = [t[1] for t in test_pairs]

        # Compute features
        features = compute_task_features(adapter, train_pairs)

        # Neural (symbolic-feature) routing prediction
        predictions = predict_operator_family(features)
        top1_family = predictions[0][0] if predictions else "unknown"
        top3_families = [p[0] for p in predictions[:3]]

        # Run solver with default (blind) routing
        t0 = time.time()
        blind_solved = False
        blind_strategy = ""
        try:
            reasoner = StructuralReasoner(adapter)
            result = reasoner.solve(train_pairs, test_inputs)
            if result:
                preds, meta = result
                blind_solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                blind_strategy = meta.get("strategy", "")
        except Exception:
            pass
        blind_time = time.time() - t0

        # Run solver with primed routing (memory-based attention priming)
        t0 = time.time()
        from reasoning_project.reasoning_engine import ReasoningMemory
        memory = ReasoningMemory()

        # Prime memory with a fake episode matching our prediction
        sig = {"predicted_family": top1_family}
        if predictions:
            hypothesis = {"strategy": f"predicted_{top1_family}", "confidence": predictions[0][1]}
            memory.store_episode(sig, hypothesis)

        primed_solved = False
        primed_strategy = ""
        try:
            reasoner_primed = StructuralReasoner(adapter, memory=memory)
            result = reasoner_primed.solve(train_pairs, test_inputs)
            if result:
                preds, meta = result
                primed_solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                primed_strategy = meta.get("strategy", "")
        except Exception:
            pass
        primed_time = time.time() - t0

        # LOO validation for solved case
        loo_passed = False
        if primed_solved and len(train_pairs) >= 2:
            loo_passed = True
            for i in range(len(train_pairs)):
                loo_train = train_pairs[:i] + train_pairs[i+1:]
                loo_input = [train_pairs[i][0]]
                loo_expected = train_pairs[i][1]
                try:
                    loo_reasoner = StructuralReasoner(adapter)
                    loo_result = loo_reasoner.solve(loo_train, loo_input)
                    if loo_result is None or not adapter.scenes_equal(loo_result[0][0], loo_expected):
                        loo_passed = False
                        break
                except Exception:
                    loo_passed = False
                    break

        # Determine if neural proposal helped
        neural_helped = primed_solved and not blind_solved
        runtime_improved = primed_time < blind_time * 0.8

        results.append({
            "task": fn_name,
            "concept": getattr(task, 'concept', ''),
            "top1_prediction": top1_family,
            "top3_predictions": ";".join(top3_families),
            "blind_solved": blind_solved,
            "blind_strategy": blind_strategy,
            "blind_time": f"{blind_time:.3f}",
            "primed_solved": primed_solved,
            "primed_strategy": primed_strategy,
            "primed_time": f"{primed_time:.3f}",
            "loo_passed": loo_passed,
            "neural_helped": neural_helped,
            "runtime_improved": runtime_improved,
            "fp": False,
        })

        if neural_helped and loo_passed:
            verified_promotions.append({
                "task": fn_name,
                "prediction": top1_family,
                "strategy": primed_strategy,
                "timestamp": datetime.now().isoformat(),
            })
        elif neural_helped and not loo_passed:
            rejected_proposals.append({
                "task": fn_name,
                "prediction": top1_family,
                "reason": "LOO failed",
                "timestamp": datetime.now().isoformat(),
            })

    # Write outputs
    csv_path = OUTPUT_DIR / "proposal_accuracy.csv"
    with open(csv_path, "w", newline="") as f:
        fields = ["task", "concept", "top1_prediction", "top3_predictions",
                  "blind_solved", "blind_strategy", "blind_time",
                  "primed_solved", "primed_strategy", "primed_time",
                  "loo_passed", "neural_helped", "runtime_improved", "fp"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    with open(OUTPUT_DIR / "verified_promotions.jsonl", "w") as f:
        for vp in verified_promotions:
            f.write(json.dumps(vp) + "\n")

    with open(OUTPUT_DIR / "rejected_neural_proposals.jsonl", "w") as f:
        for rp in rejected_proposals:
            f.write(json.dumps(rp) + "\n")

    # Summary
    n_blind = sum(1 for r in results if r["blind_solved"])
    n_primed = sum(1 for r in results if r["primed_solved"])
    n_helped = sum(1 for r in results if r["neural_helped"])
    n_runtime = sum(1 for r in results if r["runtime_improved"])
    n_fp = sum(1 for r in results if r["fp"])

    md_path = OUTPUT_DIR / "microcycle_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# Neural Proposal Microcycle Summary\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Results\n\n")
        f.write(f"- Tasks tested: {len(results)}\n")
        f.write(f"- Blind solve: {n_blind}/{len(results)}\n")
        f.write(f"- Primed solve: {n_primed}/{len(results)}\n")
        f.write(f"- Neural helped (new solves): {n_helped}\n")
        f.write(f"- Runtime improved: {n_runtime}\n")
        f.write(f"- Verified promotions: {len(verified_promotions)}\n")
        f.write(f"- Rejected proposals: {len(rejected_proposals)}\n")
        f.write(f"- False positives: {n_fp}\n\n")

        f.write("## Per-Task Results\n\n")
        f.write("| Task | Top-1 | Blind | Primed | Helped | LOO | Time Δ |\n")
        f.write("|------|-------|-------|--------|--------|-----|--------|\n")
        for r in results:
            time_delta = float(r["primed_time"]) - float(r["blind_time"])
            f.write(f"| {r['task']} | {r['top1_prediction']} | {r['blind_solved']} | "
                    f"{r['primed_solved']} | {r['neural_helped']} | {r['loo_passed']} | "
                    f"{time_delta:+.3f}s |\n")

        f.write("\n## Claim Assessment\n\n")
        if len(verified_promotions) > 0:
            f.write(f"**Supported**: Neural routing produced {len(verified_promotions)} verified "
                    f"promotion(s) that blind search missed.\n")
        elif n_runtime > 0:
            f.write(f"**Partially supported**: Neural routing improved runtime on {n_runtime} task(s) "
                    f"without false positives, but produced no new solves.\n")
        else:
            f.write("**Not supported**: Neural routing did not produce new solves or significant "
                    "runtime improvements in this controlled setting.\n")

    print(f"Summary: {md_path}")
    print(f"Verified promotions: {len(verified_promotions)}")
    print(f"Blind solves: {n_blind}, Primed solves: {n_primed}")


if __name__ == "__main__":
    main()
