"""Item-2 v1.4 mechanistic frontier localization.

Shared-input counterfactual twins, raw trajectory capture from the existing
observer, and the stagewise nonlearned audit of protocol v1.4.

Nothing here trains, proposes, compiles, installs or scores. The deployed
reasoner, the observer, the admission law, the fitter and the baseline are
the v1.3 ones, called unchanged. The only new observation is that the
observer's ordered candidate list, which v1.3 discarded after building the
TFG, is now kept, together with the per-demonstration evaluation of every
distinct executed near miss that the TFG capped at twelve.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from fractions import Fraction
from itertools import product

from cora_arc2026 import v13_gen as G

CD, V2, CV, ET = G.CD, G.V2, G.CV, G.ET

#: seeds, disjoint from every earlier corpus (v1.3 stored seeds end below
#: 1.1e7, v1.3's scheme below 1.3e7)
SEED_BASE = 100_000_000
SMOKE_BASE = 200_000_000

R_TWIN_INPUTS = "TWIN_INPUTS_DIFFER"
R_TWIN_SAME = "TWIN_OUTPUTS_IDENTICAL"
R_TWIN_EXEC = "TWIN_DEMONSTRATIONS_UNDEFINED"

MISMATCH_CAP = 64
NULL = Fraction(1, 2)
ALPHA = 0.01
TIE_EPS = 1e-12

#: pipeline order; S0 is a demonstration baseline and not a reasoning stage
CORA_STAGES = ("S2", "S3", "S4", "S5", "S6", "S7a", "S7")
SEARCH_STAGES = ("S2", "S3", "S4", "S5")
ALL_STAGES = ("S0",) + CORA_STAGES

#: the only episode keys a stage descriptor may read
VIEW_KEYS = ("demo_features", "trajectory", "mismatch", "full_engine_tfg",
             "descriptor")


# --------------------------------------------------------------------------
# canonical structure
# --------------------------------------------------------------------------

def skeleton(value):
    """Structure with every numeric literal abstracted to '#'.

    One generic rule for every stage: operator names, feature names, modes
    and nesting are kept, constants (colours, counts, sizes) are not, so a
    descriptor compares what the reasoner did rather than the particular
    grid it did it on.
    """
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return "#"
    if isinstance(value, dict):
        return {str(k): skeleton(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [skeleton(v) for v in value]
    return str(value)


def key(value) -> str:
    return json.dumps(skeleton(value), sort_keys=True)


def opaque_label(*parts) -> str:
    return "v14-" + hashlib.sha256(
        "|".join(str(p) for p in parts).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# capture, called at generation time only
# --------------------------------------------------------------------------

def serialize_trajectory(observer) -> list:
    """The observer's ordered candidate list, [ast_json, outcome] each."""
    return [[G.ET.X._canonical_ast(ast), outcome]
            for ast, outcome in observer.candidates]


def mismatch_class(rendered, target) -> str:
    import numpy as np
    if rendered is None:
        return "undefined"
    rendered, target = np.asarray(rendered), np.asarray(target)
    if rendered.shape != target.shape:
        return "shape_mismatch"
    if set(np.unique(rendered).tolist()) - set(np.unique(target).tolist()):
        return "palette_extra"
    if np.count_nonzero(rendered != target):
        return "cells_wrong"
    return "exact_on_demo"


def evaluate_near_misses(observer, pairs, cap=MISMATCH_CAP) -> list:
    """Every distinct executed-not-exact program, in order of first
    emission, rendered on EVERY demonstration by the engine's own executor.
    Diagnostic only; nothing is generated, ranked or accepted."""
    out, seen = [], set()
    for ast, outcome in observer.candidates:
        if outcome != "executed_not_exact" or len(out) >= cap:
            continue
        text = G.ET.X._canonical_ast(ast)
        if text in seen:
            continue
        seen.add(text)
        classes = []
        for grid_in, grid_out in pairs:
            try:
                rendered = ET.render_object_program(ast, grid_in)
            except Exception:                                  # noqa: BLE001
                rendered = None
            classes.append(mismatch_class(rendered, grid_out))
        out.append({"ast": text, "per_demo": classes})
    return out


def demonstrations_for(schema, seed):
    """R2/R3 rendering exactly as evaluate_target_v2 performs it, used only
    to check twin integrity before the expensive stages."""
    grid_seeds = [seed * 97 + i for i in range(14)]
    concrete = CD.instantiate_tables(
        schema, [CD.generate_grid(s) for s in grid_seeds[:6]])
    if concrete is None:
        return None
    pairs, _diag = CD.render_demonstrations(concrete, grid_seeds, min_demos=3)
    return pairs if len(pairs) >= 3 else None


