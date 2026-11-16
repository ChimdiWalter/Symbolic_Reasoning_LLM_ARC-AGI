"""LOCAL COPY of the frozen generator, with one kind of change: a memory failure is never an ordinary error.
Author: Chimdi Walter Ndubuisi

The original is experiments/core_operations_20261113/gen.py (frozen; sha256 in ORIGINAL_SHA256 below, checked when
this module is imported). The draws, their order, the seeds, the rejections and the limits are the original's, line
for line. What differs, and nothing else (gen_bl.delta is the unified diff, and a test rebuilds it):
  1. this text, the two imports (bl_frozen, ResourceStop) and the check of the original's hash;
  2. in gen_examples(), BEFORE each of its three broad handlers of ordinary errors (a function tried on a value, the
     operation tried with a drawn function, the operation run on a draw):
     `except MemoryError: raise ResourceStop(...) from None`. In the original those handlers take a MemoryError for
     an input on which the operation raises, and discard the draw;
  3. in gen_examples(), beside `except Hard`: the same translation for a MemoryError raised anywhere else in the loop
     of draws.
So gen_examples() never returns after a swallowed memory failure.

The original's own text follows.

Seeded, typed generator of invented argument tuples for one library operation.
Author: Chimdi Walter Ndubuisi

Types come from arc-dsl's own annotations (dsl.py). Everything is invented: small grids (up to 12x12, 1 to 6
colours), and objects, indices, integers, pairs, booleans and containers derived from them. For function-typed
parameters a function is drawn from the fixed sets UNARY or BINARY (a function is kept only if the operation
accepts it on the tuple drawn). The operation's output is obtained by running the operation.
"""
import hashlib
import random
import signal

import bl_frozen
import dslx
from guards_bl import ResourceStop

ORIGINAL = "experiments/core_operations_20261113/gen.py"
ORIGINAL_SHA256 = "f0ee9e26f7253f1e4719f1408a708ce4f0bc044e6bf6e09fc72bb674275cac1c"
if bl_frozen.HASHES[ORIGINAL] != ORIGINAL_SHA256:
    raise SystemExit("gen_bl.py is a copy of another version of %s: refusing to run" % ORIGINAL)

UNARY = ("identity size first last increment decrement double halve invert even positive sign flip toindices color "
         "height width uppermost lowermost leftmost rightmost ulcorner center centerofmass numcolors palette normalize "
         "merge hmirror vmirror dmirror rot90 mostcolor leastcolor asindices shape portrait square vline hline dedupe "
         "totuple toivec tojvec crement initset box corners backdrop delta neighbors dneighbors minimum maximum "
         "leastcommon asobject partition").split()
BINARY = ("add subtract multiply astuple pair equality greater both either combine intersection difference contained "
          "manhattan adjacent hmatching vmatching position product insert remove other").split()
COLOUR_PARAMS = {"value", "replacee", "replacer", "fallback"}
DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (-1, 1), (1, -1)]
FN = object()                     # placeholder for a function-typed parameter, resolved after the others
MAX_COLOURS, MAX_SIDE = 6, 12


class Hard(BaseException):
    pass


def seed_for(name):
    return int.from_bytes(hashlib.sha256(("coreops:" + name).encode()).digest()[:8], "big")


def _alarm(*_):
    raise Hard()


