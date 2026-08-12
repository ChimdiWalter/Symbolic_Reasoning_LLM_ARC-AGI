"""Build ARC task taxonomy: compute features for each task and classify into categories."""
import json
import sys
import csv
from pathlib import Path
from collections import Counter

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.arc_adapter import load_arc_tasks


def connected_components(grid):
    labeled, n = ndimage.label(grid > 0)
    return n


def grid_features(grid):
    arr = np.asarray(grid, dtype=int)
    h, w = arr.shape
    colors = set(arr.flatten().tolist())
    n_colors = len(colors)
    n_objects = connected_components(arr)
    return {
        "height": h,
        "width": w,
        "n_colors": n_colors,
        "n_objects": n_objects,
        "colors": sorted(colors),
    }


def symmetry_score(grid):
    arr = np.asarray(grid, dtype=int)
    h, w = arr.shape
    h_sym = np.mean(arr == np.fliplr(arr))
    v_sym = np.mean(arr == np.flipud(arr))
    return float(max(h_sym, v_sym))


def local_rule_likelihood(train_examples):
    """Estimate if output is a local function of input neighborhoods."""
    for ex in train_examples:
        inp = np.asarray(ex.input_grid, dtype=int)
        out = np.asarray(ex.output_grid, dtype=int)
        if inp.shape != out.shape:
            return 0.0
    consistent = 0
    total = 0
    for ex in train_examples:
        inp = np.asarray(ex.input_grid, dtype=int)
        out = np.asarray(ex.output_grid, dtype=int)
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                total += 1
                nb = []
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < h and 0 <= cc < w:
                            nb.append(inp[rr, cc])
                        else:
                            nb.append(-1)
                consistent += 1
    if total == 0:
        return 0.0
    mapping = {}
    conflicts = 0
    for ex in train_examples:
        inp = np.asarray(ex.input_grid, dtype=int)
        out = np.asarray(ex.output_grid, dtype=int)
        if inp.shape != out.shape:
            return 0.0
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                nb = []
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < h and 0 <= cc < w:
                            nb.append(int(inp[rr, cc]))
                        else:
                            nb.append(-1)
                key = tuple(nb)
                target = int(out[r, c])
                if key in mapping:
                    if mapping[key] != target:
                        conflicts += 1
                else:
                    mapping[key] = target
    total_keys = len(mapping)
    if total_keys == 0:
        return 0.0
    return 1.0 - (conflicts / max(total_keys, 1))


def color_permutation_likelihood(train_examples):
    """Check if output is a color permutation of input."""
    for ex in train_examples:
        inp = np.asarray(ex.input_grid, dtype=int)
        out = np.asarray(ex.output_grid, dtype=int)
        if inp.shape != out.shape:
            return 0.0
        in_colors = set(inp.flatten().tolist())
        out_colors = set(out.flatten().tolist())
        if in_colors != out_colors and len(in_colors) != len(out_colors):
            return 0.0
    return 1.0


def object_transform_likelihood(train_examples):
    """Estimate if task involves per-object transformation."""
    scores = []
    for ex in train_examples:
        inp = np.asarray(ex.input_grid, dtype=int)
        out = np.asarray(ex.output_grid, dtype=int)
        in_objs = connected_components(inp)
        out_objs = connected_components(out)
        if in_objs > 1 and out_objs > 0:
            scores.append(1.0)
        else:
            scores.append(0.0)
    return float(np.mean(scores)) if scores else 0.0


def classify_task(features):
    """Classify task into primary category."""
    same_size = features["same_size"]
    local_rule = features["local_rule_likelihood"]
    color_perm = features["color_perm_likelihood"]
    obj_transform = features["object_transform_likelihood"]

    if not same_size and features["output_smaller"]:
        return "crop_extract"
    if not same_size and not features["output_smaller"]:
        return "resize_generate"
    if local_rule > 0.95:
        return "local_rule"
    if color_perm > 0.9:
        return "color_permutation"
    if obj_transform > 0.7:
        return "object_transform"
    if features["symmetry_score"] > 0.8:
        return "symmetry_completion"
    return "other"


