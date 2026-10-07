"""CORA-TTI Item-2 v1.9: the engine acceptance stability audit (diagnosis).

For one synthetic task with seven training pairs and one held-out pair, and
one compiled extension e held byte-identical:

  BASE      K* alone on the seven pairs
  FULL      K* + {e} on the seven pairs, predicting the held-out pair
  FOLD_i    K* + {e} on the six pairs without pair i, predicting pair i
            (the SAME e; nothing is reselected or recompiled)

Each run is the frozen runner under `v19_trace.traced`. A rejected run
gets machine-readable reason codes from the trace by the frozen rules in
`reason_codes`, and every failed internal fold of the engine's own
leave-one-out is mapped to a mechanism:

  H1  re-induction instability: the extension's semantics, fitted from the
      fold's own pairs with every consistent witness, predict the held-out
      pair, but the engine's refit or ranking refuses it;
  H2  identifiability loss: the fold's pairs do not determine what the
      held-out pair needs (a needed key is never witnessed);
  H3  search or budget: the expression phase was cut by its deadline
      (and, in the load diagnosis, the decision moves with the clock);
  H4  selection quality: decided per task by `alternative_stability`.

The census mirrors the scoped fitter's constraint collection (same
helpers, same ownership law) without its admission rules; a test checks it
against the fitter wherever the fitter succeeds.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from cora_arc2026 import v17_compiler as X
from cora_v19 import v19_trace as TR

VERSION = "1.9.0-audit"

#: the directive's taxonomy (section 3); sub-reasons follow a colon
REASON_CODES = (
    "EXTENSION_NOT_VISIBLE", "EXTENSION_TYPE_REJECTED", "SLOT_FIT_FAILED", "SLOT_FIT_AMBIGUOUS",
    "TRAINING_PAIR_MISMATCH", "HYPOTHESIS_SCORE_BELOW_GATE", "RANKED_BELOW_COMPETITOR",
    "SEARCH_BUDGET_EXHAUSTED", "EXPRESSION_BUDGET_EXHAUSTED", "ROUTER_BUDGET_EXHAUSTED",
    "TIME_BUDGET_EXHAUSTED", "CERTIFICATE_FAILED", "ATTRIBUTION_FAILED",
    "FINAL_EXECUTION_MISMATCH", "BASELINE_ALREADY_SOLVES", "OTHER_EXPLICIT_REASON")
MECHANISMS = ("H1", "H2", "H3", "H4", "UNRESOLVED")


def _M():
    M, MI = X._meta()
    return M, MI


# --------------------------------------------------------------------------
# the witness census (diagnostic mirror of the scoped fitter, no admission)
# --------------------------------------------------------------------------

def census(schema, pairs) -> dict:
    """Per (block, key): the colour demanded and the demonstrations that
    witness it; per pair: the (block, key) constraints it shows. Mirrors the
    fitter's ownership law (the highest-index block owns a cell) and its
    region rules; returns error codes instead of admitting or refusing."""
    M, MI = _M()
    SF = X._sf()
    blocks = SF._blocks(schema)
    colour, witness, per_pair = {}, {}, []
    for index, (grid_in, grid_out) in enumerate(pairs):
        gi, go = np.asarray(grid_in), np.asarray(grid_out)
        if gi.shape != go.shape:
            return {"error": "shape"}
        changed = {(r, c) for r in range(gi.shape[0]) for c in range(gi.shape[1])
                   if int(gi[r, c]) != int(go[r, c])}
        per_block = []
        for partition, predicates, feature, _slot in blocks:
            sets = SF._selected_sets(partition, predicates, gi)
            if sets is None or not M.PARTITIONS[partition](gi):
                return {"error": f"partition {partition}"}
            per_block.append(sets)
        owner = {}
        for b, sets in enumerate(per_block):
            for cells in sets:
                for cell in cells:
                    owner[cell] = b
        shown = {}
        for b, sets in enumerate(per_block):
            feature = blocks[b][2]
            for cells in sets:
                visible = frozenset(c for c in cells if owner.get(c) == b)
                touched = visible & changed
                if not touched:
                    continue
                if touched != visible:
                    return {"error": "region_partially_changed", "pair": index}
                key = MI.descriptors(cells, gi).get(feature)
                cols = {int(go[c]) for c in visible}
                if key is None or len(cols) != 1:
                    return {"error": "region_colour", "pair": index}
                col = cols.pop()
                if colour.get((b, key), col) != col:
                    return {"error": "nonfunctional", "pair": index}
                colour[(b, key)] = col
                witness.setdefault((b, key), set()).add(index)
                shown[(b, key)] = col
        per_pair.append(shown)
    return {"error": None, "colour": colour, "witness": witness, "per_pair": per_pair,
            "blocks": len(blocks)}


def permissive_tables(schema, pairs):
    """Tables from every consistent witness (one witness suffices), keyed by
    slot name in the fitter's own canonical order; None on a census error."""
    SF = X._sf()
    c = census(schema, pairs)
    if c["error"]:
        return None
    bindings = {}
    for occ in SF.occurrences(schema):
        table = tuple(sorted(((key, col) for (b, key), col in c["colour"].items()
                              if b == occ.block_index), key=lambda kv: repr(kv[0])))
        bindings[occ.slot_name] = table
    return bindings


