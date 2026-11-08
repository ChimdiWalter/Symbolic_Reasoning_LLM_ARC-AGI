"""One search call on A2's bottom-up enumerator with a completeness record.

Fragment F(L) = every program of cost at most L over the grammar, with A2's value guards (grids at most 30 x 30,
containers at most 2,000 items, integers within +-1,000). bus.search enumerates cost levels in order; a level counts
as complete only when it finished before the budget, the CPU cap or a fit stopped it, and no closure constructor
was skipped (A2 caps closures at 400 per search). "No fit and F(L) complete" is a demonstrated fact about F(L);
"budget spent before F(L) finished" is not.
"""
import time

from cgrow import paths as P

P.ensure_import_paths()
from a2 import arcdsl as D            # noqa: E402
from a2 import bus as B               # noqa: E402

BASE_BUDGET = 150_000          # A2's per-task budget (primitive executions), CPU cap 20 s
BASE_CPU = 20.0
MAX_FN = 400
TAGS = {"B", "I", "E", "G", "GT", "TT", "T", "TU", "O", "FU", "X", "S", "XS", "Z", "U"}


def _closures(seen):
    return sum(1 for k in seen if not (isinstance(k, tuple) and len(k) == 2 and k[0] in TAGS))


def run(g, train, test_inputs, budget=BASE_BUDGET, cpu_cap=BASE_CPU, want=2, track_partial=False):
    t0 = time.process_time()
    r = B.search(g, train, test_inputs, budget=budget, max_size=24, cpu_cap=cpu_cap, want=want,
                 track_partial=track_partial, keep_seen=True)
    nfn = _closures(r.seen) if r.seen is not None else None
    out = {"fit": bool(r.solved), "program": D.show(r.program) if r.program else None,
           "program_tree": r.program, "fits": list(r.fits),
           "preds": [[tuple(tuple(row) for row in g_) for g_ in att] for att in r.preds] if r.preds else None,
           "level_complete": r.level, "stop": r.stop, "calls": r.calls, "bank": r.bank,
           "closures": nfn, "closure_capped": nfn is not None and nfn >= MAX_FN,
           "cpu_s": round(time.process_time() - t0, 3)}
    if track_partial and r.partial is not None:
        sc, tree, outs = r.partial
        out["partial"] = {"cells_correct": sc, "tree": tree, "program": D.show(tree), "outs": outs}
    r.seen = None
    return out


def correct(res, test_outputs):
    """pass@2: either attempt reproduces every query output."""
    if not res["preds"]:
        return False
    want = [tuple(tuple(row) for row in y) for y in test_outputs]
    return any(list(att) == want for att in res["preds"])
