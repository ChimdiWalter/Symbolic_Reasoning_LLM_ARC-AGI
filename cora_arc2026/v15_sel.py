"""Item-2 v1.5 conditional failure-conditioned selection under input variation.

Given two legal constructive candidates that differ in one key-feature
position, does the query's associated failure evidence improve selection of
the correct candidate beyond demonstration evidence alone, and does the
increment survive on unseen target pairs under independently rendered inputs?

Reuses, unchanged: the v1.4 FEATURE twin law and grammar contrast, the v1.3
admission law, the real-engine observer and trajectory capture, the v1.2
LogLinearScorer and Standardizer. New here: independent-input groups, the
evidence views, the matched shuffle, the pairwise fit, the exact group-level
tests, and the classification ladder. Nothing proposes, compiles, installs
or solves.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import re
import time
from fractions import Fraction

from cora_arc2026 import v13_gen as G
from cora_arc2026 import v14_loc as L

CD, V2, CV, ET = G.CD, G.V2, G.CV, G.ET

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# frozen constants
# --------------------------------------------------------------------------

#: seeds. v1.2 and v1.3 pair seeds stay below 1.3e7; v1.4 used 1.0e8 to
#: 1.04e8 and its smoke 2.0e8 upward. Grid seeds are seed * 97 + i, so these
#: ranges never meet.
TEST_BASE = 300_000_000
PILOT_BASE = 400_000_000
SLOT_STRIDE = 10_000
ATTEMPT_STRIDE = 100
TARGET_SEED_STRIDE = 10          # episode seed = pair_seed + 10 t + k

REPLICATES = 4                   # admitted episodes per target
SEEDS_PER_TARGET = 8
ATTEMPTS_PER_SLOT = 25
FAMILIES = ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]

ADMITTED = "ADMITTED"
R_EXCLUDED_TARGET = "EXCLUDED_TARGET_DIGEST"
R_EXCLUDED_GROUP = "EXCLUDED_GROUP_DIGEST"
R_USED_TARGET = "TARGET_ALREADY_IN_CORPUS"
R_DUPLICATE_GROUP = "DUPLICATE_GROUP_DIGEST"
R_PAIR_SHORT = "PAIR_REPLICATES_SHORT"

EXCLUSION_FILE = os.path.join(HERE, "outputs", "tti", "v15_exclusion_digests.json")

#: the earlier corpora whose digests the v1.5 test must avoid
EXCLUSION_SOURCES = {
    "v1.2 corpus": "outputs/tti/v12_corpus/*.json",
    "v1.3 calibration": "outputs/tti/v13_calibration/*.json",
    "v1.3 corpus": "outputs/tti/v13_contrastive_corpus/*.json",
    "v1.4 corpus": "outputs/tti/v14_twin_corpus/*.json",
    "v1.4 feasibility smoke": "logs/v14_feasibility/*.json",
}
DIGEST_KEYS = ("target_digest", "target_digests", "group_digest",
               "phase_a_target_digests", "pair_digest")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------
# the exclusion set
# --------------------------------------------------------------------------

def _collect(value, key, out):
    if isinstance(value, dict):
        for k, v in value.items():
            _collect(v, k, out)
    elif isinstance(value, list):
        for v in value:
            _collect(v, key, out)
    elif isinstance(value, str) and key in DIGEST_KEYS and _HEX64.match(value):
        out["group" if key == "group_digest" else "target"].add(value)


def build_exclusion(root=HERE) -> dict:
    """Every target and group digest in the v1.2 to v1.4 artifacts."""
    sources, targets, groups = {}, set(), set()
    for name, pattern in sorted(EXCLUSION_SOURCES.items()):
        found = {"target": set(), "group": set()}
        paths = sorted(glob.glob(os.path.join(root, pattern)))
        for path in paths:
            with open(path) as handle:
                _collect(json.load(handle), None, found)
        sources[name] = {"files": len(paths), "target_digests": len(found["target"]),
                         "group_digests": len(found["group"])}
        targets |= found["target"]
        groups |= found["group"]
    return {"sources": sources, "target_digests": sorted(targets),
            "group_digests": sorted(groups)}


def load_exclusion(path=EXCLUSION_FILE):
    with open(path) as handle:
        data = json.load(handle)
    return frozenset(data["target_digests"]), frozenset(data["group_digests"])


# --------------------------------------------------------------------------
# independent-input episodes
# --------------------------------------------------------------------------

def episode_seeds(pair_seed, t):
    return [pair_seed + TARGET_SEED_STRIDE * t + k for k in range(SEEDS_PER_TARGET)]


def attempt_order(pair_seed, k):
    """Which target is tried first at seed index k, by a label-independent
    hash, so neither target always runs first."""
    h = hashlib.sha256(f"v15-attempt-order|{pair_seed}|{k}".encode()).digest()[0]
    return (0, 1) if h % 2 == 0 else (1, 0)


def make_independent_episode(schema, other, seed, budgets, gate, label_parts,
                             engine_dir):
    """One episode of one target, on its own inputs.

    Admission is the v1.3 law unchanged; the observation is the v1.4 one
    (caches cleared, trajectory and near-miss capture). The final fitter
    call asks, for description only, whether the OTHER candidate would also
    reproduce these demonstrations; it never enters a model view.
    """
    import numpy as np
    try:
        outcome, episode, _ = V2.evaluate_target_v2(
            schema, seed=seed, split="train", regime="train_pool",
            allowed_families=[CV.family(schema)], seen_digests=set(),
            seen_train_digests=set(), v1_exclusion=set(),
            budgets=budgets, row_index=0)
    except Exception as exc:                                   # noqa: BLE001
        return f"{G.R_OTHER}:{type(exc).__name__}", None
    if outcome != "ADMITTED":
        return G.CODE_MAP.get(outcome, G.R_OTHER), None
    pairs = [(d["input"], d["output"]) for d in episode["demonstrations"]]
    L.clear_engine_caches()
    cpu = time.process_time()
    got = ET.extract(L.opaque_label(*label_parts), pairs,
                     budget_s=budgets["full_engine_observation_s"],
                     out_dir=engine_dir)
    cpu_s = round(time.process_time() - cpu, 3)
    if got["solved"]:
        return G.R_NO_TFG, None
    features = G.features_v12(got["tfg"])
    if not G.informative(features, gate):
        return G.R_NO_TFG, None
    np_pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    tfg_json = got["tfg"].to_json()
    from cora_tti import scoped_slot_fitting as SF
    try:
        other_fits = SF.fit_induced_occurrences(other, np_pairs)[0] is not None
    except Exception:                                          # noqa: BLE001
        other_fits = False
    return ADMITTED, {
        "target_digest": episode["target_digest"],
        "target_tokens": episode["target_tokens"],
        "structural_family": episode.get("structural_family"),
        "schema_mdl": episode.get("schema_mdl"),
        "seed": seed,
        "demonstrations": episode["demonstrations"],
        "demo_features": {k: features[k] for k in G.DEMO_FEATURES},
        "features": features,
        "full_engine_tfg": tfg_json,
        "descriptor": G.raw_descriptor(tfg_json),
        "trajectory": L.serialize_trajectory(got["observer"]),
        "mismatch": L.evaluate_near_misses(got["observer"], np_pairs),
        "census": got["census"],
        "observation_s": round(got["seconds"], 3),
        "cpu_s": cpu_s,
        "other_candidate_fits": other_fits,
        "base_search_evidence": episode.get("base_search_evidence"),
        "fitter_identity": episode.get("fitter_identity"),
    }


def run_pair(anchor, contrast, pair_seed, cfg, label_prefix, reject):
    """Try to admit REPLICATES episodes of each target on its own seeds.
    Returns the episodes or None; the order of tries interleaves the targets
    by attempt_order."""
    schemas = {0: anchor, 1: contrast}
    admitted, tried = {0: [], 1: []}, {0: 0, 1: 0}
    seeds = {t: episode_seeds(pair_seed, t) for t in (0, 1)}
    for k in range(SEEDS_PER_TARGET):
        for t in attempt_order(pair_seed, k):
            if len(admitted[t]) >= REPLICATES:
                continue
            if len(admitted[t]) + (SEEDS_PER_TARGET - tried[t]) < REPLICATES:
                return None
            seed = seeds[t][tried[t]]
            tried[t] += 1
            code, ep = make_independent_episode(
                schemas[t], schemas[1 - t], seed, cfg["budgets"], cfg["gate"],
                (label_prefix, pair_seed, t, k), cfg["engine"])
            cfg["counter"]["replicate_attempts"] += 1
            if code != ADMITTED:
                reject(code)
                continue
            ep["target_index"] = t
            ep["replicate_index"] = len(admitted[t])
            admitted[t].append(ep)
        if all(len(admitted[t]) >= REPLICATES for t in (0, 1)):
            return admitted[0] + admitted[1]
    return None


def run_slot(slot, fam, cfg, seen_groups=frozenset(), seen_targets=frozenset()):
    """One group slot: up to ATTEMPTS_PER_SLOT FEATURE pairs from the frozen
    grammar, skipping any pair whose group or target digest is excluded or
    already in the corpus, before any engine run."""
    record = {"slot": slot, "anchor_family": CV.family_text(fam),
              "contrast_type": "FEATURE", "admitted": False, "group": None,
              "pair_attempts": 0, "replicate_attempts": 0, "rejections": {},
              "skips": []}
    cfg["counter"] = {"replicate_attempts": 0}

    def reject(code):
        record["rejections"][code] = record["rejections"].get(code, 0) + 1

    ex_targets, ex_groups = cfg["exclusion"]
    for attempt in range(ATTEMPTS_PER_SLOT):
        record["pair_attempts"] = attempt + 1
        pair_seed = cfg["base"] + slot * SLOT_STRIDE + attempt * ATTEMPT_STRIDE
        anchor = CD.sample_target(pair_seed, fam)
        contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
        ok, why = L.twin_law(anchor, contrast)
        if not ok:
            reject(f"{L.R_TWIN_LAW}:{why}")
            continue
        da, db = CV.digest(anchor), CV.digest(contrast)
        digest = G.group_digest(da, db)
        code = (R_EXCLUDED_GROUP if digest in ex_groups else
                R_EXCLUDED_TARGET if da in ex_targets or db in ex_targets else
                R_DUPLICATE_GROUP if digest in seen_groups else
                R_USED_TARGET if da in seen_targets or db in seen_targets else None)
        if code:
            reject(code)
            record["skips"].append({"attempt": attempt, "pair_seed": pair_seed,
                                    "code": code, "group_digest": digest,
                                    "target_digests": [da, db]})
            continue
        episodes = run_pair(anchor, contrast, pair_seed, cfg,
                            (cfg["prefix"], slot, attempt), reject)
        record["replicate_attempts"] = cfg["counter"]["replicate_attempts"]
        if episodes is None:
            reject(R_PAIR_SHORT)
            continue
        record["group"] = {"group_digest": digest, "contrast_type": "FEATURE",
                           "anchor_family": CV.family_text(fam),
                           "target_digests": [da, db], "pair_seed": pair_seed,
                           "episodes": episodes}
        record["admitted"] = True
        break
    record["replicate_attempts"] = cfg["counter"]["replicate_attempts"]
    return record


# --------------------------------------------------------------------------
# frozen statistical constants
# --------------------------------------------------------------------------

ALPHA = 0.01
DELTA_MIN = Fraction(1, 20)          # +5 accuracy points on the pairwise scale
TEST_GROUPS = 288                    # exact-test power 0.909 at DELTA_MIN
FLOOR_GROUPS = 72                    # below this nothing is interpreted
LAMBDA = 0.01                        # L2, identical in every condition
NEWTON_TOL = 1e-12
NEWTON_MAX_ITER = 100
TIE_EPS = 1e-12
TWIN_FOLDS = 7
UNITS_PER_GROUP = 2 * 2 * REPLICATES  # accuracy in units of 1/16 per group


# --------------------------------------------------------------------------
# evidence views: functions of an episode's evidence only
# --------------------------------------------------------------------------

D_AGG_FIELDS = tuple(G.DEMO_FEATURES)
D_RICH_EXTRA = ("same_shape_fraction", "shrinks_fraction", "grows_fraction",
                "introduced_min", "introduced_max", "removed_min", "removed_max",
                "n_in_mean", "n_in_min", "n_in_max",
                "n_out_mean", "n_out_min", "n_out_max",
                "cells_changed_min", "cells_changed_max",
                "fraction_changed_min", "fraction_changed_max")
D_RICH_FIELDS = D_AGG_FIELDS + D_RICH_EXTRA
F_S7_FIELDS = tuple(G.DESCRIPTOR_ORDER)
VALUE_SIGNATURE_FIELDS = (
    "cells_wrong_max", "cells_wrong_mean", "cells_wrong_min",
    "defined_signatures", "fraction_wrong_max", "fraction_wrong_mean",
    "fraction_wrong_min", "palette_extra_max", "palette_extra_mean",
    "palette_extra_min", "shape_mismatch")
F_NOVSIG_FIELDS = tuple(f for f in F_S7_FIELDS if f not in VALUE_SIGNATURE_FIELDS)


def _delta_types():
    from geocat_arc.object_reasoning.types import DeltaType
    return tuple(sorted(d.value for d in DeltaType))


DELTA_TYPES = _delta_types()
SELECTOR_BUCKETS = 16
F_SEARCH_FIELDS = (("n_typed", "n_selector_induced", "n_no_selector",
                    "n_slot_fit_ok", "n_slot_fit_failed", "selector_literals_mean")
                   + tuple(f"typed_delta_{d}" for d in DELTA_TYPES)
                   + tuple(f"fit_ok_delta_{d}" for d in DELTA_TYPES)
                   + tuple(f"selector_bucket_{i}" for i in range(SELECTOR_BUCKETS)))
VIEW_BLOCKS = {"D_RICH": D_RICH_FIELDS, "F_S7": F_S7_FIELDS,
               "F_NOVSIG": F_NOVSIG_FIELDS, "F_SEARCH": F_SEARCH_FIELDS}


def _num(v):
    return 1.0 if v is True else 0.0 if v is False or v is None else float(v)


def demo_rich(ep) -> dict:
    """The six S0 features plus aggregates of the TFG's per-demonstration
    nodes, which the extractor computes from the demonstrations alone."""
    nodes = ep["full_engine_tfg"]["nodes"]
    delta = [n["attrs"] for n in nodes if n["kind"] == "delta_signature"]
    pal = [n["attrs"] for n in nodes if n["kind"] == "palette_change"]
    shape = [n["attrs"] for n in nodes if n["kind"] == "shape_change"]
    out = {k: _num(ep["demo_features"][k]) for k in D_AGG_FIELDS}

    def frac(xs, key):
        return sum(1 for x in xs if x.get(key)) / len(xs) if xs else 0.0

    def agg(xs, key, how):
        vals = [_num(x.get(key)) for x in xs]
        if not vals:
            return 0.0
        return {"mean": sum(vals) / len(vals), "min": min(vals), "max": max(vals)}[how]

    out["same_shape_fraction"] = frac(delta, "same_shape")
    out["shrinks_fraction"] = frac(delta, "shrinks")
    out["grows_fraction"] = frac(delta, "grows")
    for key, hows in (("introduced", ("min", "max")), ("removed", ("min", "max")),
                      ("n_in", ("mean", "min", "max")), ("n_out", ("mean", "min", "max"))):
        for how in hows:
            out[f"{key}_{how}"] = agg(pal, key, how)
    for key in ("cells_changed", "fraction_changed"):
        for how in ("min", "max"):
            out[f"{key}_{how}"] = agg(shape, key, how)
    return {k: out[k] for k in D_RICH_FIELDS}


def _tokens(value):
    if isinstance(value, dict):
        if "op" in value:
            yield str(value["op"])
        for v in value.values():
            yield from _tokens(v)
    elif isinstance(value, list):
        for v in value:
            yield from _tokens(v)
    elif isinstance(value, str):
        yield value


def _bucket(token):
    return hashlib.sha256(f"v15-sel|{token}".encode()).digest()[0] % SELECTOR_BUCKETS


def search_view(ep) -> dict:
    """Counts from the reasoner's own emitted trajectory: candidate formation
    (S2), selector induction (S3, from event order) and fitting (S4)."""
    events = [(json.loads(a), o) for a, o in ep["trajectory"]]
    out = {k: 0.0 for k in F_SEARCH_FIELDS}
    literals = []
    for i, (ast, o) in enumerate(events):
        op = ast[0] if isinstance(ast, list) and ast else ""
        delta = op.split(":", 1)[1] if ":" in op else ""
        payload = ast[1][0] if isinstance(ast, list) and len(ast) == 2 and \
            isinstance(ast[1], list) and ast[1] and isinstance(ast[1][0], dict) else {}
        if o == "typed":
            out["n_typed"] += 1
            if delta in DELTA_TYPES:
                out[f"typed_delta_{delta}"] += 1
            nxt = events[i + 1][1] if i + 1 < len(events) else None
            if nxt in ("slot_fit_failed", "slot_fit_ok"):
                out["n_selector_induced"] += 1
            else:
                out["n_no_selector"] += 1
        elif o in ("slot_fit_failed", "slot_fit_ok"):
            out["n_slot_fit_ok" if o == "slot_fit_ok" else "n_slot_fit_failed"] += 1
            if o == "slot_fit_ok" and delta in DELTA_TYPES:
                out[f"fit_ok_delta_{delta}"] += 1
            selector = payload.get("selector")
            if isinstance(selector, dict):
                literals.append(_num(selector.get("literals")))
                for tok in _tokens(selector.get("predicate")):
                    out[f"selector_bucket_{_bucket(tok)}"] += 1
    out["selector_literals_mean"] = sum(literals) / len(literals) if literals else 0.0
    return out


def views(ep) -> dict:
    desc = ep["descriptor"]
    return {"D_RICH": demo_rich(ep),
            "F_S7": {k: _num(desc.get(k)) for k in F_S7_FIELDS},
            "F_NOVSIG": {k: _num(desc.get(k)) for k in F_NOVSIG_FIELDS},
            "F_SEARCH": search_view(ep)}


# --------------------------------------------------------------------------
# the selection query
# --------------------------------------------------------------------------

def _scorer():
    from cora_arc2026 import scorer_fit as SFIT
    return SFIT


def differing_step(tokens_a, tokens_b):
    """The grammar state at the single position where the two targets
    differ, and the two candidate tokens there."""
    ta = [tuple(t) for t in tokens_a]
    tb = [tuple(t) for t in tokens_b]
    diffs = [i for i, (x, y) in enumerate(zip(ta, tb)) if x != y]
    if len(ta) != len(tb) or len(diffs) != 1:
        raise ValueError("candidates must differ in exactly one token")
    i = diffs[0]
    state = CV.GrammarState()
    for tok in ta[:i]:
        state = state.advance(tok)
    legal = state.legal_tokens()
    if ta[i] not in legal or tb[i] not in legal or ta[i][0] != "M":
        raise ValueError("the differing token must be a legal key feature")
    return state, ta[i], tb[i]


def query_key(ep) -> str:
    """Content hash of the task a query shows: its demonstrations only."""
    return hashlib.sha256(json.dumps(ep["demonstrations"], sort_keys=True)
                          .encode()).hexdigest()


def presentation(key, cands):
    """Candidate order by a hash of the task content and the token, never by
    which candidate is true."""
    return tuple(sorted(cands, key=lambda t: hashlib.sha256(
        f"v15-cand|{key}|{json.dumps(list(t))}".encode()).hexdigest()))


def build_queries(groups) -> list:
    SFIT = _scorer()
    out = []
    for gi, g in enumerate(groups):
        by = {(e["target_index"], e["replicate_index"]): e for e in g["episodes"]}
        state, ca, cb = differing_step(by[(0, 0)]["target_tokens"],
                                       by[(1, 0)]["target_tokens"])
        svec = SFIT.state_vector(state)
        for e in sorted(g["episodes"], key=lambda x: (x["target_index"],
                                                      x["replicate_index"])):
            key = query_key(e)
            out.append({"group": gi, "group_digest": g["group_digest"],
                        "t": e["target_index"], "r": e["replicate_index"],
                        "state": svec, "cands": presentation(key, (ca, cb)),
                        "truth": ca if e["target_index"] == 0 else cb,
                        "views": views(e), "key": key,
                        "other_fits": e.get("other_candidate_fits")})
    return out


# --------------------------------------------------------------------------
# the matched shuffle
# --------------------------------------------------------------------------

def matched_shuffle(queries, block="F_S7") -> list:
    """F of every query replaced by F of a demonstration-similar query from a
    DIFFERENT group. Greedy global matching on the standardized D_RICH view
    (pool statistics, no label), ties by index, then 2-cycles; any query left
    unmatched joins a 3-cycle with the nearest matched pair from two other
    groups. Returns the permutation pi, F_shuffled(q) = F(pi[q])."""
    import numpy as np
    n = len(queries)
    X = np.array([[q["views"]["D_RICH"][k] for k in D_RICH_FIELDS]
                  for q in queries], dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    keep = sd > 1e-12
    Z = (X[:, keep] - mu[keep]) / sd[keep]
    grp = [q["group"] for q in queries]
    garr = np.array(grp)
    sq = (Z * Z).sum(axis=1)
    dist = np.maximum(sq[:, None] + sq[None, :] - 2.0 * (Z @ Z.T), 0.0)
    iu, ju = np.triu_indices(n, k=1)
    ok = garr[iu] != garr[ju]
    iu, ju, dd = iu[ok], ju[ok], dist[iu[ok], ju[ok]]
    order = np.lexsort((ju, iu, dd))
    pi, matched = [None] * n, []
    for idx in order:
        i, j = int(iu[idx]), int(ju[idx])
        if pi[i] is None and pi[j] is None:
            pi[i], pi[j] = j, i
            matched.append((i, j))
    for e in [i for i in range(n) if pi[i] is None]:
        best = None
        for (u, v) in matched:
            if grp[u] == grp[e] or grp[v] == grp[e] or pi[u] != v:
                continue
            d = min(dist[e, u], dist[e, v])
            if best is None or d < best[0] - 1e-12:
                best = (d, u, v)
        if best is None:
            raise ValueError("no valid 3-cycle for an unmatched query")
        _, u, v = best
        pi[e], pi[u], pi[v] = u, v, e
    return pi


# --------------------------------------------------------------------------
# the pairwise scorer: LogLinearScorer weights, fitted by Newton's method
# --------------------------------------------------------------------------

def feature_tokens():
    return [t for t in _scorer().TERMINALS if t[0] == "M"]


class FieldStandardizer:
    """The v1.2 Standardizer's rule on an explicit field list: fit-set mean
    and standard deviation, constant fields dropped, never floored."""

    def __init__(self, fields):
        self.fields = tuple(fields)

    def fit(self, rows):
        n = len(rows)
        keep = []
        for i, name in enumerate(self.fields):
            mean = sum(r[i] for r in rows) / n
            sd = math.sqrt(sum((r[i] - mean) ** 2 for r in rows) / n)
            if sd > 1e-9:
                keep.append((name, i, mean, sd))
        self.order = tuple(k[0] for k in keep)
        self.index = tuple(k[1] for k in keep)
        self.mean = [k[2] for k in keep]
        self.std = [k[3] for k in keep]
        return self

    def transform(self, row, active=None):
        return [((row[i] - m) / s) if (active is None or name in active) else 0.0
                for name, i, m, s in zip(self.order, self.index, self.mean, self.std)]


#: conditions: which D fields and which F block are active, and F's source
CONDITIONS = {
    "D": ("D_RICH", None, None),
    "D+F_ASSOC": ("D_RICH", "F_S7", "assoc"),
    "D+F_SHUFFLED": ("D_RICH", "F_S7", "shuffled"),
    "F_ASSOC": (None, "F_S7", "assoc"),
    "D_AGG": ("D_AGG", None, None),
    "D_AGG+F_ASSOC": ("D_AGG", "F_S7", "assoc"),
    "D+F_NOVSIG": ("D_RICH", "F_NOVSIG", "assoc"),
    "D+F_NOVSIG_SHUFFLED": ("D_RICH", "F_NOVSIG", "shuffled"),
    "D+F_SEARCH": ("D_RICH", "F_SEARCH", "assoc"),
    "D+F_SEARCH_SHUFFLED": ("D_RICH", "F_SEARCH", "shuffled"),
}
PRIMARY = ("D", "D+F_ASSOC", "D+F_SHUFFLED")


def design(queries, cond, std, pi=None):
    """Input rows x = [1] + standardized active evidence + grammar state,
    identical width for every condition that shares an F block."""
    dsel, fblock, fsource = CONDITIONS[cond]
    fields = std.fields
    active = set()
    if dsel == "D_RICH":
        active |= set(D_RICH_FIELDS)
    elif dsel == "D_AGG":
        active |= set(D_AGG_FIELDS)
    if fblock is not None:
        active |= {f"{fblock}:{k}" for k in VIEW_BLOCKS[fblock]}
    rows = []
    for idx, q in enumerate(queries):
        src = queries[pi[idx]] if fsource == "shuffled" else q
        raw = [q["views"]["D_RICH"][k] for k in D_RICH_FIELDS]
        fb = fields[len(D_RICH_FIELDS):]
        raw += [src["views"][f.split(":", 1)[0]][f.split(":", 1)[1]] for f in fb]
        rows.append([1.0] + std.transform(raw, active) + list(q["state"]))
    return rows


def standardizer_for(queries, fblock):
    fields = list(D_RICH_FIELDS)
    if fblock is not None:
        fields += [f"{fblock}:{k}" for k in VIEW_BLOCKS[fblock]]
    raw = []
    for q in queries:
        row = [q["views"]["D_RICH"][k] for k in D_RICH_FIELDS]
        if fblock is not None:
            row += [q["views"][fblock][k] for k in VIEW_BLOCKS[fblock]]
        raw.append(row)
    return FieldStandardizer(fields).fit(raw)


def fit_pairs(rows, queries, lam=LAMBDA):
    """Minimize -(1/n) sum log sigma((w_true - w_false) . x) + lam ||W||^2
    over the key-feature rows of LogLinearScorer. Strictly convex, so the
    optimum is unique; Newton's method reaches it to NEWTON_TOL."""
    import numpy as np
    toks = feature_tokens()
    tix = {t: i for i, t in enumerate(toks)}
    X = np.array(rows, dtype=float)
    n, dim = X.shape
    K = len(toks)
    Z = np.zeros((n, K * dim))
    for q_i, q in enumerate(queries):
        a = tix[q["truth"]]
        b = tix[q["cands"][0] if q["cands"][1] == q["truth"] else q["cands"][1]]
        Z[q_i, a * dim:(a + 1) * dim] += X[q_i]
        Z[q_i, b * dim:(b + 1) * dim] -= X[q_i]
    theta = np.zeros(K * dim)
    for it in range(NEWTON_MAX_ITER):
        s = Z @ theta
        p = 1.0 / (1.0 + np.exp(-s))
        grad = -(Z.T @ (1.0 - p)) / n + 2.0 * lam * theta
        H = (Z.T * (p * (1.0 - p))) @ Z / n + 2.0 * lam * np.eye(K * dim)
        step = np.linalg.solve(H, grad)
        theta = theta - step
        if float(np.max(np.abs(step))) < NEWTON_TOL:
            break
    W = theta.reshape(K, dim)
    SFIT = _scorer()
    weights = [[0.0] * dim for _ in SFIT.TERMINALS]
    for t, i in tix.items():
        weights[SFIT.TERMINAL_INDEX[t]] = [float(x) for x in W[i]]
    model = SFIT.LogLinearScorer.__new__(SFIT.LogLinearScorer)
    model.weights, model.dim, model.standardizer = weights, dim, None
    return model, {"iterations": it + 1, "final_step": float(np.max(np.abs(step)))}