def permissive_predicts(schema, sub, held) -> bool:
    """Does the extension, fitted from `sub` with every consistent witness,
    reproduce the held-out pair exactly?"""
    M, MI = _M()
    b = permissive_tables(schema, sub)
    if b is None:
        return False
    try:
        inst = M.instantiate(schema, b)
        out = M.evaluate(inst, np.asarray(held[0]), MI.descriptors)
    except Exception:                                        # noqa: BLE001
        return False
    return out is not None and np.array_equal(out, np.asarray(held[1]))


def needed_unwitnessed(schema, sub, held) -> list:
    """(block, key) constraints the held-out pair shows that no pair of
    `sub` witnesses (with the same colour)."""
    cs, ch = census(schema, sub), census(schema, [held])
    if cs["error"] or ch["error"]:
        return ["census_error"]
    return sorted(repr(k) for k, col in ch["per_pair"][0].items()
                  if cs["colour"].get(k) != col)


# --------------------------------------------------------------------------
# reason codes from one trace
# --------------------------------------------------------------------------

def _is_overlay(p, prod) -> bool:
    return getattr(p, "concept", None) == prod["name"]


def prog_info(p) -> dict:
    """What the engine's canonical ranking reads (rank_candidates key)."""
    from geocat_arc.object_reasoning import inducer as I
    info = {"type": type(p).__name__, "concept": getattr(p, "concept", None)}
    try:
        d = p.to_dict()
        info["program_class"] = d.get("program_class")
        if d.get("program_class") == "reduction":
            info["split"] = (d.get("split") or {}).get("kind")
            info["mode"] = d.get("mode")
        info.update(parameter_class=p.worst_parameter_class.name,
                    value_bound=I._program_value_bound_count(p), stages=len(I._stages_of(p)),
                    rules=len(p.rules), expression_size=p.expression_size)
    except Exception as exc:                                 # noqa: BLE001
        info["error"] = type(exc).__name__
    return info


def _fold_ctx(rec, hold):
    return ("LOO", rec["k"], rec["phase"], hold)


def _search_code(srch) -> str | None:
    """Code for an installed-concept search that produced no hit."""
    if srch is None:
        return "EXTENSION_NOT_VISIBLE:no_concept_search"
    if srch["hits"]:
        return None
    hyp = (srch.get("stats") or {}).get("hypotheses", 0)
    if hyp < srch["bindings_total"] and srch["past_deadline"]:
        return "EXPRESSION_BUDGET_EXHAUSTED"
    fits = srch["fits"]
    if not fits:
        return "EXTENSION_NOT_VISIBLE:no_fit_call"
    last = fits[-1]
    if last["ok"]:
        return "TRAINING_PAIR_MISMATCH:observational_signature"
    detail = last.get("detail") or ""
    sub = ("witness" if "witnessed by" in detail else
           "hidden_key" if "never visible" in detail else (last.get("failure") or "unknown"))
    return f"SLOT_FIT_FAILED:{sub}"


