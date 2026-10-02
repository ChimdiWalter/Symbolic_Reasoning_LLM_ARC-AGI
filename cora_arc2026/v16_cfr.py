"""Item-2 v1.6 bounded repair: candidate-conditioned failure response (CFR).

The one repair authorized after v1.5 (FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_
SELECTION). v1.5 asked what the reasoner's failure looks like; this asks what
happens to that failure when one candidate extension is exposed.

The reasoner is the constructive domain's frozen base search K: the baseline
single-block schemas fitted with the occurrence-scoped fitter, which every
admitted episode must defeat. A candidate e is exposed as K + {e}: K's results
are computed once per episode and shared, e is the only added production, and
it is fitted by the same fitter. Nothing is installed or persisted, no module
table is written, and the two candidates of a pair never share probe state.

The v1.5 core (queries, presentation order, D rows, token-pair folds, exact
sign-flip tests) is reused unchanged; see records/ITEM2_V16_DEVELOPMENT_PLAN.md.
"""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction

from cora_arc2026 import v15_sel as S

G, L, CD, CV = S.G, S.L, S.CD, S.CV

RESPONSE_FIELDS = ("loo_exact", "loo_fit_fail", "loo_cell_error", "table_entries")
REPRESENTATIONS = ("R0", "R1", "R2")
LAMBDA = S.LAMBDA
NEWTON_TOL = S.NEWTON_TOL
NEWTON_MAX_ITER = S.NEWTON_MAX_ITER
TIE_EPS = S.TIE_EPS
RESID_RIDGE = 1.0
RESID_FOLDS = 5
CV_FOLDS = 7
ROUND = 12
HELDOUT_PREFIX = "v16-heldout|"
HELDOUT_FIRST_HEX = "01234"


def _sf():
    from cora_tti import scoped_slot_fitting as SF
    return SF


def _meta():
    from geocat_arc.object_reasoning import meta_ast as M
    from geocat_arc.object_reasoning import meta_induction as MI
    return M, MI


def probe_identity() -> str:
    """sha256 of this file; recorded with every response set."""
    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# --------------------------------------------------------------------------
# candidates of a stored group, re-derived and checked against its digests
# --------------------------------------------------------------------------

def group_candidates(record, base):
    """(anchor, contrast) schemas of an admitted slot record, re-derived from
    the pair seed exactly as the generator built them; refuses any mismatch
    with the stored target digests or family."""
    g, slot = record["group"], record["slot"]
    fam = S.FAMILIES[slot % len(S.FAMILIES)]
    if fam != g.get("anchor_family"):
        raise ValueError("family does not match the slot")
    attempt = (g["pair_seed"] - base - slot * S.SLOT_STRIDE) // S.ATTEMPT_STRIDE
    if g["pair_seed"] != base + slot * S.SLOT_STRIDE + attempt * S.ATTEMPT_STRIDE:
        raise ValueError("pair seed is not on the slot lattice")
    anchor = CD.sample_target(g["pair_seed"], G.parse_family(fam))
    contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
    if contrast is None or [CV.digest(anchor), CV.digest(contrast)] != list(g["target_digests"]):
        raise ValueError("re-derived candidates do not match the stored digests")
    return anchor, contrast


def episode_pairs(ep):
    import numpy as np
    return [(np.asarray(d["input"], dtype=int), np.asarray(d["output"], dtype=int))
            for d in ep["demonstrations"]]


# --------------------------------------------------------------------------
# the probe
# --------------------------------------------------------------------------

def baseline_state(pairs) -> dict:
    """K's failure state on these demonstrations: computed once per episode,
    shared by both candidates, never altered by a probe."""
    SF = _sf()
    base = SF.base_search_with_scoped_fitter(pairs)
    fold_exact = []
    for i in range(len(pairs)):
        sub = [p for j, p in enumerate(pairs) if j != i]
        fold_exact.append(SF.base_search_with_scoped_fitter(sub)["exact"])
    cls = ("K_EXACT" if base["exact"] else
           "K_CONSISTENT_INEXACT" if base["fitted"] else "K_NO_CONSISTENT")
    return {"exact": base["exact"], "fitted": base["fitted"],
            "fold_exact": fold_exact, "class": cls}


