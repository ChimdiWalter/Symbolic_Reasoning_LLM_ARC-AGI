#!/usr/bin/env python3
"""Controlled microcycle: validate marker-relative copy-to-position operator
invention chain on synthetic tasks.

Tests 6 marker-relative task families where:
  - The kept/anchor object is the ONLY is_largest=True object (3x3 or 5x5)
  - Each training pair has exactly ONE removed object (1x1) to avoid
    destination collisions
  - Anchor position varies across training pairs so constant CTP displacement
    fails but anchor-relative offset stays constant

Families:
  1. copy_next_to_anchor -- dest at fixed offset right of anchor center
  2. copy_to_anchor_row -- dest at anchor_center + fixed offset
  3. copy_to_anchor_column -- dest at anchor_center + fixed offset
  4. copy_inside_anchor_bbox -- dest at center of hollow anchor
  5. anchor_moves_dest_follows -- anchor varies widely, same relative offset
  6. distractor_anchor_rejection -- inconsistent rule forces rejection

Required chain per task:
  target property found -> old reconstruction fails -> marker-relative proposed ->
  parameters inferred -> LOO passes -> falsification logged -> task solved ->
  certificate emitted

Success criterion:
  operator_generated > 0, operator_validated > 0, promotions > 0,
  false_positives == 0
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.trace_operator_invention import (
    TraceDrivenOperatorInventor,
)
from reasoning_project.events import ReasoningEventLog
from reasoning_project.certificates import certificate_to_json, certificate_to_markdown


# ═══════════════════════════════════════════════════════════════════════════
# SYNTHETIC GRID BUILDERS
# ═══════════════════════════════════════════════════════════════════════════

def _place_rect(grid: np.ndarray, r: int, c: int, h: int, w: int, color: int) -> None:
    """Fill a solid rectangle into grid."""
    grid[r:r + h, c:c + w] = color


def _place_hollow_rect(grid: np.ndarray, r: int, c: int, h: int, w: int, color: int) -> None:
    """Draw a hollow rectangle border into grid."""
    grid[r, c:c + w] = color          # top
    grid[r + h - 1, c:c + w] = color  # bottom
    grid[r:r + h, c] = color          # left
    grid[r:r + h, c + w - 1] = color  # right


def _build_pair(
    grid_shape: Tuple[int, int],
    anchor_pos: Tuple[int, int],
    anchor_size: Tuple[int, int],
    anchor_color: int,
    src_pos: Tuple[int, int],
    src_color: int,
    offset: Tuple[int, int],
    hollow: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build one (input, output) training pair.

    anchor_pos: (row, col) of anchor top-left
    anchor_size: (height, width) of anchor
    src_pos: (row, col) of 1x1 removed object
    offset: (dr, dc) from anchor centroid to destination
    """
    H, W = grid_shape
    ar, ac = anchor_pos
    ah, aw = anchor_size

    inp = np.zeros(grid_shape, dtype=int)
    if hollow:
        _place_hollow_rect(inp, ar, ac, ah, aw, anchor_color)
    else:
        _place_rect(inp, ar, ac, ah, aw, anchor_color)

    sr, sc = src_pos
    assert inp[sr, sc] == 0, \
        f"source ({sr},{sc}) overlaps anchor at ({ar},{ac}) size ({ah},{aw})"
    inp[sr, sc] = src_color

    # Anchor centroid
    anchor_cr = ar + (ah - 1) / 2.0
    anchor_cc = ac + (aw - 1) / 2.0

    # Destination = anchor centroid + offset
    dest_r = int(anchor_cr + offset[0])
    dest_c = int(anchor_cc + offset[1])
    assert 0 <= dest_r < H and 0 <= dest_c < W, \
        f"dest ({dest_r},{dest_c}) out of bounds for {grid_shape}"

    out = inp.copy()
    out[sr, sc] = 0  # erase source
    out[dest_r, dest_c] = src_color  # place at destination

    return inp, out


