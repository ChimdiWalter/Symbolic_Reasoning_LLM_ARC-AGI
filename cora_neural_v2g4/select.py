"""ncv2-g4 selection: ncv2-g3's (cora_neural_v2g3.select, imported unchanged: weights, support, leave-one-out,
agreement, the diversity rule for attempt 2) with three features made readable for g4 programs, which ncv2-g3's
feature code sees only as tuples:
- description length: a g4 program counts as `(g4program VIEW BASE (list RULES))` with the identity base costing as
  much as ncv2's `keep (same_as_input)`, a part rule as `(rule SEL (part KIND COLOUR))` and a ray rule as
  `(rule SEL (ray DIRSET STOP COLOUR))`, so a whole-part recolour costs exactly what native `recolor` costs;
- rule count: the base program's rules plus the part and ray rules;
- family: ("g4", base families..., part kinds or "ray"), so attempt 2 can prefer another reading.
"""
from cora_neural_v2g3 import select as SEL
from cora_neural_v2g4 import program as PG


def description_length(prog):
    if not isinstance(prog, PG.G4Program):
        return SEL.description_length(prog)
    base = SEL.description_length(prog.base) if prog.base is not None else 2
    rules = sum(4 + SEL.description_length(r.sel) + (isinstance(r, PG.RayRule)) for r in prog.rules)
    return 2 + base + rules


def n_rules(prog):
    if not isinstance(prog, PG.G4Program):
        return SEL.n_rules(prog)
    return (SEL.n_rules(prog.base) if prog.base is not None else 0) + len(prog.rules)


def family(prog):
    if not isinstance(prog, PG.G4Program):
        return SEL.family(prog)
    base = SEL.family(prog.base)[1:] if prog.base is not None else ()
    return ("g4",) + base + tuple(sorted({r.kind if isinstance(r, PG.PartRule) else "ray" for r in prog.rules}))


def features(c, train):
    f = SEL.features(c, train)
    return dict(f, dl=description_length(c["prog"]), rules=n_rules(c["prog"]), family=family(c["prog"]))


def choose(cands, task, cfg=None, search_fn=None):
    """ncv2-g3's choose (same ranking, same attempt-2 rule) over g4-readable features. Returns (ranked, attempts)."""
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