def _render(ast, grid):
    M, MI = _meta()
    return M.evaluate(ast, grid, MI.descriptors)


def probe(schema, pairs) -> dict:
    """Expose one candidate as K + {e} and measure the leave-one-out
    re-derivation of e on the same demonstrations. Inputs are the schema
    and the demonstrations only."""
    import numpy as np
    SF = _sf()
    n = len(pairs)
    fit, ev = SF.fit_induced_occurrences(schema, pairs)
    entries = (sum(int(s.get("entries", 0)) for s in ev.get("slots", {}).values()) / n
               if fit is not None else 0.0)
    exact = fail = 0
    err = 0.0
    codes = []
    for i in range(n):
        sub = [p for j, p in enumerate(pairs) if j != i]
        f2, ev2 = SF.fit_induced_occurrences(schema, sub)
        if f2 is None:
            fail += 1
            err += 1.0
            codes.append(f"no_fit:{ev2.get('failure')}")
            continue
        target = pairs[i][1]
        try:
            out = _render(f2, pairs[i][0])
        except Exception as exc:                                  # noqa: BLE001
            err += 1.0
            codes.append(f"render_error:{type(exc).__name__}")
            continue
        if out is None or np.asarray(out).shape != target.shape:
            err += 1.0
            codes.append("render_undefined_or_shape")
            continue
        wrong = int(np.count_nonzero(np.asarray(out) != target)) / target.size
        err += wrong
        exact += int(wrong == 0)
        codes.append("exact" if wrong == 0 else "inexact")
    resp = {"loo_exact": exact / n, "loo_fit_fail": fail / n,
            "loo_cell_error": err / n, "table_entries": entries}
    resp = {k: round(float(v), ROUND) for k, v in resp.items()}
    cls = "LOO_ALL" if exact == n else ("LOO_NONE" if exact == 0 else "LOO_PARTIAL")
    return {"fits_all": fit is not None, "full_fit_failure": ev.get("failure"),
            "response": resp, "loo_class": cls, "fold_codes": codes}


def episode_responses(anchor, contrast, ep) -> dict:
    pairs = episode_pairs(ep)
    return {"s0": baseline_state(pairs), "anchor": probe(anchor, pairs),
            "contrast": probe(contrast, pairs)}


def state_snapshot() -> str:
    """Hash of every non-callable module-level value of the fitter and the
    meta language, plus K's schema list. Equal before and after any probe."""
    SF = _sf()
    M, MI = _meta()
    items = []
    for mod in (SF, M, MI):
        for k in sorted(vars(mod)):
            v = vars(mod)[k]
            if callable(v) or type(v).__name__ == "module" or k.startswith("__"):
                continue
            items.append([mod.__name__, k, repr(v)])
    items.append(["K", repr(SF.baseline_single_block_schemas())])
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def pair_key(q) -> str:
    return q["pair_key"]


def structural_pair(q) -> str:
    return f"{q['family']}|{q['pair_key']}"


def build_queries(groups, responses) -> list:
    """v1.5 queries plus the per-candidate responses of their own episode.
    `responses[(group_digest, t, r)]` is an episode_responses() result."""
    out = S.build_queries(groups)
    for q in out:
        g = groups[q["group"]]
        by = {(e["target_index"], e["replicate_index"]): e for e in g["episodes"]}
        _, ca, cb = S.differing_step(by[(0, 0)]["target_tokens"],
                                     by[(1, 0)]["target_tokens"])
        role = {ca: "anchor", cb: "contrast"}
        er = responses[(g["group_digest"], q["t"], q["r"])]
        first, second = q["cands"]
        pf, ps = er[role[first]], er[role[second]]
        q["resp"] = {"first": [pf["response"][k] for k in RESPONSE_FIELDS],
                     "second": [ps["response"][k] for k in RESPONSE_FIELDS]}
        q["delta"] = [round(a - b, ROUND) for a, b in zip(q["resp"]["first"], q["resp"]["second"])]
        q["fits"] = {"first": pf["fits_all"], "second": ps["fits_all"]}
        q["ambiguous"] = bool(pf["fits_all"] and ps["fits_all"])
        truth_fits = er[role[q["truth"]]]["fits_all"]
        other = second if q["truth"] == first else first
        q["integrity"] = []
        if not truth_fits:
            q["integrity"].append("truth_does_not_fit")
        if q.get("other_fits") is not None and bool(q["other_fits"]) != bool(er[role[other]]["fits_all"]):
            q["integrity"].append("verification_mismatch_with_record")
        q["s0_class"] = er["s0"]["class"]
        q["transition"] = f"{er['s0']['class']}|{pf['loo_class']}|{ps['loo_class']}"
    return out


