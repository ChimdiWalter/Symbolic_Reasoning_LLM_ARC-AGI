#!/usr/bin/env python3
"""Run a bounded local ARC external-validity diagnostic."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_diagnostic import run_arc_diagnostic
from reasoning_project.utils import read_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded ARC diagnostic from local ARC files.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()

    config = read_json(args.config)
    command = f"python3.11 scripts/run_arc_diagnostic.py --config {args.config} --output-dir {args.output_dir}"
    result = run_arc_diagnostic(config, output_dir=args.output_dir, command=command, config_path=args.config)
    print(f"run_dir={result['run_dir']}")
    print(f"rows={len(result['rows'])}")
    print(f"skipped_rows={result['summary'].get('skipped_rows', 0)}")


if __name__ == "__main__":
    main()
