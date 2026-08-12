from __future__ import annotations
from typing import Optional, Tuple
import re

from components import Grid
from pipeline import build_scene_bundle
from dsl import (
    Program, Apply, Var, CColor, CInt, CVec,
)

# Simple phrase parser for a few common templates. Extend as needed.
# Supported patterns:
#   1) "paint largest <color> to <color>"
#   2) "translate <color> by (<dr>,<dc>)"
#   3) "reflect <color> vertical" / "reflect <color> horizontal"
# Colors are integers 0..9 or names used in text_describer.COLOR_NAMES.

COLOR_NAMES = {
    "black": 0, "blue": 1, "red": 2, "green": 3, "yellow": 4,
    "gray": 5, "pink": 6, "orange": 7, "teal": 8, "brown": 9,
}


def _parse_color(tok: str) -> Optional[int]:
    tok = tok.strip().lower()
    if tok.isdigit():
        v = int(tok)
        return v if 0 <= v <= 9 else None
    return COLOR_NAMES.get(tok)


def parse_rule_to_program(text: str) -> Optional[Program]:
    t = text.strip().lower()
    # 1) paint largest <c1> to <c2>
    m = re.search(r"paint\s+largest\s+([a-z0-9]+)\s+to\s+([a-z0-9]+)", t)
    if m:
        c1 = _parse_color(m.group(1)); c2 = _parse_color(m.group(2))
        if c1 is None or c2 is None: return None
        term = Apply("paint", [Var("grid"), Apply("largest", [Apply("objects", [CColor(c1)])]), CColor(c2)])
        return Program(term, description=f"paint largest {c1} to {c2}")

    # 2) translate <color> by (dr,dc)
    m = re.search(r"translate\s+([a-z0-9]+)\s+by\s*\(([-+]?\d+)\s*,\s*([-+]?\d+)\)", t)
    if m:
        c = _parse_color(m.group(1)); dr = int(m.group(2)); dc = int(m.group(3))
        if c is None: return None
        term = Apply("translate", [Apply("objects", [CColor(c)]), CVec(dr, dc)])
        return Program(term, description=f"translate {c} by ({dr},{dc})")

    # 3) reflect <color> vertical/horizontal
    m = re.search(r"reflect\s+([a-z0-9]+)\s+(vertical|horizontal)", t)
    if m:
        c = _parse_color(m.group(1)); axis = 1 if m.group(2) == "vertical" else 0
        if c is None: return None
        term = Apply("reflect", [Apply("objects", [CColor(c)]), CInt(axis)])
        return Program(term, description=f"reflect {c} axis {axis}")

    return None


if __name__ == "__main__":
    p = parse_rule_to_program("Paint largest red to green")
    print(p.description if p else None)
