"""Evidence for directing search: which fragment of a non-fitting candidate the residual implicates.

`localize(task, result)` reads CORA's own diagnosis (`llm_writer.diagnose.diagnose`: levels tied to observables of
the execution, with the implicated rule where the level names one) and returns weights over the operator families
of the mutators and the hole roles of the relational sketches, plus the implicated rule indices. A grid-function
program gets the cell-level findings (shape, execution, composition, representation) and, for same-shape
demonstrations, a residual split: wrong colours on exactly the cells that had to change point to PARAMETER, cells
changed that had to stay point to SELECTOR (a condition too general), cells left unchanged that had to change point
to SELECTOR and COMPOSE. Localization is a repair HYPOTHESIS (expected internal states are unknown); it orders
search and never prunes a candidate. Demonstrations only.
"""
import re

from llm_writer.search.mutate_cora import FAMILIES

LEVEL_FAMILY = {
    "shape": {"OUTPUT": 0.7, "REPRESENTATION": 0.1, "COMPOSE": 0.2},
    "execution": {"PARAMETER": 0.5, "TRANSFORM": 0.3, "SUBTREE": 0.2},
    "selection_too_general": {"SELECTOR": 0.8, "COMPOSE": 0.2},
    "selection_too_specific": {"SELECTOR": 0.6, "COMPOSE": 0.4},
    "action": {"TRANSFORM": 0.8, "SUBTREE": 0.2},
    "parameters": {"PARAMETER": 0.8, "TRANSFORM": 0.2},
    "composition": {"COMPOSE": 0.7, "TRANSFORM": 0.3},
    "representation": {"REPRESENTATION": 0.5, "TRANSFORM": 0.3, "COMPOSE": 0.2},
}
RULE = re.compile(r"\b[Rr]ule (\d+)")


def uniform():
    return {f: 1.0 / len(FAMILIES) for f in FAMILIES}


def uniform_loc():
    return {"weights": uniform(), "rules": {}, "levels": [], "source": "uniform"}


def _normalize(w):
    s = sum(w.values())
    return {f: (w.get(f, 0.0) / s if s else 1.0 / len(FAMILIES)) for f in FAMILIES}


def localize(task, result, sep=""):
    """{"weights": {family: share}, "rules": {rule index (0-based): share}, "levels": [...], "source": ...}."""
    ex = result.ex
    if ex.status == "FITS":
        return {"weights": uniform(), "rules": {}, "levels": [], "source": "fit"}
    w, rules, levels = {}, {}, []
    try:
        from llm_writer import diagnose as DX
        d = DX.diagnose(task, result.prog, ex, None, sep)
        levels = list(d.get("levels") or [])
        for f in d.get("findings") or []:
            share = LEVEL_FAMILY.get(f["level"])
            if not share:
                continue
            cells = max(1, int(f.get("cells") or 1))
            for fam, x in share.items():
                w[fam] = w.get(fam, 0.0) + x * cells
            m = RULE.search(f.get("message") or "")
            if m:
                k = int(m.group(1)) - 1
                rules[k] = rules.get(k, 0.0) + cells
    except Exception:                                      # noqa: BLE001 (no diagnosis: residual split only)
        levels = ["diagnosis_failed"]
    for fam, x in _residual_split(ex).items():
        w[fam] = w.get(fam, 0.0) + x
    total = sum(rules.values())
    return {"weights": _normalize(w) if w else uniform(), "rules": {k: v / total for k, v in rules.items()} if total
            else {}, "levels": levels, "source": "diagnosis"}


def _residual_split(ex):
    """Cell-level split of the residual of same-shape demonstrations into family evidence (weights in cells)."""
    out = {}
    for p in getattr(ex, "per_demo", None) or []:
        if not p.get("shape_ok") or p.get("broken") is None:
            continue
        broken, remaining, fixed = p.get("broken") or 0, p.get("remaining") or 0, p.get("fixed") or 0
        changed = p.get("changed") or 0
        if broken:
            out["SELECTOR"] = out.get("SELECTOR", 0.0) + broken
        if remaining:
            # changed-but-wrong cells (right place, wrong value) versus cells left untouched
            touched = max(0, changed - fixed - broken)
            out["PARAMETER"] = out.get("PARAMETER", 0.0) + min(remaining, touched)
            untouched = max(0, remaining - touched)
            out["SELECTOR"] = out.get("SELECTOR", 0.0) + 0.5 * untouched
            out["COMPOSE"] = out.get("COMPOSE", 0.0) + 0.5 * untouched
    return out


def choose(rng, loc, floor=0.05):
    """A family drawn from the localization weights (each family keeps at least `floor` probability), and a focus
    rule drawn from the implicated rules (None if none or with probability 1/3)."""
    w = {f: max(floor, loc["weights"].get(f, 0.0)) for f in FAMILIES}
    s = sum(w.values())
    x, acc, fam = rng.random() * s, 0.0, FAMILIES[-1]
    for f in FAMILIES:
        acc += w[f]
        if x <= acc:
            fam = f
            break
    focus = None
    if loc["rules"] and rng.random() < 2 / 3:
        ks = sorted(loc["rules"])
        y, acc = rng.random(), 0.0
        for k in ks:
            acc += loc["rules"][k]
            if y <= acc:
                focus = k
                break
    return fam, focus
