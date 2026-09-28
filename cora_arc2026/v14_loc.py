"""Item-2 v1.4 mechanistic frontier localization.

Shared-input counterfactual twins, raw trajectory capture from the existing
observer, and the stagewise nonlearned audit of protocol v1.4.

Nothing here trains, proposes, compiles, installs or scores. The deployed
reasoner, the observer, the admission law, the fitter and the baseline are
the v1.3 ones, called unchanged. The only new observation is that the
observer's ordered candidate list, which v1.3 discarded after building the
TFG, is now kept, together with the evaluation on every demonstration of
every distinct executed near miss, which the TFG capped at twelve and
evaluated on one demonstration.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import Counter
from fractions import Fraction
from itertools import permutations, product

from cora_arc2026 import v13_gen as G

CD, V2, CV, ET = G.CD, G.V2, G.CV, G.ET

#: seeds, disjoint from every earlier corpus. v1.3 pair seeds stay below
#: 1.3e7, so its grid seeds (seed * 97 + i) stay below 1.3e9; v1.4 grid seeds
#: start at 9.7e9 and feasibility-smoke grid seeds at 1.94e10.
SEED_BASE = 100_000_000
SMOKE_BASE = 200_000_000
SLOT_STRIDE = 10_000
ATTEMPT_STRIDE = 100

REPLICATES = 4
SEEDS_PER_PAIR = 8
ATTEMPTS_PER_SLOT = 25
TARGET_GROUPS = 42
FLOOR_GROUPS = 14
MISMATCH_CAP = 64

NULL = Fraction(1, 2)
ALPHA = 0.01
TIE_EPS = 1e-12
#: lcm(1..6): a tie-shared credit over at most six companions, times 60, is
#: an integer
CREDIT_SCALE = 60

ADMITTED = "ADMITTED"
R_TWIN_INPUTS = "TWIN_INPUTS_DIFFER"
R_TWIN_SAME = "TWIN_OUTPUTS_IDENTICAL"
R_TWIN_EXEC = "TWIN_DEMONSTRATIONS_UNDEFINED"
R_TWIN_LAW = "TWIN_LAW_VIOLATED"
R_PAIR_SHORT = "PAIR_REPLICATES_SHORT"

#: pipeline order. S0 is a demonstration baseline, not a reasoning stage.
#: S1 (perception) is not emitted by the existing observer and is not added.
SEARCH_STAGES = ("S2", "S3", "S4")
EXECUTION_STAGES = ("S5", "S6")
TFG_STAGES = ("S7a", "S7")
CORA_STAGES = SEARCH_STAGES + EXECUTION_STAGES + TFG_STAGES
ALL_STAGES = ("S0",) + CORA_STAGES

#: all six orders of the three engine runs of a replicate: target A, target
#: B, and the rerun of A. Chosen per replicate by a hash of its seed, before
#: any outcome, so that neither target always runs first and neither the
#: twin nor the rerun is always closer in time to A.
RUN_ORDERS = tuple(permutations((0, 1, "rerun")))


def run_order(seed):
    h = int(hashlib.sha256(f"v14-order-{seed}".encode()).hexdigest(), 16)
    return RUN_ORDERS[h % len(RUN_ORDERS)]


#: the only episode keys a stage descriptor may read
VIEW_KEYS = ("demo_features", "trajectory", "mismatch", "full_engine_tfg",
             "descriptor")

#: the engine reads 18 ARC_* switches; some change behaviour across
#: episodes (ARC_ANALOGY loads persisted programs, ARC_OVERLAY rereads the
#: near-solve log, ARC_GUIDE keeps module caches). Every ARC_* variable is
#: refused except the budget, which must be exactly 8.
REQUIRED_ENV = {"ARC_META_BUDGET_S": "8", "PYTHONHASHSEED": "0"}
ENGINE_STATE_FILES = ("library.json", "learned_verbs.json")
#: files outside the digested package trees that the chain reads
EXTERNAL_FILES = (
    "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti/"
    "outputs/tti/constructive_protocol_manifest.json",
    "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti/"
    "outputs/tti/constructive_protocol_manifest_hash.txt")

TTI_ROOT = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"


def dependency_roots(here) -> dict:
    """Every project package the generator and auditor import."""
    return {"cora_arc2026": os.path.join(here, "cora_arc2026"),
            "geocat_arc": os.path.join(here, "geocat_arc"),
            "cora_tti": os.path.join(TTI_ROOT, "cora_tti"),
            "cora_parent": os.path.join(TTI_ROOT, "cora_parent"),
            "level4_blind_runtime": os.path.join(TTI_ROOT,
                                                 "level4_blind_runtime")}


def tree_digest(root, suffix=".py") -> str:
    """sha256 over (relative path, file sha256) for every source file."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d != "__pycache__" and not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(suffix):
                path = os.path.join(dirpath, name)
                with open(path, "rb") as handle:
                    h.update(os.path.relpath(path, root).encode() + b"\0"
                             + hashlib.sha256(handle.read()).digest())
    return h.hexdigest()


