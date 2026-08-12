"""Diagnostic analysis of unsolved ARC tasks in the three largest unsolved categories.

Examines the first 10 unsolved tasks in each of:
  - color_permutation (283 unsolved)
  - crop_extract (221 unsolved)
  - symmetry_completion (56 unsolved)

For each task, reports structural features and checks whether simple
pattern-matching heuristics would apply.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    python3.11 scripts/analyze_unsolved_tasks.py
"""

import csv
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARC_ROOT = PROJECT_ROOT / "data" / "arc"
TAXONOMY_CSV = PROJECT_ROOT / "outputs" / "arc_taxonomy" / "task_taxonomy.csv"
OUTPUT_MD = PROJECT_ROOT / "outputs" / "unsolved_analysis.md"

CHALLENGES_FILE = ARC_ROOT / "arc-agi_training_challenges.json"
SOLUTIONS_FILE = ARC_ROOT / "arc-agi_training_solutions.json"

CATEGORIES_OF_INTEREST = ["color_permutation", "crop_extract", "symmetry_completion"]
SAMPLE_SIZE = 10


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_taxonomy():
    """Load taxonomy CSV and return list of dicts."""
    rows = []
    with open(TAXONOMY_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_arc_raw():
    """Load raw ARC challenges and solutions."""
    with open(CHALLENGES_FILE) as f:
        challenges = json.load(f)
    with open(SOLUTIONS_FILE) as f:
        solutions = json.load(f)
    return challenges, solutions


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def grid_colors(grid):
    """Return set of colors in a grid."""
    colors = set()
    for row in grid:
        for val in row:
            colors.add(val)
    return colors


def grid_shape(grid):
    """Return (height, width) of a grid."""
    return (len(grid), len(grid[0]) if grid else 0)


def is_same_size(inp, out):
    return grid_shape(inp) == grid_shape(out)


# --- color_permutation checks ---

def check_global_color_map(train_pairs):
    """Check if a consistent global {color_in -> color_out} mapping works across
    all training pairs.  Returns (works, mapping_or_None, conflict_details)."""
    global_map = {}
    conflicts = []
    for pair_idx, (inp, out) in enumerate(train_pairs):
        if grid_shape(inp) != grid_shape(out):
            return False, None, [f"pair {pair_idx}: shape mismatch"]
        h, w = grid_shape(inp)
        for r in range(h):
            for c in range(w):
                ci = inp[r][c]
                co = out[r][c]
                if ci in global_map:
                    if global_map[ci] != co:
                        conflicts.append(
                            f"pair {pair_idx} ({r},{c}): {ci}->{co} conflicts with {ci}->{global_map[ci]}"
                        )
                else:
                    global_map[ci] = co
    works = len(conflicts) == 0
    return works, global_map if works else None, conflicts[:5]


def check_color_map_is_permutation(mapping):
    """Check if a color map is a true permutation (bijective)."""
    if mapping is None:
        return False
    vals = list(mapping.values())
    return len(set(vals)) == len(vals)


# --- crop_extract checks ---

def is_subgrid(small, big):
    """Check if small grid appears as a contiguous subgrid within big grid."""
    sh, sw = grid_shape(small)
    bh, bw = grid_shape(big)
    if sh > bh or sw > bw:
        return False, None
    for r in range(bh - sh + 1):
        for c in range(bw - sw + 1):
            match = True
            for dr in range(sh):
                for dc in range(sw):
                    if big[r + dr][c + dc] != small[dr][dc]:
                        match = False
                        break
                if not match:
                    break
            if match:
                return True, (r, c)
    return False, None


def has_separator_lines(grid):
    """Check if the grid contains full horizontal or vertical lines of a single color
    that act as separators (a full row or column with one non-background color)."""
    arr = np.array(grid, dtype=int)
    h, w = arr.shape
    h_seps = []
    v_seps = []

    for r in range(h):
        row_vals = set(arr[r, :].tolist())
        if len(row_vals) == 1 and 0 not in row_vals:
            h_seps.append((r, row_vals.pop()))
        elif len(row_vals) == 1 and row_vals == {0}:
            pass  # all-zero rows are background, not separators
        elif len(row_vals) == 2 and 0 not in row_vals:
            pass  # mixed non-bg rows are not separators

    for c in range(w):
        col_vals = set(arr[:, c].tolist())
        if len(col_vals) == 1 and 0 not in col_vals:
            v_seps.append((c, col_vals.pop()))

    return h_seps, v_seps


# --- symmetry_completion checks ---

def check_partial_symmetry(grid):
    """Check horizontal and vertical mirror symmetry fractions."""
    arr = np.array(grid, dtype=int)
    h, w = arr.shape

    # Vertical axis symmetry (left-right mirror)
    lr_match = np.sum(arr == np.fliplr(arr))
    lr_total = h * w
    lr_frac = lr_match / lr_total if lr_total > 0 else 0.0

    # Horizontal axis symmetry (top-bottom mirror)
    ud_match = np.sum(arr == np.flipud(arr))
    ud_frac = ud_match / lr_total if lr_total > 0 else 0.0

    return {
        "vertical_symmetry": round(lr_frac, 3),
        "horizontal_symmetry": round(ud_frac, 3),
        "max_symmetry": round(max(lr_frac, ud_frac), 3),
        "best_axis": "vertical" if lr_frac >= ud_frac else "horizontal",
    }


def check_output_completes_symmetry(inp, out):
    """Check if the output is more symmetric than the input."""
    if grid_shape(inp) != grid_shape(out):
        return {"completes": False, "note": "different shapes"}
    in_sym = check_partial_symmetry(inp)
    out_sym = check_partial_symmetry(out)
    in_max = in_sym["max_symmetry"]
    out_max = out_sym["max_symmetry"]
    delta = out_max - in_max
    return {
        "completes": delta > 0.05,
        "input_max_sym": in_max,
        "output_max_sym": out_max,
        "delta": round(delta, 3),
        "in_best_axis": in_sym["best_axis"],
        "out_best_axis": out_sym["best_axis"],
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_color_permutation(task_id, challenge, solution):
    """Analyze one color_permutation task."""
    train_pairs = [(ex["input"], ex["output"]) for ex in challenge["train"]]
    test_inputs = [ex["input"] for ex in challenge["test"]]
    test_outputs = solution  # list of output grids

    results = {"task_id": task_id, "category": "color_permutation"}

    # Shapes
    shapes = []
    for inp, out in train_pairs:
        shapes.append((grid_shape(inp), grid_shape(out)))
    results["train_shapes"] = shapes
    results["same_size"] = all(s[0] == s[1] for s in shapes)

    # Colors
    all_in_colors = set()
    all_out_colors = set()
    for inp, out in train_pairs:
        all_in_colors |= grid_colors(inp)
        all_out_colors |= grid_colors(out)
    results["input_colors"] = sorted(all_in_colors)
    results["output_colors"] = sorted(all_out_colors)
    results["colors_same_set"] = all_in_colors == all_out_colors

    # Global color map check
    works, mapping, conflicts = check_global_color_map(train_pairs)
    results["global_color_map_works"] = works
    results["global_color_map"] = mapping
    results["is_permutation"] = check_color_map_is_permutation(mapping)
    if not works:
        results["color_map_conflicts"] = conflicts

    return results


def analyze_crop_extract(task_id, challenge, solution):
    """Analyze one crop_extract task."""
    train_pairs = [(ex["input"], ex["output"]) for ex in challenge["train"]]

    results = {"task_id": task_id, "category": "crop_extract"}

    # Shapes
    shapes = []
    for inp, out in train_pairs:
        shapes.append((grid_shape(inp), grid_shape(out)))
    results["train_shapes"] = shapes
    results["same_size"] = all(s[0] == s[1] for s in shapes)

    # Colors
    all_in_colors = set()
    all_out_colors = set()
    for inp, out in train_pairs:
        all_in_colors |= grid_colors(inp)
        all_out_colors |= grid_colors(out)
    results["input_colors"] = sorted(all_in_colors)
    results["output_colors"] = sorted(all_out_colors)

    # Subgrid check
    subgrid_results = []
    for pair_idx, (inp, out) in enumerate(train_pairs):
        found, pos = is_subgrid(out, inp)
        subgrid_results.append({"pair": pair_idx, "output_is_subgrid": found, "position": pos})
    results["subgrid_checks"] = subgrid_results
    results["all_outputs_are_subgrids"] = all(sr["output_is_subgrid"] for sr in subgrid_results)

    # Separator line check
    sep_results = []
    for pair_idx, (inp, out) in enumerate(train_pairs):
        h_seps, v_seps = has_separator_lines(inp)
        sep_results.append({
            "pair": pair_idx,
            "horizontal_separators": h_seps,
            "vertical_separators": v_seps,
            "has_separators": len(h_seps) > 0 or len(v_seps) > 0,
        })
    results["separator_checks"] = sep_results
    results["any_has_separators"] = any(sr["has_separators"] for sr in sep_results)

    return results


def analyze_symmetry_completion(task_id, challenge, solution):
    """Analyze one symmetry_completion task."""
    train_pairs = [(ex["input"], ex["output"]) for ex in challenge["train"]]

    results = {"task_id": task_id, "category": "symmetry_completion"}

    # Shapes
    shapes = []
    for inp, out in train_pairs:
        shapes.append((grid_shape(inp), grid_shape(out)))
    results["train_shapes"] = shapes
    results["same_size"] = all(s[0] == s[1] for s in shapes)

    # Colors
    all_in_colors = set()
    all_out_colors = set()
    for inp, out in train_pairs:
        all_in_colors |= grid_colors(inp)
        all_out_colors |= grid_colors(out)
    results["input_colors"] = sorted(all_in_colors)
    results["output_colors"] = sorted(all_out_colors)

    # Symmetry analysis per pair
    sym_results = []
    for pair_idx, (inp, out) in enumerate(train_pairs):
        in_sym = check_partial_symmetry(inp)
        out_sym = check_partial_symmetry(out)
        completion = check_output_completes_symmetry(inp, out)
        sym_results.append({
            "pair": pair_idx,
            "input_symmetry": in_sym,
            "output_symmetry": out_sym,
            "completion": completion,
        })
    results["symmetry_analysis"] = sym_results
    results["any_completes_symmetry"] = any(
        sr["completion"]["completes"] for sr in sym_results
    )
    results["all_complete_symmetry"] = all(
        sr["completion"]["completes"] for sr in sym_results
    )

    return results


def format_results_md(all_results, summary_stats):
    """Format all results as a markdown report."""
    lines = []
    lines.append("# Unsolved ARC Task Analysis")
    lines.append("")
    lines.append("Analysis of the first 10 unsolved tasks in each of the 3 largest unsolved categories.")
    lines.append("")

    # --- Summary ---
    lines.append("## Summary")
    lines.append("")
    for cat, stats in summary_stats.items():
        lines.append(f"### {cat}")
        lines.append(f"- Tasks sampled: {stats['sampled']}")
        for key, val in stats.items():
            if key != "sampled":
                lines.append(f"- {key}: {val}")
        lines.append("")

    # --- Detailed results ---
    for cat in CATEGORIES_OF_INTEREST:
        lines.append(f"## {cat} (detailed)")
        lines.append("")
        cat_results = [r for r in all_results if r["category"] == cat]
        for r in cat_results:
            lines.append(f"### Task: {r['task_id']}")
            lines.append("")
            lines.append(f"- **Same size**: {r['same_size']}")
            shapes_str = ", ".join(
                f"pair {i}: {s[0]} -> {s[1]}" for i, s in enumerate(r["train_shapes"])
            )
            lines.append(f"- **Shapes**: {shapes_str}")
            lines.append(f"- **Input colors**: {r['input_colors']}")
            lines.append(f"- **Output colors**: {r['output_colors']}")

            if cat == "color_permutation":
                lines.append(f"- **Global color map works**: {r['global_color_map_works']}")
                if r["global_color_map_works"]:
                    lines.append(f"- **Color map**: {r['global_color_map']}")
                    lines.append(f"- **Is bijective permutation**: {r['is_permutation']}")
                else:
                    lines.append(f"- **Conflicts (first 5)**: {r.get('color_map_conflicts', [])}")

            elif cat == "crop_extract":
                for sc in r["subgrid_checks"]:
                    lines.append(
                        f"  - Pair {sc['pair']}: output is subgrid = {sc['output_is_subgrid']}"
                        + (f" at {sc['position']}" if sc['position'] else "")
                    )
                lines.append(f"- **All outputs are subgrids**: {r['all_outputs_are_subgrids']}")
                lines.append(f"- **Any input has separator lines**: {r['any_has_separators']}")
                if r["any_has_separators"]:
                    for sc in r["separator_checks"]:
                        if sc["has_separators"]:
                            lines.append(
                                f"  - Pair {sc['pair']}: h_seps={sc['horizontal_separators']}, "
                                f"v_seps={sc['vertical_separators']}"
                            )

            elif cat == "symmetry_completion":
                for sa in r["symmetry_analysis"]:
                    p = sa["pair"]
                    isym = sa["input_symmetry"]
                    osym = sa["output_symmetry"]
                    comp = sa["completion"]
                    lines.append(
                        f"  - Pair {p}: input sym={isym['max_symmetry']} ({isym['best_axis']}), "
                        f"output sym={osym['max_symmetry']} ({osym['best_axis']}), "
                        f"completes={comp['completes']} (delta={comp.get('delta', 'N/A')})"
                    )
                lines.append(f"- **Any pair completes symmetry**: {r['any_completes_symmetry']}")
                lines.append(f"- **All pairs complete symmetry**: {r['all_complete_symmetry']}")

            lines.append("")

    return "\n".join(lines)


def main():
    print("Loading taxonomy CSV...")
    taxonomy = load_taxonomy()

    print("Loading ARC raw data...")
    challenges, solutions = load_arc_raw()

    # Build category -> unsolved task_ids (sorted, for reproducibility)
    cat_unsolved = defaultdict(list)
    for row in taxonomy:
        if row["solved"] == "False":
            cat_unsolved[row["category"]].append(row["task_id"])

    print("\nUnsolved counts by category:")
    for cat in sorted(cat_unsolved.keys()):
        print(f"  {cat}: {len(cat_unsolved[cat])}")

    # Sample first N unsolved in each target category
    all_results = []
    summary_stats = {}

    for cat in CATEGORIES_OF_INTEREST:
        unsolved_ids = cat_unsolved[cat][:SAMPLE_SIZE]
        print(f"\n{'='*70}")
        print(f"Analyzing {cat}: {len(unsolved_ids)} tasks")
        print(f"{'='*70}")

        cat_results = []
        for tid in unsolved_ids:
            if tid not in challenges:
                print(f"  WARNING: {tid} not found in challenges file, skipping")
                continue
            sol = solutions.get(tid, [])
            print(f"\n  Task {tid}:")

            if cat == "color_permutation":
                r = analyze_color_permutation(tid, challenges[tid], sol)
            elif cat == "crop_extract":
                r = analyze_crop_extract(tid, challenges[tid], sol)
            elif cat == "symmetry_completion":
                r = analyze_symmetry_completion(tid, challenges[tid], sol)
            else:
                continue

            cat_results.append(r)

            # Print condensed summary
            print(f"    Same size: {r['same_size']}")
            print(f"    In colors:  {r['input_colors']}")
            print(f"    Out colors: {r['output_colors']}")
            shapes = r["train_shapes"]
            for i, (si, so) in enumerate(shapes):
                print(f"    Pair {i}: {si} -> {so}")

            if cat == "color_permutation":
                print(f"    Global color map works: {r['global_color_map_works']}")
                if r["global_color_map_works"]:
                    print(f"    Map: {r['global_color_map']}")
                    print(f"    Bijective: {r['is_permutation']}")
                else:
                    print(f"    Conflicts: {r.get('color_map_conflicts', [])}")

            elif cat == "crop_extract":
                for sc in r["subgrid_checks"]:
                    print(f"    Pair {sc['pair']}: subgrid={sc['output_is_subgrid']} pos={sc['position']}")
                print(f"    All subgrids: {r['all_outputs_are_subgrids']}")
                print(f"    Has separators: {r['any_has_separators']}")

            elif cat == "symmetry_completion":
                for sa in r["symmetry_analysis"]:
                    p = sa["pair"]
                    isym = sa["input_symmetry"]
                    comp = sa["completion"]
                    print(f"    Pair {p}: in_sym={isym['max_symmetry']} completes={comp['completes']} delta={comp.get('delta','N/A')}")
                print(f"    All complete symmetry: {r['all_complete_symmetry']}")

        all_results.extend(cat_results)

        # Compute category-level summary stats
        n = len(cat_results)
        if cat == "color_permutation":
            n_map_works = sum(1 for r in cat_results if r["global_color_map_works"])
            n_bijective = sum(1 for r in cat_results if r["is_permutation"])
            n_same_size = sum(1 for r in cat_results if r["same_size"])
            summary_stats[cat] = {
                "sampled": n,
                "same_size": f"{n_same_size}/{n}",
                "global_color_map_works": f"{n_map_works}/{n}",
                "bijective_permutation": f"{n_bijective}/{n}",
            }
        elif cat == "crop_extract":
            n_subgrid = sum(1 for r in cat_results if r["all_outputs_are_subgrids"])
            n_seps = sum(1 for r in cat_results if r["any_has_separators"])
            n_same_size = sum(1 for r in cat_results if r["same_size"])
            summary_stats[cat] = {
                "sampled": n,
                "same_size": f"{n_same_size}/{n}",
                "output_is_subgrid_of_input": f"{n_subgrid}/{n}",
                "input_has_separator_lines": f"{n_seps}/{n}",
            }
        elif cat == "symmetry_completion":
            n_all_complete = sum(1 for r in cat_results if r["all_complete_symmetry"])
            n_any_complete = sum(1 for r in cat_results if r["any_completes_symmetry"])
            n_same_size = sum(1 for r in cat_results if r["same_size"])
            summary_stats[cat] = {
                "sampled": n,
                "same_size": f"{n_same_size}/{n}",
                "all_pairs_complete_symmetry": f"{n_all_complete}/{n}",
                "any_pair_completes_symmetry": f"{n_any_complete}/{n}",
            }

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for cat, stats in summary_stats.items():
        print(f"\n{cat}:")
        for key, val in stats.items():
            print(f"  {key}: {val}")

    # Write output
    md_content = format_results_md(all_results, summary_stats)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MD, "w") as f:
        f.write(md_content)
    print(f"\nWrote detailed report to {OUTPUT_MD}")


if __name__ == "__main__":
    main()
