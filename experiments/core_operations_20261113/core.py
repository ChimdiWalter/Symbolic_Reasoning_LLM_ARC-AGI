"""One (operation, condition) measurement, the per-operation files, and the summary.
Author: Chimdi Walter Ndubuisi
"""
import hashlib
import json
import os

import dslx
import gen
import presets as P
import search as S


def build(op, hidden, examples, ns=None):
    """(ops, leaves, Y) for hiding the names in `hidden`; examples = [(args, out)] (fit first, then validation).
    Operations and function-valued leaves come from the condition's own namespace (hidden names do not exist)."""
    L = dslx.load()
    ns = ns if ns is not None else dslx.library_namespace(hidden)
    ops = [(nm, ns[nm], tuple(dslx.ACC[a] for _, a in L["sigs"][nm]), L["rets"][nm] == "Callable")
           for nm in L["lib_order"] if nm not in hidden]
    leaves = []
    for j, (pn, _) in enumerate(L["sigs"][op]):
        leaves.append((("P", pn), tuple(e[0][j] for e in examples)))
    for c in L["const_names"]:
        leaves.append((("C", c), (L["consts"][c],) * len(examples)))
    for fnm in L["fn_leaf_names"]:
        if fnm not in hidden:
            leaves.append((("FN", fnm), (ns[fnm],) * len(examples)))
    return ops, leaves, tuple(e[1] for e in examples)


def examples_hash(examples):
    return hashlib.sha256("|".join(dslx.canon(tuple(a)) + "->" + dslx.canon(o) for a, o in examples).encode()).hexdigest()[:16]


def _validate(tree, op, ns, examples):
    """Evaluate a chosen expression on the untouched validation examples. Returns (n_equal, n_error)."""
    L = dslx.load()
    names = [p for p, _ in L["sigs"][op]]
    eq = err = 0
    for args, out in examples:
        try:
            v = S.eval_tree(tree, ns, L["consts"], dict(zip(names, args)))
            if v == out and dslx.canon(v) == dslx.canon(out):      # exact typed equality
                eq += 1
        except Exception:                                       # noqa: BLE001
            err += 1
    return eq, err


_KNOWN = {}


def known_definitions(max_size=None):
    """Operations whose library text is a single return of nested calls of other library operations applied to its
    own parameters and named constants (function-valued library names allowed as arguments), with at most
    max_size nodes. Built with ast from LIBRARY.json source text. Returns {op: tree}."""
    import ast
    ms = max_size if max_size is not None else P.MAX_SIZE
    if ms in _KNOWN:
        return _KNOWN[ms]
    L = dslx.load()
    lib, consts, fnl = set(L["lib_order"]), set(L["const_names"]), set(L["fn_leaf_names"])

    def conv(node, params, me):
        if isinstance(node, ast.Name):
            if node.id in params:
                return ("P", node.id)
            if node.id in consts:
                return ("C", node.id)
            if node.id in fnl and node.id in lib and node.id != me:
                return ("FN", node.id)
            return None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            f = node.func.id
            if f not in lib or f == me or f in params:
                return None
            kids = [conv(x, params, me) for x in node.args]
            return None if any(k is None for k in kids) else ("L", f) + tuple(kids)
        return None

    def size(t):
        return 1 + sum(size(c) for c in t[2:]) if t[0] == "L" else 1

    out = {}
    for op in L["lib_order"]:
        fn = ast.parse(L["sources"][op]).body[0]
        if len(fn.body) == 1 and isinstance(fn.body[0], ast.Return) and fn.body[0].value is not None:
            t = conv(fn.body[0].value, [a.arg for a in fn.args.args], op)
            if t is not None and t[0] == "L" and size(t) <= ms:
                out[op] = t
    _KNOWN[ms] = out
    return out


def _node_values(tree, ns, names, examples):
    """{subtree: vector of values on all examples}; raises if the tree raises on some example."""
    L = dslx.load()
    res = {}

    def go(t, i, args):
        if t[0] == "P":
            return args[names.index(t[1])]
        if t[0] == "C":
            return L["consts"][t[1]]
        if t[0] == "FN":
            return ns[t[1]]
        return ns[t[1]](*[val(c, i, args) for c in t[2:]])

    def val(t, i, args):
        v = go(t, i, args)
        res.setdefault(t, {})[i] = v
        return v

    for i, (args, _) in enumerate(examples):
        val(tree, i, args)
    return {t: tuple(d[i] for i in range(len(examples))) for t, d in res.items() if len(d) == len(examples)}


