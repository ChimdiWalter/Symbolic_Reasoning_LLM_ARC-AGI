"""Deep analysis of unsolved ARC tasks for solver expansion.

Two goals:
1. Sub-categorize the 283 "color_permutation" tasks into actionable clusters.
2. Identify unsolved tasks with separator structure for separator_decompose expansion.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    python3.11 scripts/deep_unsolved_analysis.py
"""

import csv
import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARC_ROOT = PROJECT_ROOT / "data" / "arc"
TAXONOMY_CSV = PROJECT_ROOT / "outputs" / "arc_taxonomy" / "task_taxonomy.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "deep_unsolved_analysis"

CHALLENGES_FILE = ARC_ROOT / "arc-agi_training_challenges.json"
SOLUTIONS_FILE = ARC_ROOT / "arc-agi_training_solutions.json"

sys.path.insert(0, str(PROJECT_ROOT / "src"))


def load_data():
    with open(CHALLENGES_FILE) as f:
        challenges = json.load(f)
    with open(SOLUTIONS_FILE) as f:
        solutions = json.load(f)

    taxonomy = {}
    with open(TAXONOMY_CSV, newline="") as f:
        for row in csv.DictReader(f):
            taxonomy[row["task_id"]] = row

    solved_path = PROJECT_ROOT / "outputs" / "portfolio_arc_v6" / "summary.json"
    if solved_path.exists():
        with open(solved_path) as f:
            solved_ids = set(json.load(f).get("solved_ids", []))
    else:
        solved_ids = set()
        for row in taxonomy.values():
            if row.get("solved") == "True":
                solved_ids.add(row["task_id"])

    return challenges, solutions, taxonomy, solved_ids


def grid_to_np(grid):
    return np.array(grid, dtype=int)


def find_separators(arr):
    h, w = arr.shape
    row_seps = []
    for r in range(h):
        vals = set(arr[r, :].tolist())
        if len(vals) == 1 and 0 not in vals:
            row_seps.append((r, arr[r, 0]))

    col_seps = []
    for c in range(w):
        vals = set(arr[:, c].tolist())
        if len(vals) == 1 and 0 not in vals:
            col_seps.append((c, arr[0, c]))

    return row_seps, col_seps


def count_connected_components(arr, ignore_bg=True):
    visited = set()
    components = []
    h, w = arr.shape
    for r in range(h):
        for c in range(w):
            if (r, c) in visited:
                continue
            val = arr[r, c]
            if ignore_bg and val == 0:
                visited.add((r, c))
                continue
            stack = [(r, c)]
            comp = []
            while stack:
                cr, cc = stack.pop()
                if (cr, cc) in visited:
                    continue
                if arr[cr, cc] != val:
                    continue
                visited.add((cr, cc))
                comp.append((cr, cc))
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in visited:
                        stack.append((nr, nc))
            if comp:
                components.append((val, comp))
    return components


def check_object_movement(inp, out):
    """Check if objects in input appear moved/rearranged in output."""
    if inp.shape != out.shape:
        return False, "different shapes"
    in_comps = count_connected_components(inp)
    out_comps = count_connected_components(out)
    if len(in_comps) < 2 or len(out_comps) < 2:
        return False, "too few objects"
    in_colors = Counter(c for c, _ in in_comps)
    out_colors = Counter(c for c, _ in out_comps)
    if in_colors == out_colors:
        changed = not np.array_equal(inp, out)
        if changed:
            return True, "same objects, different positions"
    return False, "object count mismatch"


def check_pattern_growth(inp, out):
    """Check if output is a tiled/scaled version of input or a pattern from input."""
    ih, iw = inp.shape
    oh, ow = out.shape
    if oh == ih and ow == iw:
        return False, "same size"
    if oh > ih or ow > iw:
        if oh % ih == 0 and ow % iw == 0:
            return True, f"exact scale {oh // ih}x{ow // iw}"
        return True, f"growth {ih}x{iw} -> {oh}x{ow}"
    return False, f"shrink {ih}x{iw} -> {oh}x{ow}"


def check_flood_fill_pattern(inp, out):
    """Check if output fills enclosed regions."""
    if inp.shape != out.shape:
        return False
    diff = (inp != out)
    changed_pixels = np.sum(diff)
    total = inp.size
    if changed_pixels == 0:
        return False
    changed_where_zero = np.sum(diff & (inp == 0))
    if changed_where_zero > 0.8 * changed_pixels:
        return True
    return False


