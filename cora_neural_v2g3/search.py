"""ncv2-g3 search: the joint constructor interleaved with the unchanged ncv2-g2 agenda, then evidence-aware selection.
It reads the demonstrations and the test inputs only.

**Budget.** `budget` distinct programs evaluated, shared by both streams. A program reached by both is evaluated once.
Every candidate runs on every demonstration (delta.py), so fits, partial explanations and diagnostics come from the
same execution. A fitting program runs on EVERY test input, and is kept only if it gives an output for all of them.

**Streams.** `ratio` joint evaluations (joint.py: probes and constructed combinations) per ncv2-g2 evaluation
(`cora_neural_v2g2.search.enumerate_programs`: program classes first, then its best-first object programs).
`use_joint=False` gives the ncv2-g2 agenda alone, under the same evaluator, for paired comparisons.

**Two orders are recorded:** `attempts_found`, the first two distinct fitting predictions in find order (the
ncv2-g1/g2 rule), and `attempts`, the selection module's choice (select.py). Selection gains and losses can therefore
be measured apart from generation coverage, and selection cannot hide a missing candidate.
"""
import time
from collections import Counter
from dataclasses import dataclass

from cora_neural_v2 import search as G1S
from cora_neural_v2.rast import ASTError, to_sexpr
from cora_neural_v2g2 import grammar as G
from cora_neural_v2g2 import search as S2
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import joint as J
from cora_neural_v2g3 import select as SEL

GRAMMAR_VERSION = "ncv2-g3"
MAX_KEPT = 50


@dataclass
class Eval:
    fits: bool
    deltas: list
    at: int
    origin: str