def _same_grids(a, b) -> bool:
    import numpy as np
    return len(a) == len(b) and all(
        np.asarray(x).shape == np.asarray(y).shape
        and bool((np.asarray(x) == np.asarray(y)).all()) for x, y in zip(a, b))


def make_twin_replicate(anchor, contrast, seed, budgets, gate, label_parts):
    """One shared-input replicate: both targets see the SAME input grids.

    Returns (code, {0: episode, 1: episode} or None). Admission is the v1.3
    law applied to each target unchanged, plus twin integrity: identical
    demonstration inputs and at least one differing demonstration output.
    """
    pa, pb = demonstrations_for(anchor, seed), demonstrations_for(contrast, seed)
    if pa is None or pb is None:
        return R_TWIN_EXEC, None
    if not _same_grids([x for x, _ in pa], [x for x, _ in pb]):
        return R_TWIN_INPUTS, None
    if _same_grids([y for _, y in pa], [y for _, y in pb]):
        return R_TWIN_SAME, None

    episodes = {}
    for t, schema in ((0, anchor), (1, contrast)):
        try:
            outcome, episode, _ = V2.evaluate_target_v2(
                schema, seed=seed, split="train", regime="train_pool",
                allowed_families=[CV.family(schema)], seen_digests=set(),
                seen_train_digests=set(), v1_exclusion=set(),
                budgets=budgets, row_index=0)
        except Exception as exc:                               # noqa: BLE001
            return f"{G.R_OTHER}:{type(exc).__name__}", None
        if outcome != "ADMITTED":
            return G.CODE_MAP.get(outcome, G.R_OTHER), None
        episodes[t] = episode
    ia = [d["input"] for d in episodes[0]["demonstrations"]]
    ib = [d["input"] for d in episodes[1]["demonstrations"]]
    if ia != ib:                       # evaluate_target_v2 re-rendered them
        return R_TWIN_INPUTS, None

    out = {}
    for t in (0, 1):
        ep = episodes[t]
        pairs = [(d["input"], d["output"]) for d in ep["demonstrations"]]
        got = ET.extract(opaque_label(*label_parts, t), pairs,
                         budget_s=budgets["full_engine_observation_s"])
        if got["solved"]:
            return G.R_NO_TFG, None
        features = G.features_v12(got["tfg"])
        if not G.informative(features, gate):
            return G.R_NO_TFG, None
        import numpy as np
        np_pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
        tfg_json = got["tfg"].to_json()
        out[t] = {
            "target_digest": ep["target_digest"],
            "target_tokens": ep["target_tokens"],
            "structural_family": ep.get("structural_family"),
            "schema_mdl": ep.get("schema_mdl"),
            "seed": seed,
            "demonstrations": ep["demonstrations"],
            "demo_features": {k: features[k] for k in G.DEMO_FEATURES},
            "features": features,
            "full_engine_tfg": tfg_json,
            "descriptor": G.raw_descriptor(tfg_json),
            "trajectory": serialize_trajectory(got["observer"]),
            "mismatch": evaluate_near_misses(got["observer"], np_pairs),
            "census": got["census"],
            "observation_s": round(got["seconds"], 3),
            "base_search_evidence": ep.get("base_search_evidence"),
            "fitter_identity": ep.get("fitter_identity"),
        }
    return "ADMITTED", out


# --------------------------------------------------------------------------
# stage descriptors: functions of model_view(ep) only
# --------------------------------------------------------------------------

def model_view(ep) -> dict:
    return {k: ep[k] for k in VIEW_KEYS}


def _events(view):
    return [(json.loads(a), o) for a, o in view["trajectory"]]


def _payload(ast):
    """The dict an engine AST carries: (op, (detail,))."""
    if isinstance(ast, list) and len(ast) == 2 and isinstance(ast[1], list) \
            and ast[1] and isinstance(ast[1][0], dict):
        return ast[1][0]
    return {}


