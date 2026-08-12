#!/usr/bin/env python3.11
"""Controlled microcycle: verify the recolor-in-place operator invention chain.

Tests 5 recolor task families:
  1. recolor_unique_color: unique-color objects recolored to constant, common-color kept
  2. recolor_by_holes: solid objects recolored, frame objects (with holes) kept
  3. recolor_by_position: top-half objects recolored, bottom-half kept
  4. recolor_smallest: single largest object kept, all smaller recolored
  5. ambiguous_recolor (MUST REJECT): different target colors across pairs

Required chain per promotable task:
  target selector found → earlier families fail →
  recolor-in-place proposed → train validation → LOO passes →
  test prediction → task solved → certificate emitted

Success criteria:
  proposals > 0, promotions > 0, false_positives = 0,
  at least one ambiguous case rejected correctly,
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


def _make_recolor_unique_color():
    """Task 1: unique-color objects recolored to 7, most-common-color objects kept.

    4 objects of color 2 (is_most_common_color=True → kept).
    2 objects of unique colors (is_most_common_color=False → recolored to 7).
    """
    def make_pair(unique_positions, unique_colors):
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        # 4 kept objects: 2x1 blocks of color 2 (most common)
        for r, c in [(1, 1), (1, 5), (6, 1), (6, 5)]:
            inp[r, c] = 2; out[r, c] = 2
            inp[r+1, c] = 2; out[r+1, c] = 2

        # 2 target objects: 2x1 blocks of unique colors → recolored to 7
        for (r, c), color in zip(unique_positions, unique_colors):
            inp[r, c] = color; out[r, c] = 7
            inp[r+1, c] = color; out[r+1, c] = 7

        return inp, out

    train = [
        make_pair([(3, 3, ), (8, 8)], [4, 8]),
        make_pair([(3, 7), (8, 3)], [3, 6]),
        make_pair([(4, 4), (7, 7)], [5, 9]),
    ]
    test_pair = make_pair([(3, 8), (8, 4)], [1, 3])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "recolor_in_place"},
        "name": "recolor_unique_color",
        "expect_promotion": True,
    }


def _make_recolor_by_holes():
    """Task 2: solid rect objects recolored to 3, frame objects (has_holes) kept.

    2 frame objects (3x3 with center hole, color 1): has_holes=True → kept.
    3 solid 2x2 blocks (color 5): has_holes=False → recolored to 3.
    """
    def make_pair(solid_positions):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        # Frame objects: 3x3 ring (color 1), has_holes=True → kept
        for fr, fc in [(0, 0), (0, 8)]:
            for r in range(fr, fr+3):
                for c in range(fc, fc+3):
                    inp[r, c] = 1
                    out[r, c] = 1
            inp[fr+1, fc+1] = 0
            out[fr+1, fc+1] = 0

        # Solid 2x2 objects (color 5), has_holes=False → recolored to 3
        for r, c in solid_positions:
            for dr in range(2):
                for dc in range(2):
                    inp[r+dr, c+dc] = 5
                    out[r+dr, c+dc] = 3

        return inp, out

    train = [
        make_pair([(5, 2), (5, 6), (9, 4)]),
        make_pair([(4, 3), (4, 9), (8, 1)]),
        make_pair([(5, 1), (5, 9), (9, 5)]),
    ]
    test_pair = make_pair([(6, 3), (6, 8), (10, 5)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "has_holes", "needed_operator_family": "recolor_in_place"},
        "name": "recolor_by_holes",
        "expect_promotion": True,
    }


def _make_recolor_by_position():
    """Task 3: top-half objects recolored to 6, bottom-half objects kept.

    Selector: in_bottom_half (True → kept, False → recolored).
    3 objects in bottom half (kept), 3 objects in top half (recolored to 6).
    All objects are 1x2 blocks to avoid connectivity issues.
    """
    def make_pair(top_info, bottom_info):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        # Bottom objects: in_bottom_half=True → kept
        for r, c, color in bottom_info:
            inp[r, c] = color; out[r, c] = color
            inp[r, c+1] = color; out[r, c+1] = color

        # Top objects: in_bottom_half=False → recolored to 6
        for r, c, color in top_info:
            inp[r, c] = color; out[r, c] = 6
            inp[r, c+1] = color; out[r, c+1] = 6

        return inp, out

    train = [
        make_pair(
            [(1, 2, 4), (2, 6, 3), (0, 9, 1)],
            [(8, 2, 2), (9, 6, 5), (7, 9, 8)],
        ),
        make_pair(
            [(0, 1, 3), (2, 5, 4), (1, 9, 2)],
            [(7, 1, 5), (9, 5, 1), (8, 9, 8)],
        ),
        make_pair(
            [(1, 3, 1), (0, 7, 4), (2, 10, 3)],
            [(8, 3, 2), (7, 7, 5), (9, 10, 8)],
        ),
    ]
    test_pair = make_pair(
        [(0, 4, 3), (2, 8, 1), (1, 1, 4)],
        [(9, 4, 2), (7, 8, 5), (8, 1, 8)],
    )
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "in_bottom_half", "needed_operator_family": "recolor_in_place"},
        "name": "recolor_by_position",
        "expect_promotion": True,
    }


def _make_recolor_largest_kept():
    """Task 4: single largest object kept, all smaller objects recolored to 9.

    1 large 4x4 block (is_largest=True → kept).
    3 small 1x1 pixels of different colors (is_largest=False → recolored to 9).
    """
    def make_pair(small_positions, small_colors):
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        # Largest object: 4x4 block of color 2
        inp[0:4, 0:4] = 2; out[0:4, 0:4] = 2

        # Small objects: 1x1 pixels → recolored to 9
        for (r, c), color in zip(small_positions, small_colors):
            inp[r, c] = color
            out[r, c] = 9

        return inp, out

    train = [
        make_pair([(5, 5), (7, 3), (8, 8)], [4, 3, 6]),
        make_pair([(6, 6), (5, 2), (9, 7)], [1, 8, 5]),
        make_pair([(5, 8), (7, 5), (9, 1)], [3, 7, 4]),
    ]
    test_pair = make_pair([(6, 4), (8, 7), (5, 1)], [6, 1, 8])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_largest", "needed_operator_family": "recolor_in_place"},
        "name": "recolor_largest_kept",
        "expect_promotion": True,
    }


def _make_ambiguous_recolor_REJECT():
    """Task 5 (MUST REJECT): inconsistent recolor across pairs.

    Pair 1: unique-color object recolored to 7.
    Pair 2: unique-color object recolored to 3.
    No single constant-color rule fits. The per_pair_map path returns None
    in _execute_recolor, so this should fail at validation or execution.
    """
    def make_pair(target_color, target_src_color):
        inp = np.zeros((8, 8), dtype=int)
        out = np.zeros((8, 8), dtype=int)

        # 3 kept objects: color 2 (most common → True)
        for r, c in [(0, 0), (0, 4), (4, 0)]:
            inp[r, c] = 2; out[r, c] = 2
            inp[r+1, c] = 2; out[r+1, c] = 2

        # 1 target object: unique color → recolored
        inp[6, 6] = target_src_color
        out[6, 6] = target_color

        return inp, out

    train = [
        make_pair(target_color=7, target_src_color=4),
        make_pair(target_color=3, target_src_color=5),
    ]
    test_inp = np.zeros((8, 8), dtype=int)
    for r, c in [(0, 0), (0, 4), (4, 0)]:
        test_inp[r, c] = 2
        test_inp[r+1, c] = 2
    test_inp[6, 6] = 8
    return {
        "train": train,
        "test_inputs": [test_inp],
        "test_outputs": [None],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "recolor_in_place"},
        "name": "ambiguous_recolor_REJECT",
        "expect_promotion": False,
    }


def run_microcycle():
    tasks = [
        _make_recolor_unique_color(),
        _make_recolor_by_holes(),
        _make_recolor_by_position(),
        _make_recolor_largest_kept(),
        _make_ambiguous_recolor_REJECT(),
    ]

    out_dir = Path("outputs/operator_microcycle/recolor_certificates")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "tasks_run": 0,
        "proposals": 0,
        "promotions": 0,
        "correct_rejections": 0,
        "false_positives": 0,
        "certificates_emitted": 0,
        "per_task": [],
    }

    for task in tasks:
        name = task["name"]
        train = task["train"]
        test_inputs = task["test_inputs"]
        test_outputs = task["test_outputs"]
        trace = task["trace"]
        expect_promotion = task["expect_promotion"]

        print(f"\n{'='*60}")
        print(f"Task: {name}")
        print(f"  Selector: {trace['best_property']}")
        print(f"  Expect promotion: {expect_promotion}")
        print(f"{'='*60}")

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
        family = "recolor_in_place" if op_id and "rcl_" in op_id else (
            op_id.split("_")[0] if op_id else "none"
        )
        rejection = result.get("rejection_reason")

        task_result = {
            "name": name,
            "proposed": proposed,
            "promoted": promoted,
            "family": family,
            "rejection_reason": rejection,
            "expect_promotion": expect_promotion,
        }

        summary["tasks_run"] += 1
        if proposed:
            summary["proposals"] += 1

        if promoted and expect_promotion:
            summary["promotions"] += 1
            print(f"  PROMOTED via {family}")

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

    print(f"\n{'='*60}")
    print("RECOLOR MICROCYCLE SUMMARY")
    print(f"{'='*60}")
    print(f"Tasks run:          {summary['tasks_run']}")
    print(f"Proposals:          {summary['proposals']}")
    print(f"Promotions:         {summary['promotions']}")
    print(f"Correct rejections: {summary['correct_rejections']}")
    print(f"False positives:    {summary['false_positives']}")
    print(f"Certificates:       {summary['certificates_emitted']}")

    success = (
        summary["proposals"] > 0
        and summary["promotions"] > 0
        and summary["false_positives"] == 0
        and summary["correct_rejections"] >= 1
    )
    print(f"\nOverall: {'PASS' if success else 'FAIL'}")

    summary_path = out_dir.parent / "recolor_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"Summary: {summary_path}")

    return success, summary


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    success, summary = run_microcycle()
    sys.exit(0 if success else 1)
