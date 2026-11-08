"""The CALIBRATED acceptance rule (PROTOCOL.md section 6). New code; everything it calls from U5 is imported
read-only and unchanged: the grammar and its units (u5core), the program enumeration, selection and conflict rule
(u5policy), image sets, exact certification and edit application (u5run).

For one operator w on the current segmentation of the calibration images:
1. Programs are U5's (theta, guard) enumeration for w over all calibration units (u5policy.Space, unchanged), scored
   per IMAGE: each image is its own parent, so per-image F1 changes are exact sums of the units' effects (dTP, dN).
   Each accepted unit is also judged alone, as U5's evaluator judges edits: beneficial (more matched objects, or an
   unmatched object removed), harmful (fewer matched objects, or an unmatched object added), neutral otherwise.
2. Leave-one-organ-out cross-fitting over the calibration organs. In the fold of organ o, the fold program is the one
   with the largest pooled F1 gain on the other organs among programs that make at least one edit there, have no
   conflicting selection (U5 Amendment 3), raise the pooled F1, and have a harmful-edit rate (harmful / accepted) of
   at most LAMBDA on those organs; ties as U5 (fewer edits, fewer predicates, enumeration order). It is applied to
   organ o's images, giving out-of-fold per-image F1 changes and edit counts (a fold without a program abstains).
   LAMBDA (0.40) is stricter than the bound ALPHA because a program chosen on some organs is more harmful on others
   (development: the out-of-organ harmful rate exceeded the in-fold limit at every scanned setting).
3. Calibrated acceptance: w is accepted only if the one-sided lower bound of the mean out-of-fold per-image F1
   change is above 0 AND the one-sided upper bound of the out-of-fold harmful-edit rate is at most ALPHA. Both are
   organ-clustered t bounds (cluster-robust standard errors over the organs, Student t with organs - 1 degrees of
   freedom; the ratio by linearization), one-sided at level FWER. The K operators of an arm are tested in the arm's
   order as a fixed sequence: testing stops at the first operator that is not accepted, which keeps the family-wise
   error at FWER without splitting it. An operator with no out-of-fold edit is not accepted. Organ-cluster bootstrap
   bounds (B_BOOT resamples, default_rng(0)) are recorded beside them, descriptive only: with 12 or fewer organs the
   percentile bootstrap is too narrow (development: it accepted 20 of 120 pure-noise operators at a nominal 5%;
   the t bounds accepted 9 of 120).
4. If accepted, the final program is chosen by the same rule on all calibration organs, certified by exact
   execution (u5run.certify), and applied to the calibration images and, if given, to the query images. The
   calibration images then carry its edits before the next operator is processed (as U5's run_policy)."""
import time

import numpy as np

import u5core as C
import u5policy as P
import u5run as RN

ALPHA = 0.60            # the calibrated bound on the harmful-edit rate (harmful / accepted), certified out of organ
LAMBDA = 0.40           # the in-fold limit on the harmful-edit rate when a fold program is chosen
FWER = 0.05             # one-sided level of each test; fixed-sequence testing over an arm's operators
B_BOOT = 10000
SEED = 0


class ImageParents(RN.ImgSet):
    """A U5 image set whose parents are the single images, so that U5's Space, certification and edit application
    work per image; `organ[u]` keeps U5's parent (the organ) of every image."""

    def __init__(self, ds, uids, stage="S", with_ref=False, labels=None, share=None):
        super().__init__(ds, uids, stage, with_ref, labels, share)
        self.organ = dict(self.parent)
        self.parent = {u: u for u in self.uids}
        self.parents = sorted(self.uids)
        self.pidx = {u: i for i, u in enumerate(self.parents)}


def judged(dtp, dn):
    """U5's judged-alone classes of single edits (u5eval._replay): (beneficial, harmful) boolean arrays."""
    dtp, dn = np.asarray(dtp), np.asarray(dn)
    ben = (dtp > 0) | ((dtp == 0) & (dn < 0))
    harm = (dtp < 0) | ((dtp == 0) & (dn > 0))
    return ben, harm