class Ctx:
    def __init__(self, rng):
        self.rng = rng
        self.d = dslx.full_ns()
        self.grid = self.make_grid()
        self.ngrids = 0
        r = rng
        self.objs = sorted(self.d["objects"](self.grid, r.random() < .5, r.random() < .5, r.random() < .5),
                           key=lambda o: (len(o), sorted(o)))
        self.cells = sorted(self.d["asindices"](self.grid))

    def make_grid(self, h=None, w=None):
        r = self.rng
        h = h or r.randint(2, MAX_SIDE)
        w = w or r.randint(2, MAX_SIDE)
        cols = r.sample(range(10), r.randint(1, MAX_COLOURS))
        g = [[cols[0]] * w for _ in range(h)]
        for _ in range(r.randint(0, 4)):
            c = r.choice(cols)
            i0, j0 = r.randrange(h), r.randrange(w)
            for i in range(i0, min(h, i0 + r.randint(1, 4))):
                for j in range(j0, min(w, j0 + r.randint(1, 4))):
                    g[i][j] = c
        for _ in range(r.randint(0, max(1, h * w // 6))):
            g[r.randrange(h)][r.randrange(w)] = r.choice(cols)
        return tuple(tuple(row) for row in g)

    def second_grid(self):
        r = self.rng
        h, w = len(self.grid), len(self.grid[0])
        x = r.random()
        if x < .8:
            return self.make_grid(h, w)
        return self.make_grid(h if x < .9 else None, w if x >= .9 else None)

    def colour(self):
        r = self.rng
        pal = sorted({v for row in self.grid for v in row})
        return r.choice(pal) if r.random() < .7 else r.randint(0, 9)

    def cell(self, inside=.8):
        r = self.rng
        return r.choice(self.cells) if r.random() < inside else (r.randint(-2, 13), r.randint(-2, 13))

    def indices(self):
        r = self.rng
        x = r.random()
        if x < .6 or not self.objs:
            k = r.randint(1, min(8, len(self.cells)))
            return frozenset(r.sample(self.cells, k))
        if x < .85:
            return self.d["toindices"](r.choice(self.objs))
        return self.d["connect"](self.cell(), self.cell())

    def obj(self):
        r = self.rng
        if self.objs and r.random() < .8:
            return r.choice(self.objs)
        return self.d["toobject"](self.indices(), self.grid)

    def objects(self):
        r = self.rng
        if self.objs and r.random() < .8:
            return frozenset(self.objs)
        return frozenset(self.obj() for _ in range(r.randint(1, 3)))

    def ints(self, lo=0, hi=9):
        r = self.rng
        return tuple(r.randint(lo, hi) for _ in range(r.randint(1, 6)))

    def intset(self):
        return frozenset(self.ints())

    def draw(self, ann, pname, opname):
        r, d = self.rng, self.d
        if ann == "Grid":
            self.ngrids += 1
            return self.grid if self.ngrids == 1 else self.second_grid()
        if ann == "Integer":
            if pname in COLOUR_PARAMS or (opname == "switch" and pname in "ab"):
                return self.colour()
            if pname in ("n", "factor", "num") and opname not in ("even", "invert", "double", "halve"):
                return r.randint(1, 4)
            if pname in ("i", "j"):
                return r.randint(-20, 20)
            if pname == "start":
                return r.randint(0, 4)
            if pname == "stop":
                return r.randint(2, 10)
            if pname == "step":
                return r.choice([1, 2, 3, -1])
            return r.randint(-20, 30)
        if ann == "Boolean":
            return r.random() < .5
        if ann == "IntegerTuple":
            if pname in ("dims", "dimensions"):
                return (r.randint(1, 5), r.randint(1, 5))
            if pname in ("directions", "offset", "direction"):
                return r.choice(DIRS) if r.random() < .6 else (r.randint(-3, 3), r.randint(-3, 3))
            if pname in ("start", "loc", "location", "a", "b", "source", "destination"):
                return self.cell()
            return (r.randint(-3, 9), r.randint(-3, 9))
        if ann == "Numerical":
            return r.randint(-4, 6) if r.random() < .5 else (r.randint(-4, 6), r.randint(-4, 6))
        if ann == "Object":
            return self.obj()
        if ann == "Indices":
            return self.indices()
        if ann == "Objects":
            return self.objects()
        if ann == "Patch":
            return self.obj() if r.random() < .5 else self.indices()
        if ann == "Element":
            return self.obj() if r.random() < .5 else self.grid
        if ann == "Piece":
            x = r.random()
            return self.grid if x < .34 else (self.obj() if x < .67 else self.indices())
        if ann == "IntegerSet":
            return self.intset()
        if ann == "FrozenSet":
            return r.choice([self.intset, self.indices, self.obj, self.objects])()
        if ann == "Tuple":
            x = r.random()
            if x < .4:
                return self.ints()
            if x < .6:
                return self.grid
            if x < .8:
                return tuple(self.cell() for _ in range(r.randint(1, 4)))
            return tuple(self.ints() for _ in range(r.randint(1, 3)))
        if ann == "Container":
            return r.choice([self.ints, self.intset, self.indices, self.obj, self.objects, lambda: self.grid,
                             lambda: tuple(self.cell() for _ in range(r.randint(1, 4)))])()
        if ann == "ContainerContainer":
            x = r.random()
            if x < .4:
                return self.objects()
            if x < .6:
                return self.grid
            if x < .8:
                return frozenset(self.indices() for _ in range(r.randint(1, 3)))
            return tuple(self.intset() for _ in range(r.randint(1, 3)))
        if ann == "Any":
            return r.choice([lambda: r.randint(-3, 9), lambda: (r.randint(-3, 9), r.randint(-3, 9)),
                             lambda: r.random() < .5, lambda: self.grid, self.obj, self.indices, self.intset,
                             self.ints])()
        if ann in ("Callable", "?"):
            return FN
        raise ValueError("no generator for annotation %r" % ann)


def _hook(opname, args, names, rng):
    """For a few membership operations make the value come from the container about half of the time."""
    if opname in ("contained", "remove", "other"):
        ci, vi = (names.index("container"), names.index("value"))
        c = args[ci]
        if isinstance(c, (tuple, frozenset)) and c and rng.random() < .5:
            args[vi] = rng.choice(sorted(c, key=repr))
    return args


def gen_examples(name, n_total=36, max_draws=4000, hard_cpu_s=60, min_distinct=2):
    """Return dict(examples=[(args, out)], draws, raised, status, reason). status 'ok' or 'excluded'."""
    L = dslx.load()
    d = dslx.full_ns()
    f = d[name]
    sig = L["sigs"][name]
    if L["rets"][name] == "Callable":
        return dict(examples=[], draws=0, raised=0, rejected={}, status="excluded", reason="result is a function",
                    function_pool_excluded=[])
    rng = random.Random(seed_for(name))
    # one example set serves both conditions, so the function pools leave out the whole family of `name` and
    # every library operation that depends on a member (their library-text dependencies, transitively)
    gone = dslx.reverse_closure(L["fam_of"][name])
    unary = [u for u in UNARY if u not in gone]
    binary = [b for b in BINARY if b not in gone]
    is_binary = name in ("papply", "mpapply", "prapply")
    out, draws = [], 0
    rej = {"target_raised": 0, "no_function_works": 0, "output_unusable": 0, "input_too_large": 0, "duplicate": 0}
    seen_keys = set()
    old = signal.signal(signal.SIGVTALRM, _alarm)
    signal.setitimer(signal.ITIMER_VIRTUAL, hard_cpu_s)

    def result(status, reason):
        return dict(examples=out, draws=draws, raised=sum(rej.values()), rejected=dict(rej), status=status,
                    reason=reason, function_pool_excluded=sorted(gone))

    try:
        while len(out) < n_total and draws < max_draws:
            draws += 1
            ctx = Ctx(rng)
            args = [ctx.draw(a, p, name) for p, a in sig]
            names = [p for p, _ in sig]
            args = _hook(name, args, names, rng) if name in ("contained", "remove", "other") else args
            fi = [i for i, a in enumerate(args) if a is FN]
            res = None
            try:
                if name == "rapply":
                    v = args[names.index("value")]
                    cands = rng.sample(unary, len(unary))
                    fs = []
                    for c in cands:
                        try:
                            d[c](v)
                            fs.append(d[c])
                        except MemoryError:
                            raise ResourceStop("memory failure: the generator tried a function on a value") from None
                        except Exception:               # noqa: BLE001
                            pass
                        if len(fs) == 2:
                            break
                    if len(fs) < 2:
                        rej["no_function_works"] += 1
                        continue
                    args[names.index("functions")] = tuple(fs)
                    res = f(*args)
                elif fi:
                    pool = binary if is_binary else unary
                    cands = rng.sample(pool, len(pool))
                    for c in cands:
                        a2 = list(args)
                        for i in fi:
                            a2[i] = d[c]
                        try:
                            res = f(*a2)
                        except MemoryError:
                            raise ResourceStop("memory failure: the generator tried a drawn function") from None
                        except Exception:               # noqa: BLE001
                            continue
                        if dslx.valid_value(res, 2000):
                            args = a2
                            break
                        res = None
                    if res is None:
                        rej["no_function_works"] += 1
                        continue
                else:
                    res = f(*args)
            except MemoryError:
                raise ResourceStop("memory failure: the generator ran the operation on a draw") from None
            except Exception:                           # noqa: BLE001
                rej["target_raised"] += 1
                continue
            if not dslx.valid_value(res, 2000) or dslx.tag(res) == "F":
                rej["output_unusable"] += 1
                continue
            if any(dslx.vsize(a) > 2000 for a in args):
                rej["input_too_large"] += 1
                continue
            key = dslx.canon(tuple(args))
            if key in seen_keys:                        # duplicate argument tuple: dropped, never repeated
                rej["duplicate"] += 1
                continue
            seen_keys.add(key)
            out.append((tuple(args), res))
    except Hard:
        return result("excluded", "generator CPU limit")
    except MemoryError:
        raise ResourceStop("memory failure inside the generator") from None
    finally:
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, old)
    if len(out) < n_total:
        return result("excluded", "only %d of %d valid examples in %d draws" % (len(out), n_total, draws))
    # constant-output rule: reads the outputs of ALL examples drawn (fit and validation); an operation whose outputs
    # take fewer than `min_distinct` distinct values is excluded and counted
    if len({dslx.canon(o[1]) for o in out}) < min_distinct:
        return result("excluded", "output constant on all examples")
    return result("ok", None)
