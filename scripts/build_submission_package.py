#!/usr/bin/env python3
"""Build the paper-facing submission package from current local artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.paper_package import build_submission_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--breadth-sweep-dir", default=None)
    parser.add_argument("--h2-sweep-dir", default=None)
    parser.add_argument("--arc-dir", default=None)
    parser.add_argument("--h4-sweep-dir", default=None)
    args = parser.parse_args()
    result = build_submission_package(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        breadth_sweep_dir=args.breadth_sweep_dir,
        h2_sweep_dir=args.h2_sweep_dir,
        arc_dir=args.arc_dir,
        h4_sweep_dir=args.h4_sweep_dir,
    )
    print(f"wrote submission package to {result['output_dir']}")


if __name__ == "__main__":
    main()
