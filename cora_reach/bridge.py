"""Installing growth extensions into the SAME native engine (reach v1 bridge).

A context-scoped overlay, the same technique as K*-3/K*-4: four engine
attributes are wrapped for the duration and restored on exit, verified by
identity. geocat_arc is not edited. With nothing installed the engine is
untouched.

- growth.GROW_MODES: installed names are inserted before the `pattern`
  fallback, so the inducer considers them and the expression evaluator
  accepts them;
- correspondence.detect_grow: where the engine would memorize an unmoved
  object with the constant `pattern`, an installed relation that reproduces
  the added cells exactly (one colour) is returned instead;
- inducer._action_candidates: groups observed in an installed mode get the
  engine's own colour-expression candidates, as for its own modes;
- actions.ACTION_DISPATCH[GROW]: an installed mode renders its relation on
  the scene being solved (canvas.source_grid), never on the induction grid;
- correspondence._predict_cells: the raw-delta renderer used when
  correspondences are reconciled with pixels renders an installed mode by
  its relation (its fallback branch would read a `pattern` parameter).
The engine's acceptance gate (train-perfect and leave-one-out by
re-induction) is unchanged and decides.
"""
from __future__ import annotations

import contextlib
import json

import numpy as np

from cora_reach import growth_ext as GE

_STATE = {"active": False}


def _mods():
    import geocat_arc.object_reasoning.growth as GR
    import geocat_arc.object_reasoning.correspondence as CO
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.actions as AC
    from geocat_arc.object_reasoning.types import DeltaType, ExprType
    return GR, CO, I, AC, DeltaType, ExprType


def _np(grid):
    if grid is None:
        return None
    a = grid.to_numpy() if hasattr(grid, "to_numpy") else np.asarray(grid)
    return a if a.ndim == 2 else None


def originals():
    GR, CO, I, AC, DT, _ET = _mods()
    return (GR.GROW_MODES, CO.detect_grow, I._action_candidates, AC.ACTION_DISPATCH[DT.GROW],
            CO._predict_cells)


def restored(saved=None) -> bool:
    cur = originals()
    if saved is not None:
        return all(a is b for a, b in zip(cur, saved)) and not _STATE["active"]
    return not _STATE["active"] and "pattern" == cur[0][-1] and not any(
        getattr(f, "__cora_reach__", False) for f in cur[1:])


@contextlib.contextmanager
def installed(*exts):
    GR, CO, I, AC, DT, ET = _mods()
    if _STATE["active"]:
        raise RuntimeError("an extension is already installed")
    checked = [GE.load(GE.serialize(e)) for e in exts]
    names = {e["name"]: e for e in checked}
    if len(names) != len(checked):
        raise RuntimeError("an extension is installed twice")
    saved = originals()
    modes0, detect0, cands0, apply0, predict0 = saved
    order = sorted(names)

    def detect_grow(in_cc, out_cc, bounds, grid=None):
        res = detect0(in_cc, out_cc, bounds, grid)
        if res is None or res.get("mode") != "pattern" or "dr" in res or "dc" in res:
            return res
        G = _np(grid)
        if G is None:
            return res
        added = {c: col for c, col in out_cc.items() if c not in in_cc}
        cols = set(added.values())
        if len(cols) != 1:
            return res
        for n in order:
            if GE.render(names[n], set(in_cc), G) == set(added):
                return {"mode": n, "color": int(next(iter(cols)))}
        return res

    def _action_candidates(delta_type, members, table, pctx):
        if delta_type is DT.GROW:
            modes = {m.params.get("mode") for m in members.values()}
            mine = [n for n in order if n in modes]
            if mine:
                colours = list(I.enumerate_expressions(ET.COLOR, pctx))
                colours.sort(key=lambda c: (I.parameter_class_of(c).rank, c.size,
                                            json.dumps(c.to_dict(), sort_keys=True, default=str)))
                for n in mine:
                    for c in colours:
                        yield I._make_action(DT.GROW, {"mode": I.GrowModeExpr(op="const", args=(n,)), "color": c})
        yield from cands0(delta_type, members, table, pctx)

    def apply_grow(canvas, obj, action, ectx):
        mode = AC._eval_param(action, "mode", obj, ectx)
        ext = names.get(mode)
        if ext is None:
            return apply0(canvas, obj, action, ectx)
        if "vector" in action.params:
            raise AC.EvalError(f"grow {mode}: an installed relation does not move the object")
        G = _np(canvas.source_grid)
        if G is None:
            raise AC.EvalError(f"grow {mode}: no source grid on the canvas")
        colour = int(AC._eval_param(action, "color", obj, ectx))
        cc = AC.cell_colors_of(obj)
        cells = GE.render(ext, set(cc), G)
        if not cells:
            raise AC.EvalError(f"grow {mode}: no cells added")
        merged = dict(cc)
        merged.update({c: colour for c in cells})
        return [AC._build_object(obj.id, merged)]

    def _predict_cells(delta, in_obj, bounds=(0, 0), grid=None):
        params = delta.params or {}
        ext = names.get(params.get("mode")) if delta.delta_type is DT.GROW else None
        if ext is None or "dr" in params or "dc" in params:
            return predict0(delta, in_obj, bounds, grid)
        cc = AC.cell_colors_of(in_obj)
        G = _np(grid)
        if G is None:
            return dict(cc)                      # no scene: predict no growth (an honest residual)
        merged = dict(cc)
        merged.update({c: int(params["color"]) for c in GE.render(ext, set(cc), G)})
        return merged

    for f in (detect_grow, _action_candidates, apply_grow, _predict_cells):
        f.__cora_reach__ = True
    record = {"installed": order}
    GR.GROW_MODES = tuple(m for m in modes0 if m != "pattern") + tuple(order) + ("pattern",)
    CO.detect_grow, I._action_candidates = detect_grow, _action_candidates
    AC.ACTION_DISPATCH[DT.GROW] = apply_grow
    CO._predict_cells = _predict_cells
    _STATE["active"] = True
    try:
        yield record
    finally:
        GR.GROW_MODES = modes0
        CO.detect_grow, I._action_candidates = detect0, cands0
        AC.ACTION_DISPATCH[DT.GROW] = apply0
        CO._predict_cells = predict0
        _STATE["active"] = False
        record["restored"] = restored(saved)
        if not record["restored"]:
            raise RuntimeError("the growth bridge left engine state behind")


def uses(program_json, ext) -> bool:
    """Attribution: the program contains a GROW action in the extension's mode."""
    name = ext["name"]
    hit = []

    def walk(v):
        if isinstance(v, dict):
            if v.get("delta_type") == "grow":
                mode = ((v.get("params") or {}).get("mode") or {})
                if isinstance(mode, dict) and mode.get("args") and mode["args"][0] == name:
                    hit.append(True)
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(program_json)
    return bool(hit)