def choose(model, x, first, second):
    """The chosen candidate, or None for a tie; order-invariant by
    construction because each token's logit depends only on the token."""
    la, lb = model.logits([first, second], x)
    if abs(la - lb) <= TIE_EPS:
        return None
    return first if la > lb else second


def score_queries(model, rows, queries) -> list:
    out = []
    for x, q in zip(rows, queries):
        first, second = q["cands"]
        false = second if q["truth"] == first else first
        lt, lf = model.logits([q["truth"], false], x)
        margin = lt - lf
        tie = abs(margin) <= TIE_EPS
        c1, c2 = choose(model, x, first, second), choose(model, x, second, first)
        out.append({"units": 1 if tie else (2 if margin > 0 else 0),
                    "nll": math.log1p(math.exp(-margin)) if margin > -30
                    else -margin, "margin": margin, "tie": tie,
                    "order_invariant": c1 == c2})
    return out


def group_units(scored, queries):
    """Per group: accuracy in units of 1/16, mean NLL, mean margin."""
    acc, nll, mar = {}, {}, {}
    for s, q in zip(scored, queries):
        g = q["group"]
        acc[g] = acc.get(g, 0) + s["units"]
        nll.setdefault(g, []).append(s["nll"])
        mar.setdefault(g, []).append(s["margin"])
    gs = sorted(acc)
    return ([acc[g] for g in gs], [sum(nll[g]) / len(nll[g]) for g in gs],
            [sum(mar[g]) / len(mar[g]) for g in gs])


