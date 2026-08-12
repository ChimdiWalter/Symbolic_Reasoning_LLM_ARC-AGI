#!/usr/bin/env python3.11
"""Controlled microcycle: verify the variable-destination policy learning chain.

Tests 5 destination policy families:
  1. anchor_offset: consistent offset from nearest kept centroid
  2. same_side_below: all sources go below their nearest anchor
  3. nearest_anchor: sources go to nearest anchor-adjacent position
  4. min_distance_open_slot: sources move to closest empty slot
  5. ambiguous_tie (MUST REJECT): two equally valid anchor offsets

Required chain per promotable task:
  target selector found → constant displacement fails →
  marker-relative fails → correspondence fails →
  destination candidates generated → destination policy induced →
  LOO passes → proof obligations pass →
  falsification logged → task solved → certificate emitted

Success criteria:
  policies_generated > 0, policies_validated > 0, promotions > 0,
  false_positives = 0, at least one ambiguous case rejected correctly,
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
from reasoning_project.certificates import certificate_to_json, certificate_to_markdown


def _make_anchor_offset_task():
    """Task 1: each source moves to offset (2, 0) from nearest kept centroid.

    2 kept objects (3x3 blocks, color 5) at fixed positions.
    2 source objects (1x1, colors 1 and 2) near different anchors.
    Each source's destination = nearest_kept_centroid + (2, 0).
    Sources are NOT the same color as anchors (no color-match shortcut).
    """
    def make_pair(src_positions):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        # Kept: two 3x3 blocks of color 5
        inp[1:4, 1:4] = 5; out[1:4, 1:4] = 5  # centroid (2, 2)
        inp[1:4, 8:11] = 5; out[1:4, 8:11] = 5  # centroid (2, 9)

        src_colors = [1, 2]
        for (sr, sc), color in zip(src_positions, src_colors):
            inp[sr, sc] = color
            # Find nearest kept centroid
            d0 = abs(sr - 2) + abs(sc - 2)
            d1 = abs(sr - 2) + abs(sc - 9)
            if d0 <= d1:
                dest_r, dest_c = 2 + 2, 2  # (4, 2)
            else:
                dest_r, dest_c = 2 + 2, 9  # (4, 9)
            out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([(0, 0), (0, 11)]),
        make_pair([(5, 1), (5, 10)]),
        make_pair([(6, 3), (6, 7)]),
    ]
    test_pair = make_pair([(7, 2), (7, 9)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "copy_to_position"},
    }


def _make_same_side_below_task():
    """Task 2: sources always placed below their nearest anchor.

    2 kept objects (2x2 blocks, color 5).
    2 source objects (1x1, colors 3, 4).
    Destination = immediately below nearest anchor.
    """
    def make_pair(src_positions):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        # Kept: two 2x2 blocks
        inp[1:3, 1:3] = 5; out[1:3, 1:3] = 5  # bottom at row 2
        inp[1:3, 8:10] = 5; out[1:3, 8:10] = 5  # bottom at row 2

        src_colors = [3, 4]
        for (sr, sc), color in zip(src_positions, src_colors):
            inp[sr, sc] = color
            # Nearest anchor
            d0 = abs(sr - 1.5) + abs(sc - 1.5)
            d1 = abs(sr - 1.5) + abs(sc - 8.5)
            if d0 <= d1:
                dest_r, dest_c = 3, 1  # below first anchor
            else:
                dest_r, dest_c = 3, 8  # below second anchor
            out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([(5, 2), (5, 9)]),
        make_pair([(7, 0), (7, 10)]),
        make_pair([(6, 1), (8, 9)]),
    ]
    test_pair = make_pair([(9, 2), (9, 8)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "copy_to_position"},
    }


def _make_nearest_anchor_adjacent_task():
    """Task 3: source placed to the right of its nearest anchor.

    3 kept objects forming a column. Source at varying positions.
    Varying source columns break constant-displacement CTP.
    """
    def make_pair(src_pos):
        inp = np.zeros((15, 10), dtype=int)
        out = np.zeros((15, 10), dtype=int)

        for kr in [1, 6, 11]:
            inp[kr:kr + 2, 2:4] = 5
            out[kr:kr + 2, 2:4] = 5

        sr, sc = src_pos
        inp[sr, sc] = 1
        dists = [abs(sr - kr - 0.5) + abs(sc - 2.5) for kr in [1, 6, 11]]
        best_ki = dists.index(min(dists))
        anchor_r = [1, 6, 11][best_ki]
        out[anchor_r, 4] = 1

        return inp, out

    train = [
        make_pair((2, 7)),   # near anchor 0, col 7
        make_pair((7, 9)),   # near anchor 1, col 9
        make_pair((12, 6)),  # near anchor 2, col 6
    ]
    test_pair = make_pair((4, 8))
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "copy_to_position"},
    }


def _make_min_distance_open_slot_task():
    """Task 4: source moves to nearest anchor with offset (1,0).

    3 kept objects (2x2 blocks, color 5) at different positions.
    1 source object (1x1, color 3) that moves to offset (1,0) from nearest.
    Variable because source position changes → different nearest anchor.
    """
    def make_pair(src_pos):
        inp = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        anchors = [(1, 1), (1, 9), (9, 5)]
        for ar, ac in anchors:
            inp[ar:ar + 2, ac:ac + 2] = 5
            out[ar:ar + 2, ac:ac + 2] = 5

        sr, sc = src_pos
        inp[sr, sc] = 3

        # Find nearest anchor centroid
        best_d = 999
        best_a = None
        for ar, ac in anchors:
            ac_r, ac_c = ar + 0.5, ac + 0.5
            d = abs(sr - ac_r) + abs(sc - ac_c)
            if d < best_d:
                best_d = d
                best_a = (ar, ac)

        # Destination = anchor top-left + (1, 0) → bottom-left of anchor area
        dest_r = best_a[0] + 2
        dest_c = best_a[1]
        out[dest_r, dest_c] = 3

        return inp, out

    train = [
        make_pair((0, 0)),  # nearest to (1,1)
        make_pair((0, 11)),  # nearest to (1,9)
        make_pair((11, 5)),  # nearest to (9,5)
    ]
    test_pair = make_pair((5, 2))  # nearest to (1,1) or (9,5)
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "copy_to_position"},
    }


def _make_ambiguous_tie_task():
    """Task 5: ambiguous tie — MUST REJECT.

    2 kept objects at mirror positions. Source equidistant.
    Training pair 1 sends source to anchor A, pair 2 sends to anchor B.
    No consistent policy can be induced → must reject.
    """
    def make_pair_a():
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)
        inp[0:2, 0:2] = 5; out[0:2, 0:2] = 5
        inp[0:2, 8:10] = 5; out[0:2, 8:10] = 5
        inp[5, 5] = 1
        out[2, 1] = 1  # near left anchor
        return inp, out

    def make_pair_b():
        inp = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)
        inp[0:2, 0:2] = 5; out[0:2, 0:2] = 5
        inp[0:2, 8:10] = 5; out[0:2, 8:10] = 5
        inp[5, 4] = 1
        out[2, 9] = 1  # near right anchor (contradicts pair A)
        return inp, out

    train = [make_pair_a(), make_pair_b()]
    test_inp = make_pair_a()[0]
    return {
        "train": train,
        "test_inputs": [test_inp],
        "test_outputs": [make_pair_a()[1]],
        "trace": {"best_property": "is_most_common_color", "needed_operator_family": "copy_to_position"},
        "expect_rejection": True,
    }


TASK_FAMILIES = {
    "anchor_offset": _make_anchor_offset_task,
    "same_side_below": _make_same_side_below_task,
    "nearest_anchor_adjacent": _make_nearest_anchor_adjacent_task,
    "min_distance_open_slot": _make_min_distance_open_slot_task,
    "ambiguous_tie_REJECT": _make_ambiguous_tie_task,
}


def main():
    output_dir = Path(__file__).resolve().parent.parent / "outputs" / "operator_microcycle"
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "variable_destination_certificates"
    cert_dir.mkdir(exist_ok=True)

    event_log = ReasoningEventLog()
    inventor = TraceDrivenOperatorInventor(event_log=event_log)

    results = []
    promotions = 0
    false_positives = 0
    rejections_correct = 0
    rejections_expected = 0
    certificates_emitted = 0
    t0 = time.time()

    for family_name, task_fn in TASK_FAMILIES.items():
        print(f"\n{'='*60}")
        print(f"Task family: {family_name}")
        print(f"{'='*60}")

        task_data = task_fn()
        train_pairs = task_data["train"]
        test_inputs = task_data["test_inputs"]
        test_outputs = task_data["test_outputs"]
        trace = task_data["trace"]
        expect_rejection = task_data.get("expect_rejection", False)

        if expect_rejection:
            rejections_expected += 1

        task_id = f"synth_vdp_{family_name}"
        result = inventor.run_full_pipeline(
            task_id=task_id,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs,
        )

        result["family"] = family_name
        result["expect_rejection"] = expect_rejection
        results.append(result)

        if result["promoted"]:
            promotions += 1
            print(f"  PROMOTED: {task_id}")
            if expect_rejection:
                false_positives += 1
                print(f"  FALSE POSITIVE: should have been rejected!")

            if result.get("certificate"):
                cert_data = result["certificate"]
                cert_path = cert_dir / f"{task_id}.json"
                with open(cert_path, "w") as f:
                    json.dump(cert_data, f, indent=2, default=str)
                if result.get("certificate_md"):
                    md_path = cert_dir / f"{task_id}.md"
                    with open(md_path, "w") as f:
                        f.write(result["certificate_md"])
                certificates_emitted += 1
                print(f"  Certificate: {cert_path}")
        else:
            reason = result.get("rejection_reason", "unknown")
            print(f"  REJECTED: {reason}")
            if expect_rejection:
                rejections_correct += 1
                print(f"  (correct rejection)")

    elapsed = time.time() - t0

    # Write summary
    summary = {
        "total_tasks": len(results),
        "promotions": promotions,
        "false_positives": false_positives,
        "rejections_expected": rejections_expected,
        "rejections_correct": rejections_correct,
        "certificates_emitted": certificates_emitted,
        "elapsed_seconds": round(elapsed, 1),
        "results": [
            {
                "task_id": r["task_id"],
                "family": r["family"],
                "promoted": r["promoted"],
                "rejection_reason": r.get("rejection_reason"),
                "expect_rejection": r.get("expect_rejection", False),
            }
            for r in results
        ],
    }

    summary_path = output_dir / "variable_destination_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Markdown summary
    md_path = output_dir / "variable_destination_summary.md"
    with open(md_path, "w") as f:
        f.write("# Variable Destination Policy Microcycle Results\n\n")
        f.write(f"- Tasks: {len(results)}\n")
        f.write(f"- Promotions: {promotions}\n")
        f.write(f"- False positives: {false_positives}\n")
        f.write(f"- Correct rejections: {rejections_correct}/{rejections_expected}\n")
        f.write(f"- Certificates: {certificates_emitted}\n")
        f.write(f"- Elapsed: {elapsed:.1f}s\n\n")
        f.write("| Task | Family | Promoted | Reason |\n")
        f.write("|------|--------|----------|--------|\n")
        for r in results:
            status = "PROMOTED" if r["promoted"] else f"rejected: {r.get('rejection_reason', '?')}"
            f.write(f"| {r['task_id']} | {r['family']} | {r['promoted']} | {status} |\n")

    print(f"\n{'='*60}")
    print("MICROCYCLE SUMMARY")
    print(f"{'='*60}")
    print(f"Tasks:            {len(results)}")
    print(f"Promotions:       {promotions}")
    print(f"False positives:  {false_positives}")
    print(f"Correct rejects:  {rejections_correct}/{rejections_expected}")
    print(f"Certificates:     {certificates_emitted}")
    print(f"Elapsed:          {elapsed:.1f}s")

    # Success criteria
    success = (
        promotions > 0
        and false_positives == 0
        and rejections_correct == rejections_expected
        and certificates_emitted > 0
    )
    print(f"\nSUCCESS: {success}")
    if not success:
        print("FAILURE DETAILS:")
        if promotions == 0:
            print("  - No promotions achieved")
        if false_positives > 0:
            print(f"  - {false_positives} false positives")
        if rejections_correct < rejections_expected:
            print(f"  - Missing rejections: {rejections_expected - rejections_correct}")
        if certificates_emitted == 0:
            print("  - No certificates emitted")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
