"""vsearch: the enumerator of experiments/core_operations_20261113/search.py with two additions.
Author: Chimdi Walter Ndubuisi

THIS IS A COPY OF THE FROZEN ENUMERATOR WITH EXACTLY TWO CHANGES; everything else (order, type filter, caps,
pruning, equivalence merging, the CPU timer) is the same text:
  1. an ACCEPTANCE HOOK: a candidate vector is accepted when `accept(vals)` is true, instead of being compared
     with a fixed target vector Y. With accept = plain_accept(Y) it is the frozen test (tested to give the same
     first expression as the frozen search on several targets).
  2. a COLLECT option: with collect = k > 0 the search keeps going after a hit and gathers up to k accepted
     candidates (the first one is the frozen search's first fit). Each hit records the CPU seconds and bank size at
     which it was found.
Standard technique (TRANSIT, 2013; Escher, 2013); nothing new is claimed. Expressions are trees as in search.py.
"""
import itertools
import signal
import time

import frozen  # noqa: F401  (hash check, sys.path)
import dslx
import search as S
from dslx import tag

CAP = S.CAP
Hard = S.Hard
_alarm = S._alarm
render = S.render
_compositions = S._compositions
_same = S._same


def plain_accept(Y):
    """The frozen test: exact typed equality with the target vector Y."""
    n = len(Y)
    cy = dslx.canon(Y)

    def accept(vals):
        v0 = vals[0]
        return (v0 == Y[0] and type(v0) is type(Y[0]) and _same(vals, Y, n) and dslx.canon(vals) == cy)
    return accept


def search(ops, leaves, accept, n, cpu_budget, max_size, max_fn=300, max_bank=250000, collect=0):
    """As search.search, but `accept(vals) -> bool` replaces Y, n is the number of examples in use, and collect=k
    (k > 0) keeps enumerating until k candidates were accepted.

    Returns dict(found=first hit (text, size, tree) or None, hits=[(text, size, tree, cpu_s, bank)], stop, level,
    bank, function_cap_reached, cpu_s). stop as in search.search, plus 'collected' (k hits gathered).
    """
    t0 = time.process_time()
    pools = {}
    seen = set()
    st = dict(regen=None, nfn=0, level=0, stop=None, cap=False)
    hits = []
    cap_hits = collect if collect > 0 else 1
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
        if "F" not in ts and len(hits) < cap_hits:
            ok = False
            try:
                ok = bool(accept(vals))                      # CHANGE 1: acceptance hook
            except Exception:                               # noqa: BLE001 (a post that raises rejects)
                ok = False
            if ok:
                h = (render(tree), sz, tree, time.process_time() - t0, len(seen))
                hits.append(h)
                if st["regen"] is None:
                    st["regen"] = (h[0], h[1], h[2])

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
        if len(hits) >= cap_hits:
            st["stop"] = "found" if collect <= 0 else "collected"
        for sz in range(2, max_size + 1):
            if st["stop"]:
                break
            cache.clear()
            for name, f, acc, mk in ops:
                k = len(acc)
                if sz - 1 < k:
                    continue
                if mk and sz + 2 > max_size:
                    continue
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
                        except Exception:               # noqa: BLE001
                            continue
                        ts = dslx.norm(tags)
                        if ts is None:
                            continue
                        add(outs, ts, ("L", name) + tuple(c[1] for c in combo), sz)
                        if len(hits) >= cap_hits:
                            st["stop"] = "found" if collect <= 0 else "collected"
                            break
                    if st["stop"]:
                        break
                if st["stop"]:
                    break
            if st["stop"]:
                break
            st["level"] = sz
        if st["regen"] and collect <= 0:
            st["stop"] = "found"
        elif not st["stop"]:
            st["stop"] = "size_exhausted_function_cap" if st["cap"] else "size_exhausted"
    except Hard:
        st["stop"] = "hard_timeout"
    finally:
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, old)
    return dict(found=st["regen"], hits=[tuple(h) for h in hits], stop=st["stop"], level=st["level"], bank=len(seen),
                function_cap_reached=st["cap"], cpu_s=time.process_time() - t0)
