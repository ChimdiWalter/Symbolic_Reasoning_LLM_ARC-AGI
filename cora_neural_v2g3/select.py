"""ncv2-g3 evidence-aware selection of two attempts among demonstration-fitting programs. Test targets are never read.

Every candidate here fits every demonstration, so fit alone cannot choose. Features, with configurable weights:
- description length: AST nodes plus literals. Every entry of a table (colour map, feature map, pixel rule) counts,
  so a memorizing table is long;
- rule complexity: the number of rules and the deepest nesting;
- literal support: the share of colour-map and feature-map entries whose mapping (an object with that key
  recoloured to that colour) is observed in at least two demonstrations. An entry seen in one demonstration is
  memorized, not induced, and each such entry also costs `w_memo`;
- fold-local leave-one-out stability (optional, costly): the share of folds in which the search, run without one
  demonstration, derives the same program again;
- transformation agreement (optional, costly): the share of grid flips under which the search on the flipped task,
  flipped back, predicts the same output;
- find order: a weak tie-breaker (earlier is cheaper under the symbolic prior).

Attempt 2 covers a different reading: among the next `diversity_window` distinct predictions within
`diversity_margin` of attempt 1's score, it takes a different program family if there is one, then the prediction
that differs most from attempt 1 (so two readings that tie on every feature are both attempted, instead of two
variants that differ incidentally). Only predictions are compared, never a target. A training-consistent program is
never called certified: this module only ranks.
"""
import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from cora_neural_v2.rast import N
from cora_neural_v2g2 import grammar as G

TABLE_OPS = ("color_map", "feature_map")


@dataclass
class SelectConfig:
    w_dl: float = 1.0
    w_rules: float = 2.0
    w_support: float = 10.0
    w_memo: float = 6.0                  # per table entry whose mapping is seen in fewer than 2 demonstrations
    w_loo: float = 5.0
    w_agree: float = 3.0
    w_order: float = 0.5
    loo_budget: int = 0                  # 0 = off
    agree_budget: int = 0                # 0 = off
    diversity_window: int = 5
    diversity_margin: float = 3.0        # attempt 2 is chosen among candidates within this score of attempt 1


def description_length(x):
    if isinstance(x, N):
        return 1 + sum(description_length(a) for a in x.args)
    if isinstance(x, tuple):
        return sum(description_length(a) for a in x)
    return 1


def depth(x):
    if isinstance(x, N):
        return 1 + max([depth(a) for a in x.args] or [0])
    if isinstance(x, tuple):
        return max([depth(a) for a in x] or [0])
    return 0


def n_rules(prog):
    if isinstance(prog, N) and prog.op == "program":
        return len(prog.args[1])
    if isinstance(prog, N) and prog.op == "seq":
        return sum(n_rules(p) for p in prog.args[0])
    return 1


def family(prog):
    if G.is_class(prog):
        return ("class", prog.op)
    if prog.op == "program":
        return ("object",) + tuple(sorted(r.args[-1].op for r in prog.args[1]))
    return (prog.op,)


def table_entries(x, out=None):
    """Table entries as observable recolourings: ("color", from, to) and ("feature", name, value, to)."""
    out = [] if out is None else out
    if isinstance(x, N):
        if x.op == "color_map":
            out += [("color", int(a), int(b)) for a, b in x.args[0]]
        elif x.op == "feature_map":
            out += [("feature", x.args[0], int(v), int(c)) for v, c in x.args[1]]
        for a in x.args:
            table_entries(a, out)
    elif isinstance(x, tuple):
        for a in x:
            table_entries(a, out)
    return out


def literal_support(prog, train):
    """The share of table entries whose MAPPING is observed in >= 2 demonstrations: an input object with that key
    recoloured to that colour (1.0 when there is no table). A key that merely occurs, without the recolouring, does
    not count: that is what separates an induced entry from a memorized one."""
    return support_counts(prog, train)[0]


def support_counts(prog, train):
    """(share of supported table entries, number of unsupported entries)."""
    entries = table_entries(prog)
    if not entries:
        return 1.0, 0
    from geocat_arc.object_reasoning.expressions import _feature_value
    from geocat_arc.object_reasoning.features import register_builtin_features
    from geocat_arc.object_reasoning.segmentation import background_for, segment
    from geocat_arc.object_reasoning.types import GridContext, SegmentationVariant as SV
    from geocat_arc.perception.grid import Grid
    register_builtin_features()
    seen = []
    feats = {e[1] for e in entries if e[0] == "feature"}
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        k = set()
        if A.shape == B.shape:
            g = Grid(A.astype(np.int32))
            bg = background_for(g, SV("S1"))
            objs = segment(g, SV("S1"), bg)
            ctx = GridContext(grid=g, objects=objs, background=bg, pair_index=0, role="input", variant=SV("S1"))
            for o in objs:
                new = {int(B[x]) for x in o.cells}
                if len(new) != 1 or new == {int(o.color)} or new == {bg}:
                    continue
                c = next(iter(new))
                k.add(("color", int(o.color), c))
                for f in feats:
                    try:
                        k.add(("feature", f, int(_feature_value(f, o, ctx)), c))
                    except Exception:                               # noqa: BLE001 (undefined for this object)
                        pass
        seen.append(k)
    ok = sum(sum(e in k for k in seen) >= 2 for e in entries)
    return ok / len(entries), len(entries) - ok