def judged_sums(sp, du):
    """Per program (in sp.progs order) and image: accepted (selected) units, harmful units, beneficial units."""
    n = sp.P
    par = du["parent"]
    A, H, Bf = [], [], []
    for t in range(sp.T):
        F, V = du["feats"][t], du["valid"][t]
        pr = sp.preds[t]
        Pm = P.pred_matrix(pr, F)
        G = P.guards(pr)
        ben, harm = judged(du["dTP"][t], du["dN"][t]) if len(par) else (np.zeros(0, bool), np.zeros(0, bool))
        Wm = np.zeros((len(par), 3 * n), np.float32)
        if len(par):
            r = np.arange(len(par))
            Wm[r, par] = 1.0
            Wm[r, n + par] = harm
            Wm[r, 2 * n + par] = ben
        for c0 in range(0, len(G), P.CHUNK):
            gs = G[c0:c0 + P.CHUNK]
            S = np.empty((len(gs), len(par)), bool)
            for k, g in enumerate(gs):
                s = V.copy()
                for i in g:
                    s &= Pm[i]
                S[k] = s
            M = S.astype(np.float32) @ Wm
            A.append(M[:, :n])
            H.append(M[:, n:2 * n])
            Bf.append(M[:, 2 * n:])
    cat = lambda x: np.concatenate(x) if x else np.zeros((0, n))   # noqa: E731
    A, H, Bf = cat(A), cat(H), cat(Bf)
    assert len(A) == len(sp.progs), (len(A), len(sp.progs))
    return A, H, Bf


def fold_program(sp, A, H, keep, alpha=LAMBDA):
    """The fold (or final) program on images `keep`: largest pooled F1 gain among programs with >= 1 edit, no
    conflicting selection, positive gain and harmful-edit rate <= alpha (the in-fold limit) on those images; ties as
    U5. None if empty."""
    if not keep.any() or not len(sp.progs):
        return None
    G = sp.pooled_gain(keep)
    E = A[:, keep].sum(1)
    Hk = H[:, keep].sum(1)
    ok = (E > 0) & ~sp.conflicted & (G > 1e-12) & (Hk <= alpha * E + 1e-9)
    if not ok.any():
        return None
    idx = np.flatnonzero(ok)
    return int(min(idx, key=lambda i: (-round(float(G[i]), 12), int(E[i]), int(sp.npred[i]), int(i))))


def cluster_bounds(organ_idx, n_org, d, h, a, level, B_=B_BOOT, seed=SEED):
    """Organ-cluster bootstrap: one-sided lower bound of the mean per-image change d, one-sided upper bound of the
    ratio sum(h) / sum(a) (resamples with no edit are excluded and counted)."""
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, n_org, (B_, n_org))
    cnt = np.zeros((B_, n_org))
    rows = np.arange(B_)
    for j in range(n_org):
        np.add.at(cnt, (rows, pick[:, j]), 1.0)
    Sd = np.bincount(organ_idx, d, n_org)
    Sn = np.bincount(organ_idx, minlength=n_org).astype(float)
    Sh = np.bincount(organ_idx, h, n_org)
    Sa = np.bincount(organ_idx, a, n_org)
    mean_b = (cnt @ Sd) / np.maximum(cnt @ Sn, 1e-12)
    lcb = float(np.percentile(mean_b, 100 * level))
    den = cnt @ Sa
    ok = den > 0
    ucb = float(np.percentile((cnt @ Sh)[ok] / den[ok], 100 * (1 - level))) if a.sum() > 0 and ok.any() else None
    return {"mean_gain": float(d.mean()), "lcb_gain": lcb,
            "harmful_rate": float(h.sum() / a.sum()) if a.sum() > 0 else None, "ucb_harmful_rate": ucb,
            "resamples_without_edits": int((~ok).sum()), "level_one_sided": level}


