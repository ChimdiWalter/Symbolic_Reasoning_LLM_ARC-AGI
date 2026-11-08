"""U3 list DSL (31 typed operations) and its bottom-up enumerator (mirrors A2's bus.search conventions).

Types: L = list of integers (a tuple), I = integer. Leaves: the input list x (cost 1) and the integers 0..9 (cost 1).
Every operation costs 1, so a program's cost is its size. Values are valid when integers satisfy |v| <= 999 and
lists have length <= 40 with elements |v| <= 999; an operation that raises or yields an invalid value is undefined
on that input.

Operations (name: argument types -> result type; semantics):
  L -> L   reverse; sort_asc; sort_desc; dedup (keep first occurrences); tail (drop first; undefined on []);
           init (drop last; undefined on []); filter_even; filter_odd
  L,I -> L take(xs, n) first n (n >= 0); drop(xs, n) without the first n (n >= 0); append(xs, k); prepend(xs, k);
           remove(xs, k) all elements != k; map_add(xs, k) each v + k; map_mul(xs, k) each v * k;
           filter_gt(xs, k) elements > k; filter_lt(xs, k) elements < k; rotate_left(xs, n) (n >= 0; [] -> [])
  L,L -> L concat
  L -> I   length; sum; max; min; first; last (max, min, first, last undefined on [])
  L,I -> I nth(xs, i) element at 0-based index i (undefined out of range); count(xs, k) occurrences of k
  I,I -> I add; sub
  I -> L   singleton(a) = [a]
  I,I -> L repeat(k, n) = [k] * n (0 <= n <= 40)

search(): programs are enumerated by cost level. A bank value is the tuple of a subprogram's values on ALL inputs
(demonstrations, then queries); observational equivalence merges subprograms with identical value tuples. Budget =
operation executions (one per input, or one when every argument is input-constant). A level counts as complete
only when it finished before the budget, the CPU cap or the fits stopped it. Two attempts: the first two fitting
programs with distinct query predictions (the first twice if only one).
"""
import itertools
import time

MAXV, MAXLEN = 999, 40


class Undefined(Exception):
    pass


def _iv(v):
    if type(v) is not int or abs(v) > MAXV:
        raise Undefined()
    return v


def _lv(v):
    v = tuple(v)
    if len(v) > MAXLEN or any(type(e) is not int or abs(e) > MAXV for e in v):
        raise Undefined()
    return v


def _nonempty(xs):
    if not xs:
        raise Undefined()
    return xs


def _nat(n):
    if n < 0:
        raise Undefined()
    return n


def _dedup(xs):
    seen, out = set(), []
    for v in xs:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _rot(xs, n):
    n = _nat(n)
    if not xs:
        return xs
    n %= len(xs)
    return xs[n:] + xs[:n]


OPS = {
    "reverse": (("L",), "L", lambda xs: xs[::-1]),
    "sort_asc": (("L",), "L", lambda xs: sorted(xs)),
    "sort_desc": (("L",), "L", lambda xs: sorted(xs, reverse=True)),
    "dedup": (("L",), "L", _dedup),
    "tail": (("L",), "L", lambda xs: _nonempty(xs)[1:]),
    "init": (("L",), "L", lambda xs: _nonempty(xs)[:-1]),
    "filter_even": (("L",), "L", lambda xs: [v for v in xs if v % 2 == 0]),
    "filter_odd": (("L",), "L", lambda xs: [v for v in xs if v % 2 == 1]),
    "take": (("L", "I"), "L", lambda xs, n: xs[:_nat(n)]),
    "drop": (("L", "I"), "L", lambda xs, n: xs[_nat(n):]),
    "append": (("L", "I"), "L", lambda xs, k: xs + (k,)),
    "prepend": (("L", "I"), "L", lambda xs, k: (k,) + xs),
    "remove": (("L", "I"), "L", lambda xs, k: [v for v in xs if v != k]),
    "map_add": (("L", "I"), "L", lambda xs, k: [v + k for v in xs]),
    "map_mul": (("L", "I"), "L", lambda xs, k: [v * k for v in xs]),
    "filter_gt": (("L", "I"), "L", lambda xs, k: [v for v in xs if v > k]),
    "filter_lt": (("L", "I"), "L", lambda xs, k: [v for v in xs if v < k]),
    "rotate_left": (("L", "I"), "L", _rot),
    "concat": (("L", "L"), "L", lambda a, b: a + b),
    "length": (("L",), "I", lambda xs: len(xs)),
    "sum": (("L",), "I", lambda xs: sum(xs)),
    "max": (("L",), "I", lambda xs: max(_nonempty(xs))),
    "min": (("L",), "I", lambda xs: min(_nonempty(xs))),
    "first": (("L",), "I", lambda xs: _nonempty(xs)[0]),
    "last": (("L",), "I", lambda xs: _nonempty(xs)[-1]),
    "nth": (("L", "I"), "I", lambda xs, i: xs[_nat(i)]),
    "count": (("L", "I"), "I", lambda xs, k: xs.count(k)),
    "add": (("I", "I"), "I", lambda a, b: a + b),
    "sub": (("I", "I"), "I", lambda a, b: a - b),
    "singleton": (("I",), "L", lambda a: (a,)),
    "repeat": (("I", "I"), "L", lambda k, n: (k,) * min(_nat(n), MAXLEN + 1)),
}
#: list -> list operations that are also structures of the schema language (candidates for deletion)
DELETABLE = ("reverse", "sort_asc", "sort_desc", "dedup", "tail", "init", "filter_even", "filter_odd", "take", "drop",
             "append", "prepend", "remove", "map_add", "map_mul", "filter_gt", "filter_lt", "rotate_left")


