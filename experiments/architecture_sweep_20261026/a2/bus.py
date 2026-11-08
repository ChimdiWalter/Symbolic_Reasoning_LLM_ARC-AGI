"""Typed bottom-up enumeration over the arc-dsl tree IR (shared by A2 and A3).

Programs are built by tree size. A bank value is the tuple of a subprogram's values on ALL inputs of the task
(demonstration inputs, then query inputs); observational equivalence merges subprograms with identical value
tuples, so programs that agree on the demonstrations but predict different query outputs are kept apart.
Function values (closures) are never merged (keyed by their tree) and capped.

Budget: primitive executions per input. A library production is charged the primitive count of its body for every
input it runs on; failed applications are charged too. The same budget for every arm makes executor counts equal;
CPU time is measured separately (practical efficiency). Exact execution is not differentiable: learning only orders
or supplies productions; every accepted program is checked by exact execution on every demonstration.
"""
import itertools
import time

from a2 import arcdsl as D


class Prod:
    __slots__ = ("head", "fn", "argtags", "arity", "charge", "name", "makes_fn")

    def __init__(self, head, fn, argtags, charge=1, makes_fn=False):
        self.head, self.fn, self.argtags, self.arity, self.charge = head, fn, tuple(argtags), len(argtags), charge
        self.name = head.split(":", 1)[1]
        self.makes_fn = makes_fn                     # a closure constructor (skipped once the closure cap is hit)


def compile_tree(t, fns, consts, lib_fns):
    """Tree with parameters #k -> function(params tuple) -> value. `lib_fns`: name -> (callable(params), arity)."""
    h = t[0]
    if h[0] == "#":
        k = int(h[1:])
        return lambda p: p[k]
    if h.startswith("c:"):
        v = consts[h[2:]]
        return lambda p: v
    if h.startswith("fn:"):
        v = fns[h[3:]]
        return lambda p: v
    if h.startswith("lfn:"):
        v = as_callable(*lib_fns[h[4:]])
        return lambda p: v
    cs = [compile_tree(c, fns, consts, lib_fns) for c in t[1:]]
    if h.startswith("f:") or h.startswith("L:"):
        f = fns[h[2:]] if h[0] == "f" else _lib_entry(lib_fns[h[2:]][0])
        if len(cs) == 1:
            c0, = cs
            return lambda p: f(c0(p))
        if len(cs) == 2:
            c0, c1 = cs
            return lambda p: f(c0(p), c1(p))
        if len(cs) == 3:
            c0, c1, c2 = cs
            return lambda p: f(c0(p), c1(p), c2(p))
        return lambda p: f(*[c(p) for c in cs])
    if h == "@":
        fc, rest = cs[0], cs[1:]
        return lambda p: fc(p)(*[c(p) for c in rest])
    raise ValueError(h)


def _lib_entry(body_fn):
    return lambda *a: body_fn(a)


def as_callable(body_fn, arity):
    """A plain function with exactly `arity` positional parameters (arc-dsl's rbind/lbind read co_argcount)."""
    if arity == 1:
        return lambda a: body_fn((a,))
    if arity == 2:
        return lambda a, b: body_fn((a, b))
    if arity == 3:
        return lambda a, b, c: body_fn((a, b, c))
    if arity == 4:
        return lambda a, b, c, d: body_fn((a, b, c, d))
    raise ValueError(arity)


def body_charge(t, lib_charge):
    h = t[0]
    own = 1 if (h.startswith("f:") or h == "@") else (lib_charge[h[2:]] if h.startswith("L:") else 0)
    return own + sum(body_charge(c, lib_charge) for c in t[1:])


