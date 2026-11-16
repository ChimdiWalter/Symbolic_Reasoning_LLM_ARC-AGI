"""Consumers (a program that calls the target once and passes the result on), and the input streams.
Author: Chimdi Walter Ndubuisi

A consumer is the text `post(X(p1, p2, ...))` where `post` is a one-argument library operation outside the lesion
closure; with post = None the consumer is X itself (identity fill). Generator inputs come from the operations
study's generator; pooled inputs are put together as in posthoc_stress.py (values pooled by annotation over all
operations' examples; function-typed arguments only from the target's own examples). Everything is invented.
"""
import hashlib
import random
import signal

import frozen  # noqa: F401
import dslx
import gen
import search as S
import presets_vf1 as V

L = dslx.load()
_POOLS = {}


class GuardTimeout(Exception):
    pass


class guard:
    """CPU-time guard around a batch of evaluations of library code (trusted, in-process)."""

    def __init__(self, seconds=None):
        self.seconds = seconds or V.GUARD_CPU

    def __enter__(self):
        self.old = signal.signal(signal.SIGVTALRM, self._h)
        signal.setitimer(signal.ITIMER_VIRTUAL, self.seconds)
        return self

    @staticmethod
    def _h(*_):
        raise GuardTimeout()

    def __exit__(self, *a):
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, self.old)
        return False


def closure_of(X):
    return dslx.reverse_closure(L["fam_of"][X])


def same(a, b):
    """Exact typed equality of two values (canonical text)."""
    return dslx.canon(a) == dslx.canon(b)


def usable(v):
    return dslx.valid_value(v) and not callable(v)


def consumer_text(X, post):
    ps = ", ".join(p for p, _ in L["sigs"][X])
    inner = "%s(%s)" % (X, ps)
    return inner if post is None else "%s(%s)" % (post, inner)


def make_env(ns):
    env = dict(ns)
    env.update(L["consts"])
    return env


def run_text(text, env, params, args):
    """Evaluate a consumer text in `env` on one argument tuple (raises what the program raises)."""
    return eval(compile(text, "<consumer>", "eval"), env, dict(zip([p for p, _ in params], args)))  # noqa: S307


def apply_post(post_fn, v):
    return v if post_fn is None else post_fn(v)


def candidate_posts(X, setup_outputs, closure=None):
    """The seeded, ordered list of candidate `post` operations for target X.
    Candidates: one-argument library operations outside the lesion closure (never identity) that run on X's result for
    ALL setup examples (generator inputs 18-35, used for nothing else) and give at least 2 distinct final outputs. A shuffle seeded from X's name orders them;
    candidates whose output vectors equal an earlier one are dropped. Returns dict(cands=[names], n_raw=int).
    The episode takes the first three candidates for which the gate passes on the setup examples (no trivial repair
    passes); fewer than three: the target is excluded. There is no identity padding."""
    full = dslx.full_ns()
    gone = closure_of(X) if closure is None else closure
    xouts = list(setup_outputs)
    cands = []
    for o in L["lib_order"]:
        if o in gone or o == "identity" or len(L["sigs"][o]) != 1:
            continue
        f = full[o]
        outs = []
        try:
            with guard(10):
                for xo in xouts:
                    r = f(xo)
                    if not usable(r):
                        break
                    outs.append(r)
        except Exception:                                     # noqa: BLE001 (includes GuardTimeout)
            continue
        if len(outs) == len(xouts) and len({dslx.canon(r) for r in outs}) >= 2:
            cands.append((o, dslx.canon(tuple(outs))))
    rng = random.Random(int.from_bytes(hashlib.sha256(("vf1-consumer:" + X).encode()).digest()[:8], "big"))
    cands.sort()
    rng.shuffle(cands)
    names, sigs = [], set()
    for o, sg in cands:
        if sg not in sigs:
            names.append(o)
            sigs.add(sg)
    return dict(cands=names, n_raw=len(cands))