def stage_multiset(view, stage) -> Counter:
    events = _events(view)
    c = Counter()
    if stage == "S2":                       # candidate formation
        for ast, o in events:
            if o == "typed":
                c[key(ast)] += 1
    elif stage == "S3":                     # selector induction, from order
        for i, (ast, o) in enumerate(events):
            if o != "typed":
                continue
            nxt = events[i + 1] if i + 1 < len(events) else None
            if nxt and nxt[1] in ("slot_fit_failed", "slot_fit_ok"):
                sel = _payload(nxt[0]).get("selector")
                c[json.dumps(["selector_ok", key(ast), key(sel)])] += 1
            else:
                c[json.dumps(["no_fit_event", key(ast)])] += 1
    elif stage == "S4":                     # parameter fitting
        for ast, o in events:
            if o == "slot_fit_failed":
                c[json.dumps([o, ast[0] if isinstance(ast, list) else str(ast)])] += 1
            elif o == "slot_fit_ok":
                c[json.dumps([o, key(_payload(ast).get("action"))])] += 1
    elif stage == "S5":                     # fitted executable candidates
        for ast, o in events:
            if o in ("executed_not_exact", "exact"):
                c[json.dumps([o, key(ast)])] += 1
    elif stage == "S6":                     # execution and mismatch, associated
        for row in view["mismatch"]:
            k = key(json.loads(row["ast"]))
            for cls in row["per_demo"]:
                c[json.dumps([k, cls])] += 1
    elif stage == "S7a":                    # stored TFG graph, before aggregation
        nodes = view["full_engine_tfg"]["nodes"]
        term_key = {}
        for n in nodes:
            if n["kind"] == "frontier_term":
                term_key[n["id"]] = key(json.loads(n["attrs"]["ast"]))
                c[json.dumps([n["attrs"]["outcome"], term_key[n["id"]]])] += 1
        for s, rel, d in view["full_engine_tfg"]["edges"]:
            if rel == "observed_on" and d in term_key:
                sig = next(n for n in nodes if n["id"] == s)["attrs"]
                c[json.dumps([term_key[d], vsig_class(sig)])] += 1
    else:
        raise ValueError(stage)
    return c


def vsig_class(attrs) -> str:
    if not attrs.get("defined"):
        return "undefined"
    if not attrs.get("shape_matches"):
        return "shape_mismatch"
    if attrs.get("palette_extra", 0):
        return "palette_extra"
    if attrs.get("cells_wrong", 0):
        return "cells_wrong"
    return "exact_on_demo"


def ruzicka(a: Counter, b: Counter) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    hi = sum(max(a[k], b[k]) for k in keys)
    return 1.0 - sum(min(a[k], b[k]) for k in keys) / hi


def standardized(values: dict, order, mean, std) -> list:
    return [(float(values.get(k, 0) or 0) - mean[i]) / std[i]
            for i, k in enumerate(order)]


def stage_points(eps, stage, cal):
    """Per-episode descriptor for one stage, and the distance on it."""
    views = [model_view(e) for e in eps]
    if stage == "S0":
        pts = [standardized(v["demo_features"], cal["demo_features"],
                            cal["demo_mean"], cal["demo_std"]) for v in views]
        return pts, euclid
    if stage == "S7":
        pts = [standardized(v["descriptor"], cal["descriptor_order"],
                            cal["descriptor_mean"], cal["descriptor_std"])
               for v in views]
        return pts, euclid
    return [stage_multiset(v, stage) for v in views], ruzicka


def euclid(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# --------------------------------------------------------------------------
# the within-group statistics
# --------------------------------------------------------------------------

def _index(eps):
    return [(e["target_index"], e["replicate_index"]) for e in eps]


def nn_credits(dist, idx, labels):
    """Twin-excluded nearest neighbour.

    For query (t, r) the companions are the six episodes of the OTHER
    replicates; the query's own twin shares its input and is excluded. Ties
    at the minimum share credit. Returns (fractional credits, strict hits).
    """
    credits, strict = [], []
    for i, (_, r) in enumerate(idx):
        comp = [j for j, (_, rj) in enumerate(idx) if rj != r]
        dmin = min(dist[i][j] for j in comp)
        near = [j for j in comp if dist[i][j] <= dmin + TIE_EPS]
        same = sum(1 for j in near if labels[j] == labels[i])
        credits.append(Fraction(same, len(near)))
        strict.append(int(same == len(near)))
    return credits, strict


def group_stats(eps, stage, cal):
    pts, fn = stage_points(eps, stage, cal)
    n = len(eps)
    dist = [[fn(pts[i], pts[j]) for j in range(n)] for i in range(n)]
    idx = _index(eps)
    labels = [t for t, _ in idx]
    credits, strict = nn_credits(dist, idx, labels)
    reps = sorted({r for _, r in idx})
    null_values = []
    for sigma in product((0, 1), repeat=len(reps)):
        flip = dict(zip(reps, sigma))
        relabel = [t ^ flip[r] for t, r in idx]
        c, _ = nn_credits(dist, idx, relabel)
        null_values.append(sum(c))
    within, between, twin = [], [], []
    for i in range(n):
        for j in range(i + 1, n):
            (ti, ri), (tj, rj) = idx[i], idx[j]
            if ri == rj:
                twin.append(dist[i][j])
            elif ti == tj:
                within.append(dist[i][j])
            else:
                between.append(dist[i][j])
    s = (sum(between) / len(between) - sum(within) / len(within)) \
        if within and between else 0.0
    return {"credits": credits, "strict": strict, "null": null_values,
            "separation": s,
            "twin_mean": sum(twin) / len(twin) if twin else None,
            "twin_identical": sum(1 for d in twin if d <= TIE_EPS),
            "twin_pairs": len(twin)}


def randomization_p(observed: Fraction, per_group_null) -> float:
    """Exact P(T >= observed) under independent uniform within-twin label
    swaps in every group, by convolution. Credits have denominators dividing
    6, so scaling by 60 makes every value an integer."""
    scale = 60
    dist = {0: Fraction(1)}
    for values in per_group_null:
        w = Fraction(1, len(values))
        nxt: dict = {}
        for total, pr in dist.items():
            for v in values:
                k = total + int(v * scale)
                nxt[k] = nxt.get(k, 0) + pr * w
        dist = nxt
    target = int(observed * scale)
    return float(sum(pr for k, pr in dist.items() if k >= target))


def binom_sf(k, n, p) -> float:
    """Exact P(X >= k), X ~ Binomial(n, p)."""
    p = Fraction(p)
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                     for i in range(k, n + 1)))


