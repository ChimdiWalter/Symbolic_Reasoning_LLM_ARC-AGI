"""U3 schema language SIGMA_L: generic list -> list operator structures (59), optional parameter k in 0..9.

Values are tuples of integers; a structure returns a tuple or None (undefined). Validity as in listdsl.

ELEM(op)        every element v becomes op(v, k): add v+k | sub v-k | mul v*k | mod v%k (k>=1) | div v//k (k>=1) |
                max max(v,k) | min min(v,k)
KEEP(pred)      keep the elements satisfying: eq v==k | ne v!=k | gt v>k | lt v<k | ge v>=k | le v<=k |
                mult v%k==0 (k>=1) | even | odd   (even and odd take no parameter)
POS(rule)       by position i (0-based) of n: take_first i<k | drop_first i>=k | take_last i>=n-k | drop_last i<n-k |
                every_kth i%k==0 (k>=1) | skip_kth i%k!=0 (k>=1)
ORDER(kind)     reverse | sort_asc | sort_desc | dedup (first occurrences) | rotate_left k | rotate_right k
                (rotations of [] are [])
EDGE(kind)      append k | prepend k | set_first k (undefined on []) | set_last k (undefined on [])
REDUCE(kind)    a one-element list: sum | length | max | min | first | last (undefined on [] except sum, length) |
                count k (occurrences of k)
MAPIF(pred,op)  elements satisfying pred get op, the others stay: pred in eq, gt, lt (with k), even, odd;
                op in add (v+k), sub (v-k), mul (v*k), set (k)

Fixed order: ELEM, KEEP, POS, ORDER, EDGE, REDUCE, MAPIF, each in the order listed. Identifiers "FAMILY:kind" or
"MAPIF:pred:op". Seeded orders: random.Random("u3-order-" + str(seed)).shuffle(fixed list).
"""
import random

from cgrow.u3 import listdsl as LD

KS = tuple(range(10))
ELEM = ("add", "sub", "mul", "mod", "div", "max", "min")
KEEP = ("eq", "ne", "gt", "lt", "ge", "le", "mult", "even", "odd")
POS = ("take_first", "drop_first", "take_last", "drop_last", "every_kth", "skip_kth")
ORDER = ("reverse", "sort_asc", "sort_desc", "dedup", "rotate_left", "rotate_right")
EDGE = ("append", "prepend", "set_first", "set_last")
REDUCE = ("sum", "length", "max", "min", "first", "last", "count")
MPRED = ("eq", "gt", "lt", "even", "odd")
MOP = ("add", "sub", "mul", "set")
NOPARAM = {("KEEP", "even"), ("KEEP", "odd"), ("ORDER", "reverse"), ("ORDER", "sort_asc"), ("ORDER", "sort_desc"),
           ("ORDER", "dedup"), ("REDUCE", "sum"), ("REDUCE", "length"), ("REDUCE", "max"), ("REDUCE", "min"),
           ("REDUCE", "first"), ("REDUCE", "last")}


def _elem(op, v, k):
    if op in ("mod", "div") and k < 1:
        raise LD.Undefined()
    return {"add": v + k, "sub": v - k, "mul": v * k, "mod": v % k if k else 0, "div": v // k if k else 0,
            "max": max(v, k), "min": min(v, k)}[op]


def _pred(p, v, k):
    if p == "mult" and k < 1:
        raise LD.Undefined()
    return {"eq": v == k, "ne": v != k, "gt": v > k, "lt": v < k, "ge": v >= k, "le": v <= k,
            "mult": k >= 1 and v % k == 0, "even": v % 2 == 0, "odd": v % 2 == 1}[p]


