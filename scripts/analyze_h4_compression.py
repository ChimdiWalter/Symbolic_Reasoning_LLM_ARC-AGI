#!/usr/bin/env python3
"""Compare H4 proxy compression selections to exact bounded DSL minima."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.h4_analysis import write_h4_bounded_compression_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Run H4 bounded compression analysis for an experiment run.")
    parser.add_argument("--run-dir", required=True, help="Experiment run directory containing dataset/results/predictions.")
    parser.add_argument("--output-dir", default=None, help="Optional analysis output directory.")
    args = parser.parse_args()

    command = "python3.11 scripts/analyze_h4_compression.py --run-dir {}".format(args.run_dir)
    if args.output_dir:
        command += " --output-dir {}".format(args.output_dir)
    result = write_h4_bounded_compression_analysis(args.run_dir, output_dir=args.output_dir, command=command)
    print(f"wrote H4 bounded compression analysis to {result['output_dir']}")


if __name__ == "__main__":
    main()