def check_known(op, tree, ns, examples, oracle):
    """Known-answer control for one operation under condition a (see PROTOCOL.md)."""
    L = dslx.load()
    names = [p for p, _ in L["sigs"][op]]
    rec = dict(expr=S.render(tree), size=sum(1 for _ in _nodes(tree)), found=oracle["expr"] is not None)
    try:
        vals = _node_values(tree, ns, names, examples)
        rec["equals_all_36"] = dslx.canon(vals[tree]) == dslx.canon(tuple(e[1] for e in examples))
    except Exception as e:                                   # noqa: BLE001
        rec["equals_all_36"], rec["error"] = False, type(e).__name__
        return dict(rec, miss_reason=None if rec["found"] else "definition_does_not_run")
    reason = None
    if not rec["found"]:
        if not rec["equals_all_36"]:
            reason = "definition_not_equal"
        else:
            reason = "other"
            for t, vv in vals.items():
                if t[0] != "L":
                    ts = dslx.tagset(vv)
                    continue
                acc = [dslx.ACC[a] for _, a in L["sigs"][t[1]]]
                bad = [i for i, c in enumerate(t[2:]) if (dslx.tagset(vals[c]) is None
                                                          or not dslx.tagset(vals[c]) <= acc[i])]
                if bad:
                    reason = "type_filter"
                    break
            if reason == "other" and oracle.get("function_cap_reached"):
                reason = "function_cap"
    return dict(rec, miss_reason=reason)


def _nodes(t):
    yield t
    if t[0] == "L":
        for c in t[2:]:
            yield from _nodes(c)


def core_known_names():
    return list(known_definitions())


def _arm(ops, leaves, Y, k, budget, max_size):
    """One search seeing only the first k examples (k=None: all of them)."""
    kk = len(Y) if k is None else k
    r = S.search(ops, [(t, v[:kk]) for t, v in leaves], Y[:kk], budget, max_size, P.MAX_FN, P.MAX_BANK)
    return r


