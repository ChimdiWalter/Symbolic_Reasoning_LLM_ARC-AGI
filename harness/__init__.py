"""Unified evaluation harness (Stage 0) — merges the cortical pipeline and GeoCat.

Importing this package makes both underlying systems importable by inserting
the project root (for ``geocat_arc``) and ``src`` (for ``reasoning_project``)
into ``sys.path``.
"""
import os
import sys

import os as _os
PROJECT_ROOT = _os.environ.get(
    "ARC_PROJECT_ROOT",
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_SRC = os.path.join(PROJECT_ROOT, "src")

for _p in (PROJECT_ROOT, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)
