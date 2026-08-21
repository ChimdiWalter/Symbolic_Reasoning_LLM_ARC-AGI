#!/usr/bin/env python3
"""V22 FAILURE CENSUS: 819 unsolved tasks, failure-stage histogram,
near-solve divergence characterization, named candidate structures,
and 868de0fa scheduling-harm diagnosis.

OUTPUT:
  outputs/v22_census.json
  docs/V22_CENSUS_CANDIDATES.md

Usage:
    python3 scripts/diagnose_v22_census.py
    python3 scripts/diagnose_v22_census.py --max-tasks 60  # quick
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
# Helpers (adapted from diagnose_structural_vocab.py)
# ---------------------------------------------------------------------------

def load_arc_data():
    arc_dir = Path(PROJECT_ROOT) / "data" / "arc"
    with open(arc_dir / "arc-agi_training_challenges.json") as f:
        challenges = json.load(f)
    sol_path = arc_dir / "arc-agi_training_solutions.json"
    solutions = {}
    if sol_path.exists():
        with open(sol_path) as f:
            solutions = json.load(f)
    return challenges, solutions


def load_v22_sealed():
    """Return set of sealed v22 task IDs (in-run + arbitration)."""
    v22 = json.load(open(os.path.join(PROJECT_ROOT,
        "outputs/unified_harness_v22/results.json")))
    arb = json.load(open(os.path.join(PROJECT_ROOT,
        "outputs/v22_arbitration/results.json")))
    ids = {r["task_id"] for r in v22["solved"]}
    for r in arb.get("solved", []):
        ids.add(r["task_id"])
    return ids


def load_near_solve_index():
    """Load near_solves.jsonl -> {task_id: record}."""
    path = os.path.join(PROJECT_ROOT,
        "outputs/unified_harness_v22/near_solves.jsonl")
    records = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            records[r["task_id"]] = r
    return records


def load_near_solve_parts(task_id):
    """Load all near-solve part records for a task; return list of dicts."""
    ns_dir = os.path.join(PROJECT_ROOT,
        "outputs/unified_harness_v22/object/near_solve_parts")
    path = os.path.join(ns_dir, f"{task_id}.jsonl")
    if not os.path.exists(path):
        return []
    parts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return parts


def best_near_solve_part(parts):
    """Return the part record with highest train_fit_pixels."""
    if not parts:
        return None
    best = max(parts, key=lambda p: p.get("train_fit_pixels", 0) or 0)
    return best


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
    except Exception:
        return None


def compute_divergence(predicted, expected):
    pred = np.array(predicted, dtype=np.int32)
    exp = np.array(expected, dtype=np.int32)
    if pred.shape != exp.shape:
        return {
            "cells_wrong": int(np.prod(exp.shape)),
            "total_cells": int(np.prod(exp.shape)),
            "accuracy": 0.0, "shape_mismatch": True,
            "pred_shape": list(pred.shape), "exp_shape": list(exp.shape),
            "wrong_details": [],
        }
    diff_mask = pred != exp
    wrong_details = []
    for r, c in zip(*np.where(diff_mask)):
        wrong_details.append({
            "r": int(r), "c": int(c),
            "predicted": int(pred[r, c]), "expected": int(exp[r, c]),
        })
    return {
        "cells_wrong": int(diff_mask.sum()),
        "total_cells": int(np.prod(exp.shape)),
        "accuracy": float(1.0 - diff_mask.sum() / np.prod(exp.shape)),
        "shape_mismatch": False,
        "wrong_details": wrong_details,
    }


# ---------------------------------------------------------------------------
# Structural characterization (simplified from diagnose_structural_vocab.py)
# ---------------------------------------------------------------------------

def characterize_divergence_simple(divergence, input_arr, expected_arr,
                                    predicted_arr, program_dict):
    """Return a list of structural tags for one divergence."""
    tags = []
    if divergence.get("shape_mismatch"):
        tags.append(("shape", "output_size_varies"))
        return tags
    if not divergence.get("wrong_details"):
        return tags

    inp = np.array(input_arr, dtype=np.int32)
    exp = np.array(expected_arr, dtype=np.int32)
    wrong = divergence["wrong_details"]
    n_wrong = len(wrong)
    h, w_grid = exp.shape
    input_colors = set(inp.flatten().tolist())
    expected_colors = set(w["expected"] for w in wrong)

    # Novel color
    if expected_colors - input_colors:
        tags.append(("color", "novel_color_in_output"))

    # Color varies by position
    if len(expected_colors) > 1 and n_wrong > 2:
        tags.append(("color", "color_function_of_context"))

    wrong_rs = [w["r"] for w in wrong]
    wrong_cs = [w["c"] for w in wrong]
    row_counts = collections.Counter(wrong_rs)
    col_counts = collections.Counter(wrong_cs)

    # Full row/col
    if row_counts and max(row_counts.values()) >= w_grid * 0.8 and len(row_counts) <= 3:
        tags.append(("position", "full_row_divergence"))
    if col_counts and max(col_counts.values()) >= h * 0.8 and len(col_counts) <= 3:
        tags.append(("position", "full_col_divergence"))

    # Rectangular fill
    r_min, r_max = min(wrong_rs), max(wrong_rs)
    c_min, c_max = min(wrong_cs), max(wrong_cs)
    bbox_area = (r_max - r_min + 1) * (c_max - c_min + 1)
    fill_ratio = n_wrong / max(bbox_area, 1)
    if fill_ratio > 0.7 and n_wrong > 4:
        tags.append(("position", "rectangular_fill"))

    # Extension beyond objects
    try:
        from scipy import ndimage
        bg_val = int(collections.Counter(inp.flatten().tolist()).most_common(1)[0][0])
        obj_mask = inp != bg_val
        labeled, n_objs = ndimage.label(obj_mask)
        if n_objs >= 2:
            obj_bboxes = ndimage.find_objects(labeled)
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
                tags.append(("position", "extension_beyond_objects"))
            # Connector
            connected_objs = set()
            for r, c in wrong_set:
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w_grid and labeled[nr, nc] > 0:
                        connected_objs.add(int(labeled[nr, nc]))
            if len(connected_objs) >= 2:
                tags.append(("position", "connector_between_objects"))
    except Exception:
        pass

    # Extensional pattern in program
    if program_dict:
        for rule in program_dict.get("rules", []):
            action = rule.get("action", {})
            params = action.get("params", {})
            if action.get("delta_type") == "grow":
                mode_param = params.get("mode", {})
                if isinstance(mode_param, dict) and mode_param.get("args", [None])[0] == "pattern":
                    tags.append(("position", "extensional_pattern"))
                    break
            for pk, pv in params.items():
                if pk == "color" and isinstance(pv, dict) and pv.get("op") == "const":
                    tags.append(("color", "constant_color_param"))
                    break

    # Symmetry check
    if n_wrong > 2 and not divergence.get("shape_mismatch"):
        wrong_arr = np.zeros_like(exp, dtype=bool)
        for w in wrong:
            wrong_arr[w["r"], w["c"]] = True
        if np.array_equal(wrong_arr, np.flipud(wrong_arr)):
            tags.append(("shape", "symmetric_divergence"))
        elif np.array_equal(wrong_arr, np.fliplr(wrong_arr)):
            tags.append(("shape", "symmetric_divergence"))

    if not tags:
        tags.append(("unknown", "uncharacterized"))
    return tags


# ---------------------------------------------------------------------------
# 868de0fa specific diagnosis
# ---------------------------------------------------------------------------

def diagnose_868de0fa(challenges):
    """Trace why probing harms 868de0fa: which variant gets promoted
    vs which certifies."""
    result = {}

    # Off-control program (v21 flags, SOLVES)
    off_prog_path = os.path.join(PROJECT_ROOT,
        "outputs/v22_868_offcontrol/object/programs/868de0fa.json")
    if os.path.exists(off_prog_path):
        off_prog = json.load(open(off_prog_path))
        result["off_control"] = {
            "program_class": off_prog.get("program_class"),
            "description": "framed+composed two-stage (S3+S4) with "
                           "fill_interior, constant colors -- LOO-passes "
                           "because composition structure is fold-stable",
        }
        # Extract structure
        inner = off_prog.get("inner", {})
        stages = inner.get("stages", [])
        result["off_control"]["n_stages"] = len(stages)
        result["off_control"]["stage_variants"] = [
            s.get("segmentation_variant") for s in stages]

    # V22 near-solve (LOO FAIL)
    parts = load_near_solve_parts("868de0fa")
    best = best_near_solve_part(parts)
    if best:
        result["v22_near_solve"] = {
            "segmentation_variant": best.get("segmentation_variant"),
            "train_fit_pixels": best.get("train_fit_pixels"),
            "failure_stage": best.get("failure_stage"),
            "description": "single-stage S3-only with fill_interior, "
                           "constant colors -- train-perfect but LOO-fails "
                           "because const color params are not fold-stable",
        }
        prog_v22 = best.get("program_partial", {})
        rules_v22 = prog_v22.get("rules", [])
        result["v22_near_solve"]["n_rules"] = len(rules_v22)
        result["v22_near_solve"]["all_params_constant"] = all(
            rule.get("action", {}).get("parameter_class") == "constant"
            for rule in rules_v22
        )

    result["diagnosis"] = (
        "The cheap-first variant-budget scheduling promotes a simpler, "
        "shallower program (S3-only single-stage with constant-color "
        "fill_interior) that is train-perfect but LOO-fails, instead of "
        "the deeper framed+composed program (S3+S4 two-stage) that would "
        "certify under v21 flags. The v22 search exhausts budget on the "
        "promoted (non-certifiable) candidate before exploring the deeper "
        "composition path. The harm mechanism is promotion-starvation: "
        "variant-budget scheduling allocates less time to S4, so the "
        "composition stage that depends on S4 never runs."
    )
    result["remedy"] = (
        "Composition-aware budget reservation: when a single-stage program "
        "is train-perfect but LOO-fails with constant parameters, reserve "
        "budget for a composition attempt before accepting the failure."
    )
    return result


# ---------------------------------------------------------------------------
# Main census
# ---------------------------------------------------------------------------

def main():
    t_start = time.monotonic()

    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tasks", type=int, default=80,
                    help="Max tasks to run full divergence analysis on")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    print("=== V22 FAILURE CENSUS (819 unsolved) ===")

    challenges, solutions = load_arc_data()
    sealed = load_v22_sealed()
    ns_index = load_near_solve_index()

    all_task_ids = sorted(challenges.keys())
    unsolved = [t for t in all_task_ids if t not in sealed]
    print(f"Sealed: {len(sealed)}, Unsolved: {len(unsolved)}")

    # -----------------------------------------------------------------------
    # 1. FAILURE-STAGE HISTOGRAM (all 819)
    # -----------------------------------------------------------------------
    print("\n--- FAILURE-STAGE HISTOGRAM ---")

    stage_counter = collections.Counter()
    layer_counter = collections.Counter()
    family_counter = collections.Counter()

    # Classify by best available info
    ns_dir = os.path.join(PROJECT_ROOT,
        "outputs/unified_harness_v22/object/near_solve_parts")
    has_parts = set()
    for fn in os.listdir(ns_dir):
        has_parts.add(fn.replace(".jsonl", ""))

    # Categories:
    # - "loo_fail": train-perfect program exists but fails LOO
    # - "matching_fail": object engine finds partial but matching fails
    # - "parameter_fail": parameter search fails
    # - "selector_fail": selector search fails
    # - "low_fit_partial": partial program with fit < 1.0
    # - "no_object_engagement": object engine did not produce any partial
    # - "geocat_only": only geocat layer engaged
    # - "identity": no layer engaged at all

    task_classifications = {}

    for tid in unsolved:
        ns_rec = ns_index.get(tid, {})
        best_layer = ns_rec.get("best_layer") or "none"
        best_family = ns_rec.get("best_family_or_strategy") or "none"
        layer_counter[best_layer] += 1
        family_counter[best_family] += 1

        if tid in has_parts:
            parts = load_near_solve_parts(tid)
            best = best_near_solve_part(parts)
            if best:
                fit = best.get("train_fit_pixels", 0) or 0
                stage = best.get("failure_stage", "") or "unknown"
                if fit >= 1.0:
                    stage_counter[f"loo_fail:{stage}"] += 1
                    task_classifications[tid] = {
                        "category": "loo_fail",
                        "stage": stage,
                        "fit": fit,
                        "variant": best.get("segmentation_variant"),
                    }
                elif fit > 0.5:
                    stage_counter[f"partial_high:{stage}"] += 1
                    task_classifications[tid] = {
                        "category": "partial_high",
                        "stage": stage,
                        "fit": round(fit, 3),
                        "variant": best.get("segmentation_variant"),
                    }
                else:
                    stage_counter[f"partial_low:{stage}"] += 1
                    task_classifications[tid] = {
                        "category": "partial_low",
                        "stage": stage,
                        "fit": round(fit, 3),
                        "variant": best.get("segmentation_variant"),
                    }
            else:
                stage_counter["no_usable_partial"] += 1
                task_classifications[tid] = {"category": "no_usable_partial"}
        else:
            # No object-layer near-solve parts
            if best_layer == "geocat":
                stage_counter["geocat_only"] += 1
                task_classifications[tid] = {
                    "category": "geocat_only",
                    "family": best_family,
                }
            elif best_layer == "identity":
                stage_counter["no_engagement"] += 1
                task_classifications[tid] = {"category": "no_engagement"}
            else:
                stage_counter[f"other:{best_layer}"] += 1
                task_classifications[tid] = {
                    "category": f"other:{best_layer}",
                    "family": best_family,
                }

    print("Stage histogram:")
    for k, v in stage_counter.most_common():
        print(f"  {k}: {v}")
    print(f"\nLayer histogram:")
    for k, v in layer_counter.most_common():
        print(f"  {k}: {v}")

    # -----------------------------------------------------------------------
    # 2. DIVERGENCE CHARACTERIZATION (sample from tasks with partials)
    # -----------------------------------------------------------------------
    print("\n--- DIVERGENCE CHARACTERIZATION ---")

    # Sample from LOO-fail tasks (the ones with actionable near-solves)
    loo_fail_tasks = [tid for tid, cls in task_classifications.items()
                      if cls["category"] == "loo_fail"]
    partial_tasks = [tid for tid, cls in task_classifications.items()
                     if cls["category"] in ("partial_high", "partial_low")]

    rng = random.Random(args.seed)
    sample_size = min(args.max_tasks, len(loo_fail_tasks))
    sample = sorted(rng.sample(loo_fail_tasks, sample_size))

    print(f"LOO-fail tasks: {len(loo_fail_tasks)}")
    print(f"Partial tasks: {len(partial_tasks)}")
    print(f"Analyzing divergence on {sample_size} LOO-fail tasks...")

    global_tag_counter = collections.Counter()
    task_by_tag = collections.defaultdict(list)
    analyzed_results = []

    for idx, tid in enumerate(sample):
        if time.monotonic() - t_start > 2.5 * 3600:
            print(f"\n--- 2.5h cap reached at task {idx}/{sample_size} ---")
            break

        parts = load_near_solve_parts(tid)
        best = best_near_solve_part(parts)
        if not best or not best.get("program_partial"):
            continue

        prog_dict = best["program_partial"]
        task_data = challenges.get(tid)
        if not task_data:
            continue

        pairs = task_data["train"]
        all_tags = []

        for i, pair in enumerate(pairs):
            rendered = render_program_safe(prog_dict, pair["input"])
            if rendered is not None:
                div = compute_divergence(rendered, pair["output"])
                if div["cells_wrong"] > 0:
                    tags = characterize_divergence_simple(
                        div, pair["input"], pair["output"], rendered,
                        prog_dict)
                    all_tags.extend(tags)

        # Deduplicate tags for this task
        unique_tags = list(set(all_tags))
        for tag in unique_tags:
            global_tag_counter[tag] += 1
            task_by_tag[tag].append(tid)

        analyzed_results.append({
            "task_id": tid,
            "variant": best.get("segmentation_variant"),
            "failure_stage": best.get("failure_stage"),
            "tags": [{"category": t[0], "subcategory": t[1]} for t in unique_tags],
        })

        if (idx + 1) % 20 == 0:
            elapsed = time.monotonic() - t_start
            print(f"  [{idx+1}/{sample_size}] {elapsed:.0f}s elapsed")

    print(f"\nDivergence tag histogram:")
    for tag, count in global_tag_counter.most_common():
        print(f"  {tag[0]}/{tag[1]}: {count}")

    # -----------------------------------------------------------------------
    # 3. NAMED CANDIDATE STRUCTURES (top-5)
    # -----------------------------------------------------------------------
    CANDIDATE_NAMES = {
        ("color", "constant_color_param"):
            "RELATIONAL-COLOR: constant color parameters need "
            "to derive from scene context",
        ("position", "extensional_pattern"):
            "PATTERN-TO-RULE: literal pixel patterns need "
            "generative/relational rules",
        ("position", "extension_beyond_objects"):
            "RAY/LINE EXTENSION: cells placed along rays/lines "
            "beyond object boundaries",
        ("position", "connector_between_objects"):
            "INTER-OBJECT CONNECTOR: bridge/line connecting objects",
        ("position", "full_row_divergence"):
            "ROW-SPAN FILL: entire row(s) filled with computed color",
        ("position", "full_col_divergence"):
            "COLUMN-SPAN FILL: entire column(s) filled with computed color",
        ("position", "rectangular_fill"):
            "RECTANGULAR VOID FILL: region filled with input-derived content",
        ("color", "color_function_of_context"):
            "POSITIONAL COLOR: color varies by position/neighborhood",
        ("color", "novel_color_in_output"):
            "COLOR INVENTION: output uses colors absent from input",
        ("shape", "output_size_varies"):
            "SIZE-ADAPTIVE OUTPUT: grid size depends on input content",
        ("shape", "symmetric_divergence"):
            "SYMMETRY COMPLETION: divergent cells form symmetric pattern",
        ("unknown", "uncharacterized"):
            "UNCHARACTERIZED: no specific structural pattern",
    }

    BUILDABILITY = {
        ("color", "constant_color_param"):
            "BINDING BOTTLENECK (confirmed R1/R2). The relational-expression "
            "grammar needs extension: color-of-neighbor, color-of-match, "
            "conditional color. The R2 relift experiment proved 0% success "
            "with current expressions. HIGH priority, MEDIUM buildability.",
        ("position", "extensional_pattern"):
            "Needs generative modes that DERIVE patterns from object features. "
            "Delta type exists (grow), needs new generator logic. MEDIUM build.",
        ("position", "extension_beyond_objects"):
            "Partially covered by ray/line generators (R17). Gap: "
            "ray_until_obstacle, relational direction. HIGH buildability.",
        ("position", "connector_between_objects"):
            "CONNECT delta exists but fires narrowly. Needs wider connector "
            "induction (L-path, Manhattan, diagonal). MEDIUM buildability.",
        ("position", "full_row_divergence"):
            "row_line/col_line generators exist. Gap: conditional row fills. "
            "MEDIUM buildability.",
        ("position", "full_col_divergence"):
            "col_line generators exist. MEDIUM buildability.",
        ("position", "rectangular_fill"):
            "fill_interior grow mode exists. Gap: fill relative to ANOTHER "
            "object. MEDIUM buildability.",
        ("color", "color_function_of_context"):
            "Needs conditional color expressions. LOW buildability.",
        ("color", "novel_color_in_output"):
            "Needs color-arithmetic expressions. LOW buildability.",
        ("shape", "output_size_varies"):
            "NOT expressible in current program shapes.",
        ("shape", "symmetric_divergence"):
            "Symmetry family already handles some; gap is remaining subtypes.",
        ("unknown", "uncharacterized"):
            "Manual inspection needed.",
    }

    ranked_tags = global_tag_counter.most_common()
    top5 = ranked_tags[:5]
    candidates = []
    for rank, (tag, count) in enumerate(top5):
        exemplars = task_by_tag[tag][:3]
        candidates.append({
            "rank": rank + 1,
            "name": CANDIDATE_NAMES.get(tag, f"{tag[0]}/{tag[1]}"),
            "category": tag[0],
            "subcategory": tag[1],
            "task_count": count,
            "extrapolated_count": int(count * len(loo_fail_tasks) / max(sample_size, 1)),
            "exemplar_task_ids": exemplars,
            "buildability": BUILDABILITY.get(tag, "Assessment pending."),
        })

    # -----------------------------------------------------------------------
    # 4. 868de0fa DIAGNOSIS
    # -----------------------------------------------------------------------
    print("\n--- 868de0fa DIAGNOSIS ---")
    diag_868 = diagnose_868de0fa(challenges)
    for k, v in diag_868.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")

    # -----------------------------------------------------------------------
    # 5. WRITE OUTPUTS
    # -----------------------------------------------------------------------
    census = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "v22_sealed": len(sealed),
        "unsolved": len(unsolved),
        "failure_stage_histogram": dict(stage_counter.most_common()),
        "layer_histogram": dict(layer_counter.most_common()),
        "family_histogram": dict(family_counter.most_common()),
        "divergence_sample_size": sample_size,
        "divergence_tag_histogram": [
            {"category": t[0], "subcategory": t[1], "task_count": c,
             "exemplar_ids": task_by_tag[t][:3]}
            for t, c in ranked_tags
        ],
        "top5_candidates": candidates,
        "task_classifications_summary": {
            "loo_fail": len(loo_fail_tasks),
            "partial_high": len([t for t, c in task_classifications.items()
                                 if c["category"] == "partial_high"]),
            "partial_low": len([t for t, c in task_classifications.items()
                                if c["category"] == "partial_low"]),
            "geocat_only": stage_counter.get("geocat_only", 0),
            "no_engagement": stage_counter.get("no_engagement", 0),
        },
        "diagnosis_868de0fa": diag_868,
        "analyzed_tasks": analyzed_results,
        "elapsed_s": round(time.monotonic() - t_start, 1),
    }

    out_path = os.path.join(PROJECT_ROOT, "outputs/v22_census.json")
    with open(out_path, "w") as f:
        json.dump(census, f, indent=2)
    print(f"\nCensus written: {out_path}")

    # Write markdown
    docs_dir = os.path.join(PROJECT_ROOT, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    md_path = os.path.join(docs_dir, "V22_CENSUS_CANDIDATES.md")
    with open(md_path, "w") as f:
        f.write("# V22 Census: Failure Candidates for >200\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"V22 sealed: {len(sealed)}/1000, unsolved: {len(unsolved)}\n\n")

        f.write("## Failure-Stage Histogram (all 819 unsolved)\n\n")
        f.write("| Stage | Count |\n|---|---|\n")
        for k, v in stage_counter.most_common():
            f.write(f"| {k} | {v} |\n")

        f.write("\n## Top-5 Named Candidates\n\n")
        for c in candidates:
            f.write(f"### {c['rank']}. {c['name']}\n\n")
            f.write(f"- **Tasks in sample**: {c['task_count']}/{sample_size}\n")
            f.write(f"- **Extrapolated**: ~{c['extrapolated_count']}"
                    f" of {len(loo_fail_tasks)} LOO-fail tasks\n")
            f.write(f"- **Category**: {c['category']}/{c['subcategory']}\n")
            f.write(f"- **Exemplars**: {', '.join(c['exemplar_task_ids'])}\n")
            f.write(f"- **Buildability**: {c['buildability']}\n\n")

        f.write("## Build-First Recommendation\n\n")
        if candidates:
            first = candidates[0]
            f.write(f"**{first['name']}** ({first['task_count']} tasks "
                    f"in sample, ~{first['extrapolated_count']} "
                    f"extrapolated).\n\n")
            f.write(f"{first['buildability']}\n\n")

        f.write("## 868de0fa Scheduling-Harm Diagnosis\n\n")
        f.write(f"**Diagnosis**: {diag_868.get('diagnosis', 'N/A')}\n\n")
        f.write(f"**Remedy**: {diag_868.get('remedy', 'N/A')}\n")

    print(f"Candidates doc: {md_path}")

    # -----------------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------------
    elapsed = time.monotonic() - t_start
    print(f"\n{'='*60}")
    print(f"V22 FAILURE CENSUS SUMMARY")
    print(f"{'='*60}")
    print(f"Sealed: {len(sealed)}/1000 ({len(sealed)/10:.1f}%)")
    print(f"Unsolved: {len(unsolved)}")
    print(f"  LOO-fail (train-perfect, gate-rejected): {len(loo_fail_tasks)}")
    print(f"  Partial (fit < 1.0): {len(partial_tasks)}")
    print(f"  Geocat-only: {stage_counter.get('geocat_only', 0)}")
    print(f"  No engagement: {stage_counter.get('no_engagement', 0)}")
    print(f"\nTop-5 candidates (from {sample_size} analyzed LOO-fail):")
    for c in candidates:
        print(f"  {c['rank']}. {c['name']} ({c['task_count']})")
    if candidates:
        print(f"\nBUILD-FIRST: {candidates[0]['name']}")
    print(f"\n868de0fa: {diag_868.get('diagnosis', 'N/A')[:120]}...")
    print(f"\nTotal elapsed: {elapsed:.0f}s ({elapsed/60:.1f}m)")


if __name__ == "__main__":
    main()