def run_condition(op, cond, g, budgets=None, max_size=None, hidden_override=None):
    """g = gen.gen_examples(op) result. cond 'a' (only op hidden) or 'b' (whole family hidden).

    K arms (K in P.CHECKS): a separate search that sees only the first K fit examples; the first fitting expression
    is recorded, and only then evaluated on the 30 validation examples (never used by the search).
    Oracle arm: one search over all 36 examples (fit and validation): is the operation expressible at all."""
    L = dslx.load()
    fam = L["fam_of"][op]
    hidden = set(hidden_override) if hidden_override is not None else ({op} if cond == "a" else set(fam))
    budgets = budgets or P.BUDGET_S
    ms = max_size if max_size is not None else P.MAX_SIZE
    rec = dict(op=op, condition=cond, family=L["fam_label"][op], family_size=len(fam), hidden=sorted(hidden),
               in_pilot_subset=op in P.DEV_SEEN_OPS, library_deps=L["lib_deps"][op], max_size=ms,
               generator=dict(draws=g["draws"], rejected=g.get("rejected", {}), n_examples=len(g["examples"]),
                              function_pool_excluded=g.get("function_pool_excluded", [])),
               held_out_family=op in dslx.held_out_names())
    if g["status"] != "ok":
        rec.update(status="excluded", reason=g["reason"])
        return rec
    ex = g["examples"]
    fit, val = ex[:P.N_FIT], ex[P.N_FIT:]
    ns = dslx.library_namespace(hidden)
    ops, leaves, Y = build(op, hidden, ex, ns)
    arms, readings, cpu = {}, {}, 0.0
    for k in P.CHECKS:
        r = _arm(ops, leaves, Y, k, budgets[str(k)], ms)
        cpu += r["cpu_s"]
        a = dict(stop=r["stop"], level_completed=r["level"], bank=r["bank"], cpu_s=round(r["cpu_s"], 3),
                 function_cap_reached=r["function_cap_reached"])
        if r["found"]:
            eq, err = _validate(r["found"][2], op, ns, val)
            later = fit[k:]                                      # fit examples this arm did not see
            leq, lerr = _validate(r["found"][2], op, ns, later)
            a.update(expr=r["found"][0], size=r["found"][1], validation_equal=eq, validation_errors=err,
                     right=(eq == len(val)), later_fit_equal=leq, later_fit_errors=lerr,
                     later_fit_n=len(later), equal_all_36=(eq == len(val) and leq == len(later)))
            readings[str(k)] = "right" if eq == len(val) else "wrong"
        else:
            a.update(expr=None, size=None, right=None)
            readings[str(k)] = "absent"
        arms[str(k)] = a
    r = _arm(ops, leaves, Y, None, budgets["oracle"], ms)
    cpu += r["cpu_s"]
    arms["oracle"] = dict(stop=r["stop"], level_completed=r["level"], bank=r["bank"], cpu_s=round(r["cpu_s"], 3),
                          function_cap_reached=r["function_cap_reached"],
                          expr=r["found"][0] if r["found"] else None, size=r["found"][1] if r["found"] else None)
    rec.update(status="searched", examples_sha=examples_hash(ex), readings=readings, arms=arms,
               regenerated=r["found"] is not None, expr=arms["oracle"]["expr"], size=arms["oracle"]["size"],
               stop=r["stop"], cpu_s=round(cpu, 3))
    if r["found"]:
        rec["uses_names"] = sorted(S.names_used(r["found"][2]))
    if cond == "a" and hidden_override is None and op in known_definitions(ms):
        rec["known_definition"] = check_known(op, known_definitions(ms)[op], ns, ex, arms["oracle"])
    return rec


def path(outdir, op, cond):
    return os.path.join(outdir, "%s__%s.json" % (op, cond))


def run_op(outdir, op, budgets=None, max_size=None):
    """Both conditions for one operation; finished files are skipped (resumable). Returns the cpu seconds spent."""
    pa, pb = path(outdir, op, "a"), path(outdir, op, "b")
    if os.path.exists(pa) and os.path.exists(pb):
        return 0.0
    g = gen.gen_examples(op)
    L = dslx.load()
    ra = run_condition(op, "a", g, budgets, max_size)
    _write(pa, ra)
    if L["fam_of"][op] == [op] or len(L["fam_of"][op]) == 1:
        rb = dict(ra, condition="b", same_as_a="the family has one member, so conditions a and b are the same search")
    else:
        rb = run_condition(op, "b", g, budgets, max_size)
    _write(pb, rb)
    return ra.get("cpu_s", 0.0) + (0.0 if "same_as_a" in rb else rb.get("cpu_s", 0.0))


def _write(p, rec):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


# ------------------------------------------------------------------ summary
def greedy_core(regen_exprs, all_ops):
    """A GREEDY estimate (an upper bound within this witness graph, not a minimum) of a basis C.

    regen_exprs: {op: set of library names its found expression uses}; all_ops: the operations in scope.
    Names outside all_ops are external basis nodes (assumed available; reported by the caller). Operations in scope
    that were not rebuilt are KEPT AS GIVEN in C (within this witness graph and budget; not necessarily in every
    basis). Every rebuilt operation must be derivable from C through its found expression, without cycles. When an
    operation is chosen as a primitive its obligation is removed. Strict progress is asserted in every round."""
    scope = set(all_ops)
    eq = {o: (set(d) & scope) - {o} for o, d in regen_exprs.items() if o in scope}
    core = scope - set(eq)
    rest = dict(eq)

    def close(have, rest):
        have, rest, changed = set(have), dict(rest), True
        while changed:
            changed = False
            for o in sorted(rest):
                if rest[o] <= have:
                    have.add(o)
                    del rest[o]
                    changed = True
        return have, rest

    have, rest = close(core, rest)
    while rest:
        before = len(rest)
        best, bestn = None, -1
        for o in sorted(rest):                  # add o to the basis; count what becomes derivable
            h2, _ = close(have | {o}, {k: v for k, v in rest.items() if k != o})
            if len(h2) > bestn:
                best, bestn = o, len(h2)
        core.add(best)
        rest.pop(best)
        have, rest = close(have | {best}, rest)
        assert len(rest) < before, "no progress"
    return sorted(core)


