#!/usr/bin/env python3.11
"""Controlled microcycle: verify the color-transfer operator invention chain.

Tests 7 color-transfer task families:
  1. recolor_by_nearest_kept:  target objects recolored to nearest kept object's color
  2. recolor_by_marker:        target objects recolored to marker (unique-color) object's color
  3. recolor_by_same_shape:    target objects recolored to same-shape kept object's color
  4. recolor_by_paired_object: each target paired with a kept object by same-size
  5. bidirectional_color_swap: two colors swap everywhere
  6. ambiguous_nearest_REJECT: two kept objects equidistant, different colors
  7. competing_same_shape_REJECT: two same-shape sources with different colors

Required chain per promotable task:
  object-change classifier detects recolor →
  constant/map recolor fails (or is skipped) →
  color source rule inferred →
  LOO passes → proof obligations pass →
  test prediction → task solved → certificate emitted

Success criteria:
  operators_generated > 0, operators_validated > 0, promotions > 0,
  false_positives = 0, at least one ambiguity rejection,
  at least one certificate emitted
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.trace_operator_invention import TraceDrivenOperatorInventor
from reasoning_project.events import ReasoningEventLog


# ─── Task Generators ─────────────────────────────────────────────────────


def _make_recolor_by_nearest_kept():
    """Task 1: target objects take the color of the nearest kept object.

    2 kept objects at known positions with distinct colors.
    3 target objects, each closer to one kept object.
    Target objects all start as color 1, recolored to nearest kept's color.
    Selector: is_color_1 (targets are color 1; kept are not).
    """
    def make_pair(kept_positions_colors, target_positions):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        kept_info = []
        for (r, c), color in kept_positions_colors:
            for dr in range(2):
                for dc in range(2):
                    inp[r + dr, c + dc] = color
                    out[r + dr, c + dc] = color
            kept_info.append(((r + 0.5, c + 0.5), color))

        for r, c in target_positions:
            inp[r, c] = 1
            inp[r + 1, c] = 1
            # find nearest kept
            min_d = float("inf")
            best_color = 0
            for (kr, kc), kcolor in kept_info:
                d = abs(r + 0.5 - kr) + abs(c - kc)
                if d < min_d:
                    min_d = d
                    best_color = kcolor
            out[r, c] = best_color
            out[r + 1, c] = best_color

        return inp, out

    train = [
        make_pair(
            [((0, 0), 3), ((0, 9), 7)],
            [(5, 1), (5, 5), (5, 10)],
        ),
        make_pair(
            [((0, 0), 3), ((0, 9), 7)],
            [(8, 2), (8, 6), (8, 9)],
        ),
        make_pair(
            [((0, 0), 3), ((0, 9), 7)],
            [(3, 0), (3, 4), (3, 10)],
        ),
    ]
    test_pair = make_pair(
        [((0, 0), 3), ((0, 9), 7)],
        [(6, 0), (6, 7), (6, 11)],
    )
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_color_1", "needed_operator_family": "color_transfer_recolor"},
        "name": "recolor_by_nearest_kept",
        "expect_promotion": True,
    }


def _make_recolor_by_marker():
    """Task 2: target objects recolored to marker's color.

    1 kept 'marker' object (unique color, e.g. color 9) - is_unique_color=True.
    4 target objects (all color 2) - recolored to 9.
    Selector: is_unique_color (inverted: targets have NOT is_unique_color, kept IS unique).
    Actually for color transfer: the 'kept' objects (unique color) provide the source color.
    """
    def make_pair(marker_color, marker_pos, target_positions):
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        # Marker: single 2x2 block of unique color
        mr, mc = marker_pos
        for dr in range(2):
            for dc in range(2):
                inp[mr + dr, mc + dc] = marker_color
                out[mr + dr, mc + dc] = marker_color

        # 4 target objects: color 2, recolored to marker_color
        for r, c in target_positions:
            inp[r, c] = 2
            inp[r + 1, c] = 2
            out[r, c] = marker_color
            out[r + 1, c] = marker_color

        return inp, out

    train = [
        make_pair(9, (0, 4), [(3, 1), (3, 3), (3, 6), (3, 8)]),
        make_pair(9, (0, 4), [(6, 0), (6, 3), (6, 5), (6, 8)]),
        make_pair(9, (0, 4), [(5, 2), (5, 4), (5, 7), (5, 9)]),
    ]
    test_pair = make_pair(9, (0, 4), [(4, 0), (4, 3), (4, 6), (4, 9)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_color_2", "needed_operator_family": "color_transfer_recolor"},
        "name": "recolor_by_marker",
        "expect_promotion": True,
    }


def _make_recolor_by_same_shape():
    """Task 3: each target recolored to color of the same-shape kept object.

    2 kept objects: L-shape (color 4) and T-shape (color 6).
    2 target objects: same shapes as kept, but color 1.
    Each target is recolored to the color of the kept object with same shape.
    Selector: is_color_1 (targets).
    """
    # L-shape mask: 3x2
    l_shape = np.array([
        [1, 0],
        [1, 0],
        [1, 1],
    ], dtype=bool)

    # T-shape mask: 2x3
    t_shape = np.array([
        [1, 1, 1],
        [0, 1, 0],
    ], dtype=bool)

    def make_pair(kept_l_pos, kept_t_pos, target_l_pos, target_t_pos):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        # Kept L-shape (color 4)
        r, c = kept_l_pos
        inp[r:r + 3, c:c + 2][l_shape] = 4
        out[r:r + 3, c:c + 2][l_shape] = 4

        # Kept T-shape (color 6)
        r, c = kept_t_pos
        inp[r:r + 2, c:c + 3][t_shape] = 6
        out[r:r + 2, c:c + 3][t_shape] = 6

        # Target L-shape (color 1 → 4)
        r, c = target_l_pos
        inp[r:r + 3, c:c + 2][l_shape] = 1
        out[r:r + 3, c:c + 2][l_shape] = 4

        # Target T-shape (color 1 → 6)
        r, c = target_t_pos
        inp[r:r + 2, c:c + 3][t_shape] = 1
        out[r:r + 2, c:c + 3][t_shape] = 6

        return inp, out

    train = [
        make_pair((0, 0), (0, 5), (6, 0), (6, 5)),
        make_pair((0, 0), (0, 5), (7, 1), (7, 6)),
        make_pair((0, 0), (0, 5), (5, 2), (8, 5)),
    ]
    test_pair = make_pair((0, 0), (0, 5), (8, 0), (5, 7))
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_color_1", "needed_operator_family": "color_transfer_recolor"},
        "name": "recolor_by_same_shape",
        "expect_promotion": True,
    }


def _make_recolor_by_paired_object():
    """Task 4: each target paired with kept object by same-size, recolored to its color.

    2 kept objects of different sizes and colors.
    2 target objects matching the sizes, color 1.
    Selector: is_color_1.
    """
    def make_pair(kept_data, target_data):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        for (r, c, size, color) in kept_data:
            for dr in range(size):
                inp[r + dr, c] = color
                out[r + dr, c] = color

        for (r, c, size, expected_color) in target_data:
            for dr in range(size):
                inp[r + dr, c] = 1
                out[r + dr, c] = expected_color

        return inp, out

    train = [
        make_pair(
            [(0, 0, 2, 5), (0, 6, 4, 8)],
            [(6, 2, 2, 5), (6, 8, 4, 8)],
        ),
        make_pair(
            [(0, 0, 2, 5), (0, 6, 4, 8)],
            [(7, 1, 2, 5), (7, 7, 4, 8)],
        ),
        make_pair(
            [(0, 0, 2, 5), (0, 6, 4, 8)],
            [(5, 3, 2, 5), (5, 9, 4, 8)],
        ),
    ]
    test_pair = make_pair(
        [(0, 0, 2, 5), (0, 6, 4, 8)],
        [(8, 0, 2, 5), (8, 6, 4, 8)],
    )
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_color_1", "needed_operator_family": "color_transfer_recolor"},
        "name": "recolor_by_paired_object",
        "expect_promotion": True,
    }


def _make_bidirectional_color_swap():
    """Task 5: two colors swap everywhere: A↔B.

    Objects of color 3 become color 7, objects of color 7 become color 3.
    Selector: any property that partitions (use is_filled_rect since all are filled rects).
    """
    def make_pair(positions_a, positions_b):
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        for r, c in positions_a:
            inp[r, c] = 3; inp[r + 1, c] = 3
            out[r, c] = 7; out[r + 1, c] = 7
        for r, c in positions_b:
            inp[r, c] = 7; inp[r + 1, c] = 7
            out[r, c] = 3; out[r + 1, c] = 3

        return inp, out

    train = [
        make_pair([(1, 1), (1, 4), (5, 2)], [(1, 7), (5, 6), (5, 9)]),
        make_pair([(2, 0), (2, 3), (6, 1)], [(2, 7), (6, 5), (6, 8)]),
        make_pair([(0, 2), (3, 0), (3, 4)], [(0, 7), (3, 8), (7, 5)]),
    ]
    test_pair = make_pair([(1, 0), (4, 3), (4, 6)], [(1, 8), (7, 1), (7, 7)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_color_3", "needed_operator_family": "color_transfer_recolor"},
        "name": "bidirectional_color_swap",
        "expect_promotion": True,
    }


def _make_ambiguous_nearest_REJECT():
    """Task 6 (MUST REJECT): two kept objects equidistant from target, different colors.

    Target is exactly equidistant from two kept objects with colors 4 and 8.
    The nearest-kept rule should be ambiguous → rejection expected.
    """
    def make_pair(target_color_out):
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        # Kept: color 4 at (0, 0), color 8 at (0, 8) — equidistant from (5, 4)
        for dr in range(2):
            for dc in range(2):
                inp[0 + dr, 0 + dc] = 4
                out[0 + dr, 0 + dc] = 4
                inp[0 + dr, 8 + dc] = 8
                out[0 + dr, 8 + dc] = 8

        # Target: color 1 at (5, 4) — equidistant from both kept
        inp[5, 4] = 1; inp[6, 4] = 1
        out[5, 4] = target_color_out
        out[6, 4] = target_color_out

        return inp, out

    train = [
        make_pair(4),
        make_pair(8),
    ]
    return {
        "train": train,
        "test_inputs": [train[0][0].copy()],
        "test_outputs": [None],
        "trace": {"best_property": "is_color_1", "needed_operator_family": "color_transfer_recolor"},
        "name": "ambiguous_nearest_REJECT",
        "expect_promotion": False,
    }


def _make_competing_same_shape_REJECT():
    """Task 7 (MUST REJECT): two kept objects with same shape but different colors.

    Target has same shape as two kept objects. same_shape rule is ambiguous.
    """
    bar_shape = np.array([
        [1, 1, 1],
    ], dtype=bool)

    def make_pair(target_color_out):
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        # Kept object 1: 1x3 bar, color 4
        inp[1, 0:3] = 4
        out[1, 0:3] = 4

        # Kept object 2: 1x3 bar, color 8 — SAME SHAPE, different color
        inp[1, 6:9] = 8
        out[1, 6:9] = 8

        # Target: 1x3 bar, color 1 — matches both kept shapes
        inp[6, 3:6] = 1
        out[6, 3:6] = target_color_out

        return inp, out

    train = [
        make_pair(4),
        make_pair(8),
    ]
    return {
        "train": train,
        "test_inputs": [train[0][0].copy()],
        "test_outputs": [None],
        "trace": {"best_property": "is_color_1", "needed_operator_family": "color_transfer_recolor"},
        "name": "competing_same_shape_REJECT",
        "expect_promotion": False,
    }


# ─── Microcycle Runner ───────────────────────────────────────────────────


def run_microcycle():
    tasks = [
        _make_recolor_by_nearest_kept(),
        _make_recolor_by_marker(),
        _make_recolor_by_same_shape(),
        _make_recolor_by_paired_object(),
        _make_bidirectional_color_swap(),
        _make_ambiguous_nearest_REJECT(),
        _make_competing_same_shape_REJECT(),
    ]

    out_dir = Path("outputs/operator_microcycle/color_transfer_certificates")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "tasks_run": 0,
        "operators_generated": 0,
        "operators_validated": 0,
        "promotions": 0,
        "correct_rejections": 0,
        "false_positives": 0,
        "certificates_emitted": 0,
        "per_task": [],
    }

    t0 = time.time()

    for task in tasks:
        name = task["name"]
        train = task["train"]
        test_inputs = task["test_inputs"]
        test_outputs = task["test_outputs"]
        trace = task["trace"]
        expect_promotion = task["expect_promotion"]

        print(f"\n{'=' * 60}")
        print(f"Task: {name}")
        print(f"  Selector: {trace['best_property']}")
        print(f"  Expect promotion: {expect_promotion}")
        print(f"{'=' * 60}")

        event_log = ReasoningEventLog()
        inventor = TraceDrivenOperatorInventor(event_log=event_log)

        result = inventor.run_full_pipeline(
            task_id=name,
            train_pairs=train,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs if test_outputs[0] is not None else None,
        )

        proposed = result.get("operator_proposed", False)
        promoted = result.get("promoted", False)
        op_id = result.get("operator_id", "")
        family = result.get("family", "")
        if not family and op_id:
            if "ctr_" in op_id:
                family = "color_transfer_recolor"
            elif "rcl_" in op_id:
                family = "recolor_in_place"
            else:
                family = op_id.split("_")[0] if op_id else "none"
        rejection = result.get("rejection_reason")
        rule_type = result.get("rule_type", "")

        task_result = {
            "name": name,
            "proposed": proposed,
            "promoted": promoted,
            "family": family,
            "rule_type": rule_type,
            "rejection_reason": rejection,
            "expect_promotion": expect_promotion,
        }

        summary["tasks_run"] += 1
        if proposed:
            summary["operators_generated"] += 1
            if result.get("train_consistent", False):
                summary["operators_validated"] += 1

        if promoted and expect_promotion:
            summary["promotions"] += 1
            print(f"  PROMOTED via {family} (rule: {rule_type})")

            cert = result.get("certificate")
            cert_md = result.get("certificate_md")
            if cert is not None:
                summary["certificates_emitted"] += 1
                cert_path = out_dir / f"{name}_certificate.json"
                cert_path.write_text(json.dumps(
                    cert, indent=2, default=str,
                ))
                if cert_md:
                    md_path = out_dir / f"{name}_certificate.md"
                    md_path.write_text(cert_md)
                print(f"  Certificate: {cert_path}")
        elif promoted and not expect_promotion:
            summary["false_positives"] += 1
            print(f"  FALSE POSITIVE — promoted {family} but expected rejection!")
        elif not promoted and not expect_promotion:
            summary["correct_rejections"] += 1
            print(f"  Correctly rejected: {rejection}")
        elif not promoted and expect_promotion:
            print(f"  MISSED — expected promotion but got: {rejection}")

        task_result["status"] = (
            "PROMOTED" if promoted and expect_promotion
            else "FALSE_POSITIVE" if promoted and not expect_promotion
            else "CORRECT_REJECTION" if not promoted and not expect_promotion
            else "MISSED"
        )
        summary["per_task"].append(task_result)

    elapsed = time.time() - t0
    summary["elapsed_s"] = round(elapsed, 1)

    print(f"\n{'=' * 60}")
    print("COLOR-TRANSFER MICROCYCLE SUMMARY")
    print(f"{'=' * 60}")
    print(f"Tasks run:           {summary['tasks_run']}")
    print(f"Operators generated: {summary['operators_generated']}")
    print(f"Operators validated: {summary['operators_validated']}")
    print(f"Promotions:          {summary['promotions']}")
    print(f"Correct rejections:  {summary['correct_rejections']}")
    print(f"False positives:     {summary['false_positives']}")
    print(f"Certificates:        {summary['certificates_emitted']}")
    print(f"Elapsed:             {elapsed:.1f}s")

    success = (
        summary["operators_generated"] > 0
        and summary["operators_validated"] > 0
        and summary["promotions"] > 0
        and summary["false_positives"] == 0
        and summary["correct_rejections"] >= 1
        and summary["certificates_emitted"] >= 1
    )
    print(f"\nOverall: {'PASS' if success else 'FAIL'}")

    # Write outputs
    summary_path = out_dir.parent / "color_transfer_summary.md"
    with open(summary_path, "w") as f:
        f.write("# Color-Transfer Microcycle Summary\n\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"| Metric | Value |\n|--------|-------|\n")
        for k in ["tasks_run", "operators_generated", "operators_validated",
                   "promotions", "correct_rejections", "false_positives",
                   "certificates_emitted", "elapsed_s"]:
            f.write(f"| {k} | {summary[k]} |\n")
        f.write(f"\n## Per-Task Results\n\n")
        f.write(f"| Task | Status | Family | Rule | Rejection |\n")
        f.write(f"|------|--------|--------|------|-----------|\n")
        for t in summary["per_task"]:
            f.write(f"| {t['name']} | {t['status']} | {t.get('family', '')} | {t.get('rule_type', '')} | {t.get('rejection_reason', '')} |\n")
        f.write(f"\nOverall: **{'PASS' if success else 'FAIL'}**\n")

    json_path = out_dir.parent / "color_transfer_promoted_tasks.jsonl"
    with open(json_path, "w") as f:
        for t in summary["per_task"]:
            if t["status"] == "PROMOTED":
                f.write(json.dumps(t, default=str) + "\n")

    validated_path = out_dir.parent / "color_transfer_validated_operators.jsonl"
    with open(validated_path, "w") as f:
        for t in summary["per_task"]:
            if t.get("proposed"):
                f.write(json.dumps(t, default=str) + "\n")

    print(f"Summary: {summary_path}")
    return success, summary


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    success, summary = run_microcycle()
    sys.exit(0 if success else 1)
