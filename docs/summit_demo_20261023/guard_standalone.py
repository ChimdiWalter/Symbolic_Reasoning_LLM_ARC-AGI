"""Standalone evaluator for CORA-FHR guarded operators (numpy only; mirrors cora_fhr/ggrow_guard.py).

A guarded operator is: if <object feature> <op> <value>: <G-grow expression> else: <G-grow expression>.
"""
import json

import ggrow_standalone as GS


def feature(x, f):
    return {"size": lambda: len(x.O), "n_colours": lambda: x.n_colours,
            "colours": lambda: tuple(sorted(set(x.O.values()))), "h": lambda: x.h, "w": lambda: x.w}[f]()


def evaluate(expr_json, O, G):
    """The added cells of the guarded operator for object O (cell -> colour) in grid G."""
    d = json.loads(expr_json)
    f, op, v = d["guard"]
    v = tuple(v) if isinstance(v, list) else v
    x = GS.Ctx(O, G)
    val = feature(x, f)
    hit = val == v if op == "eq" else val <= v
    return GS.evaluate(GS.from_str(d["then"] if hit else d["else"]), x)