def check_core(core, regen_exprs, all_ops, exprs=None):
    """Graph check only (expressions are NOT re-executed): every rebuilt operation is reached from the basis by a
    derivation order with no cycle. Returns the order [(op, expression)] or raises AssertionError."""
    scope = set(all_ops)
    have = set(core)
    todo = {o: (set(d) & scope) - {o} for o, d in regen_exprs.items() if o in scope and o not in have}
    order = []
    while todo:
        ready = [o for o in sorted(todo) if todo[o] <= have]
        assert ready, "cyclic or unreachable: %s" % sorted(todo)
        for o in ready:
            have.add(o)
            del todo[o]
            order.append((o, (exprs or {}).get(o)))
    return order


def summarize(outdir, ops=None):
    L = dslx.load()
    names = [o for o in L["lib_order"] if ops is None or o in ops]
    recs = {c: {} for c in "ab"}
    for o in names:
        for c in "ab":
            p = path(outdir, o, c)
            if os.path.exists(p):
                recs[c][o] = json.load(open(p))
    out = dict(what="core operations measurement (model-free); see PROTOCOL.md. 'Not found' always means not found "
                    "within this size limit and CPU budget.",
               pilot_ops_in_this_summary=sorted(o for o in names if o in P.DEV_SEEN_OPS),
               n_operations=len(names),
               presets=dict(N_FIT=P.N_FIT, N_VAL=P.N_VAL, MAX_SIZE=P.MAX_SIZE, BUDGET_S=P.BUDGET_S,
                            MAX_FN=P.MAX_FN, MAX_BANK=P.MAX_BANK), conditions={})
    total_cpu = 0.0
    for c in "ab":
        R = recs[c]
        excl = {o: r["reason"] for o, r in R.items() if r["status"] == "excluded"}
        srch = {o: r for o, r in R.items() if r["status"] == "searched"}
        regen = {o: r for o, r in srch.items() if r["regenerated"]}
        by_size = {}
        for r in regen.values():
            by_size[str(r["size"])] = by_size.get(str(r["size"]), 0) + 1
        readings, stops = {}, {}
        for k in list(map(str, P.CHECKS)) + ["oracle"]:
            stops[k] = {}
            for r in srch.values():
                st = r["arms"][k]["stop"]
                stops[k][st] = stops[k].get(st, 0) + 1
        for k in map(str, P.CHECKS):
            cnt = {"right": 0, "wrong": 0, "absent": 0}
            for r in srch.values():
                cnt[r["readings"][k]] += 1
            readings[k] = cnt
        capn = {k: sum(1 for r in srch.values() if r["arms"][k].get("function_cap_reached"))
                for k in list(map(str, P.CHECKS)) + ["oracle"]}
        consist = {}
        for k in map(str, P.CHECKS):
            rights = [r["arms"][k] for r in srch.values() if r["readings"][k] == "right"]
            consist[k] = dict(right=len(rights),
                              of_which_fail_a_later_fit_example=sum(
                                  1 for a_ in rights if a_["later_fit_equal"] < a_["later_fit_n"]))
        missed = sorted(o for o, r in srch.items() if not r["regenerated"]
                        and any(r["arms"][k].get("equal_all_36") for k in map(str, P.CHECKS)))
        cpu = sum(r["cpu_s"] for r in srch.values() if "same_as_a" not in r)
        total_cpu += cpu
        cd = dict(missing_files=len(names) - len(R),
                  oracle_assisted_coverage=dict(
                      expressible_within_limit_and_budget=len(regen),
                      not_found_within_limit_and_budget=len(srch) - len(regen), excluded=len(excl),
                      by_size=dict(sorted(by_size.items())),
                      ops={o: dict(expr=r["expr"], size=r["size"], pilot=r["in_pilot_subset"])
                           for o, r in sorted(regen.items())}),
                  rule_choice_by_n_fit_examples=readings, stop_reasons_by_arm=stops,
                  function_cap_reached_by_arm=capn,
                  right_expressions_vs_later_fit_examples=consist,
                  oracle_missed_an_expression_that_a_K_arm_found_equal_on_all_36=missed,
                  excluded_reasons=excl, cpu_s=round(cpu, 1))
        nonpilot = {o: r for o, r in srch.items() if not r["in_pilot_subset"]}
        cd["without_pilot_subset"] = dict(searched=len(nonpilot),
                                          regenerated=sum(1 for r in nonpilot.values() if r["regenerated"]))
        deps = L["lib_deps"]
        with_dep = [o for o in srch if deps[o]]
        raw = [o for o in srch if not deps[o]]
        cd["library_comparison"] = dict(
            searched_with_source_calling_library=len(with_dep),
            of_which_regenerated=sum(1 for o in with_dep if o in regen),
            searched_raw_python=len(raw), raw_python_regenerated=sorted(o for o in raw if o in regen),
            regenerated_expression_uses_one_of_its_own_source_deps=sorted(
                o for o in regen if set(regen[o].get("uses_names", [])) & set(deps[o])))
        out["conditions"][c] = cd
    out["total_cpu_s"] = round(total_cpu, 1)
    kd = {o: r["known_definition"] for o, r in recs["a"].items() if "known_definition" in r}
    kd_ok = {o: v for o, v in kd.items() if v["equals_all_36"]}
    miss = {o: v["miss_reason"] for o, v in kd.items() if not v["found"]}
    by_reason = {}
    for rsn in miss.values():
        by_reason[str(rsn)] = by_reason.get(str(rsn), 0) + 1
    out["known_short_definitions"] = dict(
        note="Known-answer control, condition a. Operations whose library text is a single return of nested calls "
             "of other library operations applied to their own parameters and named constants, within the size "
             "limit. 'found' = the oracle arm found some expression; 'missed' = it did not, though this definition "
             "exists. Measures how often this annotation-typed enumerator misses a known answer.",
        n=len(kd), definition_equals_x_on_all_36=len(kd_ok), found=sum(1 for v in kd.values() if v["found"]),
        missed=len(miss), missed_by_reason=by_reason, missed_ops=miss,
        qualifying_operations_in_library=sorted(core_known_names()),
        definitions={o: dict(expr=v["expr"], size=v["size"], found=v["found"]) for o, v in sorted(kd.items())})
    ho = dslx.held_out_names()
    out["held_out_by_the_earlier_study"] = dict(
        note="the family table holds out %d names in %d families, of %d names in %d families; reported separately"
             % (len(ho), len(set(ho.values())), len(L["lib_order"]), len({tuple(sorted(m)) for m in L["fam_of"].values()})),
        names=sorted(ho),
        in_this_summary=sorted(o for o in names if o in ho),
        regenerated_condition_a=sorted(o for o in names if o in ho and o in recs["a"]
                                       and recs["a"][o].get("regenerated")),
        regenerated_condition_b=sorted(o for o in names if o in ho and o in recs["b"]
                                       and recs["b"][o].get("regenerated")))
    R = recs["a"]
    if R:
        reg = {o: set(r.get("uses_names", [])) - {o} for o, r in R.items()
               if r["status"] == "searched" and r["regenerated"]}
        ext = sorted({d for v in reg.values() for d in v} - set(names))
        core = greedy_core(reg, names)
        exprs = {o: r["expr"] for o, r in R.items() if r["status"] == "searched" and r["regenerated"]}
        order = check_core(core, reg, names, exprs)
        out["core_estimate_condition_a"] = dict(
            note="greedy estimate (an upper bound within this witness graph, built from the oracle-arm "
                 "expressions, and this budget), not a minimum. Operations not rebuilt are kept as given within "
                 "this witness graph and budget, not necessarily in every basis. Names outside the operations in "
                 "scope are external basis nodes. Graph check only; the expressions were not re-executed.",
            size=len(core), of=len(names), external_basis_names=ext, graph_check_passed=True, members=core,
            reconstruction_order=[dict(op=o, expr=e) for o, e in order])
    return out