# --------------------------------------------------------------------------
# exact group-level inference
# --------------------------------------------------------------------------

def signflip_p(values) -> Fraction:
    """Exact one-sided P(sum of randomly signed |v| >= observed sum), by
    convolution over integer group values."""
    counts = {0: 1}
    nonzero = 0
    for v in values:
        v = abs(int(v))
        if v == 0:
            continue
        nonzero += 1
        nxt = {}
        for s, c in counts.items():
            nxt[s + v] = nxt.get(s + v, 0) + c
            nxt[s - v] = nxt.get(s - v, 0) + c
        counts = nxt
    obs = sum(int(v) for v in values)
    return Fraction(sum(c for s, c in counts.items() if s >= obs), 2 ** nonzero)


def sign_test_p(values) -> Fraction:
    pos = sum(1 for v in values if v > 0)
    m = sum(1 for v in values if v != 0)
    return sum((Fraction(math.comb(m, i), 2 ** m) for i in range(pos, m + 1)),
               Fraction(0)) if m else Fraction(1)


def summary(values, scale):
    import statistics
    xs = [v / scale for v in values]
    mean = sum(xs) / len(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    se = sd / math.sqrt(len(xs)) if xs else 0.0
    return {"mean": round(mean, 6), "sd": round(sd, 6),
            "ci95": [round(mean - 1.959964 * se, 6), round(mean + 1.959964 * se, 6)],
            "upper95_one_sided": round(mean + 1.644854 * se, 6),
            "p_signflip": float(signflip_p(values)),
            "p_sign_test": float(sign_test_p(values)),
            "groups_positive": sum(1 for v in values if v > 0),
            "groups_negative": sum(1 for v in values if v < 0),
            "groups": len(values)}


# --------------------------------------------------------------------------
# twin positive-control folds
# --------------------------------------------------------------------------

def twin_folds(groups, k=TWIN_FOLDS) -> list:
    """Groups sharing any target digest are kept in one fold; components are
    ordered by their smallest group digest and dealt round-robin."""
    parent = list(range(len(groups)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for i, g in enumerate(groups):
        for d in g["target_digests"]:
            if d in owner:
                parent[find(i)] = find(owner[d])
            else:
                owner[d] = i
    comps = {}
    for i in range(len(groups)):
        comps.setdefault(find(i), []).append(i)
    ordered = sorted(comps.values(), key=lambda c: min(groups[i]["group_digest"] for i in c))
    fold = [None] * len(groups)
    for n, comp in enumerate(ordered):
        for i in comp:
            fold[i] = n % k
    return fold


# --------------------------------------------------------------------------
# leakage boundary of the selection view
# --------------------------------------------------------------------------

def scan_view(view, meta) -> list:
    """Findings; empty means clean. The view may hold only the four frozen
    numeric blocks; no value may echo a digest, a seed or a label."""
    found = []
    if set(view) != set(VIEW_BLOCKS):
        found.append(f"blocks:{sorted(set(view) ^ set(VIEW_BLOCKS))}")
    for block, fields in VIEW_BLOCKS.items():
        vals = view.get(block, {})
        if tuple(vals) != fields:
            found.append(f"fields:{block}")
        for k, v in vals.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                found.append(f"non_numeric:{block}:{k}")
    numbers = {float(v) for b in view.values() if isinstance(b, dict)
               for v in b.values() if isinstance(v, (int, float))}
    probes = set()
    for d in meta.get("digests", []):
        if d:
            probes.add(float(int(d[:8], 16)))
    for s in meta.get("seeds", []):
        if isinstance(s, int) and s >= 1000:
            probes.add(float(s))
    if numbers & probes:
        found.append("leaked_identity_number")
    return found


# --------------------------------------------------------------------------
# the frozen classification ladder
# --------------------------------------------------------------------------

def gates(test, twin=None) -> dict:
    """test/twin: dict with 'acc' (units per group for D+F_ASSOC),
    'd_demo' and 'd_shuffle' (paired unit differences per group)."""
    def g(block):
        a = signflip_p([u - UNITS_PER_GROUP // 2 for u in block["acc"]])
        b = signflip_p(block["d_demo"])
        c = signflip_p(block["d_shuffle"])
        mean_demo = Fraction(sum(block["d_demo"]), UNITS_PER_GROUP * len(block["d_demo"]))
        return {"A_above_chance": bool(sum(block["acc"]) * 2 > UNITS_PER_GROUP * len(block["acc"])
                                       and a < ALPHA),
                "B_beats_demo": bool(sum(block["d_demo"]) > 0 and b < ALPHA),
                "C_beats_shuffle": bool(sum(block["d_shuffle"]) > 0 and c < ALPHA),
                "D_min_effect": bool(mean_demo >= DELTA_MIN),
                "p": {"A": float(a), "B": float(b), "C": float(c)},
                "mean_increment_over_demo": float(mean_demo)}
    out = {"test": g(test)}
    if twin is not None:
        out["twin"] = g(twin)
    return out


def classify(gate_out, n_test, integrity_ok, order_ok, leak_ok, overlap_ok) -> dict:
    t = gate_out["test"]
    tw = gate_out.get("twin")
    primary = t["A_above_chance"] and t["B_beats_demo"] and t["C_beats_shuffle"] \
        and t["D_min_effect"]
    twin_pass = bool(tw and tw["A_above_chance"] and tw["B_beats_demo"]
                     and tw["C_beats_shuffle"] and tw["D_min_effect"])
    label, reason = None, None
    if not (integrity_ok and order_ok and leak_ok and overlap_ok):
        label, reason = "MIXED_OR_INCONCLUSIVE", "integrity"
    elif n_test < FLOOR_GROUPS:
        label, reason = "MIXED_OR_INCONCLUSIVE", "below the floor"
    elif primary:
        label = "FAILURE_CONDITIONED_SELECTION_GENERALIZES"
    elif twin_pass:
        label = "TWIN_ONLY_SELECTION_SIGNAL"
    elif n_test < TEST_GROUPS:
        label, reason = "MIXED_OR_INCONCLUSIVE", "negative below the powered size"
    elif not t["C_beats_shuffle"]:
        label = "FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION"
    elif not (t["B_beats_demo"] and t["D_min_effect"]):
        label, reason = "DEMONSTRATIONS_SUFFICIENT_FOR_SELECTION", \
            "FAILURE_CONDITIONING_INCREMENT_NOT_ESTABLISHED"
    else:
        label, reason = "MIXED_OR_INCONCLUSIVE", "conflicting primary gates"
    return {"classification": label, "reason": reason,
            "primary_gates_pass": primary, "twin_control_pass": twin_pass,
            "test_groups": n_test, "powered": n_test >= TEST_GROUPS}
