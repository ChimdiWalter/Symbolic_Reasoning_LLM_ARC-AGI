#!/usr/bin/env python3
"""Generate a synthetic reasoning dataset from a JSON config."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.cli import generate_main


if __name__ == "__main__":
    generate_main()

