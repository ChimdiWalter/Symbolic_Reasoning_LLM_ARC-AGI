#!/usr/bin/env python3
"""Aggregate H4 bounded-alignment analysis across completed sweep child runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.h4_sweep_analysis import write_h4_sweep_analysis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    result = write_h4_sweep_analysis(args.sweep_dir, output_dir=args.output_dir)
    print(f"wrote H4 sweep analysis to {result['output_dir']}")


if __name__ == "__main__":
    main()