# --------------------------------------------------------------------------
# canonical structure
# --------------------------------------------------------------------------

def skeleton(value):
    """Structure with every numeric literal abstracted to '#'.

    One generic rule for every stage: operator names, feature names, modes
    and nesting are kept; constants such as colours, counts and sizes are
    not, so a descriptor compares what the reasoner did rather than the
    particular grid it did it on.
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
    """Engine task label carrying no target, replicate or twin identity."""
    return "v14-" + hashlib.sha256(
        "|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def environment_snapshot() -> dict:
    snap = {k: v for k, v in os.environ.items() if k.startswith("ARC_")}
    snap["PYTHONHASHSEED"] = os.environ.get("PYTHONHASHSEED")
    return dict(sorted(snap.items()))


def runtime_versions() -> dict:
    import platform
    import numpy
    import scipy
    return {"python": platform.python_version(), "numpy": numpy.__version__,
            "scipy": scipy.__version__}


def engine_state_problems(engine_dir) -> list:
    problems = []
    snap = environment_snapshot()
    for k, v in snap.items():
        if REQUIRED_ENV.get(k) != v:
            problems.append(f"env:{k}")
    for k in REQUIRED_ENV:
        if k not in snap:
            problems.append(f"env:{k}")
    for name in ENGINE_STATE_FILES:
        if os.path.exists(os.path.join(engine_dir, name)):
            problems.append(f"file:{name}")
    return sorted(set(problems))


def clear_engine_caches() -> int:
    """Reset every memo cache in the engine, so that no run starts warm
    from an earlier run on the same input. Semantics are unchanged."""
    import sys
    cleared = 0
    for name, mod in list(sys.modules.items()):
        if name == "geocat_arc" or name.startswith("geocat_arc."):
            for attr in list(vars(mod).values()):
                fn = getattr(attr, "cache_clear", None)
                if callable(fn) and hasattr(attr, "cache_info"):
                    fn()
                    cleared += 1
    return cleared


# --------------------------------------------------------------------------
# the twin law, from the frozen grammar only
# --------------------------------------------------------------------------

def twin_law(anchor, contrast) -> tuple:
    """Same family, block count, partition, selects and MDL; exactly one
    grammar token differs."""
    if contrast is None:
        return False, "no_contrast"
    if tuple(CV.family(anchor)) != tuple(CV.family(contrast)):
        return False, "family"
    if CV.block_count(anchor) != CV.block_count(contrast):
        return False, "block_count"
    if CV.mdl(anchor) != CV.mdl(contrast):
        return False, "mdl"
    ta, tb = CV.tokens_from_ast(anchor), CV.tokens_from_ast(contrast)
    if len(ta) != len(tb):
        return False, "token_length"
    if sum(1 for a, b in zip(ta, tb) if a != b) != 1:
        return False, "differing_positions"
    ba, bb = CV.blocks_from_ast(anchor), CV.blocks_from_ast(contrast)
    if ba[0][0] != bb[0][0] or tuple(ba[0][1]) != tuple(bb[0][1]) \
            or ba[1:] != bb[1:]:
        return False, "not_a_feature_change"
    return True, "ok"


# --------------------------------------------------------------------------
# capture, called at generation time only
# --------------------------------------------------------------------------

def serialize_trajectory(observer) -> list:
    """The observer's ordered candidate list, [ast_json, outcome] each."""
    return [[ET.X._canonical_ast(ast), outcome]
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
    Diagnostic only; runs after the engine has returned and generates,
    ranks or accepts nothing."""
    out, seen = [], set()
    for ast, outcome in observer.candidates:
        if outcome != "executed_not_exact" or len(out) >= cap:
            continue
        text = ET.X._canonical_ast(ast)
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


def same_grids(a, b) -> bool:
    import numpy as np
    return len(a) == len(b) and all(
        np.asarray(x).shape == np.asarray(y).shape
        and bool((np.asarray(x) == np.asarray(y)).all()) for x, y in zip(a, b))


def make_twin_replicate(anchor, contrast, seed, budgets, gate, label_parts,
                        engine_dir):
    """One shared-input replicate: both targets see the SAME input grids.

    Returns (code, {0: episode, 1: episode} or None). Admission is the v1.3
    law applied to each target unchanged, plus twin integrity: identical
    demonstration inputs and at least one differing demonstration output.
    """
    import numpy as np
    pa = demonstrations_for(anchor, seed)
    pb = demonstrations_for(contrast, seed)
    if pa is None or pb is None:
        return R_TWIN_EXEC, None
    if not same_grids([x for x, _ in pa], [x for x, _ in pb]):
        return R_TWIN_INPUTS, None
    if same_grids([y for _, y in pa], [y for _, y in pb]):
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
    if [d["input"] for d in episodes[0]["demonstrations"]] != \
            [d["input"] for d in episodes[1]["demonstrations"]]:
        return R_TWIN_INPUTS, None

    #  target A is observed twice on the same input: the rerun measures the
    #  timing noise of a deadline-bound run. The run order is balanced over
    #  all six permutations (see RUN_ORDERS).
    order = run_order(seed)
    runs = {}
    for which in order:
        ep = episodes[0 if which == "rerun" else which]
        pairs = [(d["input"], d["output"]) for d in ep["demonstrations"]]
        clear_engine_caches()
        cpu = time.process_time()
        got = ET.extract(opaque_label(*label_parts, which), pairs,
                         budget_s=budgets["full_engine_observation_s"],
                         out_dir=engine_dir)
        got["cpu_s"] = round(time.process_time() - cpu, 3)
        if which != "rerun":
            if got["solved"]:
                return G.R_NO_TFG, None
            if not G.informative(G.features_v12(got["tfg"]), gate):
                return G.R_NO_TFG, None
        runs[which] = (got, pairs)

    def observed(got, pairs):
        features = G.features_v12(got["tfg"])
        tfg_json = got["tfg"].to_json()
        np_pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
        return features, {
            "demo_features": {k: features[k] for k in G.DEMO_FEATURES},
            "full_engine_tfg": tfg_json,
            "descriptor": G.raw_descriptor(tfg_json),
            "trajectory": serialize_trajectory(got["observer"]),
            "mismatch": evaluate_near_misses(got["observer"], np_pairs),
            "census": got["census"],
            "observation_s": round(got["seconds"], 3),
            "cpu_s": got.get("cpu_s"),
        }

    out = {}
    for t in (0, 1):
        ep = episodes[t]
        got, pairs = runs[t]
        features, obs = observed(got, pairs)
        out[t] = dict(obs, **{
            "target_digest": ep["target_digest"],
            "target_tokens": ep["target_tokens"],
            "structural_family": ep.get("structural_family"),
            "schema_mdl": ep.get("schema_mdl"),
            "seed": seed,
            "demonstrations": ep["demonstrations"],
            "features": features,
            "base_search_evidence": ep.get("base_search_evidence"),
            "fitter_identity": ep.get("fitter_identity"),
        })
    got, pairs = runs["rerun"]
    _, rerun = observed(got, pairs)
    rerun["solved"] = bool(got["solved"])
    rerun["order"] = ["A" if w == 0 else "B" if w == 1 else "rerun"
                      for w in order]
    out[0]["self_rerun"] = rerun
    return ADMITTED, out


# --------------------------------------------------------------------------
# stage descriptors: functions of model_view(ep) only
# --------------------------------------------------------------------------

def model_view(ep) -> dict:
    return {k: ep[k] for k in VIEW_KEYS}


def _events(view):
    return [(json.loads(a), o) for a, o in view["trajectory"]]


def _payload(ast):
    """The dict an engine AST carries: [op, [detail]]."""
    if isinstance(ast, list) and len(ast) == 2 and isinstance(ast[1], list) \
            and ast[1] and isinstance(ast[1][0], dict):
        return ast[1][0]
    return {}


def _op(ast):
    return ast[0] if isinstance(ast, list) and ast else str(ast)


def stage_multiset(view, stage) -> Counter:
    events = _events(view)
    c = Counter()
    if stage == "S2":                  # candidate formation: typed groups
        for ast, o in events:
            if o == "typed":
                c[key(ast)] += 1
    elif stage == "S3":                # selector induction, from event order
        for i, (ast, o) in enumerate(events):
            if o != "typed":
                continue
            nxt = events[i + 1] if i + 1 < len(events) else None
            if nxt and nxt[1] in ("slot_fit_failed", "slot_fit_ok"):
                c[json.dumps(["selector_induced", key(ast),
                              key(_payload(nxt[0]).get("selector"))])] += 1
            else:
                c[json.dumps(["no_selector", key(ast)])] += 1
    elif stage == "S4":                # parameter fitting
        for ast, o in events:
            if o == "slot_fit_failed":
                c[json.dumps([o, _op(ast)])] += 1
            elif o == "slot_fit_ok":
                c[json.dumps([o, key(_payload(ast).get("action"))])] += 1
    elif stage == "S5":                # fitted executable candidates, uncapped
        for ast, o in events:
            if o in ("executed_not_exact", "exact"):
                c[json.dumps([o, key(ast)])] += 1
    elif stage == "S6":                # execution x mismatch, associated
        for row in view["mismatch"]:
            k = key(json.loads(row["ast"]))
            for cls in row["per_demo"]:
                c[json.dumps([k, cls])] += 1
    elif stage == "S7a":               # stored TFG graph, before aggregation
        nodes = {n["id"]: n for n in view["full_engine_tfg"]["nodes"]}
        term_key = {}
        for n in nodes.values():
            if n["kind"] == "frontier_term":
                term_key[n["id"]] = key(json.loads(n["attrs"]["ast"]))
                c[json.dumps([n["attrs"]["outcome"], term_key[n["id"]]])] += 1
        for src, rel, dst in view["full_engine_tfg"]["edges"]:
            if rel == "observed_on" and dst in term_key:
                c[json.dumps([term_key[dst],
                              vsig_class(nodes[src]["attrs"])])] += 1
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
    """Weighted Jaccard distance on multisets; 0 for two empty multisets."""
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    return 1.0 - sum(min(a[k], b[k]) for k in keys) / \
        sum(max(a[k], b[k]) for k in keys)


def euclid(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def standardized(values: dict, order, mean, std) -> list:
    return [(float(values.get(k, 0) or 0) - mean[i]) / std[i]
            for i, k in enumerate(order)]


def stage_points(views, stage, cal):
    """Per-episode descriptor for one stage, and the distance on it."""
    if stage == "S0":
        return [standardized(v["demo_features"], cal["demo_features"],
                             cal["demo_mean"], cal["demo_std"])
                for v in views], euclid
    if stage == "S7":
        return [standardized(v["descriptor"], cal["descriptor_order"],
                             cal["descriptor_mean"], cal["descriptor_std"])
                for v in views], euclid
    return [stage_multiset(v, stage) for v in views], ruzicka


# --------------------------------------------------------------------------
# within-group statistics
# --------------------------------------------------------------------------

def _tie_key(salt, i, j):
    return hashlib.sha256(f"v14-tie|{salt}|{i}|{j}".encode()).digest()


def nn_credits(dist, idx, labels, salt=""):
    """Twin-excluded nearest neighbour.

    For query (t, r) the companions are the six episodes of the OTHER three
    replicates: three of the same target, three of the other. The query's
    own twin shares its input and is excluded. Ties at the minimum share
    credit. A hit breaks ties by a hash of (salt, query, companion), which
    does not depend on any label, so its null probability is exactly 1/2.
    Returns (credits as Fractions, hits, strict hits, tie flags).
    """
    credits, hits, strict, tied = [], [], [], []
    for i, (_, r) in enumerate(idx):
        comp = [j for j, (_, rj) in enumerate(idx) if rj != r]
        dmin = min(dist[i][j] for j in comp)
        near = [j for j in comp if dist[i][j] <= dmin + TIE_EPS]
        same = sum(1 for j in near if labels[j] == labels[i])
        chosen = min(near, key=lambda j: _tie_key(salt, i, j))
        credits.append(Fraction(same, len(near)))
        hits.append(int(labels[chosen] == labels[i]))
        strict.append(int(same == len(near)))
        tied.append(int(len(near) > 1))
    return credits, hits, strict, tied


def group_stats(eps, stage, cal, salt=""):
    views = [model_view(e) for e in eps]
    pts, fn = stage_points(views, stage, cal)
    n = len(eps)
    dist = [[fn(pts[i], pts[j]) for j in range(n)] for i in range(n)]
    idx = [(e["target_index"], e["replicate_index"]) for e in eps]
    labels = [t for t, _ in idx]
    credits, hits, strict, tied = nn_credits(dist, idx, labels, salt)
    reps = sorted({r for _, r in idx})
    null_totals = []
    for sigma in product((0, 1), repeat=len(reps)):
        flip = dict(zip(reps, sigma))
        c = nn_credits(dist, idx, [t ^ flip[r] for t, r in idx], salt)[0]
        null_totals.append(sum(c))
    within, between = [], []
    for i in range(n):
        for j in range(i + 1, n):
            (ti, ri), (tj, rj) = idx[i], idx[j]
            if ri == rj:
                continue
            (within if ti == tj else between).append(dist[i][j])
    s = (sum(between) / len(between) - sum(within) / len(within)) \
        if within and between else 0.0
    return {"credits": credits, "hits": hits, "strict": strict, "tied": tied,
            "null_totals": null_totals, "separation": s}


def randomization_p(observed, per_group_null) -> Fraction:
    """Exact P(T >= observed) under independent uniform within-twin label
    swaps in every group, by convolution over integer pattern counts."""
    counts = {0: 1}
    patterns = 1
    for values in per_group_null:
        vc = Counter()
        for v in values:
            scaled = v * CREDIT_SCALE
            assert scaled.denominator == 1
            vc[int(scaled)] += 1
        nxt: dict = {}
        for total, c in counts.items():
            for v, k in vc.items():
                nxt[total + v] = nxt.get(total + v, 0) + c * k
        counts = nxt
        patterns *= len(values)
    target = Fraction(observed) * CREDIT_SCALE
    assert target.denominator == 1
    return Fraction(sum(c for t, c in counts.items() if t >= int(target)),
                    patterns)


def binom_sf(k, n, p) -> Fraction:
    """Exact P(X >= k), X ~ Binomial(n, p)."""
    p = Fraction(p)
    return sum((math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                for i in range(k, n + 1)), Fraction(0))


def clopper_pearson(k, n, level=0.95):
    from scipy.stats import beta
    a = (1 - level) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return lo, hi


def _median(xs):
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _frac(xs):
    return round(sum(xs) / len(xs), 5) if xs else None


def stage_result(groups, stage, cal) -> dict:
    per = [group_stats(g["episodes"], stage, cal, f"{stage}|{gi}")
           for gi, g in enumerate(groups)]
    hits = sum(sum(p["hits"]) for p in per)
    strict = sum(sum(p["strict"]) for p in per)
    total = sum(len(p["hits"]) for p in per)
    credit = sum((sum(p["credits"]) for p in per), Fraction(0))
    p_binom = float(binom_sf(hits, total, NULL)) if total else 1.0
    p_rand = float(randomization_p(credit, [p["null_totals"] for p in per])) \
        if total else 1.0
    rate = hits / total if total else 0.0
    seps = sorted(p["separation"] for p in per)
    return {
        "stage": stage,
        "hits": hits, "total": total, "hit_rate": round(rate, 5),
        "ci95_hit_rate": [round(x, 5) for x in clopper_pearson(hits, total)]
        if total else None,
        "p_binomial": p_binom,
        "strict_hits": strict,
        "strict_rate": round(strict / total, 5) if total else None,
        "credit": round(float(credit), 5),
        "credit_rate": round(float(credit) / total, 5) if total else None,
        "p_randomization": p_rand,
        "tie_fraction": _frac([x for p in per for x in p["tied"]]),
        "target_identifying": bool(total and rate > float(NULL)
                                   and p_binom < ALPHA and p_rand < ALPHA),
        "separation_mean": round(sum(seps) / len(seps), 5) if seps else None,
        "separation_median": round(_median(seps), 5) if seps else None,
        "fraction_s_positive": _frac([int(s > 0) for s in seps]),
        "separation_min": round(seps[0], 5) if seps else None,
        "separation_max": round(seps[-1], 5) if seps else None,
        "per_group_separation": [round(p["separation"], 5) for p in per],
    }


#: stages built only from events the engine itself emitted. S6, S7a and S7
#: also score each target's candidates against that target's own outputs,
#: so they differ between twins even when the trajectory is identical; they
#: are reported for sensitivity but never enter the reaction qualifier.
REACTION_STAGES = ("S2", "S3", "S4", "S5")


def sensitivity(groups, stage, cal) -> dict:
    """Does the stage react to the semantic change beyond timing noise?

    Per replicate, the twin distance d(A, B) is compared with the rerun
    distance d(A, A'), same input and same target. If the stage does not
    depend on the target, B and A' are exchangeable given A, so the twin is
    farther with probability 1/2 among untied replicates. Exact one-sided
    sign test. Replicates are independent (own input, own runs)."""
    plus = minus = ties = solved = 0
    strata = {"twin_closer_in_time": [0, 0], "rerun_closer_in_time": [0, 0],
              "equal_time_gaps": [0, 0]}
    twin_d, self_d = [], []
    for g in groups:
        by = {(e["target_index"], e["replicate_index"]): e for e in g["episodes"]}
        for r in range(REPLICATES):
            a, b = by[(0, r)], by[(1, r)]
            rerun = a["self_rerun"]
            if rerun.get("solved"):
                solved += 1
                continue
            pts, fn = stage_points([model_view(a), model_view(b),
                                    model_view(rerun)], stage, cal)
            dt, ds = fn(pts[0], pts[1]), fn(pts[0], pts[2])
            twin_d.append(dt)
            self_d.append(ds)
            order = rerun["order"]
            gap_twin = abs(order.index("B") - order.index("A"))
            gap_self = abs(order.index("rerun") - order.index("A"))
            stratum = ("twin_closer_in_time" if gap_twin < gap_self else
                       "rerun_closer_in_time" if gap_twin > gap_self else
                       "equal_time_gaps")
            if dt > ds + TIE_EPS:
                plus += 1
                strata[stratum][0] += 1
            elif dt < ds - TIE_EPS:
                minus += 1
                strata[stratum][1] += 1
            else:
                ties += 1
    n = plus + minus
    p = float(binom_sf(plus, n, NULL)) if n else 1.0
    return {"stage": stage, "twin_farther": plus, "rerun_farther": minus,
            "ties": ties, "rerun_solved_excluded": solved, "p_sign": p,
            "rescoring_stage": stage not in REACTION_STAGES,
            "median_twin_distance": round(_median(sorted(twin_d)), 5)
            if twin_d else None,
            "median_rerun_distance": round(_median(sorted(self_d)), 5)
            if self_d else None,
            "strata_twin_farther_rerun_farther": strata}


def holm(pvalues: dict) -> dict:
    items = sorted(pvalues.items(), key=lambda kv: (kv[1], kv[0]))
    m, out, running = len(items), {}, 0.0
    for rank, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - rank) * p))
        out[name] = running
    return out


# --------------------------------------------------------------------------
# the frozen classification ladder
# --------------------------------------------------------------------------

def classify(results: dict, n_groups: int, reacting=None) -> dict:
    q = [s for s in CORA_STAGES if results[s]["target_identifying"]]
    rand_only = [s for s in CORA_STAGES
                 if s not in q and results[s]["p_randomization"] < ALPHA]
    adjusted = holm({s: results[s]["p_randomization"] for s in CORA_STAGES})
    search = [s for s in q if s in SEARCH_STAGES]
    execution = [s for s in q if s in EXECUTION_STAGES]
    label, det, reason = None, None, None
    if n_groups < FLOOR_GROUPS:
        label = "MIXED_OR_INCONCLUSIVE"
        reason = f"admitted groups below the frozen floor of {FLOOR_GROUPS}"
    elif "S7" in q:
        label, det = "CURRENT_TFG_IDENTIFYING_UNDER_TWINS", "S7"
    elif q and any(CORA_STAGES.index(s) < CORA_STAGES.index(q[0])
                   for s in rand_only):
        label = "MIXED_OR_INCONCLUSIVE"
        reason = ("a stage before the first qualifying stage passes the exact "
                  "randomization test but not the binomial, so the first "
                  "stage carrying signal is unresolved")
    elif search:
        label, det = "RAW_TRAJECTORY_SIGNAL_TFG_LOSS", search[0]
    elif execution:
        label, det = "LATE_EXECUTION_SIGNAL_ONLY", execution[0]
    elif "S7a" in q:
        label, det = "TFG_AGGREGATION_LOSS", "S7a"
    elif rand_only:
        label = "MIXED_OR_INCONCLUSIVE"
        reason = ("a stage passes the exact randomization test but not the "
                  "strict binomial test")
    elif n_groups >= TARGET_GROUPS:
        label = "REASONER_TRAJECTORY_INSENSITIVE"
        reason = ("REACTS_BUT_NOT_CONSISTENTLY" if reacting
                  else "NO_REACTION_BEYOND_TIMING_NOISE")
    else:
        label = "MIXED_OR_INCONCLUSIVE"
        reason = (f"no stage qualified and the sample is below the powered "
                  f"target of {TARGET_GROUPS} groups")
    loss_point = None
    if label in ("RAW_TRAJECTORY_SIGNAL_TFG_LOSS", "LATE_EXECUTION_SIGNAL_ONLY"):
        loss_point = ("42-field aggregation" if "S7a" in q
                      else "TFG construction")
    elif label == "TFG_AGGREGATION_LOSS":
        loss_point = "42-field aggregation"
    return {
        "classification": label, "determining_stage": det, "reason": reason,
        "loss_point": loss_point,
        "qualifying_stages": q, "randomization_only_stages": rand_only,
        "tfg_graph_identifying": "S7a" in q,
        "reacting_stages": list(reacting or []),
        "holm_adjusted_p_randomization": adjusted,
        "determining_stage_survives_holm":
            (adjusted[det] < ALPHA) if det else None,
        "groups": n_groups, "confirmatory": n_groups >= TARGET_GROUPS,
    }


def audit_groups(groups, cal) -> dict:
    results = {s: stage_result(groups, s, cal) for s in ALL_STAGES}
    react = {s: sensitivity(groups, s, cal) for s in CORA_STAGES}
    adjusted = holm({s: react[s]["p_sign"] for s in REACTION_STAGES})
    for s in CORA_STAGES:
        react[s]["p_sign_holm"] = adjusted.get(s)
        react[s]["reacts"] = bool(s in adjusted and adjusted[s] < ALPHA)
    reacting = [s for s in REACTION_STAGES if react[s]["reacts"]]
    return {"stages": results, "sensitivity": react,
            "classification": classify(results, len(groups), reacting)}


# --------------------------------------------------------------------------
# integrity and leakage, checked by the auditor before any statistic
# --------------------------------------------------------------------------

def integrity_problems(group) -> list:
    """Violations of the frozen group law; any one blocks the audit."""
    p = []
    if group.get("contrast_type") != "FEATURE":
        p.append("contrast_type")
    eps = group.get("episodes", [])
    if len(eps) != 2 * REPLICATES:
        p.append("episode_count")
    cells = sorted((e.get("target_index"), e.get("replicate_index")) for e in eps)
    if cells != sorted((t, r) for t in (0, 1) for r in range(REPLICATES)):
        p.append("design_cells")
    digests = list(group.get("target_digests", []))
    if len(set(digests)) != 2:
        p.append("target_digests")
    elif any(e.get("target_digest") != digests[e.get("target_index")]
             for e in eps if e.get("target_index") in (0, 1)):
        p.append("episode_digest")
    if len({json.dumps(e.get("structural_family")) for e in eps}) != 1:
        p.append("family")
    if len({e.get("schema_mdl") for e in eps}) != 1:
        p.append("mdl")
    by = {(e.get("target_index"), e.get("replicate_index")): e for e in eps}
    for r in range(REPLICATES):
        a, b = by.get((0, r)), by.get((1, r))
        if a is None or b is None:
            continue
        if a.get("seed") != b.get("seed"):
            p.append(f"twin_seed_r{r}")
        if [d["input"] for d in a["demonstrations"]] != \
                [d["input"] for d in b["demonstrations"]]:
            p.append(f"twin_inputs_r{r}")
        if [d["output"] for d in a["demonstrations"]] == \
                [d["output"] for d in b["demonstrations"]]:
            p.append(f"twin_outputs_identical_r{r}")
    if any(k not in e for e in eps for k in VIEW_KEYS):
        p.append("view_keys")
    for e in eps:
        if e.get("target_index") == 0:
            rerun = e.get("self_rerun")
            if not isinstance(rerun, dict) or any(k not in rerun for k in VIEW_KEYS) \
                    or sorted(rerun.get("order", [])) != ["A", "B", "rerun"]:
                p.append("self_rerun")
                break
    return p


R_DUPLICATE_GROUP = "DUPLICATE_GROUP_DIGEST"


def first_admissions(records):
    """Erratum 2. The first admitted occurrence of a group digest in
    ascending slot order is the scientific occurrence; any later admission
    of the same digest is an excluded duplicate, kept in the corpus and
    counted but never audited. Uses only the digest and the slot number.
    Returns (included records in slot order, excluded duplicates)."""
    included, excluded, first_slot = [], [], {}
    for r in sorted((r for r in records if r.get("admitted")),
                    key=lambda r: r["slot"]):
        d = r["group"]["group_digest"]
        if d in first_slot:
            excluded.append({"group_digest": d, "first_slot": first_slot[d],
                             "excluded_slot": r["slot"]})
        else:
            first_slot[d] = r["slot"]
            included.append(r)
    return included, excluded


def _sha_file(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def preserved_problems(hash_list, hash_list_sha256, corpus_dir,
                       archived=()) -> list:
    """Erratum 2. Every file named in the committed corpus hash list is
    byte-identical to its listed digest, and every archived copy, given as
    (copy path, listed original name), matches the listed original."""
    if not os.path.exists(hash_list) or _sha_file(hash_list) != hash_list_sha256:
        return ["hash_list"]
    listed = {}
    with open(hash_list) as handle:
        for line in handle:
            digest, name = line.split()
            listed[name] = digest
    p = []
    for name, digest in sorted(listed.items()):
        path = os.path.join(corpus_dir, name)
        if not os.path.exists(path) or _sha_file(path) != digest:
            p.append(f"preserved:{name}")
    for copy_path, original in archived:
        if not os.path.exists(copy_path) or \
                _sha_file(copy_path) != listed.get(original):
            p.append(f"archived:{os.path.basename(copy_path)}")
    return p


def corpus_problems(records, target_groups, expected_env, expected_versions,
                    require_freeze_ok=True, dedupe_from_slot=None) -> list:
    """Run-level integrity: contiguous slots, at most the target of groups,
    one frozen environment, no engine state problem, freeze re-verified
    every slot. Without dedupe_from_slot this is the pre-erratum-2 rule: any
    duplicate group digest blocks. With it (erratum 2), a later admission of
    an already-included digest is excluded by first_admissions and only the
    included groups count toward the target; from dedupe_from_slot on the
    generator skips such pairs, so an excluded admission there blocks."""
    p = []
    slots = sorted(r.get("slot", -1) for r in records)
    if slots != list(range(len(records))):
        p.append("slots_not_contiguous")
    included, excluded = first_admissions(records)
    raw = sum(1 for r in records if r.get("admitted"))
    if dedupe_from_slot is None:
        if excluded:
            p.append("duplicate_group_digest")
        if raw > target_groups:
            p.append("more_groups_than_target")
    else:
        if any(x["excluded_slot"] >= dedupe_from_slot for x in excluded):
            p.append("duplicate_after_erratum2_resume")
        if len(included) > target_groups:
            p.append("more_groups_than_target")
    for r in records:
        tag = f"slot{r.get('slot')}"
        if r.get("environment") != expected_env:
            p.append(f"{tag}:environment")
        if r.get("runtime_versions") != expected_versions:
            p.append(f"{tag}:runtime_versions")
        if r.get("engine_state_problems"):
            p.append(f"{tag}:engine_state")
        if require_freeze_ok and r.get("freeze_ok") is not True:
            p.append(f"{tag}:freeze_not_reverified")
    return p


def view_leaks(ep, group) -> list:
    """Target identity, group identity or generation seed echoed into the
    model view. Engine vocabulary is not checked against grammar token
    names: the engine's own feature names legitimately overlap them, and the
    engine receives only demonstration grids and an opaque label."""
    import re
    views = [model_view(ep)]
    if isinstance(ep.get("self_rerun"), dict):
        views.append(model_view(ep["self_rerun"]))
    text = json.dumps(views, sort_keys=True)
    found = set()
    identities = [ep.get("target_digest", "")] + \
        list(group.get("target_digests", [])) + [group.get("group_digest", "")]
    for d in identities:
        if any(d and len(d) >= w and d[:w] in text for w in (8, 12, 16)):
            found.add("digest")
    for s in (ep.get("seed"), group.get("pair_seed")):
        if isinstance(s, int) and s >= 1000 and \
                re.search(rf"(?<!\d){s}(?!\d)", text):
            found.add("seed")
    return sorted(found)