# --------------------------------------------------------------------------
# representations
# --------------------------------------------------------------------------

def rms_scale(deltas) -> list:
    """Per-field RMS over the pool; zero for an inactive field. No centering,
    so Delta stays exactly antisymmetric."""
    if not deltas:
        return []
    k = len(deltas[0])
    out = []
    for j in range(k):
        m = math.sqrt(sum(d[j] * d[j] for d in deltas) / len(deltas))
        out.append(m if m > 1e-12 else 0.0)
    return out


def apply_scale(deltas, scale) -> list:
    return [[(d[j] / scale[j]) if scale[j] > 0 else 0.0 for j in range(len(scale))]
            for d in deltas]


def active_fields(scale) -> int:
    return sum(1 for s in scale if s > 0)


def _resid_design(q, which, std):
    toks = S.feature_tokens()
    raw = [q["views"]["D_RICH"][k] for k in S.D_RICH_FIELDS]
    tok = q["cands"][0 if which == "first" else 1]
    onehot = [1.0 if t == tok else 0.0 for t in toks]
    return [1.0] + std.transform(raw) + onehot


def _ridge(X, Y, lam):
    import numpy as np
    X, Y = np.asarray(X, float), np.asarray(Y, float)
    P = lam * np.eye(X.shape[1])
    P[0, 0] = 0.0
    return np.linalg.solve(X.T @ X + P, X.T @ Y)


def residualized(train_q, eval_q, train_groups_digests, std):
    """Cross-fitted residualized Delta: (r_f - r^_f) - (r_s - r^_s), with r^
    from a ridge fit of each response field on standardized D_RICH plus a
    one-hot candidate token. Training-pool residuals are out-of-fold over
    RESID_FOLDS token-pair components; evaluation residuals use a fit on the
    whole training pool. Never fitted on the evaluation pool."""
    import numpy as np

    def rows(qs):
        X, Y = [], []
        for q in qs:
            for w in ("first", "second"):
                X.append(_resid_design(q, w, std))
                Y.append(q["resp"][w])
        return X, Y

    def deltas_from(qs, pred):
        out = []
        for i, q in enumerate(qs):
            rf = np.asarray(q["resp"]["first"]) - pred[2 * i]
            rs = np.asarray(q["resp"]["second"]) - pred[2 * i + 1]
            out.append([round(float(v), ROUND) for v in (rf - rs)])
        return out

    gkeys = sorted({q["group_digest"] for q in train_q})
    pseudo = []
    for gd in gkeys:
        q0 = next(q for q in train_q if q["group_digest"] == gd)
        pseudo.append({"group_digest": gd, "target_digests": [],
                       "pair": q0["pair_key"]})
    inner = _component_folds(pseudo, RESID_FOLDS)
    fold_of = {p["group_digest"]: f for p, f in zip(pseudo, inner)}
    Xtr, Ytr = rows(train_q)
    pred_tr = np.zeros((len(Xtr), len(RESPONSE_FIELDS)))
    for f in range(RESID_FOLDS):
        fit_idx = [i for i, q in enumerate(train_q) if fold_of[q["group_digest"]] != f]
        hold = [i for i, q in enumerate(train_q) if fold_of[q["group_digest"]] == f]
        if not hold:
            continue
        if not fit_idx:
            raise ValueError("residualizer inner fold without fitting data")
        Xf = [Xtr[2 * i + w] for i in fit_idx for w in (0, 1)]
        Yf = [Ytr[2 * i + w] for i in fit_idx for w in (0, 1)]
        B = _ridge(Xf, Yf, RESID_RIDGE)
        for i in hold:
            for w in (0, 1):
                pred_tr[2 * i + w] = np.asarray(Xtr[2 * i + w]) @ B
    B_all = _ridge(Xtr, Ytr, RESID_RIDGE)
    Xev, _ = rows(eval_q)
    pred_ev = np.asarray(Xev) @ B_all if Xev else np.zeros((0, len(RESPONSE_FIELDS)))
    return deltas_from(train_q, pred_tr), deltas_from(eval_q, pred_ev)