def cluster_t_bounds(organ_idx, n_org, d, h, a, level):
    """Organ-clustered t bounds: the image-weighted mean of d with a cluster-robust standard error (CR1: residual
    organ sums, factor G / (G - 1)), and the ratio sum(h) / sum(a) with its linearized cluster-robust standard error;
    Student t quantile with G - 1 degrees of freedom, one-sided at `level`. G counts organs with images."""
    from scipy import stats
    n_o = np.bincount(organ_idx, minlength=n_org).astype(float)
    use = n_o > 0
    G = int(use.sum())
    Sd = np.bincount(organ_idx, d, n_org)[use]
    Sh = np.bincount(organ_idx, h, n_org)[use]
    Sa = np.bincount(organ_idx, a, n_org)[use]
    n_o = n_o[use]
    N = n_o.sum()
    tq = float(stats.t.ppf(1 - level, G - 1)) if G > 1 else float("inf")
    mean = Sd.sum() / N
    se = float(np.sqrt(G / (G - 1) * np.sum((Sd - mean * n_o) ** 2)) / N) if G > 1 else float("inf")
    out = {"mean_gain": float(mean), "lcb_gain": float(mean - tq * se), "se_gain": se, "t_quantile": tq,
           "organs": G, "level_one_sided": level, "harmful_rate": None, "ucb_harmful_rate": None, "se_harmful_rate": None}
    if Sa.sum() > 0:
        r = Sh.sum() / Sa.sum()
        se_r = float(np.sqrt(G / (G - 1) * np.sum((Sh - r * Sa) ** 2)) / Sa.sum()) if G > 1 else float("inf")
        out.update(harmful_rate=float(r), ucb_harmful_rate=float(min(1.0, r + tq * se_r)), se_harmful_rate=se_r)
    return out


def calibrate_op(sp, A, H, Bf, organ_idx, n_org, K, alpha=ALPHA, lam=LAMBDA, bounds_kind="t", level=FWER):
    """Steps 2 and 3 for one operator: fold programs under the in-fold limit `lam`, certification against the bound
    `alpha`. Returns the acceptance record and the final program index (or None). bounds_kind="bootstrap" with
    level=FWER / 3 and lam=alpha reproduces the first development version (development/v1_alpha020)."""
    n = sp.P
    d, h, a, b = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    tops, per_organ = [], []
    for o in range(n_org):
        test = organ_idx == o
        top = fold_program(sp, A, H, ~test, lam)
        tops.append(top)
        if top is not None:
            d[test] = (sp.f1_new[top] - sp.f1_base)[test]
            h[test], a[test], b[test] = H[top, test], A[top, test], Bf[top, test]
        per_organ.append({"organ_index": o, "images": int(test.sum()), "fold_program": top,
                          "mean_gain": float(d[test].mean()) if test.any() else 0.0,
                          "accepted": int(a[test].sum()), "harmful": int(h[test].sum()),
                          "beneficial": int(b[test].sum())})
    tb = cluster_t_bounds(organ_idx, n_org, d, h, a, level)
    boot = cluster_bounds(organ_idx, n_org, d, h, a, level)
    bounds = tb if bounds_kind == "t" else boot
    final = fold_program(sp, A, H, np.ones(n, bool), lam)
    if a.sum() == 0:
        status = "NO_OUT_OF_FOLD_EDIT"
    elif not bounds["lcb_gain"] > 0:
        status = "GAIN_NOT_CERTIFIED"
    elif bounds["ucb_harmful_rate"] is None or bounds["ucb_harmful_rate"] > alpha:
        status = "HARM_NOT_CERTIFIED"
    elif final is None:
        status = "NO_FINAL_PROGRAM"
    else:
        status = "ACCEPTED"
    rec = {"status": status, "alpha": alpha, "lambda_in_fold": lam, "K": K, **bounds,
           "out_of_fold": {"accepted": int(a.sum()), "harmful": int(h.sum()), "beneficial": int(b.sum()),
                           "images": int(n), "organs_with_fold_program": int(sum(t is not None for t in tops))},
           "per_organ": per_organ, "fold_programs": [None if t is None else int(t) for t in tops],
           "final_program": final, "bounds_kind": bounds_kind, "bootstrap_bounds_descriptive": boot,
           "t_bounds": tb}
    return rec, (final if status == "ACCEPTED" else None)


