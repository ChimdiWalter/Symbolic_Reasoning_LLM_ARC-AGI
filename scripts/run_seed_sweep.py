#!/usr/bin/env python3
"""Run a config over repeated seeds and aggregate mean/std metrics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.cli import sweep_main


if __name__ == "__main__":
    sweep_main()