def clopper_pearson(k, n, level=0.95):
    from scipy.stats import beta
    a = (1 - level) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return lo, hi


def stage_result(groups, stage, cal) -> dict:
    per = [group_stats(g["episodes"], stage, cal) for g in groups]
    strict = sum(sum(p["strict"]) for p in per)
    total = sum(len(p["strict"]) for p in per)
    credit = sum(sum(p["credits"]) for p in per)
    p_binom = binom_sf(strict, total, NULL) if total else 1.0
    p_rand = randomization_p(credit, [p["null"] for p in per]) if total else 1.0
    seps = sorted(p["separation"] for p in per)
    rate = strict / total if total else 0.0
    twin_pairs = sum(p["twin_pairs"] for p in per)
    return {
        "stage": stage, "strict_hits": strict, "total": total,
        "strict_rate": round(rate, 5),
        "credit": round(float(credit), 5),
        "credit_rate": round(float(credit) / total, 5) if total else None,
        "p_binomial": p_binom, "p_randomization": p_rand,
        "ci95": [round(x, 5) for x in clopper_pearson(strict, total)] if total else None,
        "target_identifying": bool(rate > float(NULL) and p_binom < ALPHA
                                   and p_rand < ALPHA),
        "separation_mean": round(sum(seps) / len(seps), 5) if seps else None,
        "separation_median": round(_median(seps), 5) if seps else None,
        "fraction_s_positive": round(sum(1 for s in seps if s > 0) / len(seps), 5)
        if seps else None,
        "separation_min": round(seps[0], 5) if seps else None,
        "separation_max": round(seps[-1], 5) if seps else None,
        "per_group_separation": [round(p["separation"], 5) for p in per],
        "twin_identical_fraction": round(
            sum(p["twin_identical"] for p in per) / twin_pairs, 5) if twin_pairs else None,
        "twin_mean_distance": round(sum(p["twin_mean"] for p in per
                                        if p["twin_mean"] is not None) / len(per), 5)
        if per else None,
    }


def _median(xs):
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def holm(pvalues: dict) -> dict:
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for rank, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - rank) * p))
        out[name] = running
    return out


# --------------------------------------------------------------------------
# the frozen classification ladder
# --------------------------------------------------------------------------

def classify(results: dict, achieved_instances: int, required_instances: int,
             floor_instances: int) -> dict:
    q = [s for s in CORA_STAGES if results[s]["target_identifying"]]
    confirmatory = achieved_instances >= required_instances
    out = {"qualifying_stages": q, "confirmatory": confirmatory,
           "earliest_qualifying": q[0] if q else None}
    if achieved_instances < floor_instances:
        out["classification"] = "MIXED_OR_INCONCLUSIVE"
        out["reason"] = "achieved sample below the frozen diagnostic floor"
    elif "S7" in q:
        out["classification"] = "CURRENT_TFG_IDENTIFYING_UNDER_TWINS"
    elif any(s in q for s in SEARCH_STAGES):
        out["classification"] = "RAW_TRAJECTORY_SIGNAL_TFG_LOSS"
        out["loss_between"] = ("S7a", "S7") if "S7a" in q else (q[-1], "S7a")
    elif "S6" in q:
        out["classification"] = "LATE_EXECUTION_SIGNAL_ONLY"
    elif "S7a" in q:
        out["classification"] = "MIXED_OR_INCONCLUSIVE"
        out["reason"] = "stored graph qualifies while every raw stage it summarizes does not"
    elif confirmatory:
        out["classification"] = "REASONER_TRAJECTORY_INSENSITIVE"
    else:
        out["classification"] = "MIXED_OR_INCONCLUSIVE"
        out["reason"] = "no stage qualified and the run is underpowered"
    return out
