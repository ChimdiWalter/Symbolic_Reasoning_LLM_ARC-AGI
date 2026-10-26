"""Version 5 selection: version 4's (cora_neural_v2g4.select, imported unchanged) with the same three features made
readable for version 5 programs: description length (a stamp rule counts as `(rule SRC ANCHORS (stamp SCOPE ALIGN
RECOLOUR))`, the other new rules as `(rule SEL (op PARAMS...))`), rule count (base rules plus every rule), and family
("g5", base families..., rule kinds). Weights, support, leave-one-out and the attempt-2 rule are version 3's."""
from cora_neural_v2g3 import select as SEL
from cora_neural_v2g4 import program as PG
from cora_neural_v2g4 import select as SEL4
from cora_neural_v2g5 import program as P5

KIND = {"PartRule": lambda r: r.kind, "RayRule": lambda r: "ray", "Ray2Rule": lambda r: "ray2",
        "SegmentRule": lambda r: "segment", "FillRule": lambda r: "fill_" + r.kind, "StampRule": lambda r: "stamp"}


def _rule_dl(r):
    if isinstance(r, P5.StampRule):
        return 6 + SEL.description_length(r.src) + SEL.description_length(r.anchors)
    extra = {PG.PartRule: 4, PG.RayRule: 5, P5.Ray2Rule: 6, P5.SegmentRule: 5, P5.FillRule: 5}[type(r)]
    return extra + SEL.description_length(r.sel)


def description_length(prog):
    if not isinstance(prog, P5.G5Program):
        return SEL4.description_length(prog)
    base = SEL.description_length(prog.base) if prog.base is not None else 2
    return 2 + base + sum(_rule_dl(r) for r in prog.rules)


def n_rules(prog):
    if not isinstance(prog, P5.G5Program):
        return SEL4.n_rules(prog)
    return (SEL.n_rules(prog.base) if prog.base is not None else 0) + len(prog.rules)


def family(prog):
    if not isinstance(prog, P5.G5Program):
        return SEL4.family(prog)
    base = SEL.family(prog.base)[1:] if prog.base is not None else ()
    return ("g5",) + base + tuple(sorted({KIND[type(r).__name__](r) for r in prog.rules}))


def features(c, train):
    f = SEL.features(c, train)
    return dict(f, dl=description_length(c["prog"]), rules=n_rules(c["prog"]), family=family(c["prog"]))


def choose(cands, task, cfg=None, search_fn=None):
    """Version 4's choose (version 3's ranking and attempt-2 rule) over version 5-readable features."""
    cfg = cfg or SEL.SelectConfig()
    if not cands:
        return [], []
    train = task["train"]
    feats = [features(c, train) for c in cands]
    loo = SEL.loo_stability(task, [c["prog"] for c in cands], search_fn, cfg.loo_budget) \
        if cfg.loo_budget and search_fn else {}
    agree = SEL.transform_agreement(task, cands, search_fn, cfg.agree_budget) if cfg.agree_budget and search_fn else {}
    ranked = []
    for c, f in zip(cands, feats):
        k = SEL.pred_key(c["preds"])
        s = SEL.score(f, c["at"], cfg, loo.get(c["prog"]), agree.get(k))
        ranked.append(dict(c, features=f, score=s, loo=loo.get(c["prog"]), agree=agree.get(k)))
    ranked.sort(key=lambda r: (-r["score"], r["at"]))
    best = {}
    for r in ranked:
        best.setdefault(SEL.pred_key(r["preds"]), r)
    distinct = [r for r in ranked if best[SEL.pred_key(r["preds"])] is r]
    attempts = distinct[:1]
    if len(distinct) > 1:
        a1 = distinct[0]
        pool = [r for r in distinct[1:1 + cfg.diversity_window] if a1["score"] - r["score"] <= cfg.diversity_margin] \
            or distinct[1:2]
        attempts.append(max(pool, key=lambda r: (r["features"]["family"] != a1["features"]["family"],
                                                 SEL.spread(r["preds"], a1["preds"]), r["score"], -r["at"])))
    return ranked, attempts