def reason_codes(trace, prod, pairs) -> dict:
    """Frozen classification of one traced run (decisions are read, never
    recomputed). `pairs` are the run's training pairs."""
    out = {"accepted": None, "codes": [], "folds": [], "phases": [], "top": {}}
    if not trace["induce_program"]:
        out["codes"] = ["OTHER_EXPLICIT_REASON:no_induction"]
        return out
    res = trace["induce_program"][0]["result"]
    out["accepted"] = bool(res.accepted)
    out["events"] = list(res.events)
    top_trig = next((t for t in trace["trigger"] if t["ctx"] == ("TOP",)), None)
    top_search = next((s for s in trace["search"] if s["ctx"] == ("TOP",)), None)
    top_comp = next((c for c in trace["composed"] if c["ctx"] == ("TOP",)
                     and not c["force_compose"] and not c["force_relational"]), None)
    progs = top_comp["programs"] if top_comp else []
    ov = [i for i, p in enumerate(progs) if _is_overlay(p, prod)]
    out["top"] = {"trigger": None if top_trig is None else top_trig["fired"],
                  "search_code": _search_code(top_search) if top_trig and top_trig["fired"] else None,
                  "candidates": len(progs), "overlay_rank": ov[0] if ov else None,
                  "pool": [prog_info(p) for p in progs[:5]]}
    out["phases"] = [{"phase": r["phase"], "ctx": list(r["ctx"]), "folds": r["n"],
                      "passed": getattr(r.get("report"), "passed", None),
                      "failed": list(getattr(r.get("report"), "failed_pair_indices", []) or []),
                      "fold_seconds": [round(f["t1"] - f["t0"], 3) for f in r["folds"] if "t1" in f],
                      "seconds": round(r["t1"] - r["t0"], 3) if "t1" in r else None}
                     for r in trace["loo"]]
    if res.accepted:
        return out
    if top_trig is not None and not top_trig["fired"]:
        out["codes"] = ["EXTENSION_NOT_VISIBLE:trigger"]
        return out
    if not progs:
        out["codes"] = [_search_code(top_search) or "OTHER_EXPLICIT_REASON:no_top_candidates"]
        return out
    loo_a = next((r for r in trace["loo"] if r["ctx"] == ("TOP",) and r["phase"] == "_fold_inducer"), None)
    if loo_a is None or loo_a.get("report") is None:
        out["codes"] = ["OTHER_EXPLICIT_REASON:no_phase_a_loo"]
        return out
    report = loo_a["report"]
    by_hold = {f["hold"]: f for f in loo_a["folds"]}
    for hold in report.failed_pair_indices:
        f = by_hold.get(hold, {})
        ctx = _fold_ctx(loo_a, hold)
        trig = next((t for t in trace["trigger"] if t["ctx"] == ctx), None)
        srch = next((s for s in trace["search"] if s["ctx"] == ctx), None)
        comp = next((c for c in trace["composed"] if c["ctx"] == ctx), None)
        sub = [p for i, p in enumerate(pairs) if i != hold]
        held = pairs[hold]
        fold = {"hold": hold, "n_sub": f.get("n_sub"),
                "seconds": round(f["t1"] - f["t0"], 3) if "t1" in f else None,
                "deadline_left_at_start": (round(comp["deadline"] - comp["t0"], 3)
                                           if comp and comp.get("deadline") is not None else None)}
        result = f.get("result")
        fprog = getattr(result, "program", None) if result is not None else None
        fold["fold_program_class"] = type(fprog).__name__ if fprog is not None else None
        fold["fold_program_is_overlay"] = bool(fprog is not None and _is_overlay(fprog, prod))
        if "exception" in f:
            code = f"OTHER_EXPLICIT_REASON:{f['exception']}"
        elif trig is not None and not trig["fired"]:
            code = "EXTENSION_NOT_VISIBLE:trigger"
        else:
            code = _search_code(srch)
            if code is None:                                  # the concept fitted here
                if not fold["fold_program_is_overlay"]:
                    code = "RANKED_BELOW_COMPETITOR"
                    pool = comp["programs"] if comp else []
                    ovr = [i for i, p in enumerate(pool) if _is_overlay(p, prod)]
                    fold["overlay_rank"] = ovr[0] if ovr else None
                    fold["competitor"] = prog_info(fprog) if fprog is not None else None
                    fold["overlay"] = prog_info(pool[ovr[0]]) if ovr else None
                    fold["pool_size"] = len(pool)
                else:
                    code = ("SLOT_FIT_AMBIGUOUS:unseen_key"
                            if needed_unwitnessed(_schema(prod), sub, held) else
                            "FINAL_EXECUTION_MISMATCH")
        if srch is not None and srch["fits"]:
            fold["fit_detail"] = srch["fits"][-1].get("detail")
        fold["code"] = code
        fold["mechanism"] = mechanism(code, prod, sub, held)
        out["folds"].append(fold)
    out["codes"] = sorted({f["code"] for f in out["folds"]}) or ["OTHER_EXPLICIT_REASON:no_failed_fold"]
    return out


def _schema(prod):
    M, _ = _M()
    return M.ast_from_json(prod["body"])


def mechanism(code: str, prod, sub, held) -> dict:
    """H1/H2/H3 for one failed internal fold; H4 is per task."""
    schema = _schema(prod)
    pp = permissive_predicts(schema, sub, held)
    missing = needed_unwitnessed(schema, sub, held)
    kind = None
    if code.startswith(("EXPRESSION_BUDGET_EXHAUSTED", "TIME_BUDGET_EXHAUSTED", "SEARCH_BUDGET")):
        h = "H3"
    elif code.startswith(("SLOT_FIT_FAILED", "RANKED_BELOW_COMPETITOR", "TRAINING_PAIR_MISMATCH")):
        h = "H1" if pp else "H2"
        if h == "H1":
            kind = "ranking" if code.startswith("RANKED_BELOW_COMPETITOR") else "fitting"
    elif code.startswith(("SLOT_FIT_AMBIGUOUS", "FINAL_EXECUTION_MISMATCH")):
        h = "H2" if (missing or not pp) else "UNRESOLVED"
    else:
        h = "UNRESOLVED"
    return {"class": h, "h1_kind": kind, "permissive_predicts": pp,
            "needed_unwitnessed": missing[:6]}