class Grammar:
    """Ordered productions + leaves. `library`: list of (name, arity, body tree, param tags) in promotion order."""

    def __init__(self, prims, fn_leaves, const_names, library=(), order=None, sigs=None, costs=None):
        dsl, consts, _, _ = D.load()
        self.fns = D.guarded(dsl)
        self.consts = consts
        sigs = sigs or D.prim_signatures()
        rets = D.prim_returns()
        self.lib_fns, self.lib_charge, self.library = {}, {}, list(library)
        prods = {}
        for name in prims:
            prods["f:" + name] = Prod("f:" + name, self.fns[name], [D.arg_tags(a) for a in sigs[name]],
                                      makes_fn=rets.get(name) == "Callable")
        for name, arity, body, ptags in self.library:
            bf = compile_tree(body, self.fns, consts, self.lib_fns)
            self.lib_fns[name] = (bf, arity)
            self.lib_charge[name] = body_charge(body, self.lib_charge)
            prods["L:" + name] = Prod("L:" + name, _lib_entry(bf), [frozenset(t) for t in ptags],
                                      charge=self.lib_charge[name])
        heads = list(order) if order else list(prods)
        heads += [h for h in prods if h not in heads]
        self.prods = [prods[h] for h in heads if h in prods]
        self.const_names = list(const_names)
        self.fn_leaves = list(fn_leaves) + ["lfn:" + n for n, a, _, _ in self.library if fn_leaf_ok(a)]
        self.costs = dict(costs or {})              # head -> integer cost (productions and leaves); default 1

    def cost(self, head):
        return self.costs.get(head, 1)

    def leaf_value(self, head):
        if head.startswith("lfn:"):
            return as_callable(*self.lib_fns[head[4:]])
        return self.fns[head[3:]]


def fn_leaf_ok(arity):
    return 1 <= arity <= 2


class Result:
    __slots__ = ("solved", "program", "preds", "calls", "cpu_s", "bank", "level", "seen", "stop", "fits",
                 "first_fit_calls", "partial")

    def as_dict(self):
        return {"solved": self.solved, "program": D.show(self.program) if self.program else None,
                "preds": [[list(r) for r in g] for g in self.preds] if self.preds else None, "calls": self.calls,
                "first_fit_calls": self.first_fit_calls, "cpu_s": round(self.cpu_s, 3), "bank": self.bank,
                "level": self.level, "stop": self.stop, "fits": self.fits}