def _verify_objects(
    pairs: List[Tuple[np.ndarray, np.ndarray]],
    family_name: str,
) -> None:
    """Verify that each pair has exactly one is_largest=True anchor and at
    least one removed object, and they don't overlap."""
    from reasoning_project.reasoning_engine import (
        _extract_objects_with_properties,
        _get_property_value,
    )
    for idx, (inp, _) in enumerate(pairs):
        objs = _extract_objects_with_properties(inp)
        kept = [o for o in objs if _get_property_value(o, "is_largest")]
        removed = [o for o in objs if not _get_property_value(o, "is_largest")]
        assert len(kept) == 1, \
            f"{family_name}[{idx}]: expected 1 kept, got {len(kept)}"
        assert len(removed) >= 1, \
            f"{family_name}[{idx}]: expected >=1 removed, got {len(removed)}"
        assert kept[0]["area"] > max(o["area"] for o in removed), \
            f"{family_name}[{idx}]: anchor area not strictly larger"


# ═══════════════════════════════════════════════════════════════════════════
# FAMILY 1: copy_next_to_anchor
#
# 3x3 anchor (color 5) at varying positions. One 1x1 object per pair.
# Rule: each removed object moves to anchor_center + (0, +4).
# Anchor moves between examples so absolute displacement differs.
# ═══════════════════════════════════════════════════════════════════════════