def pred_key(preds):
    return b"".join(p.tobytes() + bytes(p.shape) for p in preds)


def features(c, train):
    share, unsupported = support_counts(c["prog"], train)
    return {"dl": description_length(c["prog"]), "rules": n_rules(c["prog"]), "depth": depth(c["prog"]),
            "support": share, "unsupported": unsupported, "family": family(c["prog"])}


def score(f, at, cfg, loo=None, agree=None):
    s = -cfg.w_dl * f["dl"] - cfg.w_rules * f["rules"] + cfg.w_support * f["support"] - cfg.w_memo * f["unsupported"] \
        - cfg.w_order * math.log1p(at)
    if loo is not None:
        s += cfg.w_loo * loo
    if agree is not None:
        s += cfg.w_agree * agree
    return s


FLIPS = {"flip_lr": (np.fliplr, np.fliplr), "flip_ud": (np.flipud, np.flipud)}


def loo_stability(task, progs, search_fn, budget):
    """{program: share of folds whose search (without that demonstration) fits the same program}."""
    train = task["train"]
    if len(train) < 3:
        return {p: None for p in progs}
    found = []
    for i in range(len(train)):
        red = {"train": train[:i] + train[i + 1:], "test_inputs": [train[i][0]]}
        found.append(set(search_fn(red, budget)))
    return {p: sum(p in f for f in found) / len(found) for p in progs}


def transform_agreement(task, cands, search_fn, budget):
    """{prediction key: share of flips whose search, flipped back, predicts it first}."""
    votes = Counter()
    for fwd, inv in FLIPS.values():
        t = {"train": [(fwd(np.asarray(a)).tolist(), fwd(np.asarray(b)).tolist()) for a, b in task["train"]],
             "test_inputs": [fwd(np.asarray(x)).tolist() for x in task["test_inputs"]]}
        fits = search_fn(t, budget, preds=True)
        if fits:
            votes[pred_key([inv(np.asarray(p)) for p in fits[0]])] += 1
    return {pred_key(c["preds"]): votes[pred_key(c["preds"])] / len(FLIPS) for c in cands}


def choose(cands, task, cfg=None, search_fn=None):
    """Rank fitting candidates and pick two attempts with distinct predictions. Returns (ranked, attempts)."""
    cfg = cfg or SelectConfig()
    if not cands:
        return [], []
    train = task["train"]
    best = {}                                                   # one representative (the best) per prediction
    feats = [features(c, train) for c in cands]
    loo = loo_stability(task, [c["prog"] for c in cands], search_fn, cfg.loo_budget) \
        if cfg.loo_budget and search_fn else {}
    agree = transform_agreement(task, cands, search_fn, cfg.agree_budget) if cfg.agree_budget and search_fn else {}
    ranked = []
    for c, f in zip(cands, feats):
        s = score(f, c["at"], cfg, loo.get(c["prog"]), agree.get(pred_key(c["preds"])))
        ranked.append(dict(c, features=f, score=s, loo=loo.get(c["prog"]), agree=agree.get(pred_key(c["preds"]))))
    ranked.sort(key=lambda r: (-r["score"], r["at"]))
    for r in ranked:
        best.setdefault(pred_key(r["preds"]), r)
    distinct = [r for r in ranked if best[pred_key(r["preds"])] is r]
    attempts = distinct[:1]
    if len(distinct) > 1:
        a1 = distinct[0]
        pool = [r for r in distinct[1:1 + cfg.diversity_window] if a1["score"] - r["score"] <= cfg.diversity_margin] \
            or distinct[1:2]
        attempts.append(max(pool, key=lambda r: (r["features"]["family"] != a1["features"]["family"],
                                                 spread(r["preds"], a1["preds"]), r["score"], -r["at"])))
    return ranked, attempts


def spread(preds, ref):
    """How different two predictions are: differing cells over all test inputs (a shape mismatch counts in full)."""
    out = 0
    for p, q in zip(preds, ref):
        p, q = np.asarray(p), np.asarray(q)
        out += int((p != q).sum()) if p.shape == q.shape else max(p.size, q.size)
    return out