# ------------------------------------------------------------ pooled inputs
def pools():
    """(examples {op: [(args, out)]}, pools {annotation: [values]}) over all operations the generator serves."""
    if "p" in _POOLS:
        return _POOLS["p"]
    examples, pl, seen = {}, {}, {}
    for op in L["lib_order"]:
        g = gen.gen_examples(op)
        if g["status"] != "ok":
            continue
        examples[op] = g["examples"]
        for args, _ in g["examples"]:
            for (_, ann), v in zip(L["sigs"][op], args):
                if ann == "Callable" or callable(v):
                    continue
                key = dslx.canon(v)
                if key not in seen.setdefault(ann, set()):
                    seen[ann].add(key)
                    pl.setdefault(ann, []).append(v)
    _POOLS["p"] = (examples, pl)
    return _POOLS["p"]


def roster_all():
    """The operations the generator serves (the 145 of the operations study), in library order."""
    return list(pools()[0])


def pooled_args(X, own, pl, rng):
    sig = L["sigs"][X]
    args = []
    for j, (_, ann) in enumerate(sig):
        if ann == "Callable" or callable(own[0][0][j]) or ann not in pl:
            args.append(rng.choice(own)[0][j])
        else:
            args.append(rng.choice(pl[ann]))
    return tuple(args)


def gen_keys(examples):
    return {dslx.canon(tuple(a)) for a, _ in examples}


def pooled_sequence(X, own, avoid_keys, total, tag="seq", max_iter=60000):
    """Seeded sequence of UNIQUE pooled argument tuples, none equal to a generator tuple of the target (avoid_keys).
    X is not run here. Streams are slices of this one sequence, so they are disjoint from each other by construction.
    `own`: the target's own examples used for function-typed arguments (never the final ones)."""
    pl = pools()[1]
    rng = random.Random("%d:%s:%s" % (V.SEED, X, tag))
    seen = set(avoid_keys)
    out = []
    for _ in range(max_iter):
        args = pooled_args(X, own, pl, rng)
        k = dslx.canon(args)
        if k in seen:
            continue
        seen.add(k)
        out.append(args)
        if len(out) >= total:
            break
    return out


def stream_usable(X, argsets, post_fns=(), cpu=20):
    """[(args, x_out)]: the tuples on which X runs in the full library, its result is usable and every post(result) is
    usable too. Reads X's outputs (evaluator)."""
    full = dslx.full_ns()
    out = []
    try:
        with guard(cpu):
            for args in argsets:
                try:
                    y = full[X](*args)
                    if usable(y) and all(usable(apply_post(pf, y)) for pf in post_fns):
                        out.append((args, y))
                except Exception:                              # noqa: BLE001
                    continue
    except GuardTimeout:
        pass
    return out


def bank_grids():
    grids = []
    for op, ex in pools()[0].items():
        for args, _ in ex:
            for (_, ann), v in zip(L["sigs"][op], args):
                if ann == "Grid" and len(grids) < V.N_BANK_GRIDS and v not in grids:
                    grids.append(v)
        if len(grids) >= V.N_BANK_GRIDS:
            break
    return grids


def bank_baseline(ns):
    """Preservation bank, before admission: [(op, grid index, canonical value)] for the entries that RUN and give a
    value. An entry that raises is not preserved behaviour and is not counted."""
    grids = bank_grids()
    base = []
    for o in V.PRESERVATION_BANK_OPS:
        if o not in ns:
            continue
        for gi, g in enumerate(grids):
            try:
                v = ns[o](g)
                base.append((o, gi, dslx.canon(v)))
            except Exception:                                  # noqa: BLE001
                pass
    return base


def bank_check(ns, name, fn, baseline):
    """True when the baseline is not empty, the new name is free, and every baseline entry gives the same value after
    the admitted operation is added under its new name."""
    if not baseline or name in ns:
        return False
    ns2 = dict(ns)
    ns2[name] = fn
    grids = bank_grids()
    for o, gi, c in baseline:
        try:
            if dslx.canon(ns2[o](grids[gi])) != c:
                return False
        except Exception:                                      # noqa: BLE001
            return False
    return True