# --------------------------------------------------------------------------
# folds
# --------------------------------------------------------------------------

def _component_folds(items, k) -> list:
    """Connected components of items sharing a target digest or a candidate
    token pair, ordered by smallest group digest, dealt round-robin."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for i, it in enumerate(items):
        keys = list(it.get("target_digests", [])) + ["pair:" + it["pair"]]
        for d in keys:
            if d in owner:
                parent[find(i)] = find(owner[d])
            else:
                owner[d] = i
    comps = {}
    for i in range(len(items)):
        comps.setdefault(find(i), []).append(i)
    ordered = sorted(comps.values(), key=lambda c: min(items[i]["group_digest"] for i in c))
    fold = [None] * len(items)
    for n, comp in enumerate(ordered):
        for i in comp:
            fold[i] = n % k
    return fold


def group_items(groups, queries) -> list:
    pk = {}
    for q in queries:
        pk.setdefault(q["group"], q["pair_key"])
    return [{"group_digest": g["group_digest"], "target_digests": list(g["target_digests"]),
             "pair": pk[i]} for i, g in enumerate(groups)]


def cv_a_folds(groups, queries, k=CV_FOLDS) -> list:
    return _component_folds(group_items(groups, queries), k)


def cv_b_folds(groups, k=CV_FOLDS) -> list:
    order = sorted(range(len(groups)), key=lambda i: groups[i]["group_digest"])
    fold = [None] * len(groups)
    for n, i in enumerate(order):
        fold[i] = n % k
    return fold


def heldout_pair(pk: str) -> bool:
    """Frozen transfer rule: a token pair is held out of the final training
    set when its hash starts with a hex digit in HELDOUT_FIRST_HEX."""
    return hashlib.sha256((HELDOUT_PREFIX + pk).encode()).hexdigest()[0] in HELDOUT_FIRST_HEX


# --------------------------------------------------------------------------
# the matched shuffle of complete response units
# --------------------------------------------------------------------------

def response_shuffle(queries) -> list:
    """pi[i] = donor of query i: a different group with the same verification
    status, the same candidate token pair first, else the same family; nearest
    by pool-standardized D_RICH; greedy 2-cycles, ties by index; any leftover
    joins a 3-cycle with the nearest matched pair from two other groups."""
    import numpy as np
    n = len(queries)
    if n < 3:
        raise ValueError("a shuffle needs at least three queries")
    X = np.array([[q["views"]["D_RICH"][k] for k in S.D_RICH_FIELDS] for q in queries], float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    keep = sd > 1e-12
    Z = (X[:, keep] - mu[keep]) / sd[keep] if keep.any() else np.zeros((n, 1))
    sq = (Z * Z).sum(axis=1)
    dist = np.maximum(sq[:, None] + sq[None, :] - 2.0 * (Z @ Z.T), 0.0)
    grp = np.array([q["group"] for q in queries])
    amb = np.array([bool(q["ambiguous"]) for q in queries])
    pk = np.array([q["pair_key"] for q in queries])
    fam = np.array([str(q["family"]) for q in queries])
    iu, ju = np.triu_indices(n, k=1)
    ok = (grp[iu] != grp[ju]) & (amb[iu] == amb[ju])
    iu, ju = iu[ok], ju[ok]
    dd = dist[iu, ju]
    same_pk, same_fam = pk[iu] == pk[ju], fam[iu] == fam[ju]
    pi, matched = [None] * n, []
    for sel in (same_pk, same_fam & ~same_pk):
        I, J, D = iu[sel], ju[sel], dd[sel]
        for idx in np.lexsort((J, I, D)):
            i, j = int(I[idx]), int(J[idx])
            if pi[i] is None and pi[j] is None:
                pi[i], pi[j] = j, i
                matched.append((i, j))
    for e in [i for i in range(n) if pi[i] is None]:
        best = None
        for (u, v) in matched:
            if grp[u] == grp[e] or grp[v] == grp[e] or pi[u] != v or pi[v] != u:
                continue
            key = (0 if amb[u] == amb[e] == amb[v] else 1,
                   0 if fam[u] == fam[e] == fam[v] else 1,
                   min(dist[e, u], dist[e, v]), u, v)
            if best is None or key < best[0]:
                best = (key, u, v)
        if best is None:
            raise ValueError("no valid 3-cycle for an unmatched query")
        _, u, v = best
        pi[e], pi[u], pi[v] = u, v, e
    return pi


def donor_deltas(queries, pi, deltas) -> list:
    """The donor's complete Delta, re-oriented to the recipient's candidate
    order by token identity when the token pair is the same."""
    out = []
    for i, q in enumerate(queries):
        j = pi[i]
        d = list(deltas[j])
        if queries[j]["pair_key"] == q["pair_key"] and queries[j]["cands"][0] != q["cands"][0]:
            d = [-v for v in d]
        out.append(d)
    return out


def shuffle_fidelity(queries, pi) -> dict:
    import numpy as np
    n = len(queries)
    X = np.array([[q["views"]["D_RICH"][k] for k in S.D_RICH_FIELDS] for q in queries], float)
    Y = X[pi]
    cors = [float(np.corrcoef(X[:, j], Y[:, j])[0, 1]) for j in range(X.shape[1])
            if X[:, j].std() > 1e-12 and Y[:, j].std() > 1e-12]
    share = lambda f: round(sum(1 for i in range(n) if f(queries[i]) == f(queries[pi[i]])) / n, 6)
    return {"same_pair_share": share(lambda q: q["pair_key"]),
            "same_family_share": share(lambda q: q["family"]),
            "same_status_share": share(lambda q: q["ambiguous"]),
            "same_group_count": sum(1 for i in range(n) if queries[i]["group"] == queries[pi[i]]["group"]),
            "mean_field_correlation": round(sum(cors) / len(cors), 6) if cors else None}


# --------------------------------------------------------------------------
# the conditional logit: v1.5 D part plus shared response weights
# --------------------------------------------------------------------------

def d_rows(queries, std) -> list:
    return S.design(queries, "D", std)


def _oriented(q, d):
    """Delta oriented truth-minus-other (training only)."""
    return list(d) if q["truth"] == q["cands"][0] else [-v for v in d]


def fit(queries, rows=None, deltas=None, lam=LAMBDA) -> tuple:
    """Minimize -(1/n) sum log sigma(s_true) + lam ||theta||^2 where
    s = (W[a] - W[b]) . x + v . Delta. With deltas None this is exactly v1.5's
    fit_pairs; with rows None it is the response-only model."""
    import numpy as np
    toks = S.feature_tokens()
    tix = {t: i for i, t in enumerate(toks)}
    n = len(queries)
    blocks = []
    dim = 0
    if rows is not None:
        X = np.array(rows, float)
        dim = X.shape[1]
        Zd = np.zeros((n, len(toks) * dim))
        for i, q in enumerate(queries):
            a = tix[q["truth"]]
            b = tix[q["cands"][0] if q["cands"][1] == q["truth"] else q["cands"][1]]
            Zd[i, a * dim:(a + 1) * dim] += X[i]
            Zd[i, b * dim:(b + 1) * dim] -= X[i]
        blocks.append(Zd)
    k = 0
    if deltas is not None:
        Zr = np.array([_oriented(q, d) for q, d in zip(queries, deltas)], float)
        k = Zr.shape[1]
        blocks.append(Zr)
    Z = np.hstack(blocks)
    p_dim = Z.shape[1]
    theta = np.zeros(p_dim)
    step = np.zeros(p_dim)
    it = 0
    for it in range(NEWTON_MAX_ITER):
        s = Z @ theta
        p = 1.0 / (1.0 + np.exp(-s))
        grad = -(Z.T @ (1.0 - p)) / n + 2.0 * lam * theta
        H = (Z.T * (p * (1.0 - p))) @ Z / n + 2.0 * lam * np.eye(p_dim)
        step = np.linalg.solve(H, grad)
        theta = theta - step
        if float(np.max(np.abs(step))) < NEWTON_TOL:
            break
    W = theta[: len(toks) * dim].reshape(len(toks), dim) if dim else None
    v = theta[len(toks) * dim:] if k else None
    final = float(np.max(np.abs(step))) if p_dim else 0.0
    model = {"tokens": toks, "W": W, "v": v, "dim": dim, "k": k}
    return model, {"iterations": it + 1, "final_step": final,
                   "converged": bool(final < NEWTON_TOL)}


def margin(model, q, x=None, d=None, order=None) -> float:
    """Logit of order[0] minus order[1] (default: presentation order)."""
    import numpy as np
    first, second = order or q["cands"]
    s = 0.0
    if model["W"] is not None:
        tix = {t: i for i, t in enumerate(model["tokens"])}
        s += float((model["W"][tix[first]] - model["W"][tix[second]]) @ np.asarray(x, float))
    if model["v"] is not None:
        dd = list(d) if (first, second) == tuple(q["cands"]) else [-v for v in d]
        s += float(model["v"] @ np.asarray(dd, float))
    return s


def score(model, queries, rows=None, deltas=None) -> list:
    out = []
    for i, q in enumerate(queries):
        x = rows[i] if rows is not None else None
        d = deltas[i] if deltas is not None else None
        first, second = q["cands"]
        s12 = margin(model, q, x, d, (first, second))
        s21 = margin(model, q, x, d, (second, first))
        c1 = None if abs(s12) <= TIE_EPS else (first if s12 > 0 else second)
        c2 = None if abs(s21) <= TIE_EPS else (second if s21 > 0 else first)
        m = s12 if q["truth"] == first else -s12
        tie = abs(m) <= TIE_EPS
        out.append({"units": 1 if tie else (2 if m > 0 else 0), "margin": m,
                    "nll": math.log1p(math.exp(-m)) if m > -30 else -m,
                    "tie": tie, "order_invariant": c1 == c2})
    return out


# --------------------------------------------------------------------------
# group-level statistics on the ambiguous population
# --------------------------------------------------------------------------

def ambiguous_group_diffs(queries, units_a, units_b, select=None) -> list:
    """Per group with at least one selected ambiguous query: the integer sum
    of half-credit unit differences a - b over those queries."""
    by = {}
    for q, a, b in zip(queries, units_a, units_b):
        if not q["ambiguous"] or (select is not None and not select(q)):
            continue
        by[q["group"]] = by.get(q["group"], 0) + (a - b)
    return [by[g] for g in sorted(by)]


def ambiguous_counts(queries, select=None) -> dict:
    by = {}
    for q in queries:
        if q["ambiguous"] and (select is None or select(q)):
            by[q["group"]] = by.get(q["group"], 0) + 1
    return by


def increment_summary(queries, units_a, units_b, select=None) -> dict:
    """Mean per-query increment (a - b) on ambiguous queries with a
    group-clustered 95 percent interval and one-sided upper bound, plus the
    exact sign-flip test over group sums."""
    vals = ambiguous_group_diffs(queries, units_a, units_b, select)
    cnt = ambiguous_counts(queries, select)
    m_q = sum(cnt.values())
    if not vals or m_q == 0:
        return {"groups": 0, "queries": 0}
    groups = sorted(cnt)
    tot = sum(vals) / 2.0
    est = tot / m_q
    resid = [(v / 2.0) - est * cnt[g] for v, g in zip(vals, groups)]
    k = len(vals)
    var = (k / (k - 1)) * sum(r * r for r in resid) / (m_q ** 2) if k > 1 else 0.0
    se = math.sqrt(var)
    return {"groups": k, "queries": m_q, "mean_increment": round(est, 6),
            "ci95": [round(est - 1.959964 * se, 6), round(est + 1.959964 * se, 6)],
            "upper95_one_sided": round(est + 1.644854 * se, 6),
            "lower95_one_sided": round(est - 1.644854 * se, 6),
            "p_signflip": float(S.signflip_p(vals)),
            "groups_positive": sum(1 for v in vals if v > 0),
            "groups_negative": sum(1 for v in vals if v < 0)}


def ambiguous_accuracy(queries, units, select=None) -> float | None:
    tot = cnt = 0
    for q, u in zip(queries, units):
        if q["ambiguous"] and (select is None or select(q)):
            tot += u
            cnt += 1
    return round(tot / (2 * cnt), 6) if cnt else None


def end_to_end_accuracy(queries, units) -> float:
    """Decided queries are correct by verification (the true candidate always
    fits); ambiguous queries take the selector's units."""
    tot = sum(2 if not q["ambiguous"] else u for q, u in zip(queries, units))
    return round(tot / (2 * len(queries)), 6)