def apply_op(fn, rt, args):
    try:
        v = fn(*args)
    except (Undefined, IndexError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        raise Undefined()
    return _lv(v) if rt == "L" else _iv(v)


class Prod:
    __slots__ = ("name", "argtypes", "rettype", "fn")

    def __init__(self, name, argtypes, rettype, fn):
        self.name, self.argtypes, self.rettype, self.fn = name, tuple(argtypes), rettype, fn


class Grammar:
    def __init__(self, removed=()):
        self.prods = [Prod(n, a, r, f) for n, (a, r, f) in OPS.items() if n not in set(removed)]
        self.removed = tuple(sorted(removed))

    def copy(self):
        g = Grammar.__new__(Grammar)
        g.prods, g.removed = list(self.prods), self.removed
        return g

    def add(self, name, fn, n_int_params):
        """A new list operation (L[, I]) -> L (a schema structure or a reference)."""
        self.prods.append(Prod(name, ("L",) + ("I",) * n_int_params, "L", fn))
        return self


def show(t):
    if t[0] == "x":
        return "x"
    if t[0] == "c":
        return str(t[1])
    return f"{t[0]}({', '.join(show(c) for c in t[1:])})"


def evaluate(t, x, g_by_name):
    if t[0] == "x":
        return tuple(x)
    if t[0] == "c":
        return t[1]
    p = g_by_name[t[0]]
    return apply_op(p.fn, p.rettype, [evaluate(c, x, g_by_name) for c in t[1:]])


_COMP = {}


def _compositions(total, k):
    key = (total, k)
    if key not in _COMP:
        if k == 1:
            out = [(total,)] if total >= 1 else []
        else:
            out = [(a,) + r for a in range(1, total - k + 2) for r in _compositions(total - a, k - 1)]
        _COMP[key] = out
    return _COMP[key]


def search(g, train, test_inputs, budget=150_000, cpu_cap=20.0, want=2, max_size=24):
    t0 = time.process_time()
    xs = [tuple(a) for a, _ in train] + [tuple(q) for q in test_inputs]
    ys = tuple(tuple(b) for _, b in train)
    n, ntr = len(xs), len(train)
    seen, pools, fits = set(), {}, []
    calls, tick, stop, level = 0, 0, None, 1

    def add(vals, tp, tree, sz, const):
        key = (tp, vals)
        if key in seen:
            return
        seen.add(key)
        pools.setdefault((sz, tp), []).append((vals, tree, const))
        if tp == "L" and vals[:ntr] == ys:
            pred = vals[ntr:]
            if all(pred != f[1] for f in fits):
                fits.append((tree, pred))

    add(tuple(xs), "L", ("x",), 1, False)
    for c in range(10):
        add((c,) * n, "I", ("c", c), 1, True)
    for sz in range(2, max_size + 1):
        if len(fits) >= want:
            break
        for p in g.prods:
            k = len(p.argtypes)
            if sz - 1 < k:
                continue
            for parts in _compositions(sz - 1, k):
                lists = [pools.get((si, tp), ()) for si, tp in zip(parts, p.argtypes)]
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
                    const = all(c[2] for c in combo)
                    try:
                        if const:
                            calls += 1
                            v = apply_op(p.fn, p.rettype, [c[0][0] for c in combo])
                            vals = (v,) * n
                        else:
                            out = []
                            for i in range(n):
                                calls += 1
                                out.append(apply_op(p.fn, p.rettype, [c[0][i] for c in combo]))
                            vals = tuple(out)
                    except Undefined:
                        continue
                    add(vals, p.rettype, (p.name,) + tuple(c[1] for c in combo), sz, const)
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
    res = {"fit": bool(fits), "program": show(fits[0][0]) if fits else None,
           "program_tree": fits[0][0] if fits else None, "fits": [show(f[0]) for f in fits],
           "preds": [list(fits[0][1]), list(fits[1][1] if len(fits) > 1 else fits[0][1])] if fits else None,
           "level_complete": level, "stop": stop or ("fits" if fits else "max_size"), "calls": calls,
           "bank": len(seen), "cpu_s": round(time.process_time() - t0, 3)}
    return res


def uses(tree, names):
    if tree[0] in names:
        return True
    return any(uses(c, names) for c in tree[1:] if isinstance(c, tuple))