def analyze_task(task):
    train_examples = task.train
    test_examples = task.test

    in_feats = [grid_features(ex.input_grid) for ex in train_examples]
    out_feats = [grid_features(ex.output_grid) for ex in train_examples]

    avg_in_h = np.mean([f["height"] for f in in_feats])
    avg_in_w = np.mean([f["width"] for f in in_feats])
    avg_out_h = np.mean([f["height"] for f in out_feats])
    avg_out_w = np.mean([f["width"] for f in out_feats])

    same_size = all(
        np.asarray(ex.input_grid).shape == np.asarray(ex.output_grid).shape
        for ex in train_examples
    )

    output_smaller = avg_out_h * avg_out_w < avg_in_h * avg_in_w

    in_colors = np.mean([f["n_colors"] for f in in_feats])
    out_colors = np.mean([f["n_colors"] for f in out_feats])
    color_change = out_colors - in_colors

    in_objs = np.mean([f["n_objects"] for f in in_feats])
    out_objs = np.mean([f["n_objects"] for f in out_feats])
    obj_change = out_objs - in_objs

    sym = np.mean([symmetry_score(ex.input_grid) for ex in train_examples])
    local_rule = local_rule_likelihood(train_examples)
    color_perm = color_permutation_likelihood(train_examples)
    obj_transform = object_transform_likelihood(train_examples)

    features = {
        "task_id": task.task_id,
        "n_train": len(train_examples),
        "n_test": len(test_examples),
        "avg_in_h": round(avg_in_h, 1),
        "avg_in_w": round(avg_in_w, 1),
        "avg_out_h": round(avg_out_h, 1),
        "avg_out_w": round(avg_out_w, 1),
        "same_size": same_size,
        "output_smaller": output_smaller,
        "in_colors": round(in_colors, 1),
        "out_colors": round(out_colors, 1),
        "color_change": round(color_change, 1),
        "in_objects": round(in_objs, 1),
        "out_objects": round(out_objs, 1),
        "object_change": round(obj_change, 1),
        "symmetry_score": round(sym, 3),
        "local_rule_likelihood": round(local_rule, 3),
        "color_perm_likelihood": round(color_perm, 3),
        "object_transform_likelihood": round(obj_transform, 3),
    }
    features["category"] = classify_task(features)
    return features


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/arc_taxonomy")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_arc_tasks(args.arc_root)
    print(f"Loaded {len(tasks)} tasks")

    dsl_solved = {
        "00d62c1b", "1cf80156", "1e0a9b12", "1f85a75f", "25ff71a9",
        "3906de3d", "3c9b0459", "4347f46a", "60c09cac", "6150a2bd",
        "67a3c6ac", "68b16354", "68b67ca3", "6d0aefbc", "6fa7a44f",
        "7468f01a", "74dd1130", "8be77c9e", "9172f3a0", "9dfd6313",
        "a416b8f3", "a5313dff", "a740d043", "a79310a0", "b1948b0a",
        "be94b721", "c59eb873", "c8f0f002", "c9e6f938", "d511f180",
        "ed36ccf7",
    }
    ri_solved = {
        "332efdb3", "3618c87e", "4258a5f9", "5614dbcf", "6e82a1ae",
        "6f8cd79b", "a699fb00", "ae58858e", "ba26e723", "d2abd087",
        "dc1df850",
    }

    results = []
    for i, task in enumerate(tasks):
        if i % 100 == 0:
            print(f"  {i}/{len(tasks)}", flush=True)
        feats = analyze_task(task)
        feats["solved_by_dsl"] = task.task_id in dsl_solved
        feats["solved_by_ri"] = task.task_id in ri_solved
        feats["solved"] = feats["solved_by_dsl"] or feats["solved_by_ri"]
        results.append(feats)

    # Write CSV
    csv_path = output_dir / "task_taxonomy.csv"
    fieldnames = list(results[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {csv_path}")

    # Category summary
    categories = Counter(r["category"] for r in results)
    solved_by_cat = Counter()
    unsolved_by_cat = Counter()
    for r in results:
        if r["solved"]:
            solved_by_cat[r["category"]] += 1
        else:
            unsolved_by_cat[r["category"]] += 1

    md_lines = ["# ARC Task Taxonomy Summary\n"]
    md_lines.append(f"Total tasks: {len(results)}")
    md_lines.append(f"Total solved: {sum(1 for r in results if r['solved'])}")
    md_lines.append(f"  - DSL: {sum(1 for r in results if r['solved_by_dsl'])}")
    md_lines.append(f"  - Rule Induction: {sum(1 for r in results if r['solved_by_ri'])}\n")
    md_lines.append("## Category Breakdown\n")
    md_lines.append("| Category | Total | Solved | Unsolved | Solve Rate |")
    md_lines.append("|----------|-------|--------|----------|-----------|")
    for cat in sorted(categories.keys()):
        total = categories[cat]
        solved = solved_by_cat.get(cat, 0)
        unsolved = unsolved_by_cat.get(cat, 0)
        rate = solved / total if total > 0 else 0
        md_lines.append(f"| {cat} | {total} | {solved} | {unsolved} | {rate:.1%} |")

    md_lines.append("\n## Same-Size vs Resized\n")
    same = sum(1 for r in results if r["same_size"])
    diff = len(results) - same
    same_solved = sum(1 for r in results if r["same_size"] and r["solved"])
    diff_solved = sum(1 for r in results if not r["same_size"] and r["solved"])
    md_lines.append(f"- Same size: {same} tasks, {same_solved} solved ({same_solved/same:.1%})")
    md_lines.append(f"- Different size: {diff} tasks, {diff_solved} solved ({diff_solved/diff:.1%})")

    md_lines.append("\n## Local-Rule Tasks (likelihood > 0.95)\n")
    local_tasks = [r for r in results if r["local_rule_likelihood"] > 0.95]
    local_solved = sum(1 for r in local_tasks if r["solved"])
    md_lines.append(f"- Total: {len(local_tasks)}")
    md_lines.append(f"- Already solved: {local_solved}")
    md_lines.append(f"- Unsolved (target for local-rule solver): {len(local_tasks) - local_solved}")

    md_lines.append("\n## Opportunity Analysis\n")
    md_lines.append("Tasks by category where new solvers could help:\n")
    for cat in sorted(categories.keys()):
        unsolved = unsolved_by_cat.get(cat, 0)
        if unsolved > 0:
            md_lines.append(f"- **{cat}**: {unsolved} unsolved tasks")

    md_path = output_dir / "task_taxonomy.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Wrote {md_path}")

    # Solvable vs unsolved breakdown
    breakdown_lines = ["# Solvable vs Unsolved Breakdown\n"]
    breakdown_lines.append("## Solved Tasks by Category and Solver\n")
    breakdown_lines.append("| Task ID | Category | Solver | Local Rule Likelihood |")
    breakdown_lines.append("|---------|----------|--------|----------------------|")
    for r in sorted(results, key=lambda x: x["category"]):
        if r["solved"]:
            solver = "DSL" if r["solved_by_dsl"] else "Rule Induction"
            breakdown_lines.append(f"| {r['task_id']} | {r['category']} | {solver} | {r['local_rule_likelihood']:.3f} |")

    breakdown_lines.append("\n## High-Opportunity Unsolved Tasks\n")
    breakdown_lines.append("Tasks with local_rule_likelihood > 0.9 but not yet solved:\n")
    breakdown_lines.append("| Task ID | Category | Local Rule | Symmetry | Same Size |")
    breakdown_lines.append("|---------|----------|-----------|----------|-----------|")
    for r in sorted(results, key=lambda x: -x["local_rule_likelihood"]):
        if not r["solved"] and r["local_rule_likelihood"] > 0.9:
            breakdown_lines.append(
                f"| {r['task_id']} | {r['category']} | {r['local_rule_likelihood']:.3f} | {r['symmetry_score']:.3f} | {r['same_size']} |"
            )
            if len(breakdown_lines) > 60:
                break

    breakdown_path = output_dir / "solvable_vs_unsolved_breakdown.md"
    with open(breakdown_path, "w") as f:
        f.write("\n".join(breakdown_lines) + "\n")
    print(f"Wrote {breakdown_path}")


if __name__ == "__main__":
    main()
