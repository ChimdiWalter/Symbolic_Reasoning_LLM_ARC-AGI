"""The view intervention of revision 2 (no patches; shared by the measurement and the generator).

A2's search over the world's G0 with four alternative arc-dsl object views as representation leaves (A2's own
mechanism for representation leaves, the A3 arm's: cost 1 each). Every extraction of a view from a grid counts one
call. It has no cheap check of whether it applies: when no program over the views fits, it runs to its cap.
"""
from fgc import common as C
from fgc.common import D
from a2 import bus as B                                                     # noqa: E402

NO_CPU_CAP = 1e9
_OBJECTS = {}


def lists(preds):
    return [[C.as_lists(g) for g in att] for att in preds] if preds else None


def view_values(xs):
    """The alternative views of every grid in xs (demonstration inputs, then query inputs); one call each."""
    if "f" not in _OBJECTS:
        _OBJECTS["f"] = D.guarded(D.load()[0])["objects"]
    obj = _OBJECTS["f"]
    reps, calls = {}, 0
    for name, flags in C.VIEWS.items():
        vals = []
        for x in xs:
            calls += 1
            try:
                vals.append(obj(x, *flags))
            except Exception:                                                 # noqa: BLE001
                vals.append(None)
        if all(v is not None for v in vals):
            reps[name] = tuple(vals)
    return reps, calls


def view_search(g, train, qs, budget):
    """One fit wanted, no CPU cap; calls include the view extractions."""
    xs = [a for a, _ in train] + list(qs)
    reps, rep_calls = view_values(xs)
    r = B.search(g, train, qs, budget=max(0, budget - rep_calls), reps=reps, cpu_cap=NO_CPU_CAP, want=1)
    preds = [[tuple(tuple(row) for row in g_) for g_ in att] for att in r.preds] if r.preds else None
    return {"fit": bool(r.solved), "preds": lists(preds), "raw_preds": preds,
            "program": D.show(r.program) if r.program else None, "calls": int(r.calls) + rep_calls,
            "rep_calls": rep_calls, "stop": r.stop, "level_complete": r.level}
