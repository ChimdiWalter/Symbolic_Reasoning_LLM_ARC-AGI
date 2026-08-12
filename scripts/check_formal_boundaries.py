#!/usr/bin/env python3
"""Generate a finite formal-boundary audit report from a generated dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.formal import (
    FiniteMorphism,
    aid_profile,
    check_finite_category_laws,
    finite_path_witness,
)
from reasoning_project.generators import load_suite
from reasoning_project.schemas import ProgramStep
from reasoning_project.utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run finite category/path/AID formal-boundary checks.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-examples", type=int, default=12)
    args = parser.parse_args()

    suite = load_suite(args.dataset)
    domain = []
    for task in suite.tasks:
        for example in task.examples.get("train", []):
            domain.append(example.input_grid)
            if len(domain) >= args.max_examples:
                break
        if len(domain) >= args.max_examples:
            break

    morphisms = [
        FiniteMorphism("identity", [ProgramStep("identity")]),
        FiniteMorphism("reflect_horizontal", [ProgramStep("reflect_horizontal")]),
        FiniteMorphism("reflect_vertical", [ProgramStep("reflect_vertical")]),
    ]
    category_report = check_finite_category_laws(morphisms, domain)
    left = [ProgramStep("reflect_vertical"), ProgramStep("recolor_largest_component", {"new_color": 7})]
    right = [ProgramStep("recolor_largest_component", {"new_color": 7}), ProgramStep("reflect_vertical")]
    path_report = finite_path_witness(left, right, domain)
    first_task = suite.tasks[0]
    aid_report = aid_profile(first_task.program, first_task.examples.get("train", []))

    write_json(
        args.output,
        {
            "dataset": args.dataset,
            "domain_examples": len(domain),
            "category_laws": category_report.to_dict(),
            "path_witness": path_report.to_dict(),
            "aid_profile_first_task": aid_report.to_dict(),
            "non_claims": [
                "not full category theory",
                "not full HoTT",
                "not exact algorithmic information dynamics",
                "not ARC state of the art",
                "not an AGI proof",
            ],
        },
    )
    print(f"wrote formal boundary report to {args.output}")


if __name__ == "__main__":
    main()