def check_line_drawing(inp, out):
    """Check if output adds lines/paths connecting objects."""
    if inp.shape != out.shape:
        return False
    diff = (inp != out)
    if np.sum(diff) == 0:
        return False
    new_pixels = diff & (inp == 0)
    if np.sum(new_pixels) == 0:
        return False
    new_coords = np.argwhere(new_pixels)
    if len(new_coords) < 3:
        return False
    rows = new_coords[:, 0]
    cols = new_coords[:, 1]
    row_spread = rows.max() - rows.min()
    col_spread = cols.max() - cols.min()
    n_new = len(new_coords)
    if row_spread > 0 and col_spread == 0:
        return True
    if col_spread > 0 and row_spread == 0:
        return True
    if n_new <= max(row_spread, col_spread) + 2:
        return True
    return False


def check_conditional_recolor(inp, out):
    """Check if output recolors objects based on some property (size, position, etc)."""
    if inp.shape != out.shape:
        return False, "different shapes"
    in_comps = count_connected_components(inp)
    out_comps = count_connected_components(out)
    if len(in_comps) < 2:
        return False, "too few objects"
    diff = (inp != out)
    changed_pix = np.sum(diff)
    if changed_pix == 0:
        return False, "identical"
    nonzero_changed = np.sum(diff & (inp != 0))
    if nonzero_changed > 0.5 * changed_pix:
        return True, "recolors existing objects"
    return False, "mostly new pixels"


def check_region_coloring(inp, out):
    """Check if output colors enclosed/bounded regions."""
    if inp.shape != out.shape:
        return False
    diff = (inp != out)
    if np.sum(diff) == 0:
        return False
    changed_where_zero = np.sum(diff & (inp == 0))
    changed_nonzero = np.sum(diff & (inp != 0))
    return changed_where_zero > 3 * changed_nonzero


def subcategorize_color_perm(task_id, challenge, solution):
    """Attempt to sub-categorize a 'color_permutation' task."""
    train_pairs = [(grid_to_np(ex["input"]), grid_to_np(ex["output"]))
                   for ex in challenge["train"]]

    inp0, out0 = train_pairs[0]
    same_size = all(i.shape == o.shape for i, o in train_pairs)

    subcats = []

    if same_size:
        moved, detail = check_object_movement(inp0, out0)
        if moved:
            subcats.append(("object_rearrangement", detail))

        is_recolor, detail = check_conditional_recolor(inp0, out0)
        if is_recolor:
            subcats.append(("conditional_recolor", detail))

        if check_flood_fill_pattern(inp0, out0):
            subcats.append(("flood_fill", "fills zero regions"))

        if check_region_coloring(inp0, out0):
            subcats.append(("region_coloring", "colors bounded regions"))

        if check_line_drawing(inp0, out0):
            subcats.append(("line_drawing", "adds lines/paths"))

        row_seps, col_seps = find_separators(inp0)
        if row_seps or col_seps:
            subcats.append(("has_separators",
                            f"{len(row_seps)} row, {len(col_seps)} col"))
    else:
        grew, detail = check_pattern_growth(inp0, out0)
        if grew:
            subcats.append(("pattern_growth", detail))
        else:
            subcats.append(("size_change", detail))

    if not subcats:
        subcats.append(("unclassified", ""))

    return subcats


