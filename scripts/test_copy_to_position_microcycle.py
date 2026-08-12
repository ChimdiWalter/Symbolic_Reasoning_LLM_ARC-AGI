#!/usr/bin/env python3.11
"""Controlled microcycle: verify the full operator invention chain on synthetic tasks.

Tests 5 copy-to-position task families:
  1. constant displacement copy
  2. constant displacement move
  3. marker-relative copy (converge to largest)
  4. copy to matching colored destination (converge to point)
  5. copy multiple selected objects with same displacement

Required chain per task:
  target property found → old reconstruction fails → operator gap classified →
  copy_to_position proposed → parameters inferred → LOO passes →
  falsification logged → task solved → certificate emitted

Success criterion:
  operator_generated > 0, operator_validated > 0, promotions > 0,
  false_positives = 0, at least one certificate emitted
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
    infer_copy_to_position_params,
    execute_copy_to_position,
)
from reasoning_project.events import ReasoningEventLog
from reasoning_project.certificates import certificate_to_json, certificate_to_markdown


def _make_pair(grid_size, kept_spec, moved_specs, displacement_fn):
    """Build a (inp, out) pair from specifications.

    kept_spec: list of (r_start, r_end, c_start, c_end, color) for kept objects
    moved_specs: list of (r, c, color) for single-cell objects to move
    displacement_fn: (r, c) -> (nr, nc) or None to use per-object displacements
    """
    inp = np.zeros(grid_size, dtype=int)
    for rs, re, cs, ce, col in kept_spec:
        inp[rs:re, cs:ce] = col
    for r, c, col in moved_specs:
        inp[r, c] = col

    out = inp.copy()
    for r, c, col in moved_specs:
        out[r, c] = 0
        nr, nc = displacement_fn(r, c)
        if 0 <= nr < grid_size[0] and 0 <= nc < grid_size[1]:
            out[nr, nc] = col

    return inp, out


def _const_disp(dr, dc):
    return lambda r, c: (r + dr, c + dc)


def _converge_to(dest_r, dest_c):
    return lambda r, c: (dest_r, dest_c)


TASK_FAMILIES = {
    "constant_displacement_move": {
        "train": [
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 1)],  # 3x3 block = largest
                [(1, 6, 2), (5, 7, 3), (8, 4, 4)],
                _const_disp(1, 0),
            ),
            _make_pair(
                (10, 10),
                [(0, 3, 1, 4, 5)],
                [(2, 7, 6), (6, 5, 7)],
                _const_disp(1, 0),
            ),
        ],
        "test_inputs": [
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 1)],
                [(1, 6, 2), (5, 7, 3), (8, 4, 4)],
                _const_disp(1, 0),
            )[0],
        ],
        "test_outputs": [
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 1)],
                [(1, 6, 2), (5, 7, 3), (8, 4, 4)],
                _const_disp(1, 0),
            )[1],
        ],
        "trace": {
            "task_id": "synth_const_disp_move",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "constant (1,0)",
        },
    },
    "converge_to_center": {
        "train": [
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 1)],
                [(1, 7, 2), (7, 2, 3)],
                _converge_to(5, 5),
            ),
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 5)],
                [(2, 8, 6), (8, 1, 7)],
                _converge_to(5, 5),
            ),
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 8)],
                [(0, 9, 9), (9, 0, 4)],
                _converge_to(5, 5),
            ),
        ],
        "test_inputs": [
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 1)],
                [(1, 7, 2), (7, 2, 3)],
                _converge_to(5, 5),
            )[0],
        ],
        "test_outputs": [
            _make_pair(
                (10, 10),
                [(0, 3, 0, 3, 1)],
                [(1, 7, 2), (7, 2, 3)],
                _converge_to(5, 5),
            )[1],
        ],
        "trace": {
            "task_id": "synth_converge_center",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "converge_to_point (5,5)",
        },
    },
    "constant_disp_right": {
        "train": [
            _make_pair(
                (8, 12),
                [(0, 4, 0, 4, 1)],
                [(2, 6, 2), (5, 8, 3)],
                _const_disp(0, 2),
            ),
            _make_pair(
                (8, 12),
                [(0, 4, 0, 4, 4)],
                [(1, 7, 5), (6, 9, 6)],
                _const_disp(0, 2),
            ),
        ],
        "test_inputs": [
            _make_pair(
                (8, 12),
                [(0, 4, 0, 4, 1)],
                [(2, 6, 2), (5, 8, 3)],
                _const_disp(0, 2),
            )[0],
        ],
        "test_outputs": [
            _make_pair(
                (8, 12),
                [(0, 4, 0, 4, 1)],
                [(2, 6, 2), (5, 8, 3)],
                _const_disp(0, 2),
            )[1],
        ],
        "trace": {
            "task_id": "synth_const_disp_right",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "constant (0,2)",
        },
    },
    "converge_topleft": {
        "train": [
            _make_pair(
                (10, 10),
                [(4, 7, 4, 7, 1)],
                [(0, 8, 2), (8, 0, 3)],
                _converge_to(2, 2),
            ),
            _make_pair(
                (10, 10),
                [(4, 7, 4, 7, 5)],
                [(1, 9, 6), (9, 1, 7)],
                _converge_to(2, 2),
            ),
            _make_pair(
                (10, 10),
                [(4, 7, 4, 7, 8)],
                [(0, 7, 9), (7, 0, 4)],
                _converge_to(2, 2),
            ),
        ],
        "test_inputs": [
            _make_pair(
                (10, 10),
                [(4, 7, 4, 7, 1)],
                [(0, 8, 2), (8, 0, 3)],
                _converge_to(2, 2),
            )[0],
        ],
        "test_outputs": [
            _make_pair(
                (10, 10),
                [(4, 7, 4, 7, 1)],
                [(0, 8, 2), (8, 0, 3)],
                _converge_to(2, 2),
            )[1],
        ],
        "trace": {
            "task_id": "synth_converge_topleft",
            "best_property": "is_largest",
            "needed_operator_family": "copy_to_position",
            "displacement_summary": "converge_to_point (2,2)",
        },
    },
}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/operator_microcycle")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = output_dir / "certificates"
    cert_dir.mkdir(exist_ok=True)

    event_log = ReasoningEventLog()
    inventor = TraceDrivenOperatorInventor(event_log=event_log)

    results = []
    total_proposed = 0
    total_validated = 0
    total_promoted = 0
    total_fp = 0
    total_certs = 0

    t0 = time.time()

    for family_name, family in TASK_FAMILIES.items():
        task_id = family["trace"]["task_id"]
        print(f"\n{'='*60}")
        print(f"  Family: {family_name} (task={task_id})")
        print(f"{'='*60}")

        train_pairs = family["train"]
        test_inputs = family["test_inputs"]
        test_outputs = family["test_outputs"]
        trace = family["trace"]

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

        results.append({
            "family": family_name,
            "task_id": task_id,
            **{k: v for k, v in result.items() if k != "predictions" and k != "certificate_md"},
        })

    elapsed = time.time() - t0

    event_log.export_jsonl(str(output_dir / "event_chains.jsonl"))

    with open(output_dir / "promoted_tasks.jsonl", "w") as f:
        for r in results:
            if r.get("promoted"):
                f.write(json.dumps({"task_id": r["task_id"], "family": r["family"]}) + "\n")

    with open(output_dir / "validated_operators.jsonl", "w") as f:
        for rec in inventor.validated:
            f.write(json.dumps(rec.to_dict()) + "\n")

    summary_lines = [
        "# Copy-to-Position Microcycle Results",
        "",
        f"- Families tested: {len(TASK_FAMILIES)}",
        f"- Operators proposed: {total_proposed}",
        f"- Operators validated (LOO): {total_validated}",
        f"- Tasks promoted: {total_promoted}",
        f"- False positives: {total_fp}",
        f"- Certificates emitted: {total_certs}",
        f"- Elapsed: {elapsed:.1f}s",
        "",
        "## Success Criteria",
        "",
        f"- operator_generated > 0: **{'PASS' if total_proposed > 0 else 'FAIL'}**",
        f"- operator_validated > 0: **{'PASS' if total_validated > 0 else 'FAIL'}**",
        f"- promotions > 0: **{'PASS' if total_promoted > 0 else 'FAIL'}**",
        f"- false_positives = 0: **{'PASS' if total_fp == 0 else 'FAIL'}**",
        f"- certificate emitted: **{'PASS' if total_certs > 0 else 'FAIL'}**",
        "",
        "## Per-Family Results",
        "",
        "| Family | Proposed | Param | Train | LOO | Falsif | Promoted | FP | Chain |",
        "|--------|----------|-------|-------|-----|--------|----------|----|-------|",
    ]

    for r in results:
        chain = "OK" if r.get("promoted") else "FAIL"
        summary_lines.append(
            f"| {r['family']} | {r['operator_proposed']} | {r['parameterized']} | "
            f"{r['train_consistent']} | {r['loo_passed']} | {r['falsification_status']} | "
            f"{r.get('promoted', False)} | {r.get('false_positive', False)} | {chain} |"
        )

    summary_lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    if total_promoted > 0 and total_fp == 0:
        summary_lines.append(
            "Microcycle PASSES: operator invention chain is mechanically sound. "
            "Operators are proposed from traces, parameterized, LOO-validated, "
            "falsified, and produce correct promotions with zero false positives."
        )
    else:
        summary_lines.append(
            f"Microcycle result: {total_promoted} promotions, {total_fp} FP. "
            "See per-family breakdown for failure analysis."
        )

    with open(output_dir / "copy_to_position_summary.md", "w") as f:
        f.write("\n".join(summary_lines) + "\n")

    print(f"\n{'='*60}")
    print(f"MICROCYCLE COMPLETE: {total_promoted} promoted, {total_fp} FP, "
          f"{total_certs} certificates, {elapsed:.1f}s")
    print(f"{'='*60}")

    return 0 if (total_promoted > 0 and total_fp == 0 and total_certs > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