def search(grammar, train_pairs, test_inputs, budget, max_size=24, reps=None, extra_leaves=(), keep_seen=False,
           cpu_cap=120.0, max_fn=400, want=2, track_partial=False):
    """Enumerate until `want` fitting programs with distinct query predictions are found or the budget is spent.

    reps: {name: tuple of per-input values} representation leaves ('R:name'); extra_leaves: (tree, values, cost).
    max_size is the highest cost level.
    """
    t0 = time.process_time()
    xs = tuple(D.to_grid(x) for x, _ in train_pairs) + tuple(D.to_grid(x) for x in test_inputs)
    ys = tuple(D.to_grid(y) for _, y in train_pairs)
    n, ntr = len(xs), len(train_pairs)
    seen = set()
    pools = {}                      # (size, tag) -> list of (vals, tree)
    nfn = [0]
    res = Result()
    res.solved, res.program, res.preds, res.fits, res.stop, res.first_fit_calls = False, None, None, [], "budget", None
    res.partial = None                  # best demonstration-shaped grid program: (correct cells, tree, demo outputs)
    shapes = tuple((len(y), len(y[0])) for y in ys)
    best = [-1]
    calls = 0
    fits = []

    def add(vals, tg, tree, sz):
        if tg == "F":
            key = tree
            if nfn[0] >= max_fn:
                return False
            nfn[0] += 1
        else:
            key = (tg, vals)
        if key in seen:
            return False
        seen.add(key)
        v0 = vals[0]
        const = all(v is v0 for v in vals) or (tg != "F" and vals.count(v0) == n)
        pools.setdefault((sz, tg), []).append((vals, tree, const))
        if tg == "G" and vals[:ntr] == ys:
            pred = vals[ntr:]
            if all(pred != f[1] for f in fits):
                fits.append((tree, pred))
        elif track_partial and tg == "G" and all((len(v), len(v[0])) == s for v, s in zip(vals[:ntr], shapes)):
            sc = sum(a == b for v, y in zip(vals[:ntr], ys) for rv, ry in zip(v, y) for a, b in zip(rv, ry))
            if sc > best[0]:
                best[0] = sc
                res.partial = (sc, tree, vals[:ntr])
        return True

    gc = grammar.cost
    add(xs, "G", ("I",), gc("I"))
    for name in grammar.const_names:
        v = grammar.consts[name]
        add((v,) * n, D.tag(v), ("c:" + name,), gc("c:" + name))
    for head in grammar.fn_leaves:
        v = grammar.leaf_value(head)
        add((v,) * n, "F", (head,), gc(head))
    for name, vals in (reps or {}).items():
        tg = _tag_all(vals)
        if tg:
            add(tuple(vals), tg, ("R:" + name,), gc("R:" + name))
    for tree, vals, c in extra_leaves:
        tg = _tag_all(vals)
        if tg:
            add(tuple(vals), tg, tree, c)
    level = 1
    stop = None
    tick = 0
    pool_cache = {}

    def pool(sz, tags):
        k = (sz, tags)
        if k not in pool_cache:
            out = []
            for tg in tags:
                out.extend(pools.get((sz, tg), ()))
            pool_cache[k] = out
        return pool_cache[k]

    pcost = [gc(p.head) for p in grammar.prods]
    for sz in range(2, max_size + 1):          # sz = cost level (sum of production and leaf costs)
        if fits and len(fits) >= want:
            break
        pool_cache.clear()              # pools of lower levels are final; the current level is never read
        for prod, pc in zip(grammar.prods, pcost):
            k = prod.arity
            f, ch = prod.fn, prod.charge
            if sz - pc < k or (prod.makes_fn and nfn[0] >= max_fn):
                continue
            for parts in _compositions(sz - pc, k):
                lists = [pool(si, tg) for si, tg in zip(parts, prod.argtags)]
                if not all(lists):
                    continue
                for combo in itertools.product(*lists):
                    if calls >= budget:
                        stop = "budget"
                        break
                    tick += 1
                    if tick & 255 == 0 and time.process_time() - t0 > cpu_cap:
                        stop = "cpu_cap"
                        break
                    outs = []
                    ok = True
                    if all(c[2] for c in combo):       # input-constant arguments: one execution (pure functions)
                        calls += ch
                        try:
                            v = f(*[c[0][0] for c in combo])
                            ok = D.valid(v)
                        except Exception:              # noqa: BLE001
                            ok = False
                        outs = [v] * n if ok else outs
                    else:
                        for i in range(n):
                            calls += ch
                            try:
                                v = f(*[c[0][i] for c in combo])
                            except Exception:          # noqa: BLE001 (type errors are the common outcome)
                                ok = False
                                break
                            if not D.valid(v):
                                ok = False
                                break
                            outs.append(v)
                    if not ok:
                        continue
                    tg = _tag_all(outs)
                    if tg is None:
                        continue
                    tree = (prod.head,) + tuple(c[1] for c in combo)
                    if add(tuple(outs), tg, tree, sz) and fits and res.first_fit_calls is None:
                        res.first_fit_calls = calls
                    if len(fits) >= want:
                        stop = "fits"
                        break
                if stop:
                    break
            if stop:
                break
        if stop:
            break
        level = sz
    res.stop = stop or ("fits" if fits else "max_size")
    res.calls, res.level = calls, level
    res.cpu_s = time.process_time() - t0
    res.bank = len(seen)
    res.fits = [D.show(t) for t, _ in fits]
    if fits:
        res.solved, res.program = True, fits[0][0]
        res.preds = _attempts([p for _, p in fits])
    res.seen = seen if keep_seen else None
    return res


def _attempts(preds_list):
    """Two attempts per query input: the first two fitting programs with distinct predictions."""
    first = preds_list[0]
    second = preds_list[1] if len(preds_list) > 1 else first
    return [first, second]


def _tag_all(vals):
    tags = {D.tag(v) for v in vals}
    if len(tags) == 1:
        tg = tags.pop()
        return None if tg == "U" else tg
    tags.discard("E")
    if len(tags) == 1:
        tg = tags.pop()
        return None if tg in ("U", "I", "B", "G", "T") else tg
    return None


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


# ------------------------------------------------------------------ reachability trace of a verified program
def subtrees(t, out=None):
    out = [] if out is None else out
    out.append(t)
    for c in t[1:]:
        subtrees(c, out)
    return out


def node_keys(tree, xs, ev):
    """{subtree: bank key} for every distinct subtree of a verified program (values on all inputs)."""
    keys = {}
    for st in set(subtrees(tree)):
        if st[0] == "I" or st[0].startswith("c:"):
            vals = tuple(ev.run(st, x) for x in xs)
            keys[st] = (_tag_all(vals), vals)
        else:
            try:
                vals = tuple(ev.run(st, x) for x in xs)
            except Exception:                                   # noqa: BLE001
                keys[st] = None
                continue
            tg = _tag_all(vals)
            keys[st] = st if tg == "F" else (tg, vals)
    return keys