def above_chance_values(queries, units, select=None) -> list:
    """Per group: integer sum of (units - 1) over ambiguous queries, the
    sign-flip test of accuracy above one half."""
    by = {}
    for q, u in zip(queries, units):
        if q["ambiguous"] and (select is None or select(q)):
            by[q["group"]] = by.get(q["group"], 0) + (u - 1)
    return [by[g] for g in sorted(by)]


def fraction(x) -> str:
    return str(Fraction(x).limit_denominator())


# --------------------------------------------------------------------------
# P0 PURE_CFR: the deterministic lexicographic rule (plan section 13)
# --------------------------------------------------------------------------

#: key order and direction, fixed before any response was read:
#: +1 means the larger value wins, -1 the smaller
P0_KEYS = ("loo_exact", "loo_cell_error", "loo_fit_fail", "table_entries")
P0_SIGNS = (1, -1, -1, -1)
P0_TOL = 1e-9


def p0_choice(delta, keys=P0_KEYS):
    """+1 chooses the first candidate, -1 the second, 0 no choice. Reads only
    the sign of Delta = r(first) - r(second) key by key, so it is exactly
    antisymmetric: p0_choice(-delta) == -p0_choice(delta)."""
    idx = {k: i for i, k in enumerate(RESPONSE_FIELDS)}
    for key, sign in zip(P0_KEYS, P0_SIGNS):
        if key not in keys:
            continue
        v = delta[idx[key]] * sign
        if v > P0_TOL:
            return 1
        if v < -P0_TOL:
            return -1
    return 0