def search(task, budget, ratio=1, cpu_cap_s=None, classes=True, gen_deadline_s=20.0, use_joint=True,
           joint_cfg=None, select_cfg=None, proposals=None, proposal_ratio=1, _fits_only=False):
    """`proposals`: optional untrusted neural.Proposal objects (complete programs or sketches), evaluated as a third
    stream, `proposal_ratio` per ncv2-g2 evaluation. Sketch holes are filled from the joint rule pools."""
    train, tests = task["train"], task["test_inputs"]
    c0 = time.process_time()
    ev = S2.evidence2(train)
    views = G1S.distinct_views(task)
    cache, fits, origins, info = {}, [], Counter(), {}
    st = {"n": 0, "truncated": False, "ill_typed": 0, "test_rejected": 0, "proposal_rejected": 0, "proposal_unfilled": 0}
    pools = J.build_pools(task, ev, views, joint_cfg) if (use_joint or proposals) else {}

    def evaluate(prog, origin, full=True):
        """One budget unit per distinct program. g2-stream candidates stop at the first failed demonstration (as
        ncv2-g2's fit does); the joint stream needs full deltas, which are completed free of charge if a cheap
        evaluation of the same program came first."""
        if prog in cache:
            e = cache[prog]
            if full and e.deltas is not None and len(e.deltas) < len(train):
                e.deltas = D.deltas(prog, train)
            return e
        if st["n"] >= budget:
            return None
        if cpu_cap_s is not None and time.process_time() - c0 > cpu_cap_s:
            st["truncated"] = True
            return None
        st["n"] += 1
        if origin == "g2" and G.is_class(prog):
            origin = "g2_class"
        try:
            ds = D.deltas(prog, train, stop_early=not full)
        except ASTError:
            st["ill_typed"] += 1
            cache[prog] = Eval(False, None, st["n"], origin)
            return cache[prog]
        e = cache[prog] = Eval(D.fits(ds, len(train)), ds, st["n"], origin)
        origins[origin] += 1
        if e.fits:
            preds = [D.execute(prog, t) for t in tests]
            if all(p is not None for p in preds):
                fits.append({"prog": prog, "preds": preds, "at": st["n"], "origin": origin})
            else:
                st["test_rejected"] += 1
        return e

    def g2_stream():
        for prog, _ in S2.enumerate_programs(task, 10 ** 9, None, classes, gen_deadline_s, info):
            fresh = prog not in cache
            e = evaluate(prog, "g2", full=False)
            if e is None:
                return
            if fresh:
                yield e

    def proposal_stream():
        from cora_neural_v2.rast import holes
        from cora_neural_v2g3 import neural as NN
        for p in sorted(proposals, key=lambda q: -q.confidence):
            prog, _ = NN.admit(p)
            if prog is None:
                st["proposal_rejected"] += 1
                continue
            for c in (NN.complete_sketch(prog, pools) if holes(prog) else [prog]):
                if holes(c):
                    st["proposal_unfilled"] += 1
                    continue
                fresh = c not in cache
                e = evaluate(c, "proposal:" + p.source)
                if e is None:
                    return
                if fresh:
                    yield e

    streams = ([["joint", J.construct(task, ev, views, evaluate, joint_cfg, pools), ratio]] if use_joint else []) + \
        ([["proposal", proposal_stream(), proposal_ratio]] if proposals else []) + [["g2", g2_stream(), 1]]
    while streams and st["n"] < budget and not st["truncated"]:
        for s in list(streams):
            for _ in range(s[2]):
                try:
                    next(s[1])
                except StopIteration:
                    streams.remove(s)
                    break
    if _fits_only:
        return fits

    def lite(reduced, b, preds=False):                         # inner searches for the optional LOO / agreement
        f = search(reduced, b, ratio, None, classes, gen_deadline_s, use_joint, joint_cfg, None, _fits_only=True)
        return [x["preds"] for x in f] if preds else [x["prog"] for x in f]

    ranked, chosen = SEL.choose(fits, task, select_cfg, lite)
    found, seen = [], set()
    for f in fits:                                              # find order: the ncv2-g2 rule
        k = SEL.pred_key(f["preds"])
        if k not in seen:
            seen.add(k)
            found.append(f)
    return {"grammar": GRAMMAR_VERSION,
            "attempts": [c["preds"][0].tolist() for c in chosen],
            "attempts_by_test": [[c["preds"][t].tolist() for c in chosen] for t in range(len(tests))],
            "attempts_found": [f["preds"][0].tolist() for f in found[:2]],
            "attempts_found_by_test": [[f["preds"][t].tolist() for f in found[:2]] for t in range(len(tests))],
            "attempt_programs": [to_sexpr(c["prog"]) for c in chosen],
            "predictions": [f["preds"][0].tolist() for f in found[:MAX_KEPT]],
            "pred_at": [f["at"] for f in found[:MAX_KEPT]],
            "programs": [to_sexpr(f["prog"]) for f in found[:MAX_KEPT]],
            "first_fit_at": fits[0]["at"] if fits else None,
            "n_candidates": st["n"], "n_consistent": len(fits), "n_distinct_predictions": len(found),
            "origins": dict(origins), "fit_origins": dict(Counter(f["origin"] for f in fits)),
            "class_candidates": info.get("class_candidates", 0), "class_refused": info.get("class_refused", {}),
            "selection": [{"program": to_sexpr(r["prog"]), "at": r["at"], "origin": r["origin"],
                           "score": round(r["score"], 3), "loo": r["loo"], "agree": r["agree"],
                           **{k: (list(v) if isinstance(v, tuple) else v) for k, v in r["features"].items()}}
                          for r in ranked[:8]],
            "state": {"budget": budget, "ratio": ratio, "use_joint": use_joint, "ill_typed": st["ill_typed"],
                      "n_test_rejected": st["test_rejected"], "cpu_cap_s": cpu_cap_s, "cpu_truncated": st["truncated"],
                      "proposals": len(proposals or ()), "proposal_rejected": st["proposal_rejected"],
                      "proposal_unfilled": st["proposal_unfilled"]},
            "cpu_s": round(time.process_time() - c0, 3)}
