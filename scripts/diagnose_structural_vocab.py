#!/usr/bin/env python3
"""STRUCTURAL VOCABULARY DIAGNOSIS (R15-R18 method: census -> trace -> NAME)

For a sample of 40 tasks drawn from the 194 LOO-fail + 75 vocabulary-blocked
sets:
  (1) Load the persisted overfit/partial program
  (2) Render it on each train pair
  (3) Compute per-fold TEST-TIME divergence (what the overfit program gets
      wrong on held-out folds)
  (4) CHARACTERIZE each divergence structurally: position, color, count,
      shape, ordering, conditional
  (5) Cluster characterizations across tasks
  (6) For top-5 clusters: human-readable name + 2 exemplar task ids +
      pixel-level trace

OUTPUT:
  outputs/structural_vocab_census.json
  docs/STRUCTURAL_VOCAB_CANDIDATES.md

Usage:
    python3 scripts/diagnose_structural_vocab.py
    python3 scripts/diagnose_structural_vocab.py --max-tasks 10  # quick
"""
import argparse
import collections
import json
import os
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = os.environ.get(
    "ARC_PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import numpy as np

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_arc_data():
    """Load ARC training challenges and solutions."""
    arc_dir = Path(PROJECT_ROOT) / "data" / "arc"
    with open(arc_dir / "arc-agi_training_challenges.json") as f:
        challenges = json.load(f)
    sol_path = arc_dir / "arc-agi_training_solutions.json"
    solutions = {}
    if sol_path.exists():
        with open(sol_path) as f:
            solutions = json.load(f)
    return challenges, solutions


def load_graduation_results():
    """Load graduation results, return {task_id: record}."""
    grad_path = (Path(PROJECT_ROOT) /
                 "outputs/graduation_r1_contention/graduation_results.jsonl")
    records = {}
    with open(grad_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            records[d["task_id"]] = d
    return records


def load_near_solve_program(task_id, near_solve_dir):
    """Load the best near-solve program dict for a task."""
    ns_path = near_solve_dir / f"{task_id}.jsonl"
    if not ns_path.exists():
        return None, None
    best_fit = -1.0
    best_rec = None
    with open(ns_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                fit = rec.get("train_fit_pixels", 0)
                if fit > best_fit:
                    best_fit = fit
                    best_rec = rec
            except json.JSONDecodeError:
                continue
    if best_rec is None:
        return None, None
    return best_rec.get("program_partial"), best_rec


def render_program_safe(program_dict, input_arr):
    """Render a program dict on an input array. Returns numpy array or None."""
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.actions import render_program
    from geocat_arc.object_reasoning.types import (
        ObjectProgram, GenerativeProgram, ReductionProgram,
        FramedProgram, ComposedProgram,
    )
    from geocat_arc.object_reasoning.expressions import EvalError

    try:
        grid_in = Grid(np.array(input_arr, dtype=np.int32))
        # Determine program type
        prog_dict = program_dict
        if "stages" in prog_dict:
            prog = ComposedProgram.from_dict(prog_dict)
        elif prog_dict.get("split", {}).get("kind") in (
                "pixel_rule", "symmetry", "counting", None):
            if "split" in prog_dict:
                prog = ReductionProgram.from_dict(prog_dict)
            elif "generators" in prog_dict:
                prog = GenerativeProgram.from_dict(prog_dict)
            elif "inner" in prog_dict and "frame" in prog_dict:
                prog = FramedProgram.from_dict(prog_dict)
            else:
                prog = ObjectProgram.from_dict(prog_dict)
        elif "generators" in prog_dict:
            prog = GenerativeProgram.from_dict(prog_dict)
        elif "inner" in prog_dict and "frame" in prog_dict:
            prog = FramedProgram.from_dict(prog_dict)
        else:
            prog = ObjectProgram.from_dict(prog_dict)
        result = render_program(prog, grid_in)
        return result.to_numpy()
    except (EvalError, Exception) as e:
        return None


def compute_divergence(predicted, expected):
    """Compute pixel-level divergence between predicted and expected grids.

    Returns dict with:
      - cells_wrong: int
      - total_cells: int
      - accuracy: float
      - wrong_positions: list of (r, c)
      - wrong_details: list of {r, c, predicted, expected}
      - shape_mismatch: bool
    """
    pred = np.array(predicted, dtype=np.int32)
    exp = np.array(expected, dtype=np.int32)

    if pred.shape != exp.shape:
        return {
            "cells_wrong": int(np.prod(exp.shape)),
            "total_cells": int(np.prod(exp.shape)),
            "accuracy": 0.0,
            "wrong_positions": [],
            "wrong_details": [],
            "shape_mismatch": True,
            "pred_shape": list(pred.shape),
            "exp_shape": list(exp.shape),
        }

    diff_mask = pred != exp
    wrong_positions = list(zip(*np.where(diff_mask)))
    wrong_details = []
    for r, c in wrong_positions:
        wrong_details.append({
            "r": int(r), "c": int(c),
            "predicted": int(pred[r, c]),
            "expected": int(exp[r, c]),
        })

    return {
        "cells_wrong": int(diff_mask.sum()),
        "total_cells": int(np.prod(exp.shape)),
        "accuracy": float(1.0 - diff_mask.sum() / np.prod(exp.shape)),
        "wrong_positions": [(int(r), int(c)) for r, c in wrong_positions],
        "wrong_details": wrong_details,
        "shape_mismatch": False,
    }


# ---------------------------------------------------------------------------
# Structural characterization of divergence
# ---------------------------------------------------------------------------

def characterize_divergence(divergence, input_arr, expected_arr, predicted_arr,
                            program_dict, all_train_pairs):
    """Characterize a divergence structurally.

    Returns a list of structural tags, each a dict:
      {category: str, description: str, evidence: dict}

    Categories: position, color, count, shape, ordering, conditional,
                pattern_fill, size_dependent, relational_position,
                object_correspondence, fused_output
    """
    tags = []
    if divergence["shape_mismatch"]:
        tags.append({
            "category": "shape",
            "subcategory": "output_size_varies",
            "description": "Output grid size varies across pairs; "
                           "program uses fixed size",
            "evidence": {
                "pred_shape": divergence.get("pred_shape"),
                "exp_shape": divergence.get("exp_shape"),
            }
        })
        return tags

    if not divergence["wrong_details"]:
        return tags

    inp = np.array(input_arr, dtype=np.int32)
    exp = np.array(expected_arr, dtype=np.int32)
    pred = np.array(predicted_arr, dtype=np.int32) if predicted_arr is not None else None

    wrong = divergence["wrong_details"]
    n_wrong = len(wrong)
    total = divergence["total_cells"]

    # ---- Analyze the wrong cells ----

    # 1. Color analysis: are wrong cells all one color? Is expected color
    #    derivable from input?
    expected_colors = set(w["expected"] for w in wrong)
    predicted_colors = set(w["predicted"] for w in wrong)
    input_colors = set(inp.flatten().tolist())

    # Check if expected colors at wrong positions are input-derived
    novel_colors = expected_colors - input_colors
    if novel_colors:
        tags.append({
            "category": "color",
            "subcategory": "novel_color_in_output",
            "description": f"Output uses color(s) {novel_colors} not in input",
            "evidence": {"novel_colors": sorted(novel_colors),
                         "input_colors": sorted(input_colors)},
        })

    # Check if wrong cells have color that depends on position/context
    color_varies_by_position = len(expected_colors) > 1
    if color_varies_by_position and n_wrong > 2:
        tags.append({
            "category": "color",
            "subcategory": "color_function_of_context",
            "description": "Wrong cells need different colors depending on position",
            "evidence": {"n_distinct_expected_colors": len(expected_colors)},
        })

    # 2. Position analysis: where are wrong cells relative to objects?
    wrong_rs = [w["r"] for w in wrong]
    wrong_cs = [w["c"] for w in wrong]

    # Check for row/column alignment patterns
    row_counts = collections.Counter(wrong_rs)
    col_counts = collections.Counter(wrong_cs)
    max_row_count = max(row_counts.values()) if row_counts else 0
    max_col_count = max(col_counts.values()) if col_counts else 0

    h, w_grid = exp.shape
    # Are wrong cells on full rows or columns?
    if max_row_count >= w_grid * 0.8 and len(row_counts) <= 3:
        tags.append({
            "category": "position",
            "subcategory": "full_row_divergence",
            "description": "Divergent cells span full row(s) -- "
                           "likely row-based line/fill operation",
            "evidence": {"rows_affected": len(row_counts),
                         "max_cells_per_row": max_row_count},
        })
    if max_col_count >= h * 0.8 and len(col_counts) <= 3:
        tags.append({
            "category": "position",
            "subcategory": "full_col_divergence",
            "description": "Divergent cells span full column(s) -- "
                           "likely column-based line/fill operation",
            "evidence": {"cols_affected": len(col_counts),
                         "max_cells_per_col": max_col_count},
        })

    # Check for rectangular region of wrong cells
    r_min, r_max = min(wrong_rs), max(wrong_rs)
    c_min, c_max = min(wrong_cs), max(wrong_cs)
    bbox_area = (r_max - r_min + 1) * (c_max - c_min + 1)
    fill_ratio = n_wrong / max(bbox_area, 1)
    if fill_ratio > 0.7 and n_wrong > 4:
        tags.append({
            "category": "position",
            "subcategory": "rectangular_fill",
            "description": f"Wrong cells form a rectangular block "
                           f"({r_max-r_min+1}x{c_max-c_min+1}, "
                           f"fill={fill_ratio:.2f})",
            "evidence": {"bbox": [r_min, c_min, r_max, c_max],
                         "fill_ratio": round(fill_ratio, 3)},
        })

    # 3. Pattern analysis: is the expected pattern a shifted/scaled copy
    #    of something in input?
    # Check if wrong expected cells form a pattern that matches an input object
    expected_patch = exp[r_min:r_max+1, c_min:c_max+1]
    input_patch = inp[r_min:r_max+1, c_min:c_max+1]
    if pred is not None:
        pred_patch = pred[r_min:r_max+1, c_min:c_max+1]
    else:
        pred_patch = None

    # 4. Relational position analysis: do wrong positions depend on
    #    the positions of OTHER objects?
    # Look for wrong cells between objects or at specific offsets from objects
    # Find input objects as connected components
    from scipy import ndimage
    bg_val = int(collections.Counter(inp.flatten().tolist()).most_common(1)[0][0])
    obj_mask = inp != bg_val
    labeled, n_objs = ndimage.label(obj_mask)

    if n_objs >= 2:
        # Check if wrong cells are BETWEEN objects
        obj_centers = ndimage.center_of_mass(obj_mask, labeled,
                                              range(1, n_objs + 1))
        obj_bboxes = ndimage.find_objects(labeled)

        # Are wrong cells outside all object bboxes? (extension/ray pattern)
        wrong_set = set((w["r"], w["c"]) for w in wrong)
        inside_count = 0
        for bbox in obj_bboxes:
            if bbox is None:
                continue
            for r, c in wrong_set:
                if (bbox[0].start <= r < bbox[0].stop and
                    bbox[1].start <= c < bbox[1].stop):
                    inside_count += 1
        outside_ratio = 1.0 - inside_count / max(n_wrong, 1)

        if outside_ratio > 0.7 and n_wrong > 2:
            tags.append({
                "category": "position",
                "subcategory": "extension_beyond_objects",
                "description": f"{outside_ratio:.0%} of wrong cells are outside "
                               f"any input object bbox -- likely ray/line/extension",
                "evidence": {"outside_ratio": round(outside_ratio, 3),
                             "n_objects": n_objs},
            })

        # Check if wrong cells connect two objects (connector pattern)
        # Find which objects the wrong cells are adjacent to
        connected_objs = set()
        for r, c in wrong_set:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w_grid and labeled[nr, nc] > 0:
                    connected_objs.add(int(labeled[nr, nc]))
        if len(connected_objs) >= 2:
            tags.append({
                "category": "position",
                "subcategory": "connector_between_objects",
                "description": f"Wrong cells are adjacent to {len(connected_objs)} "
                               f"different objects -- likely connector/bridge",
                "evidence": {"connected_objects": len(connected_objs)},
            })

    # 5. Count analysis: does the count of some output feature depend
    #    on a count in the input?
    # Check if different training pairs have different counts of wrong cells
    # (handled at task level in the main loop)

    # 6. Conditional analysis: is there a subset of wrong cells that
    #    appears only under certain conditions?
    # Check if wrong cells have different expected values depending
    # on neighboring input values
    if pred is not None and n_wrong > 2:
        # Group wrong cells by their neighborhood in input
        neighborhoods = {}
        for w in wrong:
            r, c = w["r"], w["c"]
            # 3x3 neighborhood
            patch_vals = []
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w_grid:
                        patch_vals.append(int(inp[nr, nc]))
                    else:
                        patch_vals.append(-1)
            key = tuple(patch_vals)
            if key not in neighborhoods:
                neighborhoods[key] = []
            neighborhoods[key].append(w["expected"])

        # If same neighborhood -> same expected color: CONDITIONAL rule
        consistent = sum(1 for vs in neighborhoods.values()
                         if len(set(vs)) == 1)
        if consistent > 0.7 * len(neighborhoods) and len(neighborhoods) > 1:
            tags.append({
                "category": "conditional",
                "subcategory": "neighborhood_conditional",
                "description": "Expected color at wrong cells depends on "
                               "local input neighborhood (if-then structure)",
                "evidence": {"n_neighborhoods": len(neighborhoods),
                             "consistent_ratio": round(
                                 consistent / len(neighborhoods), 3)},
            })

    # 7. Check for symmetry-related divergence
    if n_wrong > 2 and not divergence["shape_mismatch"]:
        # Check if wrong cells are symmetric about some axis
        wrong_arr = np.zeros_like(exp, dtype=bool)
        for w in wrong:
            wrong_arr[w["r"], w["c"]] = True
        # Horizontal symmetry
        if np.array_equal(wrong_arr, np.flipud(wrong_arr)):
            tags.append({
                "category": "shape",
                "subcategory": "symmetric_divergence_h",
                "description": "Wrong cells are horizontally symmetric",
                "evidence": {},
            })
        # Vertical symmetry
        if np.array_equal(wrong_arr, np.fliplr(wrong_arr)):
            tags.append({
                "category": "shape",
                "subcategory": "symmetric_divergence_v",
                "description": "Wrong cells are vertically symmetric",
                "evidence": {},
            })

    # 8. Analyze program structure for overfitting signals
    if program_dict:
        rules = program_dict.get("rules", [])
        for rule in rules:
            action = rule.get("action", {})
            params = action.get("params", {})
            param_class = action.get("parameter_class", "")

            # Check for extensional patterns (literal pixel lists)
            if action.get("delta_type") == "grow":
                mode_param = params.get("mode", {})
                if isinstance(mode_param, dict):
                    mode_val = mode_param.get("args", [None])[0]
                    if mode_val == "pattern":
                        pattern_param = params.get("pattern", {})
                        if isinstance(pattern_param, dict):
                            pargs = pattern_param.get("args", [None])
                            if pargs and isinstance(pargs[0], (dict, list)):
                                # Count pattern cells
                                if isinstance(pargs[0], dict) and "__tuple__" in pargs[0]:
                                    n_cells = len(pargs[0]["__tuple__"])
                                elif isinstance(pargs[0], list):
                                    n_cells = len(pargs[0])
                                else:
                                    n_cells = 0
                                if n_cells > 3:
                                    tags.append({
                                        "category": "position",
                                        "subcategory": "extensional_pattern",
                                        "description": f"Program uses literal pixel "
                                                       f"pattern ({n_cells} cells) -- "
                                                       f"the CORE overfitting mode",
                                        "evidence": {"n_pattern_cells": n_cells,
                                                     "delta_type": "grow"},
                                    })

            # Check for shape_sig selectors (hash-based, not generalizable)
            selector = rule.get("selector", {})
            pred = selector.get("predicate", {})
            if isinstance(pred, dict):
                args = pred.get("args", [])
                if len(args) >= 2 and args[0] == "shape_sig":
                    tags.append({
                        "category": "shape",
                        "subcategory": "shape_hash_selector",
                        "description": "Selector uses shape_sig hash -- "
                                       "cannot generalize to unseen shapes",
                        "evidence": {"shape_sig": args[2] if len(args) > 2 else ""},
                    })

            # Check for color-const parameters
            for pk, pv in params.items():
                if pk == "color" and isinstance(pv, dict) and pv.get("op") == "const":
                    color_val = pv.get("args", [None])[0]
                    tags.append({
                        "category": "color",
                        "subcategory": "constant_color_param",
                        "description": f"Color parameter is constant ({color_val}) -- "
                                       f"may need to be input-derived",
                        "evidence": {"color": color_val, "param": pk},
                    })

    # 9. Cross-pair consistency analysis
    if len(all_train_pairs) > 1:
        # Check if number of objects changes across pairs
        n_objs_per_pair = []
        for inp_p, _ in all_train_pairs:
            inp_a = np.array(inp_p, dtype=np.int32)
            bg = int(collections.Counter(inp_a.flatten().tolist()).most_common(1)[0][0])
            mask = inp_a != bg
            _, n = ndimage.label(mask)
            n_objs_per_pair.append(n)
        if len(set(n_objs_per_pair)) > 1:
            tags.append({
                "category": "count",
                "subcategory": "varying_object_count",
                "description": f"Object count varies across pairs: "
                               f"{n_objs_per_pair}",
                "evidence": {"counts": n_objs_per_pair},
            })

    # If no specific tags found, add a generic one
    if not tags:
        tags.append({
            "category": "unknown",
            "subcategory": "uncharacterized",
            "description": f"Divergence at {n_wrong}/{total} cells, "
                           f"no specific structural pattern detected",
            "evidence": {"n_wrong": n_wrong, "total": total},
        })

    return tags


def summarize_task_characterization(per_fold_tags):
    """Merge per-fold tags into a task-level characterization."""
    # Collect all (category, subcategory) pairs and their frequencies
    tag_counts = collections.Counter()
    tag_details = {}
    for fold_idx, tags in enumerate(per_fold_tags):
        for tag in tags:
            key = (tag["category"], tag["subcategory"])
            tag_counts[key] += 1
            if key not in tag_details:
                tag_details[key] = tag
    return tag_counts, tag_details


def generate_pixel_trace(task_id, task_data, program_dict, fold_idx):
    """Generate a pixel-level trace for one fold divergence.

    Returns a dict with input/expected/predicted grids and the diff mask,
    all as lists-of-lists for JSON serialization.
    """
    pairs = task_data["train"]
    n = len(pairs)

    # Build LOO training set (all pairs except fold_idx)
    train_subset_in = [pairs[i]["input"] for i in range(n) if i != fold_idx]
    train_subset_out = [pairs[i]["output"] for i in range(n) if i != fold_idx]

    # The held-out pair
    held_in = pairs[fold_idx]["input"]
    held_out = pairs[fold_idx]["output"]

    # Render the overfit program on the held-out input
    rendered = render_program_safe(program_dict, held_in)
    if rendered is None:
        return None

    exp = np.array(held_out, dtype=np.int32)
    if rendered.shape != exp.shape:
        diff = np.ones_like(exp, dtype=bool).tolist()
    else:
        diff = (rendered != exp).tolist()

    return {
        "task_id": task_id,
        "fold": fold_idx,
        "input": held_in,
        "expected": [[int(c) for c in row] for row in exp],
        "predicted": [[int(c) for c in row] for row in rendered],
        "diff_mask": diff,
        "cells_wrong": int(np.sum(rendered != exp)) if rendered.shape == exp.shape
                       else int(np.prod(exp.shape)),
    }


# ---------------------------------------------------------------------------
# Main diagnosis loop
# ---------------------------------------------------------------------------

def main():
    t_global_start = time.monotonic()

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tasks", type=int, default=40,
                    help="Tasks to sample (default 40)")
    ap.add_argument("--near-solve-dir", default=os.path.join(
        PROJECT_ROOT, "outputs/unified_harness_v20/object/near_solve_parts"))
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for sampling")
    ap.add_argument("--out-dir", default=os.path.join(
        PROJECT_ROOT, "outputs"))
    ap.add_argument("--jsonl-log", default=os.path.join(
        PROJECT_ROOT, "logs/structural_vocab_diagnosis.jsonl"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.jsonl_log).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Open realtime JSONL log
    jsonl_f = open(args.jsonl_log, "w")

    def log_event(event_type, data):
        rec = {"t": round(time.monotonic() - t_global_start, 2),
               "event": event_type, **data}
        jsonl_f.write(json.dumps(rec) + "\n")
        jsonl_f.flush()

    log_event("start", {"max_tasks": args.max_tasks, "seed": args.seed})
    print("=== STRUCTURAL VOCABULARY DIAGNOSIS ===")
    print(f"Load > 23 -- CONTENTION NOTED (diagnosis is read-only, safe)")

    # -----------------------------------------------------------------------
    # 1. Load data
    # -----------------------------------------------------------------------
    challenges, solutions = load_arc_data()
    grad_results = load_graduation_results()

    loo_fail_ids = [tid for tid, r in grad_results.items()
                    if (r.get("partial_fit") or 0) >= 1.0]
    vocab_blocked_ids = [tid for tid, r in grad_results.items()
                         if (r.get("partial_fit") or 0) < 1.0]

    print(f"LOO-fail (194): {len(loo_fail_ids)}")
    print(f"Vocabulary-blocked (75): {len(vocab_blocked_ids)}")

    # -----------------------------------------------------------------------
    # 2. Sample 40 tasks: stratified (28 LOO-fail, 12 vocab-blocked)
    # -----------------------------------------------------------------------
    rng = random.Random(args.seed)
    n_total = min(args.max_tasks, len(loo_fail_ids) + len(vocab_blocked_ids))
    # Proportional: 194/(194+75) ~ 72% -> 29 LOO-fail, 11 vocab-blocked
    n_loo = min(int(n_total * 194 / 269 + 0.5), len(loo_fail_ids))
    n_vocab = min(n_total - n_loo, len(vocab_blocked_ids))

    sample_loo = sorted(rng.sample(loo_fail_ids, n_loo))
    sample_vocab = sorted(rng.sample(vocab_blocked_ids, n_vocab))
    sample = sample_loo + sample_vocab
    rng.shuffle(sample)

    print(f"Sample: {len(sample)} tasks "
          f"({n_loo} LOO-fail + {n_vocab} vocab-blocked)")
    log_event("sample", {"n_loo": n_loo, "n_vocab": n_vocab,
                          "task_ids": sample})

    near_solve_dir = Path(args.near_solve_dir)

    # -----------------------------------------------------------------------
    # 3. Process each task
    # -----------------------------------------------------------------------
    all_task_results = []
    global_tag_counter = collections.Counter()
    task_by_tag = collections.defaultdict(list)  # (cat, subcat) -> [task_ids]

    for idx, task_id in enumerate(sample):
        t_task = time.monotonic()
        print(f"\n[{idx+1}/{len(sample)}] Task {task_id}", end="", flush=True)

        if task_id not in challenges:
            print(" SKIP (not in challenges)")
            continue

        task_data = challenges[task_id]
        pairs = task_data["train"]
        n_pairs = len(pairs)
        task_type = "loo_fail" if task_id in set(loo_fail_ids) else "vocab_blocked"

        # Load program
        prog_dict, ns_record = load_near_solve_program(task_id, near_solve_dir)
        if prog_dict is None:
            print(" SKIP (no program)")
            log_event("skip", {"task_id": task_id, "reason": "no_program"})
            continue

        # Get the full program (train on all pairs)
        full_rendered = []
        for pair in pairs:
            r = render_program_safe(prog_dict, pair["input"])
            if r is not None:
                full_rendered.append(r)
            else:
                full_rendered.append(None)

        # Compute full-train fit
        full_train_match = 0
        for i, pair in enumerate(pairs):
            if full_rendered[i] is not None:
                exp_a = np.array(pair["output"], dtype=np.int32)
                if np.array_equal(full_rendered[i], exp_a):
                    full_train_match += 1
        full_train_fit = full_train_match / n_pairs

        # Per-fold LOO divergence: render the FULL program on each pair
        # and compute divergence (the overfit program was induced on ALL
        # pairs, so rendering on any one shows what it gets right/wrong
        # structurally -- but for LOO-fail tasks the key signal is that
        # the program is TRAIN-PERFECT but cannot generalize because
        # parameters are extensional/constant)
        per_fold_divergences = []
        per_fold_tags = []

        # For LOO-fail tasks (partial_fit=1.0): the program fits all
        # train pairs perfectly. The divergence we want is: when induced
        # on N-1 pairs, what goes wrong on the held-out? The stored LOO
        # divergence in the near-solve record tells us.
        # For vocab-blocked tasks: the program itself doesn't fit all
        # pairs, so we compute divergence directly.

        if task_type == "loo_fail" and ns_record:
            # Use stored LOO divergence if available
            loo_div = ns_record.get("residual", {}).get("loo_divergence", [])
            if loo_div:
                for ld in loo_div:
                    fold_idx = ld.get("fold", 0)
                    fold_prog = ld.get("fold_program")
                    cells_wrong = ld.get("cells_wrong", 0)

                    if fold_prog and fold_idx < n_pairs:
                        # Render the fold program on the held-out pair
                        held_in = pairs[fold_idx]["input"]
                        held_out = pairs[fold_idx]["output"]
                        rendered = render_program_safe(fold_prog, held_in)

                        if rendered is not None:
                            div = compute_divergence(
                                rendered, held_out)
                            per_fold_divergences.append({
                                "fold": fold_idx, **div})

                            # Characterize
                            all_train = [(p["input"], p["output"])
                                         for p in pairs]
                            tags = characterize_divergence(
                                div, held_in, held_out, rendered,
                                fold_prog, all_train)
                            per_fold_tags.append(tags)
                        else:
                            # Render error -- use cells_wrong from record
                            per_fold_divergences.append({
                                "fold": fold_idx,
                                "cells_wrong": cells_wrong,
                                "render_error": True,
                            })
                            per_fold_tags.append([])
                    else:
                        per_fold_divergences.append({
                            "fold": fold_idx,
                            "cells_wrong": cells_wrong,
                            "no_fold_program": True,
                        })
                        per_fold_tags.append([])
            else:
                # No stored LOO divergence -- render full program and diff
                for i, pair in enumerate(pairs):
                    r = full_rendered[i]
                    if r is not None:
                        div = compute_divergence(r, pair["output"])
                        per_fold_divergences.append({"fold": i, **div})
                        all_train = [(p["input"], p["output"]) for p in pairs]
                        tags = characterize_divergence(
                            div, pair["input"], pair["output"], r,
                            prog_dict, all_train)
                        per_fold_tags.append(tags)
                    else:
                        per_fold_divergences.append({
                            "fold": i, "render_error": True})
                        per_fold_tags.append([])
        else:
            # Vocab-blocked: compute divergence directly
            for i, pair in enumerate(pairs):
                r = full_rendered[i]
                if r is not None:
                    div = compute_divergence(r, pair["output"])
                    per_fold_divergences.append({"fold": i, **div})
                    all_train = [(p["input"], p["output"]) for p in pairs]
                    tags = characterize_divergence(
                        div, pair["input"], pair["output"], r,
                        prog_dict, all_train)
                    per_fold_tags.append(tags)
                else:
                    per_fold_divergences.append({
                        "fold": i, "render_error": True})
                    per_fold_tags.append([])

        # Summarize task-level characterization
        tag_counts, tag_details = summarize_task_characterization(per_fold_tags)

        # Update global counters
        for key, count in tag_counts.items():
            global_tag_counter[key] += 1  # count tasks, not folds
            task_by_tag[key].append(task_id)

        # Total wrong cells across folds
        total_wrong = sum(d.get("cells_wrong", 0) or 0
                          for d in per_fold_divergences)

        result = {
            "task_id": task_id,
            "task_type": task_type,
            "n_train_pairs": n_pairs,
            "full_train_fit": round(full_train_fit, 4),
            "delta_histogram": ns_record.get("delta_histogram", {})
                               if ns_record else {},
            "failure_stage": ns_record.get("failure_stage", "")
                             if ns_record else "",
            "n_folds_with_divergence": sum(
                1 for d in per_fold_divergences
                if (d.get("cells_wrong", 0) or 0) > 0),
            "total_cells_wrong": total_wrong,
            "structural_tags": [
                {"category": k[0], "subcategory": k[1],
                 "description": tag_details[k]["description"],
                 "fold_count": v}
                for k, v in tag_counts.most_common()
            ],
            "per_fold_summary": [
                {"fold": d.get("fold", i),
                 "cells_wrong": d.get("cells_wrong", 0) or 0,
                 "accuracy": round(d.get("accuracy", 0) or 0, 4)
                             if "accuracy" in d else None,
                 "shape_mismatch": d.get("shape_mismatch", False)}
                for i, d in enumerate(per_fold_divergences)
            ],
        }

        all_task_results.append(result)
        elapsed_task = time.monotonic() - t_task
        print(f" ({elapsed_task:.1f}s) tags={len(tag_counts)} "
              f"wrong={total_wrong}c", flush=True)
        log_event("task_done", {"task_id": task_id,
                                 "elapsed_s": round(elapsed_task, 2),
                                 "n_tags": len(tag_counts),
                                 "total_wrong": total_wrong})

        # Cap at 2.5h
        if time.monotonic() - t_global_start > 2.5 * 3600:
            print("\n--- 2.5h cap reached, stopping ---")
            log_event("cap_reached", {"tasks_done": idx + 1})
            break

    # -----------------------------------------------------------------------
    # 4. Cluster characterizations
    # -----------------------------------------------------------------------
    print("\n\n=== CLUSTERING ===")
    # Sort by task count
    ranked = global_tag_counter.most_common()
    print(f"Distinct structural tags: {len(ranked)}")
    for (cat, subcat), count in ranked:
        print(f"  {cat}/{subcat}: {count} tasks")

    # -----------------------------------------------------------------------
    # 5. Name top-5 clusters as structural vocabulary candidates
    # -----------------------------------------------------------------------
    # Map (category, subcategory) to candidate names
    CANDIDATE_NAMES = {
        ("position", "extensional_pattern"):
            "PATTERN-TO-RULE: extensional pixel patterns that need "
            "generative/relational rules",
        ("position", "extension_beyond_objects"):
            "RAY/LINE EXTENSION: cells placed along rays/lines beyond "
            "object boundaries",
        ("position", "connector_between_objects"):
            "INTER-OBJECT CONNECTOR: bridge/line drawn between two objects",
        ("position", "full_row_divergence"):
            "ROW-SPAN FILL: entire row(s) filled with a computed color",
        ("position", "full_col_divergence"):
            "COLUMN-SPAN FILL: entire column(s) filled with a computed color",
        ("position", "rectangular_fill"):
            "RECTANGULAR VOID FILL: rectangular region filled with "
            "input-derived content",
        ("color", "constant_color_param"):
            "COLOR-FROM-CONTEXT: color parameter that should be derived "
            "from scene context, not fixed",
        ("color", "color_function_of_context"):
            "POSITIONAL COLOR: color varies by position/neighborhood",
        ("color", "novel_color_in_output"):
            "COLOR INVENTION: output uses colors absent from input",
        ("shape", "shape_hash_selector"):
            "SHAPE-PROPERTY SELECTOR: selector uses shape hashes instead "
            "of generalizable shape properties",
        ("shape", "output_size_varies"):
            "SIZE-ADAPTIVE OUTPUT: output grid size depends on input content",
        ("conditional", "neighborhood_conditional"):
            "CONDITIONAL RULE: output depends on local neighborhood "
            "(if-then structure)",
        ("count", "varying_object_count"):
            "COUNT-ADAPTIVE: number of output elements depends on input count",
        ("shape", "symmetric_divergence_h"):
            "SYMMETRY COMPLETION: wrong cells form symmetric pattern",
        ("shape", "symmetric_divergence_v"):
            "SYMMETRY COMPLETION: wrong cells form symmetric pattern",
        ("unknown", "uncharacterized"):
            "UNCHARACTERIZED: no specific structural pattern detected",
    }

    BUILDABILITY = {
        ("position", "extensional_pattern"):
            "Current program shape stores literal patterns. Needs: "
            "generative mode that DERIVES pattern from object features "
            "(e.g., fill_interior + scale_to_container). Medium buildability "
            "-- delta type exists (grow), needs new generator logic.",
        ("position", "extension_beyond_objects"):
            "Partially covered by ray/line generators (R17). Gap: "
            "ray_until_obstacle, ray_through_absorbed, relational direction. "
            "HIGH buildability -- machinery exists, vocabulary extensions needed.",
        ("position", "connector_between_objects"):
            "CONNECT delta type exists but fires narrowly. Needs: "
            "wider connector induction (L-path, Manhattan, diagonal). "
            "MEDIUM buildability -- delta type exists.",
        ("position", "full_row_divergence"):
            "row_line/col_line generators exist (R17b). Gap: conditional "
            "row fills (only certain rows). MEDIUM buildability.",
        ("position", "full_col_divergence"):
            "col_line generators exist (R17b). See row fill above. "
            "MEDIUM buildability.",
        ("position", "rectangular_fill"):
            "fill_interior grow mode exists. Gap: fill relative to ANOTHER "
            "object (not self), or fill bounded by scene geometry. "
            "MEDIUM buildability -- new fill-region mode.",
        ("color", "constant_color_param"):
            "Phase C force_relational already tries this. The relift pass "
            "proved 0% success (R2). NOT expressible with current expression "
            "vocabulary -- needs richer feature expressions.",
        ("color", "color_function_of_context"):
            "Needs conditional color expressions (if-then or lookup). "
            "LOW buildability -- requires new expression type.",
        ("color", "novel_color_in_output"):
            "Needs color-arithmetic or color-mapping expressions. "
            "LOW buildability -- new expression type.",
        ("shape", "shape_hash_selector"):
            "Needs generalizable shape property predicates (convexity, "
            "symmetry axis, n_cells, aspect_ratio). HIGH buildability "
            "-- feature predicates exist, need more.",
        ("shape", "output_size_varies"):
            "Needs size-inference from input (count-based or content-based). "
            "NOT expressible in current program shapes.",
        ("conditional", "neighborhood_conditional"):
            "Needs conditional/case rules per cell. NOT expressible "
            "in current per-object rule structure -- needs per-pixel rules.",
        ("count", "varying_object_count"):
            "Handled by segmentation variants. The gap is programs that "
            "need to COUNT objects and use the count. MEDIUM buildability.",
        ("unknown", "uncharacterized"):
            "Diagnosis incomplete. Manual inspection needed.",
    }

    top5 = ranked[:5]
    candidates = []
    for rank, ((cat, subcat), count) in enumerate(top5):
        key = (cat, subcat)
        exemplars = task_by_tag[key][:2]

        # Generate pixel trace for first exemplar
        trace = None
        if exemplars and exemplars[0] in challenges:
            ex_task = challenges[exemplars[0]]
            prog_d, ns_r = load_near_solve_program(
                exemplars[0], near_solve_dir)
            if prog_d:
                # Try fold 0
                trace = generate_pixel_trace(
                    exemplars[0], ex_task, prog_d, 0)

        candidate = {
            "rank": rank + 1,
            "name": CANDIDATE_NAMES.get(key, f"{cat}/{subcat}"),
            "category": cat,
            "subcategory": subcat,
            "task_count": count,
            "exemplar_task_ids": exemplars,
            "pixel_trace": trace,
            "buildability": BUILDABILITY.get(key, "Assessment pending."),
        }
        candidates.append(candidate)

    # -----------------------------------------------------------------------
    # 6. Write outputs
    # -----------------------------------------------------------------------
    census = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "sample_size": len(all_task_results),
        "n_loo_fail": n_loo,
        "n_vocab_blocked": n_vocab,
        "cluster_histogram": [
            {"category": k[0], "subcategory": k[1], "task_count": v,
             "exemplar_ids": task_by_tag[k][:3]}
            for k, v in ranked
        ],
        "top5_candidates": candidates,
        "task_results": all_task_results,
        "elapsed_s": round(time.monotonic() - t_global_start, 1),
    }

    census_path = out_dir / "structural_vocab_census.json"
    with open(census_path, "w") as f:
        json.dump(census, f, indent=2)
    print(f"\nCensus written: {census_path}")
    log_event("census_written", {"path": str(census_path)})

    # Write markdown candidates doc
    docs_dir = Path(PROJECT_ROOT) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    md_path = docs_dir / "STRUCTURAL_VOCAB_CANDIDATES.md"
    with open(md_path, "w") as f:
        f.write("# Structural Vocabulary Candidates\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Sample: {len(all_task_results)} tasks "
                f"({n_loo} LOO-fail + {n_vocab} vocab-blocked)\n\n")
        f.write("## Cluster Histogram\n\n")
        f.write("| Rank | Category | Subcategory | Tasks | Exemplars |\n")
        f.write("|------|----------|-------------|-------|-----------|\n")
        for i, ((cat, subcat), count) in enumerate(ranked):
            exs = ", ".join(task_by_tag[(cat, subcat)][:3])
            f.write(f"| {i+1} | {cat} | {subcat} | {count} | {exs} |\n")
        f.write("\n## Top 5 Named Candidates\n\n")
        for c in candidates:
            f.write(f"### {c['rank']}. {c['name']}\n\n")
            f.write(f"- **Tasks**: {c['task_count']} / {len(all_task_results)}\n")
            f.write(f"- **Category**: {c['category']}/{c['subcategory']}\n")
            f.write(f"- **Exemplars**: {', '.join(c['exemplar_task_ids'])}\n")
            f.write(f"- **Buildability**: {c['buildability']}\n")
            if c.get("pixel_trace"):
                tr = c["pixel_trace"]
                f.write(f"- **Pixel trace** (fold {tr['fold']}): "
                        f"{tr['cells_wrong']} cells wrong\n")
            f.write("\n")
        f.write("## Build-First Recommendation\n\n")
        if candidates:
            first = candidates[0]
            f.write(f"**{first['name']}** ({first['task_count']} tasks) -- "
                    f"highest-count cluster.\n\n")
            f.write(f"Buildability: {first['buildability']}\n")
    print(f"Candidates doc written: {md_path}")
    log_event("doc_written", {"path": str(md_path)})

    # -----------------------------------------------------------------------
    # 7. Print summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STRUCTURAL VOCABULARY DIAGNOSIS SUMMARY")
    print("=" * 60)
    print(f"Sample: {len(all_task_results)} tasks analyzed "
          f"({n_loo} LOO-fail + {n_vocab} vocab-blocked)")
    print(f"Distinct structural tags: {len(ranked)}")
    print(f"\nCluster histogram (top 10):")
    for (cat, subcat), count in ranked[:10]:
        pct = count / len(all_task_results) * 100
        print(f"  {cat}/{subcat}: {count} tasks ({pct:.0f}%)")
    print(f"\nTop-5 named candidates:")
    for c in candidates:
        print(f"  {c['rank']}. {c['name']} ({c['task_count']} tasks)")
        print(f"     Exemplars: {', '.join(c['exemplar_task_ids'])}")
        print(f"     Build: {c['buildability'][:80]}...")
    if candidates:
        print(f"\nBUILD-FIRST: {candidates[0]['name']}")
        print(f"  Reason: highest task count ({candidates[0]['task_count']} "
              f"of {len(all_task_results)})")
    elapsed = time.monotonic() - t_global_start
    print(f"\nTotal elapsed: {elapsed:.0f}s ({elapsed/60:.1f}m)")

    log_event("done", {"elapsed_s": round(elapsed, 1),
                        "n_clusters": len(ranked),
                        "top5": [(c["name"], c["task_count"])
                                 for c in candidates]})
    jsonl_f.close()


if __name__ == "__main__":
    main()
