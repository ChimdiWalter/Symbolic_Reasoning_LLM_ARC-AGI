"""Capability-growth controller v1: typed failure record, competing diagnoses, executable probes, decision.

Inputs (safeguard 2): the task's demonstrations and query inputs, the current grammar, and CORA's own search
traces. Nothing else.

Record for an unsolved task:
- completeness of the base search: last fully enumerated cost level L, closure cap hit or not (search.py);
- probe P1, deeper search at 4x the budget: a fit means the program exists in the language (SEARCH level);
- shape relation between inputs and outputs (one rule consistent with every demonstration, if any);
- closest program: the right-shaped program with most correct cells, with its residual on one demonstration;
- unreachable sketches: identity ?(I); outer B(?(I)) with B an invertible G0 grid operation (hole target
  B^-1(output)); inner ?(A(I)) with A invertible (hole input A(input)). Ranked by how much of the hole's target the
  hole's input already explains (cell agreement after proportional resizing). Every hole target is unreachable:
  a reachable target would have given a fit.
Decision (executable actions only): CONTINUE_PROGRAM_SEARCH (P1 found a fit), INVENT_NEW_OPERATION (complete or
budget-limited search with no fit, at least two demonstrations), REQUEST_ADDITIONAL_ADMISSIBLE_EVIDENCE (fewer than
two demonstrations), PRESERVE_COMPETING_HYPOTHESES (the base search fits with two distinct query predictions).
Competing levels not probed in v1 (representation, interpretation, relation, composition) are listed as untested.
"""
from cgrow import paths as P, search as S

P.ensure_import_paths()
from a2 import arcdsl as D            # noqa: E402

PROBE_FACTOR = 4


def invertible_ops(g):
    """{name: inverse name} among G0's unary grid operations that are bijections on test grids (found by probing)."""
    fns = D.guarded(D.load()[0])
    names = [p.name for p in g.prods if p.head.startswith("f:") and p.arity == 1 and p.name in fns]
    tests = [((1, 2, 3), (4, 5, 6)), ((1, 2), (3, 4), (5, 7)), ((1, 0, 0, 2), (3, 4, 5, 6), (7, 8, 9, 1))]
    out = {}
    for a in names:
        for b in names:
            try:
                if all(D.tag(fns[a](t)) == "G" and fns[b](fns[a](t)) == t for t in tests) and \
                        any(fns[a](t) != t for t in tests):
                    out[a] = b
                    break
            except Exception:                                    # noqa: BLE001
                continue
    return out


