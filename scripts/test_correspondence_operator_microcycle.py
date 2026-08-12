#!/usr/bin/env python3.11
"""Controlled microcycle: verify the correspondence-based operator invention chain.

Tests 6 correspondence task families:
  1. row-indexed correspondence (sources matched to kept blocks by row order,
     source colors DISTINCT from kept block colors)
  2. order-preserving row correspondence
  3. nearest-anchor correspondence
  4. nearest-by-position correspondence (different-sized kept blocks)
  5. ambiguous correspondence that MUST reject (two identical kept blocks,
     inconsistent source→target mapping across training pairs)
  6. inconsistent-displacement case that MUST reject

DESIGN RULE: source colors must NEVER appear in kept blocks. This avoids
_find_object_in_output false-matching source pixels inside kept blocks.

Required chain per promotable task:
  target selector found → constant displacement fails →
  marker-relative rule fails → correspondence rule inferred →
  relative displacement inferred → LOO passes →
  falsification logged → task solved → certificate emitted

Success criteria:
  operator_generated > 0, promotions > 0, false_positives = 0,
  at least one reject case handled correctly, at least one certificate emitted
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.trace_operator_invention import (
    TraceDrivenOperatorInventor,
    infer_correspondence_params,
    execute_correspondence_copy,
)
from reasoning_project.events import ReasoningEventLog
from reasoning_project.certificates import certificate_to_json, certificate_to_markdown


def _make_row_indexed_task():
    """Task 1: sources matched to kept blocks by row order; source colors
    are DISTINCT from kept block colors.

    3 kept blocks: 4x4, colors 6, 7, 8 at rows 0, 6, 12, col 0.
    3 source pixels: colors 1, 2, 3 at various positions in right half.
    Correspondence: source ranked 1st by row → kept ranked 1st by row, etc.
    Relative displacement from matched kept centroid: (0, 6).
    """
    def make_pair(src_positions):
        inp = np.zeros((16, 20), dtype=int)
        out = np.zeros((16, 20), dtype=int)

        kept_positions = [(0, 0), (6, 0), (12, 0)]
        kept_colors = [6, 7, 8]
        for (kr, kc), color in zip(kept_positions, kept_colors):
            inp[kr:kr + 4, kc:kc + 4] = color
            out[kr:kr + 4, kc:kc + 4] = color

        kept_centroids = [(kr + 1.5, kc + 1.5) for kr, kc in kept_positions]
        src_colors = [1, 2, 3]

        sorted_src = sorted(enumerate(src_positions), key=lambda x: x[1][0])
        for rank, (orig_idx, (sr, sc)) in enumerate(sorted_src):
            color = src_colors[orig_idx]
            inp[sr, sc] = color
            kr, kc = kept_centroids[rank]
            dest_r = int(round(kr))
            dest_c = int(round(kc)) + 6
            out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([(1, 14), (7, 14), (13, 14)]),
        make_pair([(2, 16), (8, 16), (14, 16)]),
        make_pair([(0, 15), (6, 15), (12, 15)]),
    ]
    test_pair = make_pair([(3, 14), (9, 14), (15, 14)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "large_object", "needed_operator_family": "copy_to_position"},
    }


def _make_order_preserving_task():
    """Task 2: sources matched to targets by row order.

    3 kept objects: 4x4 blocks at rows 0, 6, 12 (color 9, large_object=True).
    3 source objects: single pixels at various rows (colors 1, 2, 3).
    Sorted by row: 1st source → 1st kept, 2nd → 2nd, 3rd → 3rd.
    Relative displacement from matched target centroid: (0, 6).
    """
    def make_pair(src_rows):
        inp = np.zeros((16, 14), dtype=int)
        out = np.zeros((16, 14), dtype=int)

        kept_rows = [0, 6, 12]
        for kr in kept_rows:
            inp[kr:kr + 4, 0:4] = 9
            out[kr:kr + 4, 0:4] = 9

        kept_centroids = [(kr + 1.5, 1.5) for kr in kept_rows]
        src_colors = [1, 2, 3]

        sorted_src = sorted(enumerate(src_rows), key=lambda x: x[1])
        for rank, (orig_idx, sr) in enumerate(sorted_src):
            color = src_colors[orig_idx]
            inp[sr, 10] = color
            kr, kc = kept_centroids[rank]
            dest_r = int(round(kr))
            dest_c = int(round(kc)) + 6
            out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([1, 7, 13]),
        make_pair([2, 8, 14]),
        make_pair([0, 9, 12]),
    ]
    test_pair = make_pair([3, 6, 15])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "large_object", "needed_operator_family": "copy_to_position"},
    }


def _make_nearest_anchor_task():
    """Task 3: each source moves to a fixed offset from its nearest kept object.

    3 kept objects at well-separated corners: 4x4 blocks, color 9.
    3 source objects (colors 1, 2, 3), each clearly nearest to one kept object.
    Relative displacement: (3, 0) from matched target centroid.
    """
    def make_pair(src_positions):
        inp = np.zeros((20, 20), dtype=int)
        out = np.zeros((20, 20), dtype=int)

        kept_positions = [(0, 0), (0, 14), (14, 0)]
        for kr, kc in kept_positions:
            inp[kr:kr + 4, kc:kc + 4] = 9
            out[kr:kr + 4, kc:kc + 4] = 9

        kept_centroids = [(kr + 1.5, kc + 1.5) for kr, kc in kept_positions]
        src_colors = [1, 2, 3]

        for (sr, sc), color in zip(src_positions, src_colors):
            inp[sr, sc] = color
            dists = [abs(sr - kr) + abs(sc - kc) for kr, kc in kept_centroids]
            ki = dists.index(min(dists))
            kr, kc = kept_centroids[ki]
            dest_r = int(round(kr)) + 3
            dest_c = int(round(kc))
            if 0 <= dest_r < 20 and 0 <= dest_c < 20:
                out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([(5, 5), (5, 19), (19, 5)]),
        make_pair([(6, 6), (6, 19), (19, 6)]),
        make_pair([(7, 5), (7, 13), (18, 5)]),
    ]
    test_pair = make_pair([(8, 5), (8, 19), (19, 7)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "large_object", "needed_operator_family": "copy_to_position"},
    }


def _make_nearest_by_position_task():
    """Task 4: sources matched to nearest kept object by centroid distance.
    Kept objects have different sizes (to test that size alone isn't the rule).

    3 kept objects touching left boundary, different sizes, all color 9.
    3 source pixels (colors 1, 2, 3) each near a specific kept object.
    Relative displacement: (4, 0) from matched kept centroid.
    """
    def make_pair(src_positions):
        inp = np.zeros((16, 20), dtype=int)
        out = np.zeros((16, 20), dtype=int)

        kept_specs = [
            (0, 0, 4, 4),   # row, col, h, w
            (5, 0, 3, 3),
            (9, 0, 5, 2),
        ]
        kept_centroids = []
        for (kr, kc, kh, kw) in kept_specs:
            inp[kr:kr + kh, kc:kc + kw] = 9
            out[kr:kr + kh, kc:kc + kw] = 9
            kept_centroids.append((kr + (kh - 1) / 2.0, kc + (kw - 1) / 2.0))

        src_colors = [1, 2, 3]
        for (sr, sc), color in zip(src_positions, src_colors):
            inp[sr, sc] = color
            dists = [abs(sr - kr) + abs(sc - kc) for kr, kc in kept_centroids]
            ki = dists.index(min(dists))
            kr, kc = kept_centroids[ki]
            dest_r = int(round(kr)) + 4
            dest_c = int(round(kc))
            out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([(2, 8), (6, 8), (11, 8)]),
        make_pair([(1, 10), (5, 10), (10, 10)]),
        make_pair([(3, 12), (7, 12), (12, 12)]),
    ]
    test_pair = make_pair([(2, 14), (6, 14), (11, 14)])
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "touches_left", "needed_operator_family": "copy_to_position"},
    }


def _make_ambiguous_reject_task():
    """Task 5: ambiguous — MUST REJECT.

    2 kept objects: identical 4x4 blocks (both color 9) at rows 0 and 8.
    2 source pixels (colors 1, 2).
    Mapping is inconsistent across training pairs:
      pair 1: source near kept[0] → kept[0], source near kept[1] → kept[1]
      pair 2: source near kept[0] → kept[1], source near kept[1] → kept[0]
    No correspondence rule can be consistent.
    """
    def make_pair(src_positions, mapping):
        inp = np.zeros((14, 14), dtype=int)
        out = np.zeros((14, 14), dtype=int)

        kept_positions = [(0, 0), (8, 0)]
        for kr, kc in kept_positions:
            inp[kr:kr + 4, kc:kc + 4] = 9
            out[kr:kr + 4, kc:kc + 4] = 9

        src_colors = [1, 2]
        for i, ((sr, sc), color) in enumerate(zip(src_positions, src_colors)):
            inp[sr, sc] = color
            ki = mapping[i]
            kr, kc = kept_positions[ki]
            out[kr + 2, kc + 6] = color

        return inp, out

    # Pair 1: src near top → dest near top, src near bottom → dest near bottom
    # Pair 2: src near top → dest near BOTTOM, src near bottom → dest near TOP
    # This is inconsistent for any single rule.
    train = [
        make_pair([(2, 10), (10, 10)], [0, 1]),
        make_pair([(10, 10), (2, 10)], [0, 1]),
        make_pair([(1, 10), (9, 10)], [0, 1]),
    ]
    test_inp, test_out = make_pair([(3, 10), (11, 10)], [0, 1])
    return {
        "train": train,
        "test_inputs": [test_inp],
        "test_outputs": [test_out],
        "trace": {"best_property": "large_object", "needed_operator_family": "copy_to_position"},
        "expect_rejection": True,
    }


def _make_inconsistent_displacement_reject_task():
    """Task 6: inconsistent displacement — MUST REJECT.

    3 kept objects, 3 source objects. Nearest-anchor matching works,
    but the relative displacement CHANGES between training pairs.
    """
    def make_pair(src_positions, extra_offset):
        inp = np.zeros((20, 20), dtype=int)
        out = np.zeros((20, 20), dtype=int)

        kept_positions = [(0, 0), (0, 14), (14, 0)]
        for kr, kc in kept_positions:
            inp[kr:kr + 4, kc:kc + 4] = 9
            out[kr:kr + 4, kc:kc + 4] = 9

        kept_centroids = [(kr + 1.5, kc + 1.5) for kr, kc in kept_positions]
        src_colors = [1, 2, 3]

        for (sr, sc), color in zip(src_positions, src_colors):
            inp[sr, sc] = color
            dists = [abs(sr - kr) + abs(sc - kc) for kr, kc in kept_centroids]
            ki = dists.index(min(dists))
            kr, kc = kept_centroids[ki]
            dest_r = int(round(kr)) + 3 + extra_offset
            dest_c = int(round(kc))
            if 0 <= dest_r < 20 and 0 <= dest_c < 20:
                out[dest_r, dest_c] = color

        return inp, out

    train = [
        make_pair([(5, 5), (5, 19), (19, 5)], 0),
        make_pair([(6, 6), (6, 19), (19, 6)], 2),  # displacement differs
        make_pair([(7, 5), (7, 13), (18, 5)], 0),
    ]
    test_pair = make_pair([(8, 5), (8, 19), (19, 7)], 0)
    return {
        "train": train,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {"best_property": "large_object", "needed_operator_family": "copy_to_position"},
        "expect_rejection": True,
    }


TASK_FAMILIES = {
    "row_indexed_correspondence": _make_row_indexed_task,
    "order_preserving_row": _make_order_preserving_task,
    "nearest_anchor": _make_nearest_anchor_task,
    "nearest_by_position": _make_nearest_by_position_task,
    "ambiguous_REJECT": _make_ambiguous_reject_task,
    "inconsistent_displacement_REJECT": _make_inconsistent_displacement_reject_task,
}


def _hypothesis_family(result):
    oid = result.get("operator_id", "")
    if oid and oid.startswith("cctp_"):
        return "correspondence_copy_to_position"
    elif oid and oid.startswith("mrctp_"):
        return "marker_relative_copy_to_position"
    elif oid and oid.startswith("ctp_"):
        return "copy_to_position"
    return "unknown"


def main():
    output_dir = Path(__file__).resolve().parent.parent / "outputs" / "operator_microcycle"
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "correspondence_certificates"
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

        task_id = f"synth_{family_name}"
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
            fam = _hypothesis_family(result)
            print(f"  PROMOTED: {task_id} (family={fam})")
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

    print(f"\n{'='*60}")
    print(f"CORRESPONDENCE MICROCYCLE SUMMARY")
    print(f"{'='*60}")
    print(f"Tasks attempted:        {len(results)}")
    print(f"Promotions:             {promotions}")
    print(f"False positives:        {false_positives}")
    print(f"Certificates emitted:   {certificates_emitted}")
    print(f"Expected rejections:    {rejections_expected}")
    print(f"Correct rejections:     {rejections_correct}")
    print(f"Time:                   {elapsed:.1f}s")

    checks = {
        "operator_generated > 0": promotions > 0 or any(r.get("operator_proposed") for r in results),
        "promotions > 0": promotions > 0,
        "false_positives == 0": false_positives == 0,
        "at least one reject case handled correctly": rejections_correct >= 1,
        "at least one certificate emitted": certificates_emitted > 0,
    }

    print(f"\nSuccess criteria:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check_name}")
        if not passed:
            all_passed = False

    overall = "MICROCYCLE PASSES" if all_passed else "MICROCYCLE FAILS"
    print(f"\n{overall}")

    with open(output_dir / "correspondence_summary.md", "w") as f:
        f.write("# Correspondence Operator Microcycle Summary\n\n")
        f.write(f"- Tasks attempted: {len(results)}\n")
        f.write(f"- Promotions: {promotions}\n")
        f.write(f"- False positives: {false_positives}\n")
        f.write(f"- Certificates emitted: {certificates_emitted}\n")
        f.write(f"- Expected rejections: {rejections_expected}\n")
        f.write(f"- Correct rejections: {rejections_correct}\n")
        f.write(f"- Time: {elapsed:.1f}s\n")
        f.write(f"\n## Result: {overall}\n\n")
        f.write("## Per-task results\n\n")
        f.write("| Family | Promoted | Family Type | Rejection Reason | Expected Rejection |\n")
        f.write("|--------|----------|-------------|-----------------|--------------------|\n")
        for r in results:
            fam = _hypothesis_family(r) if r["promoted"] else "-"
            f.write(f"| {r['family']} | {r['promoted']} | {fam} | {r.get('rejection_reason', '-')} | {r.get('expect_rejection', False)} |\n")

    with open(output_dir / "correspondence_promoted_tasks.jsonl", "w") as f:
        for r in results:
            if r["promoted"]:
                f.write(json.dumps({
                    "task_id": r["task_id"],
                    "family": r["family"],
                    "operator_id": r.get("operator_id"),
                    "operator_family": _hypothesis_family(r),
                }, default=str) + "\n")

    with open(output_dir / "correspondence_validated_operators.jsonl", "w") as f:
        for rec in inventor.validated:
            f.write(json.dumps(rec.to_dict(), default=str) + "\n")

    event_log.export_jsonl(str(output_dir / "correspondence_event_chains.jsonl"))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