def _build_family_1() -> Dict[str, Any]:
    """copy_next_to_anchor: dest at anchor_center + (0, +4)."""
    offset = (0, 4)
    # Anchor at different positions each time; src well separated
    configs = [
        # (anchor_pos, src_pos, src_color)
        ((1, 1), (0, 8), 1),
        ((3, 2), (9, 9), 2),
        ((1, 0), (8, 7), 3),
    ]
    train_pairs = []
    for (ap, sp, sc) in configs:
        pair = _build_pair((10, 10), ap, (3, 3), 5, sp, sc, offset)
        train_pairs.append(pair)

    _verify_objects(train_pairs, "family1")

    # Test pair with new anchor position
    test_pair = _build_pair((10, 10), (2, 1), (3, 3), 5, (8, 9), 4, offset)

    return {
        "train": train_pairs,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {
            "task_id": "synth_marker_copy_next_to_anchor",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "marker_relative offset (0,+4) from anchor center",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# FAMILY 2: copy_to_anchor_row
#
# All removed objects go to anchor_center + (-2, +4).
# ═══════════════════════════════════════════════════════════════════════════

def _build_family_2() -> Dict[str, Any]:
    """copy_to_anchor_row: dest at anchor_center + (-2, +4)."""
    offset = (-2, 4)
    configs = [
        ((4, 1), (0, 8), 1),
        ((3, 0), (9, 7), 2),
        ((5, 2), (0, 9), 3),
    ]
    train_pairs = []
    for (ap, sp, sc) in configs:
        pair = _build_pair((10, 10), ap, (3, 3), 5, sp, sc, offset)
        train_pairs.append(pair)

    _verify_objects(train_pairs, "family2")

    test_pair = _build_pair((10, 10), (4, 0), (3, 3), 5, (0, 8), 4, offset)

    return {
        "train": train_pairs,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {
            "task_id": "synth_marker_copy_to_anchor_row",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "marker_relative offset (-2,+4) from anchor center",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# FAMILY 3: copy_to_anchor_column
#
# All removed objects go to anchor_center + (+4, 0).
# ═══════════════════════════════════════════════════════════════════════════

def _build_family_3() -> Dict[str, Any]:
    """copy_to_anchor_column: dest at anchor_center + (+4, 0)."""
    offset = (4, 0)
    configs = [
        ((0, 1), (8, 7), 1),
        ((0, 3), (7, 8), 2),
        ((1, 2), (9, 7), 3),
    ]
    train_pairs = []
    for (ap, sp, sc) in configs:
        pair = _build_pair((10, 10), ap, (3, 3), 5, sp, sc, offset)
        train_pairs.append(pair)

    _verify_objects(train_pairs, "family3")

    test_pair = _build_pair((10, 10), (0, 0), (3, 3), 5, (7, 6), 4, offset)

    return {
        "train": train_pairs,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {
            "task_id": "synth_marker_copy_to_anchor_col",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "marker_relative offset (+4,0) from anchor center",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# FAMILY 4: copy_inside_anchor_bbox
#
# Large hollow 5x5 rectangle (border color 5). Interior is empty (0).
# One 1x1 object placed outside. Copies to anchor_center + (0, 0).
# The anchor area is 16 (border cells), source is 1x1.
# ═══════════════════════════════════════════════════════════════════════════

def _build_family_4() -> Dict[str, Any]:
    """copy_inside_anchor_bbox: dest at anchor_center + (0, 0)."""
    offset = (0, 0)
    configs = [
        # (anchor_pos, src_pos, src_color) - anchor is 5x5 hollow
        ((0, 0), (8, 8), 1),
        ((2, 3), (0, 0), 2),
        ((1, 1), (9, 7), 3),
    ]
    train_pairs = []
    for (ap, sp, sc) in configs:
        pair = _build_pair((12, 12), ap, (5, 5), 5, sp, sc, offset, hollow=True)
        train_pairs.append(pair)

    _verify_objects(train_pairs, "family4")

    test_pair = _build_pair((12, 12), (3, 2), (5, 5), 5, (0, 0), 4, offset, hollow=True)

    return {
        "train": train_pairs,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {
            "task_id": "synth_marker_copy_inside_bbox",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "marker_relative offset (0,0) from anchor center",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# FAMILY 5: anchor_moves_dest_follows
#
# Same logic as Family 1 but anchor moves MORE dramatically.
# Offset from anchor center: (+3, +3).
# ═══════════════════════════════════════════════════════════════════════════

def _build_family_5() -> Dict[str, Any]:
    """anchor_moves_dest_follows: anchor varies widely, offset (+3,+3)."""
    offset = (3, 3)
    configs = [
        ((0, 0), (8, 8), 1),
        ((4, 4), (0, 0), 2),
        ((0, 4), (8, 0), 3),
    ]
    train_pairs = []
    for (ap, sp, sc) in configs:
        pair = _build_pair((10, 10), ap, (3, 3), 5, sp, sc, offset)
        train_pairs.append(pair)

    _verify_objects(train_pairs, "family5")

    test_pair = _build_pair((10, 10), (2, 1), (3, 3), 5, (9, 0), 4, offset)

    return {
        "train": train_pairs,
        "test_inputs": [test_pair[0]],
        "test_outputs": [test_pair[1]],
        "trace": {
            "task_id": "synth_marker_anchor_moves_dest_follows",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "marker_relative offset (+3,+3) anchor varies",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# FAMILY 6: distractor_anchor_rejection
#
# Two 3x3 objects of EQUAL area but different colors. is_largest only
# marks one (the first in label order), but the "rule" is inconsistent
# across examples: destination changes unpredictably.
# Expected: no consistent offset found, system rejects.
# ═══════════════════════════════════════════════════════════════════════════

def _build_family_6() -> Dict[str, Any]:
    """distractor_anchor_rejection: inconsistent rule forces rejection."""
    train_pairs: List[Tuple[np.ndarray, np.ndarray]] = []

    # Example 1: two 3x3 blocks, one 1x1 moved to arbitrary dest
    inp1 = np.zeros((10, 10), dtype=int)
    _place_rect(inp1, 0, 0, 3, 3, 5)   # block A (area=9)
    _place_rect(inp1, 0, 5, 3, 3, 6)   # block B (area=9) -- same area
    inp1[8, 8] = 1                       # removed object
    out1 = inp1.copy()
    out1[8, 8] = 0
    out1[1, 9] = 1  # arbitrary dest (close to block B)
    train_pairs.append((inp1, out1))

    # Example 2: blocks at different positions, dest somewhere else
    inp2 = np.zeros((10, 10), dtype=int)
    _place_rect(inp2, 3, 0, 3, 3, 5)
    _place_rect(inp2, 3, 5, 3, 3, 6)
    inp2[9, 9] = 2
    out2 = inp2.copy()
    out2[9, 9] = 0
    out2[0, 0] = 2  # different arbitrary dest
    train_pairs.append((inp2, out2))

    # Example 3: yet another arrangement
    inp3 = np.zeros((10, 10), dtype=int)
    _place_rect(inp3, 5, 1, 3, 3, 5)
    _place_rect(inp3, 5, 6, 3, 3, 6)
    inp3[0, 9] = 3
    out3 = inp3.copy()
    out3[0, 9] = 0
    out3[9, 0] = 3  # yet another arbitrary dest
    train_pairs.append((inp3, out3))

    # Test
    test_inp = np.zeros((10, 10), dtype=int)
    _place_rect(test_inp, 1, 0, 3, 3, 5)
    _place_rect(test_inp, 1, 5, 3, 3, 6)
    test_inp[8, 8] = 4
    test_out = test_inp.copy()
    test_out[8, 8] = 0
    test_out[5, 5] = 4

    return {
        "train": train_pairs,
        "test_inputs": [test_inp],
        "test_outputs": [test_out],
        "trace": {
            "task_id": "synth_marker_distractor_rejection",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "ambiguous_anchor_distractor",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

FAMILY_BUILDERS = {
    "copy_next_to_anchor":         _build_family_1,
    "copy_to_anchor_row":          _build_family_2,
    "copy_to_anchor_column":       _build_family_3,
    "copy_inside_anchor_bbox":     _build_family_4,
    "anchor_moves_dest_follows":   _build_family_5,
    "distractor_anchor_rejection": _build_family_6,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Marker-relative copy-to-position operator microcycle test",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/operator_microcycle",
        help="Directory for output artifacts",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "marker_relative_certificates"
    cert_dir.mkdir(exist_ok=True)

    event_log = ReasoningEventLog()
    inventor = TraceDrivenOperatorInventor(event_log=event_log)

    results: List[Dict[str, Any]] = []
    total_proposed = 0
    total_validated = 0
    total_promoted = 0
    total_fp = 0
    total_certs = 0

    t0 = time.time()

    for family_name, builder in FAMILY_BUILDERS.items():
        family = builder()
        task_id = family["trace"]["task_id"]

        print(f"\n{'=' * 60}")
        print(f"  Family: {family_name} (task={task_id})")
        print(f"{'=' * 60}")

        train_pairs = family["train"]
        test_inputs = family["test_inputs"]
        test_outputs = family["test_outputs"]
        trace = family["trace"]

        # Diagnostic: show grid shapes and object counts
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        for idx, (inp, out) in enumerate(train_pairs):
            objs = _extract_objects_with_properties(inp)
            kept = [o for o in objs if _get_property_value(o, "is_largest")]
            removed = [o for o in objs if not _get_property_value(o, "is_largest")]
            print(f"  train[{idx}]: shape={inp.shape}, "
                  f"n_objects={len(objs)}, kept={len(kept)}, removed={len(removed)}")
            for oi, o in enumerate(objs):
                print(f"    obj[{oi}]: area={o['area']}, color={o['primary_color']}, "
                      f"center=({o['center_r']:.1f},{o['center_c']:.1f}), "
                      f"is_largest={o.get('is_largest', False)}")

        result = inventor.run_full_pipeline(
            task_id=task_id,
            train_pairs=train_pairs,
            test_inputs=test_inputs,
            trace=trace,
            test_outputs=test_outputs,
        )

        proposed = result["operator_proposed"]
        validated = result["loo_passed"]
        promoted = result["promoted"]
        fp = result.get("false_positive", False)

        total_proposed += int(proposed)
        total_validated += int(validated)
        total_promoted += int(promoted)
        total_fp += int(fp)

        chain_ok = (
            proposed
            and result["parameterized"]
            and result["train_consistent"]
            and result["loo_passed"]
            and result["promoted"]
        )

        # Save certificate if emitted
        cert_data = result.get("certificate")
        if cert_data:
            total_certs += 1
            cert_path = cert_dir / f"{task_id}.json"
            with open(cert_path, "w") as f:
                json.dump(cert_data, f, indent=2)
            cert_md = result.get("certificate_md", "")
            with open(cert_dir / f"{task_id}.md", "w") as f:
                f.write(cert_md)
            result["certificate_path"] = str(cert_path)

        print(f"  proposed={proposed} param={result['parameterized']} "
              f"train={result['train_consistent']} loo={result['loo_passed']} "
              f"falsif={result['falsification_status']} "
              f"promoted={promoted} fp={fp} chain={'OK' if chain_ok else 'FAIL'}")
        if result.get("rejection_reason"):
            print(f"  rejection_reason: {result['rejection_reason']}")

        results.append({
            "family": family_name,
            "task_id": task_id,
            **{k: v for k, v in result.items()
               if k != "predictions" and k != "certificate_md"},
        })

    elapsed = time.time() - t0

    # -- Write output artifacts --

    # Event chains
    event_log.export_jsonl(str(output_dir / "marker_relative_event_chains.jsonl"))

    # Promoted tasks
    with open(output_dir / "marker_relative_promoted_tasks.jsonl", "w") as f:
        for r in results:
            if r.get("promoted"):
                f.write(json.dumps({
                    "task_id": r["task_id"],
                    "family": r["family"],
                    "operator_id": r.get("operator_id"),
                }) + "\n")

    # Validated operators
    with open(output_dir / "marker_relative_validated_operators.jsonl", "w") as f:
        for rec in inventor.validated:
            f.write(json.dumps(rec.to_dict()) + "\n")

    # -- Summary markdown --

    positive_families = [r for r in results if r["family"] != "distractor_anchor_rejection"]
    negative_families = [r for r in results if r["family"] == "distractor_anchor_rejection"]
    distractor_correct = all(not r.get("promoted") for r in negative_families)

    summary_lines = [
        "# Marker-Relative Copy-to-Position Microcycle Results",
        "",
        f"- Families tested: {len(FAMILY_BUILDERS)}",
        f"- Positive families (should promote): {len(positive_families)}",
        f"- Negative families (should reject): {len(negative_families)}",
        f"- Operators proposed: {total_proposed}",
        f"- Operators validated (LOO): {total_validated}",
        f"- Tasks promoted: {total_promoted}",
        f"- False positives: {total_fp}",
        f"- Certificates emitted: {total_certs}",
        f"- Distractor rejection correct: {distractor_correct}",
        f"- Elapsed: {elapsed:.1f}s",
        "",
        "## Success Criteria",
        "",
        f"- operator_generated > 0: **{'PASS' if total_proposed > 0 else 'FAIL'}**",
        f"- operator_validated > 0: **{'PASS' if total_validated > 0 else 'FAIL'}**",
        f"- promotions > 0: **{'PASS' if total_promoted > 0 else 'FAIL'}**",
        f"- false_positives == 0: **{'PASS' if total_fp == 0 else 'FAIL'}**",
        f"- distractor rejected: **{'PASS' if distractor_correct else 'FAIL'}**",
        "",
        "## Per-Family Results",
        "",
        "| Family | Proposed | Param | Train | LOO | Falsif | Promoted | FP | Chain |",
        "|--------|----------|-------|-------|-----|--------|----------|----|-------|",
    ]

    for r in results:
        chain = "OK" if r.get("promoted") else "FAIL"
        if r["family"] == "distractor_anchor_rejection":
            chain = "OK (reject)" if not r.get("promoted") else "FAIL (should reject)"
        summary_lines.append(
            f"| {r['family']} | {r['operator_proposed']} | {r['parameterized']} | "
            f"{r['train_consistent']} | {r['loo_passed']} | {r['falsification_status']} | "
            f"{r.get('promoted', False)} | {r.get('false_positive', False)} | {chain} |"
        )

    summary_lines.extend(["", "## Interpretation", ""])
    if total_promoted > 0 and total_fp == 0 and distractor_correct:
        summary_lines.append(
            "Marker-relative microcycle PASSES: the marker-relative copy-to-position "
            "operator invention chain is mechanically sound. Operators are proposed "
            "from traces, parameterized relative to anchors, LOO-validated, falsified, "
            "and produce correct promotions with zero false positives. The distractor "
            "family is correctly rejected."
        )
    else:
        summary_lines.append(
            f"Marker-relative microcycle result: {total_promoted} promotions, "
            f"{total_fp} FP, distractor_correct={distractor_correct}. "
            "See per-family breakdown for failure analysis."
        )

    summary_lines.extend(["", "## Rejection Details", ""])
    for r in results:
        if r.get("rejection_reason"):
            summary_lines.append(
                f"- **{r['family']}**: {r['rejection_reason']}"
            )

    with open(output_dir / "marker_relative_summary.md", "w") as f:
        f.write("\n".join(summary_lines) + "\n")

    # -- Print final verdict --

    print(f"\n{'=' * 60}")
    print("MARKER-RELATIVE MICROCYCLE COMPLETE")
    print(f"  Promoted: {total_promoted}/{len(positive_families)} positive families")
    print(f"  False positives: {total_fp}")
    print(f"  Certificates: {total_certs}")
    print(f"  Distractor rejected: {distractor_correct}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print()
    print("SUCCESS CRITERIA:")
    print(f"  operator_generated > 0: {'PASS' if total_proposed > 0 else 'FAIL'}")
    print(f"  operator_validated > 0: {'PASS' if total_validated > 0 else 'FAIL'}")
    print(f"  promotions > 0:        {'PASS' if total_promoted > 0 else 'FAIL'}")
    print(f"  false_positives == 0:  {'PASS' if total_fp == 0 else 'FAIL'}")
    print(f"{'=' * 60}")

    all_pass = (
        total_proposed > 0
        and total_validated > 0
        and total_promoted > 0
        and total_fp == 0
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
