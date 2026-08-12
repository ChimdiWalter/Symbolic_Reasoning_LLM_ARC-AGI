#!/usr/bin/env python3
"""Run the full resumable experiment loop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.cli import run_main


if __name__ == "__main__":
    run_main()

