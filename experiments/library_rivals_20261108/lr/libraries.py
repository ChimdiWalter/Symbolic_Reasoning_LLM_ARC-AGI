"""The three same-size libraries of each benchmark, built before the freeze from source-half and training material
only (no held task, no held output, no ARC-AGI-2 file):

FAILURE-KEPT  the object-level operations that CORA's builder admitted from failures on the benchmark's source half
              (experiments/object_growth_20261105/runs/v2/<bench>/registry.json, frozen in study B; registry order).
              Its size N sets the size of the other two libraries of that benchmark.
COMPRESSION   N abstractions compressed from SOLVED programs, in the style of Stitch and DreamCoder's library
              step, restricted to abstractions over the input grid: candidate fragments are the Grid-valued
              subtrees of solved programs whose only free variable is the input; a fragment's corpus utility is
              uses x (cost - 4) - cost (A2 prior costs; 4 is the cost of the new production applied to the input,
              3 + 1; the last term is the cost of writing the fragment once; uses counts the corpus programs, as
              rewritten so far, that contain the fragment, so a subtree repeated inside one solver does not count
              as frequent); the fragment with the highest utility is taken, its occurrences are rewritten to the
              new production, and the step repeats until N are taken (ties: more uses, lower cost, program
              text).
              Corpus: the benchmark's solved source-half programs (study B's discovery records: base-budget and
              4x fits) and the 194 verified arc-dsl solvers of A2's training corpus (S_train). The source half
              alone has too few distinct solved programs for a same-size library (section 2 of PROTOCOL.md).
RANDOM-1/2    N entries drawn without replacement, with frozen seeds 1 and 2, from the admissible entries of the
              211-structure schema language: a structure, with k fixed for the 44 structures that take k (k in 2,
              3, 4), is admissible for a benchmark when it is defined and differs from its input on at least one
              source-half demonstration input of that benchmark.

Every library entry becomes one production (Grid) -> Grid of cost 3 and charge 1, as in the construction test and
the object-level builder (section 3 of PROTOCOL.md).

    python3 -I run.py build      writes libraries/LIBRARIES.json
"""
import collections
import json
import os
import random

from lr import env as E
from ngrow import data as DT
from cgrow import lang0 as L0, schema as SG
from a2 import arcdsl as D, bus as B

ADDED_COST = 3
REGISTRY = {b: os.path.join(E.OBJ, "runs", "v2", b, "registry.json") for b in DT.BENCHMARKS}
DISCOVER = [os.path.join(E.STUDY_B, "feasibility", f"discover_shard{i}.jsonl") for i in (0, 1)]
OUT = os.path.join(E.STUDY, "libraries", "LIBRARIES.json")
SEEDS = (1, 2)


def tup(t):
    return tuple(tup(c) for c in t) if isinstance(t, list) else t


def failure_kept(b):
    return list(E.load(REGISTRY[b])["registry"])


def source_solved(b):
    """One solved program per solved source-half task of benchmark b (base-budget fit, else 4x fit)."""
    out = []
    for p in DISCOVER:
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["bench"] == b and r.get("tree") not in (None, "None"):
                out.append((r["task"], tup(r["tree"])))
    return [t for _, t in sorted(out)]


def tree_cost(t, costs):
    if t == ("I",):
        return 1
    return costs.get(t[0], ADDED_COST if t[0].startswith("L:") else 1) + sum(tree_cost(c, costs) for c in t[1:])


def _fragments(t, returns, out):
    """Grid-valued subtrees with the input as their only free variable (no parameter, not the bare input)."""
    for s in B.subtrees(t):
        if s == ("I",) or not s[0].startswith("f:"):
            continue
        if returns.get(s[0][2:]) != "Grid":
            continue
        heads = [x[0] for x in B.subtrees(s)]
        if "I" not in heads or any(h.startswith("#") or h.startswith("lfn:") for h in heads):
            continue
        out.append(s)


def _rewrite(t, frag, leaf):
    if t == frag:
        return leaf
    if len(t) == 1:
        return t
    return (t[0],) + tuple(_rewrite(c, frag, leaf) for c in t[1:])


def _expand(t, defs):
    if t[0].startswith("L:") and t[0] in defs:
        return defs[t[0]]
    if len(t) == 1:
        return t
    return (t[0],) + tuple(_expand(c, defs) for c in t[1:])


def compression(b, n, costs, returns):
    corpus = list(L0.corpus("S_train").values()) + source_solved(b)
    taken, defs = [], {}
    while len(taken) < n:
        occ = collections.Counter()
        for t in corpus:
            fr = []
            _fragments(t, returns, fr)
            occ.update(set(fr))                                  # programs containing the fragment
        # an earlier abstraction inside a fragment counts at the new production's cost (rewritten corpus)
        cand = []
        for f, u in occ.items():
            c = tree_cost(f, costs)
            cand.append((u * (c - ADDED_COST - 1) - c, u, -c, D.show(_expand(f, defs)), f))
        if not cand:
            break
        cand.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))
        util, uses, negc, text, f = cand[0]
        name = f"L:cmp{len(taken)}"
        full = _expand(f, defs)
        defs[name] = full
        taken.append({"name": name, "program": D.show(full), "tree": full, "utility": util, "uses": uses,
                      "cost_in_rewritten_corpus": -negc, "cost_expanded": tree_cost(full, costs)})
        leaf = (name, ("I",))
        corpus = [_rewrite(t, f, leaf) for t in corpus]
    return taken, len(corpus)


def admissible_sigma(b):
    tasks = DT.tasks(b)
    inputs = [x for _, _, t in DT.half("source", (b,)) for x, _ in tasks[t]["train"]]
    out = []
    for st in SG.structures():
        for k in (SG.KS if st.param else (None,)):
            ok = False
            for x in inputs:
                try:
                    y = st(x, k) if k is not None else st(x)
                except Exception:                                    # noqa: BLE001
                    y = None
                if y is not None and D.valid(y) and D.tag(y) == "G" and y != x:
                    ok = True
                    break
            if ok:
                out.append([st.sid, k])
    return out


def build():
    from ngrow import plugin as PL
    g0b = PL.G0Builder()
    costs = dict(g0b.g.costs)
    returns = D.prim_returns()
    out = {"added_cost": ADDED_COST, "g0_sha256": g0b.sha, "seeds": list(SEEDS), "benchmarks": {}}
    for b in DT.BENCHMARKS:
        fk = failure_kept(b)
        n = len(fk)
        comp, ncorp = compression(b, n, costs, returns) if n else ([], 0)
        adm = admissible_sigma(b) if n else []
        rnd = {}
        for s in SEEDS:
            rng = random.Random(f"library-rivals-20261108|random|{s}|{b}")
            rnd[f"random_{s}"] = rng.sample(adm, n) if n <= len(adm) else None
        out["benchmarks"][b] = {"n": n, "failure_kept": fk, "compression": comp, "compression_corpus_programs": ncorp,
                                "source_solved_programs": len(source_solved(b)), "admissible_sigma_entries": len(adm),
                                **rnd}
    out["registry_sha256"] = {b: E.sha_file(REGISTRY[b]) for b in DT.BENCHMARKS}
    out["discover_sha256"] = [E.sha_file(p) for p in DISCOVER]
    E.dump(OUT, out)
    return out
