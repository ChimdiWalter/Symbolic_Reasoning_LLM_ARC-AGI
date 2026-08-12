#!/usr/bin/env python3
"""Write family-balanced revised-H2 analysis artifacts for a seed sweep."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.h2_analysis import write_h2_family_balanced_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze revised H2 family-balanced seed-sweep evidence.")
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument("--max-examples", type=int, default=20)
    args = parser.parse_args()
    report = write_h2_family_balanced_analysis(args.sweep_dir, max_examples=args.max_examples)
    print(f"sweep_dir={report['sweep_dir']}")
    print(f"false_rule_examples={report['false_rule_examples_count']}")
    print(f"falsifier_traces={report['falsifier_traces_count']}")


if __name__ == "__main__":
    main()
