"""Typed bottom-up enumeration by expression size with observational equivalence, over several typed parameters.
Author: Chimdi Walter Ndubuisi

Standard technique (see TRANSIT, PLDI 2013; Escher, CAV 2013); nothing new is claimed. Expressions are trees:
('P', name) a parameter of the hidden operation, ('C', name) a named constant, ('FN', name) a library function used
as a value, ('L', name, child, ...) a library operation applied to children. Size = number of nodes.

A bank entry is an expression with its value on every example (the bank is all examples at once). An expression is
kept only if it runs without error on every example and gives one usable type; two expressions with identical values
on all examples are merged (the first in enumeration order is kept). Function values are never merged by value
(keyed by their tree) and are capped. Enumeration order: size, then the operation order given, then the order
of the argument size split, then the order the children were found. It is fixed, so runs are reproducible.
The time limit is process CPU time (time.process_time), not wall time.
"""
import itertools
import signal
import time

import dslx
from dslx import tag

CAP = 3000


class Hard(BaseException):
    pass


def _alarm(*_):
    raise Hard()


def render(t):
    if t[0] == "L":
        return t[1] + "(" + ", ".join(render(c) for c in t[2:]) + ")"
    return t[1]


def names_used(t, out=None):
    """Library names (operations and function-valued leaves) an expression uses."""
    out = set() if out is None else out
    if t[0] in ("L", "FN"):
        out.add(t[1])
    for c in t[2:] if t[0] == "L" else ():
        names_used(c, out)
    return out


def _same(a, b, k):
    return a[:k] == b[:k] and all(type(x) is type(y) for x, y in zip(a[:k], b[:k]))


_COMP = {}


def _compositions(total, k):
    key = (total, k)
    if key not in _COMP:
        if k == 1:
            out = [(total,)] if total >= 1 else []
        else:
            out = [(a,) + rest for a in range(1, total - k + 2) for rest in _compositions(total - a, k - 1)]
        _COMP[key] = out
    return _COMP[key]


def search(ops, leaves, Y, cpu_budget, max_size, max_fn=300, max_bank=250000):
    """ops: list of (name, fn, acc tuple of tag sets, makes_fn); leaves: list of (tree, vals); Y: target values.
    Only the examples in Y (and the same-length leaf vectors) are used: equivalence, pruning, order and stopping.
    Stops at the FIRST expression (smallest size, fixed tie order) equal to Y on all of them.

    Returns dict(found=(text, size, tree) or None, stop, level, bank, cpu_s).
    stop: 'found', 'size_exhausted', 'size_exhausted_function_cap' (the cap on function-valued entries was reached,
    so the enumeration was not exhaustive), 'budget_cpu', 'budget_bank' or 'hard_timeout'.
    """
    n = len(Y)
    t0 = time.process_time()
    pools = {}                              # size -> {tagset: [(vals, tree, const)]}
    seen = set()
    st = dict(regen=None, nfn=0, level=0, stop=None, cap=False)
    old = signal.signal(signal.SIGVTALRM, _alarm)
    signal.setitimer(signal.ITIMER_VIRTUAL, cpu_budget + 30)

    def add(vals, ts, tree, sz, leaf=False):
        if "F" in ts:
            key = tree
            if not leaf and st["nfn"] >= max_fn:
                st["cap"] = True
                return
            st["nfn"] += 1
        else:
            key = (ts, vals)
        if key in seen:
            return
        seen.add(key)
        v0 = vals[0]
        const = all(v is v0 or (type(v) is type(v0) and v == v0) for v in vals) if "F" not in ts else False
        pools.setdefault(sz, {}).setdefault(ts, []).append((vals, tree, const))
        if "F" not in ts and v0 == Y[0] and type(v0) is type(Y[0]) and st["regen"] is None and _same(vals, Y, n) \
                and dslx.canon(vals) == dslx.canon(Y):          # exact typed equality at acceptance
            st["regen"] = (render(tree), sz, tree)

    try:
        for tree, vals in leaves:
            ts = dslx.tagset(vals)
            if ts is not None:
                add(vals, ts, tree, 1, leaf=True)
        cache = {}

        def pool(sz, acc):
            k = (sz, acc)
            if k not in cache:
                out = []
                d = pools.get(sz, {})
                for ts in sorted(d, key=lambda s: tuple(sorted(s))):
                    if ts <= acc:
                        out.extend(d[ts])
                cache[k] = out
            return cache[k]

        tick = 0
        for sz in range(2, max_size + 1):
            if st["regen"]:
                break
            cache.clear()
            for name, f, acc, mk in ops:
                k = len(acc)
                if sz - 1 < k:
                    continue
                if mk and sz + 2 > max_size:
                    continue    # exact pruning: a consumer of a function takes at least 2 arguments, so a
                    #             function entry of size sz is used only if sz + 2 <= max_size; it is never the target
                if mk and st["nfn"] >= max_fn:
                    st["cap"] = True
                    continue
                for parts in _compositions(sz - 1, k):
                    lists = [pool(si, a) for si, a in zip(parts, acc)]
                    if not all(lists):
                        continue
                    for combo in itertools.product(*lists):
                        tick += 1
                        if tick & 127 == 0:
                            if time.process_time() - t0 > cpu_budget:
                                st["stop"] = "budget_cpu"
                                break
                            if len(seen) >= max_bank:
                                st["stop"] = "budget_bank"
                                break
                        try:
                            if all(c[2] for c in combo):
                                v = f(*[c[0][0] for c in combo])
                                tg = tag(v)
                                if tg == "U" or (tg not in ("B", "I", "F") and len(v) > CAP):
                                    continue
                                outs = (v,) * n
                                tags = {tg}
                            else:
                                outs, tags = [], set()
                                for i in range(n):
                                    v = f(*[c[0][i] for c in combo])
                                    tg = tag(v)
                                    if tg == "U" or (tg not in ("B", "I", "F") and len(v) > CAP):
                                        break
                                    tags.add(tg)
                                    outs.append(v)
                                else:
                                    outs = tuple(outs)
                                if len(outs) != n:
                                    continue
                        except Exception:               # noqa: BLE001 (type errors are the common outcome)
                            continue
                        ts = dslx.norm(tags)
                        if ts is None:
                            continue
                        add(outs, ts, ("L", name) + tuple(c[1] for c in combo), sz)
                        if st["regen"]:
                            st["stop"] = "found"
                            break
                    if st["stop"]:
                        break
                if st["stop"]:
                    break
            if st["stop"]:
                break
            st["level"] = sz
        if st["regen"]:
            st["stop"] = "found"
        elif not st["stop"]:
            st["stop"] = "size_exhausted_function_cap" if st["cap"] else "size_exhausted"
    except Hard:
        st["stop"] = "hard_timeout"
    finally:
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, old)
    return dict(found=st["regen"], stop=st["stop"], level=st["level"], bank=len(seen), function_cap_reached=st["cap"],
                cpu_s=time.process_time() - t0)


def eval_tree(tree, ns, consts, params):
    """Value of an expression in namespace `ns` with parameter values `params` {name: value} (raises on error)."""
    h = tree[0]
    if h == "P":
        return params[tree[1]]
    if h == "C":
        return consts[tree[1]]
    if h == "FN":
        return ns[tree[1]]
    return ns[tree[1]](*[eval_tree(c, ns, consts, params) for c in tree[2:]])