class Structure:
    __slots__ = ("sid", "family", "args", "param")

    def __init__(self, family, args):
        self.family, self.args = family, tuple(args)
        self.sid = family + ":" + ":".join(args)
        self.param = not (family != "MAPIF" and (family, args[0]) in NOPARAM)

    def thetas(self):
        return [(k,) for k in KS] if self.param else [()]

    def _f(self, xs, k):
        f, a = self.family, self.args
        n = len(xs)
        if f == "ELEM":
            return [_elem(a[0], v, k) for v in xs]
        if f == "KEEP":
            return [v for v in xs if _pred(a[0], v, k)]
        if f == "POS":
            r = a[0]
            if r in ("every_kth", "skip_kth") and k < 1:
                raise LD.Undefined()
            keep = {"take_first": lambda i: i < k, "drop_first": lambda i: i >= k, "take_last": lambda i: i >= n - k,
                    "drop_last": lambda i: i < n - k, "every_kth": lambda i: i % k == 0,
                    "skip_kth": lambda i: i % k != 0}[r]
            return [v for i, v in enumerate(xs) if keep(i)]
        if f == "ORDER":
            r = a[0]
            if r == "reverse":
                return xs[::-1]
            if r == "sort_asc":
                return sorted(xs)
            if r == "sort_desc":
                return sorted(xs, reverse=True)
            if r == "dedup":
                return LD._dedup(xs)
            if not xs:
                return xs
            s = k % n
            return xs[s:] + xs[:s] if r == "rotate_left" else (xs[n - s:] + xs[:n - s] if s else xs)
        if f == "EDGE":
            r = a[0]
            if r == "append":
                return xs + (k,)
            if r == "prepend":
                return (k,) + xs
            if not xs:
                raise LD.Undefined()
            return ((k,) + xs[1:]) if r == "set_first" else (xs[:-1] + (k,))
        if f == "REDUCE":
            r = a[0]
            if r == "count":
                return (xs.count(k),)
            if r == "sum":
                return (sum(xs),)
            if r == "length":
                return (n,)
            if not xs:
                raise LD.Undefined()
            return ({"max": max(xs), "min": min(xs), "first": xs[0], "last": xs[-1]}[r],)
        if f == "MAPIF":
            p, op = a
            return [({"add": v + k, "sub": v - k, "mul": v * k, "set": k}[op] if _pred(p, v, k) else v) for v in xs]
        raise ValueError(f)

    def __call__(self, xs, *th):
        k = th[0] if th else 0
        try:
            return LD._lv(self._f(tuple(xs), k))
        except (LD.Undefined, ZeroDivisionError, IndexError, ValueError, TypeError):
            return None


def structures():
    out = [Structure("ELEM", (o,)) for o in ELEM] + [Structure("KEEP", (p,)) for p in KEEP]
    out += [Structure("POS", (r,)) for r in POS] + [Structure("ORDER", (r,)) for r in ORDER]
    out += [Structure("EDGE", (r,)) for r in EDGE] + [Structure("REDUCE", (r,)) for r in REDUCE]
    out += [Structure("MAPIF", (p, o)) for p in MPRED for o in MOP]
    return out


def seeded_order(seed):
    s = structures()
    random.Random(f"u3-order-{seed}").shuffle(s)
    return s


def by_sid():
    return {s.sid: s for s in structures()}


def consistent(st, pairs):
    return [th for th in st.thetas() if all(st(x, *th) == tuple(y) for x, y in pairs)]


#: evaluator-only: the schema structure (and parameter rule) equal to each deletable DSL operation
MEMBER = {"reverse": "ORDER:reverse", "sort_asc": "ORDER:sort_asc", "sort_desc": "ORDER:sort_desc",
          "dedup": "ORDER:dedup", "tail": "POS:drop_first", "init": "POS:drop_last", "filter_even": "KEEP:even",
          "filter_odd": "KEEP:odd", "take": "POS:take_first", "drop": "POS:drop_first", "append": "EDGE:append",
          "prepend": "EDGE:prepend", "remove": "KEEP:ne", "map_add": "ELEM:add", "map_mul": "ELEM:mul",
          "filter_gt": "KEEP:gt", "filter_lt": "KEEP:lt", "rotate_left": "ORDER:rotate_left"}
