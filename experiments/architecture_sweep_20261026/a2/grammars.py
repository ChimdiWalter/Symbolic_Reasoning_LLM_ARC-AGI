"""Grammars of the A2 arms. One procedure for every arm (DreamCoder-style re-estimation):

- productions = every arc-dsl primitive used in the S_train corpus, plus the arm's library definitions;
- function leaves / constants = those used as values in the S_train corpus (plus library functions as values);
- integer prior cost per head from its document frequency in the S_train corpus REWRITTEN with the arm's library
  (cost = clip(1 + round(log2(top / df) / 1.5), 1, 4) within productions, function leaves and constants);
  heads with df 0 cost 4. A matched control library takes the costs of the library it is matched to.
"""
import collections
import math

from a2 import bus as B
from a2 import library as LB


def _cost(df, top):
    if df <= 0:
        return 4
    return max(1, min(4, 1 + round(math.log2(top / df) / 1.5)))


def base_heads(trees):
    prims, fnl, consts = collections.Counter(), collections.Counter(), collections.Counter()
    for t in trees:
        hs = {s[0] for s in B.subtrees(t)}
        for h in hs:
            if h.startswith("f:"):
                prims[h] += 1
            elif h.startswith("fn:"):
                fnl[h] += 1
            elif h.startswith("c:"):
                consts[h] += 1
    return prims, fnl, consts


def build(trees, library=(), cost_override=None, extra_prims=(), drop_prims=(), rep_leaves=()):
    """trees: S_train verified trees; library: [(name, arity, flat body, param tags)]."""
    prims, fnl, consts = base_heads(trees)
    if library:
        idx, memo = LB.by_head(library), {}
        rw = [LB.rewrite(t, idx, memo)[0] for t in trees]
    else:
        rw = list(trees)
    df = collections.Counter()
    for t in rw:
        df.update({s[0] for s in B.subtrees(t)})
    prod_heads = [h for h in prims if h[2:] not in drop_prims] + ["f:" + p for p in extra_prims] + \
        ["L:" + d[0] for d in library]
    fn_heads = list(fnl)
    const_heads = list(consts)
    costs = {"I": 1}
    for grp in (prod_heads, fn_heads, const_heads):
        top = max([df[h] for h in grp] + [1])
        for h in grp:
            costs[h] = _cost(df[h], top)
    for d in library:
        costs["lfn:" + d[0]] = 4
    for r in rep_leaves:
        costs["R:" + r] = 1
    if cost_override:
        costs.update(cost_override)
    order = sorted(prod_heads, key=lambda h: (costs[h], -df[h], h))
    g = B.Grammar([h[2:] for h in order if h.startswith("f:")], sorted(fn_heads, key=lambda h: (-df[h], h)),
                  [h[2:] for h in sorted(const_heads, key=lambda h: (-df[h], h))], library=library, order=order,
                  costs=costs)
    g.df = dict(df)
    return g
