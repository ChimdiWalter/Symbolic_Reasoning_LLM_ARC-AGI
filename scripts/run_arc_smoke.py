#!/usr/bin/env python3
"""Run a tiny local ARC adapter smoke evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_smoke import run_arc_smoke
from reasoning_project.utils import read_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a tiny ARC loader/evaluator smoke test.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()

    config = read_json(args.config)
    command = f"python3.11 scripts/run_arc_smoke.py --config {args.config} --output-dir {args.output_dir}"
    result = run_arc_smoke(config, output_dir=args.output_dir, command=command, config_path=args.config)
    print(f"run_dir={result['run_dir']}")
    print(f"rows={len(result['rows'])}")


if __name__ == "__main__":
    main()
