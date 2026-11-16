"""LOCAL COPY of the frozen enumerator, with two listed changes: a memory failure is never an ordinary error, and a
budget counted in candidate combinations can be asked for (off unless asked for).
Author: Chimdi Walter Ndubuisi

The original is experiments/core_operations_20261113/search.py (frozen; sha256 in ORIGINAL_SHA256 below, checked
when this module is imported). The enumeration, its order, its merging, its caps, its hard stop and its handling of
the timer are the original's, line for line. What differs, and nothing else (search_bl.delta is the unified diff,
and a test rebuilds it):
  1. this text, the two imports (bl_frozen, ResourceStop) and the check of the original's hash;
  2. in search(), BEFORE the one broad handler of ordinary errors (around the evaluation of a candidate):
     `except MemoryError: raise ResourceStop(...) from None`. Python's MemoryError derives from Exception; in the
     original that handler takes it for a failed candidate and goes on;
  3. in search(), beside `except Hard`: the same translation for a MemoryError raised anywhere else inside the
     enumeration (leaves, the bank, the pools, the product of argument lists);
  4. eval_tree is not copied: this experiment evaluates a tree with build_bl.eval_tree_bl;
  5. a budget counted in candidate combinations. The enumerator already counts every combination of arguments it
     offers to an operation (`tick`). search() takes one more keyword parameter, max_ticks=None, and the dictionary
     it returns has one more key, ticks: that count. When max_ticks is a number and one more combination is offered
     after max_ticks of them, the search ends with stop 'budget_ticks'. The check stands before the count and
     before the evaluation, so exactly max_ticks combinations were counted and evaluated: where such a search
     stops does not depend on the load of the machine. The other limits stay as they are and can end the search
     first. (When a search ends by the processor-time budget or the bank cap, the last combination counted was not
     evaluated: the original checks those after counting.) With max_ticks=None the enumeration is the original's;
     `tick` is also bound before the `try`, so that the count exists on every path.
So search() never returns after a swallowed memory failure, and a memory failure inside it leaves it as
guards_bl.ResourceStop (the timer is disarmed and the handler restored by the original's `finally`).

The original's own text follows.

Typed bottom-up enumeration by expression size with observational equivalence, over several typed parameters.
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

import bl_frozen
import dslx
from dslx import tag
from guards_bl import ResourceStop

ORIGINAL = "experiments/core_operations_20261113/search.py"
ORIGINAL_SHA256 = "49fc72e1be57c67696b41d938b5cb900cfad557422b95a22c63a23811376a4f2"
if bl_frozen.HASHES[ORIGINAL] != ORIGINAL_SHA256:
    raise SystemExit("search_bl.py is a copy of another version of %s: refusing to run" % ORIGINAL)

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


def search(ops, leaves, Y, cpu_budget, max_size, max_fn=300, max_bank=250000, max_ticks=None):
    """ops: list of (name, fn, acc tuple of tag sets, makes_fn); leaves: list of (tree, vals); Y: target values.
    Only the examples in Y (and the same-length leaf vectors) are used: equivalence, pruning, order and stopping.
    Stops at the FIRST expression (smallest size, fixed tie order) equal to Y on all of them.

    Returns dict(found=(text, size, tree) or None, stop, level, bank, cpu_s).
    stop: 'found', 'size_exhausted', 'size_exhausted_function_cap' (the cap on function-valued entries was reached,
    so the enumeration was not exhaustive), 'budget_cpu', 'budget_bank' or 'hard_timeout'.
    This copy: max_ticks, the stop 'budget_ticks' and the key ticks of the result are described in the module's text.
    """
    n = len(Y)
    t0 = time.process_time()
    pools = {}                              # size -> {tagset: [(vals, tree, const)]}
    seen = set()
    st = dict(regen=None, nfn=0, level=0, stop=None, cap=False)
    tick = 0                                # this copy: bound here too, so that the count exists on every path
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
                        if max_ticks is not None and tick >= max_ticks:
                            st["stop"] = "budget_ticks"         # this copy: exactly max_ticks combinations were evaluated
                            break
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
                        except MemoryError:
                            raise ResourceStop("memory failure: the enumerator evaluated a candidate") from None
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
    except MemoryError:
        raise ResourceStop("memory failure inside the enumerator") from None
    finally:
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, old)
    return dict(found=st["regen"], stop=st["stop"], level=st["level"], bank=len(seen), function_cap_reached=st["cap"],
                cpu_s=time.process_time() - t0, ticks=tick)