def p0_units(q, delta, keys=P0_KEYS, fallback_units=None) -> int:
    """Half-credit units of the P0 decision on a query; a tie takes the
    fallback units when given (P0_then_D), else 1."""
    c = p0_choice(delta, keys)
    if c == 0:
        return 1 if fallback_units is None else fallback_units
    chosen = q["cands"][0] if c > 0 else q["cands"][1]
    return 2 if chosen == q["truth"] else 0


def p0_key_diagnostics(queries, deltas, select=None) -> dict:
    """Per key: how often it is the deciding key on ambiguous queries, and how
    often its fixed direction points at the truth when it decides."""
    idx = {k: i for i, k in enumerate(RESPONSE_FIELDS)}
    out = {}
    for key, sign in zip(P0_KEYS, P0_SIGNS):
        decides = right = 0
        for q, d in zip(queries, deltas):
            if not q["ambiguous"] or (select is not None and not select(q)):
                continue
            earlier = [k2 for k2 in P0_KEYS[:P0_KEYS.index(key)]]
            if any(abs(d[idx[k2]]) > P0_TOL for k2 in earlier):
                continue
            v = d[idx[key]] * sign
            if abs(v) <= P0_TOL:
                continue
            decides += 1
            chosen = q["cands"][0] if v > 0 else q["cands"][1]
            right += int(chosen == q["truth"])
        out[key] = {"decides": decides, "direction_right": right,
                    "direction_right_share": round(right / decides, 6) if decides else None}
    return out