def similarity(x, y):
    """Share of y's cells equal to x at the proportionally mapped position (x, y grids)."""
    hx, wx, hy, wy = len(x), len(x[0]), len(y), len(y[0])
    eq = sum(y[i][j] == x[min(hx - 1, i * hx // hy)][min(wx - 1, j * wx // wy)] for i in range(hy) for j in range(wy))
    return eq / (hy * wy)


def shape_relation(train):
    dims = [((len(a), len(a[0])), (len(b), len(b[0]))) for a, b in train]
    rules = [("output size equals input size", lambda i, o: o == i),
             ("output is the input transposed in size", lambda i, o: o == (i[1], i[0]))]
    for k in (2, 3, 4, 5):
        rules.append((f"output rows and columns are {k} times the input's", lambda i, o, k=k: o == (i[0] * k, i[1] * k)))
        rules.append((f"output rows and columns are the input's divided by {k} (rounded up)",
                      lambda i, o, k=k: o == (-(-i[0] // k), -(-i[1] // k))))
    for c in (1, 2, 3, 4):
        rules.append((f"output has {c} fewer rows and {c} fewer columns than the input",
                      lambda i, o, c=c: o == (i[0] - c, i[1] - c)))
    rules.append(("output has half the input's rows", lambda i, o: o == (i[0] // 2, i[1])))
    rules.append(("output has half the input's columns", lambda i, o: o == (i[0], i[1] // 2)))
    for name, f in rules:
        if all(f(i, o) for i, o in dims):
            return name
    if len({o for _, o in dims}) == 1:
        return f"output size is always {dims[0][1][0]} x {dims[0][1][1]}"
    if all(o[0] <= i[0] and o[1] <= i[1] for i, o in dims):
        return "output is never larger than the input; the amount removed varies"
    return "no simple rule relates output size to input size"


def sketches(train, g):
    fns = D.guarded(D.load()[0])
    inv = invertible_ops(g)
    xs, ys = [a for a, _ in train], [b for _, b in train]
    cands = [{"form": "?(I)", "outer": None, "inner": None, "pairs": list(zip(xs, ys))}]
    for b, binv in inv.items():
        try:
            cands.append({"form": "B(?(I))", "outer": b, "inner": None,
                          "pairs": [(x, fns[binv](y)) for x, y in zip(xs, ys)]})
        except Exception:                                        # noqa: BLE001
            pass
    for a in inv:
        try:
            cands.append({"form": "?(A(I))", "outer": None, "inner": a, "pairs": [(fns[a](x), y) for x, y in
                                                                                    zip(xs, ys)]})
        except Exception:                                        # noqa: BLE001
            pass
    cands = [c for c in cands if all(D.tag(x) == "G" and D.tag(y) == "G" for x, y in c["pairs"])]
    for c in cands:
        c["score"] = round(sum(similarity(x, y) for x, y in c["pairs"]) / len(c["pairs"]), 4)
    ident = cands[0]
    rest = sorted(cands[1:], key=lambda c: (-c["score"], c["outer"] or "", c["inner"] or ""))
    ranked = sorted([ident] + rest[:2], key=lambda c: -c["score"])
    return ranked, inv


def residual(partial, train):
    """Expected values where the closest program is wrong ('.' where right), on the first demo it gets wrong."""
    for k, ((_, y), out) in enumerate(zip(train, partial["outs"])):
        if out != y:
            return k, [[("." if out[i][j] == y[i][j] else str(y[i][j])) for j in range(len(y[0]))]
                       for i in range(len(y))]
    return None, None


def analyze(task, g, budget=S.BASE_BUDGET):
    train = [(D.to_grid(a), D.to_grid(b)) for a, b in task["train"]]
    qs = [D.to_grid(q) for q in task["test_inputs"]]
    base = S.run(g, train, qs, budget=budget, track_partial=True)
    rec = {"base": {k: base[k] for k in ("fit", "program", "level_complete", "stop", "calls", "bank", "closures",
                                         "closure_capped", "cpu_s")}, "n_demos": len(train)}
    rec["base_preds"] = base["preds"]
    if base["fit"]:
        distinct = base["preds"] and len(base["preds"]) > 1 and base["preds"][0] != base["preds"][1]
        rec["status"] = "solved"
        rec["decision"] = "PRESERVE_COMPETING_HYPOTHESES" if distinct else "NONE"
        rec["level"] = None
        return rec
    deep = S.run(g, train, qs, budget=budget * PROBE_FACTOR, cpu_cap=S.BASE_CPU * PROBE_FACTOR)
    rec["probe_deeper_search"] = {k: deep[k] for k in ("fit", "program", "level_complete", "stop", "calls",
                                                       "closure_capped", "cpu_s")}
    rec["probe_deeper_preds"] = deep["preds"]
    rec["shape_relation"] = shape_relation(train)
    if "partial" in base:
        k, grid = residual(base["partial"], train)
        cells = sum(len(y) * len(y[0]) for _, y in train)
        rec["closest"] = {"program_tree": base["partial"]["tree"], "cells_correct": base["partial"]["cells_correct"],
                          "cells_total": cells, "residual_demo": k, "residual": grid}
    else:
        rec["closest"] = None
    sk, inv = sketches(train, g)
    rec["sketches"] = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"],
                        "pairs": c["pairs"]} for c in sk]
    complete = not base["closure_capped"]
    rec["inexpressible_within"] = {"cost_level": base["level_complete"], "enumeration_complete": complete,
                                   "deeper_level": deep["level_complete"],
                                   "deeper_complete": not deep["closure_capped"]}
    hyps = [
        {"level": "search", "claim": "the program exists in the language at a higher cost",
         "probe": "deeper search at 4x the budget",
         "verdict": "supported" if deep["fit"] else "weakened (no fit up to the deeper search's cost level)"},
        {"level": "operation", "claim": "an operation the program needs is missing from the language",
         "probe": "fragment completeness, unreachable sketches",
         "verdict": "excluded" if deep["fit"] else "supported"},
        {"level": "insufficient_evidence", "claim": "the demonstrations do not determine a rule",
         "probe": "number of demonstrations",
         "verdict": "supported" if len(train) < 2 else "not supported"},
        {"level": "composition", "claim": "operations exist but a control structure is missing", "probe": None,
         "verdict": "untested in v1"},
        {"level": "representation", "claim": "the grid is decomposed into the wrong entities", "probe": None,
         "verdict": "untested in v1"},
    ]
    rec["hypotheses"] = hyps
    if deep["fit"]:
        rec["status"], rec["decision"], rec["level"] = "solved_by_deeper_search", "CONTINUE_PROGRAM_SEARCH", "search"
    elif len(train) < 2:
        rec["status"], rec["decision"], rec["level"] = "unresolved", "REQUEST_ADDITIONAL_ADMISSIBLE_EVIDENCE", \
            "insufficient_evidence"
    else:
        rec["status"], rec["decision"], rec["level"] = "unresolved", "INVENT_NEW_OPERATION", "operation"
    rec["cpu_s"] = round(base["cpu_s"] + deep["cpu_s"], 2)
    return rec