def _prog_text(sp, i):
    t, g = sp.progs[i]
    pr = sp.preds[t]
    return {"theta_index": int(t), "theta": C.THETA[sp.op][t] if hasattr(sp, "op") else None,
            "guard": [[C.FEATS[sp.op][pr[k][0]] if hasattr(sp, "op") else pr[k][0], pr[k][1], float(pr[k][2])]
                      for k in g]}


def run_calibrated(grammar, demos, queries=None, K=None, alpha=ALPHA, lam=LAMBDA):
    """The CALIBRATED arm over an ordered operator list. demos: ImageParents with references (calibration images);
    queries: a U5-compatible image set or None. Labels of both sets are updated in place with accepted edits.
    Returns a record in the shape of u5run.run_policy's (ops, query_log, demo_log, query_stats, cpu_s)."""
    K = len(grammar) if K is None else K
    t0 = time.process_time()
    organs = sorted(set(demos.organ.values()))
    oi = {o: i for i, o in enumerate(organs)}
    organ_idx = np.array([oi[demos.organ[u]] for u in demos.parents], int)
    recs, qlog, dlog, qstats = [], [], [], {}
    stopped = False
    for op in grammar:
        if stopped:                          # fixed-sequence testing: no operator after the first one not accepted
            recs.append({"op": op, "status": "NOT_TESTED_FIXED_SEQUENCE"})
            continue
        t1 = time.process_time()
        du = RN.set_units(demos, op)
        sp = P.Space(du, demos.base(), len(demos.parents))
        sp.op = op
        rec = {"op": op, "demo_units": len(du["keys"]), "programs": len(sp.progs)}
        if not len(du["keys"]) or not len(sp.progs):
            rec.update(status="NO_UNITS")
            rec["cpu_s"] = round(time.process_time() - t1, 2)
            recs.append(rec)
            stopped = True
            continue
        A, H, Bf = judged_sums(sp, du)
        acc, final = calibrate_op(sp, A, H, Bf, organ_idx, len(organs), K, alpha, lam)
        rec.update(acc)
        rec["fold_program_text"] = [None if t is None else _prog_text(sp, t) for t in acc["fold_programs"]]
        if final is not None:
            rec["final_program_text"] = _prog_text(sp, final)
            rec["final_calibration"] = {"pooled_gain": float(sp.pooled_gain(np.ones(sp.P, bool))[final]),
                                        "accepted": int(A[final].sum()), "harmful": int(H[final].sum()),
                                        "beneficial": int(Bf[final].sum())}
            # U5 Amendment 3: the decisive programs (final and fold programs) are certified by exact execution
            dec = sorted(set([final] + [t for t in acc["fold_programs"] if t is not None]))
            rec["certification"] = RN.certify(sp, du, demos, dec, op)
            t_top = sp.progs[final][0]
            if queries is not None:
                qu = RN.set_units(queries, op)
                s_q, _ = P.select(sp, final, qu)
                st = qstats.setdefault(op, {})
                for (u, _), x in zip(qu["keys"], s_q):
                    z = st.setdefault(u, [0, 0, 0])
                    z[0] += 1
                    z[2] += int(x)
                b_q = len(qlog)
                qlog += RN.apply_accepted(queries, op, qu["keys"], s_q, np.where(s_q, t_top, -1))
                rec["query_units"], rec["query_accepted"] = len(qu["keys"]), int(s_q.sum())
                rec["query_applied"] = len(qlog) - b_q
            s_d, _ = P.select(sp, final, du)
            b_d = len(dlog)
            dlog += RN.apply_accepted(demos, op, du["keys"], s_d, np.where(s_d, t_top, -1))
            rec["demo_applied"] = len(dlog) - b_d
        rec["cpu_s"] = round(time.process_time() - t1, 2)
        recs.append(rec)
        stopped = final is None
    return {"ops": recs, "query_log": qlog, "demo_log": dlog, "query_stats": qstats, "rule": "calibrated",
            "alpha": alpha, "lambda_in_fold": lam, "K": K, "cpu_s": round(time.process_time() - t0, 2),
            "cpu_s_exact": time.process_time() - t0}
