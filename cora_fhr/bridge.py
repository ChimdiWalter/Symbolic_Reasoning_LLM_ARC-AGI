"""Installing G-grow extensions into the SAME native engine: an adapted copy of cora_reach/bridge.py.

The five overlay points are the same as in cora_reach, wrapped for the duration and restored on exit
(verified by identity):
- growth.GROW_MODES (installed names before the `pattern` fallback);
- correspondence.detect_grow (an installed operator that reproduces a `pattern` fallback's added cells, one
  colour, is returned instead);
- inducer._action_candidates (native's own colour-expression candidates for installed modes);
- actions.ACTION_DISPATCH[GROW] (render on the scene being solved, canvas.source_grid);
- correspondence._predict_cells (raw-delta prediction).

The differences: rendering uses the G-grow evaluator with the object's colours (cell -> colour), and this
bridge has its own active flag and marker. geocat_arc is not edited; cora_reach is not mutated. The
engine's acceptance gate (train-perfect and leave-one-out by re-induction) is unchanged and decides.
"""
import contextlib
import json

import numpy as np

from cora_fhr import ggrow as GG

_STATE = {"active": False}


def _mods():
    import geocat_arc.object_reasoning.actions as AC
    import geocat_arc.object_reasoning.correspondence as CO
    import geocat_arc.object_reasoning.growth as GR
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.types import DeltaType, ExprType
    return GR, CO, I, AC, DeltaType, ExprType


def _np(grid):
    if grid is None:
        return None
    a = grid.to_numpy() if hasattr(grid, "to_numpy") else np.asarray(grid)
    return a if a.ndim == 2 else None


def originals():
    GR, CO, I, AC, DT, _ET = _mods()
    return (GR.GROW_MODES, CO.detect_grow, I._action_candidates, AC.ACTION_DISPATCH[DT.GROW], CO._predict_cells)


def restored(saved=None) -> bool:
    cur = originals()
    if saved is not None:
        return all(a is b for a, b in zip(cur, saved)) and not _STATE["active"]
    return not _STATE["active"] and cur[0][-1] == "pattern" and not any(
        getattr(f, "__cora_fhr__", False) or getattr(f, "__cora_reach__", False) for f in cur[1:])


@contextlib.contextmanager
def installed(*exts):
    GR, CO, I, AC, DT, ET = _mods()
    if _STATE["active"]:
        raise RuntimeError("an extension is already installed")
    checked = [GG.load(GG.serialize(e)) for e in exts]
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
            if GG.render(names[n], dict(in_cc), G) == set(added):
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
            raise AC.EvalError(f"grow {mode}: an installed operator does not move the object")
        G = _np(canvas.source_grid)
        if G is None:
            raise AC.EvalError(f"grow {mode}: no source grid on the canvas")
        colour = int(AC._eval_param(action, "color", obj, ectx))
        cc = AC.cell_colors_of(obj)
        cells = GG.render(ext, dict(cc), G)
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
            return dict(cc)
        merged = dict(cc)
        merged.update({c: int(params["color"]) for c in GG.render(ext, dict(cc), G)})
        return merged

    for f in (detect_grow, _action_candidates, apply_grow, _predict_cells):
        f.__cora_fhr__ = True
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
            raise RuntimeError("the FHR bridge left engine state behind")


def uses(program_json, ext) -> bool:
    """Attribution: the program contains a GROW action in the extension's mode."""
    from cora_reach.bridge import uses as reach_uses
    return reach_uses(program_json, ext)
