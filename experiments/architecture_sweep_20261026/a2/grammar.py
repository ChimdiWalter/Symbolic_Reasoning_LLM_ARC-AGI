"""Grammars for the A2/A3 searches: the fixed base grammar estimated from the S_train verified corpus only, and the
same grammar extended by a library of typed productions (weights re-estimated on the corpus rewritten with it).
"""
import collections
import json
import os

from a2 import arcdsl as D
from a2 import bus as B
from a2.corpus import tree_from_json

HERE = os.path.dirname(os.path.abspath(__file__))


def load_corpus(split="S_train"):
    with open(os.path.join(HERE, "out", "corpus.json")) as f:
        doc = json.load(f)
    return {t: tree_from_json(v["tree"]) for t, v in doc["tasks"].items() if v["split"] == split and v["verified"]}


def usage(trees):
    """Counts of primitive heads, function-value leaves, constants and computed calls ('@', by arity)."""
    heads, fns, consts, calls, libs = (collections.Counter() for _ in range(5))

    def walk(t):
        h = t[0]
        if h.startswith("f:"):
            heads[h[2:]] += 1
        elif h.startswith("fn:"):
            fns[h[3:]] += 1
        elif h.startswith("c:"):
            consts[h[2:]] += 1
        elif h == "@":
            calls[len(t) - 2] += 1
        elif h.startswith("L:"):
            libs[h[2:]] += 1
        for c in t[1:]:
            walk(c)
    for t in trees:
        walk(t)
    return heads, fns, consts, calls, libs


class Grammar:
    """Base primitives + optional library; `prods` is the ordered production list for bus.search."""

    def __init__(self, corpus_trees, library=None, exclude_prims=(), extra_prims=()):
        dsl, consts, _, _ = D.load()
        self.dsl, self.consts = dsl, consts
        self.gfns = D.guarded(dsl)
        self.library = dict(library or {})          # name -> {"arity", "body", "argtags", "cost"}
        heads, fns, cs, calls, _ = usage(corpus_trees)
        names = sorted((set(heads) | set(extra_prims)) - set(exclude_prims))
        self.prim_names = names
        self.fn_names = sorted(set(fns) - set(exclude_prims), key=lambda f: (-fns[f], f))
        self.const_names = sorted(cs, key=lambda c: (-cs[c], c))
        self.call_arities = sorted(calls)
        self.ev = D.Evaluator(self.gfns, consts, {k: (v["arity"], v["body"]) for k, v in self.library.items()})
        # weights: production counts in the corpus rewritten with the library (rewritten by the caller if any)
        self.weights = {n: heads.get(n, 0) for n in names}

    def set_weights(self, weights):
        self.weights = dict(weights)

    def productions(self):
        out = B.base_prods(self.dsl, self.prim_names)
        for k in self.call_arities:
            out.append(B.Prod(f"@{k}", "@", lambda f, *a: f(*a), [frozenset({"F"})] + [D.ALL] * k))
        for name, v in self.library.items():
            out.append(B.lib_prod(name, v["arity"], v["body"], v["argtags"], self.ev, v["cost"]))
        w = self.weights
        out.sort(key=lambda p: (-w.get(p.name, 0.0), p.name))
        return out

    def leaves(self, inputs, extra=()):
        return B.task_leaves(inputs, self.consts, self.const_names, self.fn_names, self.dsl, extra)
