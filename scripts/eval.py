#!/usr/bin/env python3
"""Compatibility entry point for evaluation/report regeneration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.cli import analyze_main


if __name__ == "__main__":
    analyze_main()