def analyze_separator_opportunities(challenges, solutions, taxonomy, solved_ids):
    """Find unsolved tasks with separator structure."""
    results = []

    for task_id, challenge in challenges.items():
        if task_id in solved_ids:
            continue

        train_pairs = [(grid_to_np(ex["input"]), grid_to_np(ex["output"]))
                       for ex in challenge["train"]]

        has_sep = False
        sep_details = []
        for i, (inp, out) in enumerate(train_pairs):
            row_seps, col_seps = find_separators(inp)
            if row_seps or col_seps:
                has_sep = True
                n_rows_seps = len(row_seps)
                n_col_seps = len(col_seps)
                same_size = inp.shape == out.shape
                sep_details.append({
                    "pair": i,
                    "input_shape": inp.shape,
                    "output_shape": out.shape,
                    "row_seps": n_rows_seps,
                    "col_seps": n_col_seps,
                    "same_size": same_size,
                    "sep_colors": sorted(set(
                        [c for _, c in row_seps] + [c for _, c in col_seps]
                    )),
                })

        if has_sep:
            cat = taxonomy.get(task_id, {}).get("category", "unknown")
            all_same_size = all(d["same_size"] for d in sep_details)
            has_both = any(
                d["row_seps"] > 0 and d["col_seps"] > 0 for d in sep_details
            )
            max_cells = max(
                (d["row_seps"] + 1) * (d["col_seps"] + 1) for d in sep_details
            )

            out_shrinks = any(
                np.prod(d["output_shape"]) < np.prod(d["input_shape"])
                for d in sep_details
            )

            results.append({
                "task_id": task_id,
                "category": cat,
                "n_train": len(train_pairs),
                "all_same_size": all_same_size,
                "has_both_row_col": has_both,
                "max_cells": max_cells,
                "output_shrinks": out_shrinks,
                "details": sep_details,
            })

    return results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    challenges, solutions, taxonomy, solved_ids = load_data()

    print(f"Total tasks: {len(challenges)}")
    print(f"Currently solved: {len(solved_ids)}")

    # ---- Part 1: Color permutation sub-categorization ----
    print("\n=== Color Permutation Sub-categorization ===")

    cp_tasks = [
        tid for tid, row in taxonomy.items()
        if row.get("category") == "color_permutation" and tid not in solved_ids
    ]
    print(f"Unsolved color_permutation tasks: {len(cp_tasks)}")

    subcat_counts = Counter()
    subcat_tasks = defaultdict(list)
    task_subcats = {}

    for tid in cp_tasks:
        if tid not in challenges:
            continue
        subcats = subcategorize_color_perm(tid, challenges[tid], solutions.get(tid))
        task_subcats[tid] = subcats
        for sc, detail in subcats:
            subcat_counts[sc] += 1
            subcat_tasks[sc].append((tid, detail))

    print("\nSub-category breakdown:")
    for sc, count in subcat_counts.most_common():
        print(f"  {sc}: {count}")

    # ---- Part 2: Separator opportunities ----
    print("\n=== Separator Expansion Opportunities ===")

    sep_results = analyze_separator_opportunities(
        challenges, solutions, taxonomy, solved_ids
    )
    print(f"Unsolved tasks with separators: {len(sep_results)}")

    by_category = Counter(r["category"] for r in sep_results)
    print("\nBy taxonomy category:")
    for cat, count in by_category.most_common():
        print(f"  {cat}: {count}")

    grid_tasks = [r for r in sep_results if r["has_both_row_col"]]
    print(f"\nWith both row AND column separators (grid structure): {len(grid_tasks)}")

    shrink_tasks = [r for r in sep_results if r["output_shrinks"]]
    print(f"Where output is smaller (crop/extract pattern): {len(shrink_tasks)}")

    same_size_tasks = [r for r in sep_results if r["all_same_size"]]
    print(f"Same-size input/output (combine/transform pattern): {len(same_size_tasks)}")

    # ---- Write reports ----

    # Color perm report
    lines = ["# Color Permutation Sub-categorization\n"]
    lines.append(f"Total unsolved color_permutation tasks: {len(cp_tasks)}\n")
    lines.append("## Sub-category Breakdown\n")
    lines.append("| Sub-category | Count | % | Tractability |")
    lines.append("|---|---|---|---|")

    tractability = {
        "conditional_recolor": "HIGH — rule-based recoloring",
        "region_coloring": "HIGH — flood-fill / enclosed region",
        "flood_fill": "HIGH — extend existing fill strategies",
        "line_drawing": "MEDIUM — path-finding between objects",
        "has_separators": "HIGH — separator_decompose expansion",
        "object_rearrangement": "MEDIUM — object matching + placement",
        "pattern_growth": "LOW — iterative pattern rules",
        "size_change": "LOW — diverse resize operations",
        "unclassified": "UNKNOWN — needs manual inspection",
    }

    for sc, count in subcat_counts.most_common():
        pct = round(100 * count / len(cp_tasks), 1)
        tract = tractability.get(sc, "UNKNOWN")
        lines.append(f"| {sc} | {count} | {pct}% | {tract} |")

    lines.append("\n## High-Tractability Tasks (top 5 per sub-category)\n")
    for sc in ["conditional_recolor", "region_coloring", "flood_fill",
               "has_separators", "line_drawing"]:
        tasks = subcat_tasks.get(sc, [])
        if not tasks:
            continue
        lines.append(f"### {sc} ({len(tasks)} tasks)\n")
        for tid, detail in tasks[:5]:
            lines.append(f"- `{tid}`: {detail}")
        if len(tasks) > 5:
            lines.append(f"- ... and {len(tasks) - 5} more")
        lines.append("")

    lines.append("## Sample Unclassified Tasks (first 10)\n")
    for tid, detail in subcat_tasks.get("unclassified", [])[:10]:
        ch = challenges[tid]
        inp = ch["train"][0]["input"]
        out = ch["train"][0]["output"]
        h, w = len(inp), len(inp[0])
        oh, ow = len(out), len(out[0])
        in_cols = sorted(set(v for row in inp for v in row))
        out_cols = sorted(set(v for row in out for v in row))
        lines.append(f"- `{tid}`: {h}x{w} → {oh}x{ow}, "
                      f"in_colors={in_cols}, out_colors={out_cols}")
    lines.append("")

    with open(OUTPUT_DIR / "color_perm_subcategories.md", "w") as f:
        f.write("\n".join(lines))
    print(f"\nWrote {OUTPUT_DIR / 'color_perm_subcategories.md'}")

    # Separator report
    lines = ["# Separator Expansion Opportunities\n"]
    lines.append(f"Total unsolved tasks with separator structure: {len(sep_results)}\n")
    lines.append("## By Taxonomy Category\n")
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    for cat, count in by_category.most_common():
        lines.append(f"| {cat} | {count} |")

    lines.append(f"\n## Structure Breakdown\n")
    lines.append(f"- Grid structure (both row + col seps): {len(grid_tasks)}")
    lines.append(f"- Output shrinks (crop/extract): {len(shrink_tasks)}")
    lines.append(f"- Same-size (combine/transform): {len(same_size_tasks)}")
    lines.append(f"- Output grows: {len([r for r in sep_results if not r['all_same_size'] and not r['output_shrinks']])}")

    lines.append("\n## Grid-Structure Tasks (both row + col separators)\n")
    lines.append("These are the best candidates for separator_decompose expansion.\n")
    for r in sorted(grid_tasks, key=lambda x: -x["max_cells"])[:20]:
        inp_s = r["details"][0]["input_shape"]
        out_s = r["details"][0]["output_shape"]
        lines.append(
            f"- `{r['task_id']}` ({r['category']}): "
            f"{inp_s[0]}x{inp_s[1]} → {out_s[0]}x{out_s[1]}, "
            f"max_cells={r['max_cells']}, same_size={r['all_same_size']}"
        )

    lines.append("\n## Same-Size Separator Tasks (combine/transform candidates)\n")
    same_size_sep = [r for r in sep_results if r["all_same_size"]]
    for r in same_size_sep[:20]:
        inp_s = r["details"][0]["input_shape"]
        rseps = r["details"][0]["row_seps"]
        cseps = r["details"][0]["col_seps"]
        lines.append(
            f"- `{r['task_id']}` ({r['category']}): "
            f"{inp_s[0]}x{inp_s[1]}, "
            f"seps: {rseps}r/{cseps}c, cells={r['max_cells']}"
        )

    lines.append("\n## Output-Shrinks Separator Tasks (extraction candidates)\n")
    for r in shrink_tasks[:20]:
        inp_s = r["details"][0]["input_shape"]
        out_s = r["details"][0]["output_shape"]
        lines.append(
            f"- `{r['task_id']}` ({r['category']}): "
            f"{inp_s[0]}x{inp_s[1]} → {out_s[0]}x{out_s[1]}, "
            f"cells={r['max_cells']}"
        )

    lines.append("")
    with open(OUTPUT_DIR / "separator_opportunities.md", "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {OUTPUT_DIR / 'separator_opportunities.md'}")

    # JSON dump for programmatic use
    summary = {
        "color_perm_subcategories": {
            sc: {"count": count, "task_ids": [t for t, _ in subcat_tasks[sc]]}
            for sc, count in subcat_counts.most_common()
        },
        "separator_opportunities": {
            "total": len(sep_results),
            "grid_structure": len(grid_tasks),
            "output_shrinks": len(shrink_tasks),
            "same_size": len(same_size_tasks),
            "by_category": dict(by_category),
            "grid_task_ids": [r["task_id"] for r in grid_tasks],
            "shrink_task_ids": [r["task_id"] for r in shrink_tasks],
            "same_size_task_ids": [r["task_id"] for r in same_size_tasks],
        },
    }
    with open(OUTPUT_DIR / "analysis_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {OUTPUT_DIR / 'analysis_summary.json'}")


if __name__ == "__main__":
    main()