# --------------------------------------------------------------------------
# one traced run, and the paired audit
# --------------------------------------------------------------------------

def _prod_sha(prod) -> str:
    return hashlib.sha256(X.serialize(prod)).hexdigest()


def top_fitted_tables(trace) -> dict | None:
    """The installed concept's fitted tables at the top level of the run."""
    M, _ = _M()
    s = next((s for s in trace["search"] if s["ctx"] == ("TOP",)), None)
    if not s or not s["hits"]:
        return None
    ast = s["hits"][0][1]
    return {"ast_sha": hashlib.sha256(json.dumps(M.ast_to_json(ast), sort_keys=True,
                                                  default=str).encode()).hexdigest()[:16],
            "fits": [{"n": f["n"], "ok": f["ok"], "failure": f["failure"]} for f in s["fits"]]}


def traced_run(pairs, prod=None, clock="WALL", held=None, budget_s=8.0) -> dict:
    prods = (prod,) if prod is not None else ()
    with TR.traced(clock) as tr:
        run = X.run_reasoner(pairs, prods, budget_s=budget_s)
        res = tr["induce_program"][0]["result"] if tr["induce_program"] else None
        rc = reason_codes(tr, prod, pairs) if prod is not None else None
        tables = top_fitted_tables(tr) if prod is not None else None
        loo = res.loo if res is not None else None
        timing = {"seconds": run["seconds"],
                  "induction_s": round(res.induction_time_s, 3) if res is not None else None,
                  "clock": clock, "clock_patched": len(tr.get("clock_patched") or [])}
    out = {"accepted": run["accepted"], "events": run["events"], "timing": timing,
           "uses": bool(prod is not None and run["accepted"] and X.uses_extension(run["program"], prod)),
           "program_sha": (hashlib.sha256(json.dumps(run["program"], sort_keys=True).encode())
                           .hexdigest()[:16] if run["program"] else None),
           "loo": None if loo is None else {"folds": loo.folds, "passed": loo.passed,
                                            "failed": list(loo.failed_pair_indices)},
           "reason": rc, "tables": tables}
    if held is not None:
        out["heldout_exact"] = X.predict_exact(run, *held)
    return out


def run_signature(r) -> dict:
    """What must reproduce on repeat execution."""
    rc = r.get("reason") or {}
    return {"accepted": r["accepted"], "codes": rc.get("codes"),
            "fold_codes": [(f["hold"], f["code"]) for f in rc.get("folds", [])],
            "loo_failed": (r.get("loo") or {}).get("failed")}


def paired_audit(train, held, prod, clock="WALL") -> dict:
    """BASE, FULL and the seven same-e folds for one task."""
    out = {"production": prod["name"], "production_sha256": _prod_sha(prod),
           "signature": prod["signature"], "clock": clock}
    out["BASE"] = traced_run(train, None, clock, held)
    out["FULL"] = traced_run(train, prod, clock, held)
    folds = []
    for i in range(len(train)):
        sub = [train[j] for j in range(len(train)) if j != i]
        r = traced_run(sub, prod, clock, train[i])
        r["fold"] = i
        r["production_sha256"] = _prod_sha(prod)
        folds.append(r)
    out["FOLDS"] = folds
    return out


# --------------------------------------------------------------------------
# H4: is the selected extension the stable one among the verified pool?
# --------------------------------------------------------------------------

def nested_proxy(schema, train) -> list:
    """Fitter-level proxy of the engine's acceptance on each outer fold:
    for outer fold j, every internal fold i of the six pairs refits with the
    frozen scoped fitter (its admission rules on) and predicts pair i."""
    M, MI = _M()
    SF = X._sf()
    res = []
    for j in range(len(train)):
        outer = [train[k] for k in range(len(train)) if k != j]
        ok = True
        for i in range(len(outer)):
            sub = [outer[k] for k in range(len(outer)) if k != i]
            g, _ = SF.fit_induced_occurrences(schema, sub)
            o = None if g is None else M.evaluate(g, np.asarray(outer[i][0]), MI.descriptors)
            if o is None or not np.array_equal(o, np.asarray(outer[i][1])):
                ok = False
                break
        res.append(ok)
    return res
