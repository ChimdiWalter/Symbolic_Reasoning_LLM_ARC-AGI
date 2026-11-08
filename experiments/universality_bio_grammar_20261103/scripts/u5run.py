"""U5 runner: STRONG_NATIVE (section 5), image sets with unit caching, the section 10 policy over an ordered grammar,
and admission (section 9). <python environment>, python -I."""
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import u5core as C      # noqa: E402
import u5policy as P    # noqa: E402

R = "/path/to/repository"
U1 = os.path.join(R, "experiments/universality_submitted_pkg_20261101/scripts")
DATA = "/path/to/bio_data"
W = os.path.join(DATA, "work")


def man(ds):
    return json.load(open(os.path.join(W, ds, "DATA_MANIFEST.json")))


def lab(ds, stage, u):
    return np.load(os.path.join(W, ds, "seg", stage, f"{u}.npz"))["labels"].astype(np.int32)


def inten(ds, u):
    return np.load(os.path.join(W, ds, "int", f"{u}.npy")).astype(np.float32)


def refign(ds, u):
    z = np.load(os.path.join(W, ds, "ref_cal", f"{u}.npz"))
    return z["ref"].astype(np.int32), z["ign"]


# ------------------------------------------------------------------------------------------------ strong native ----
def strong_native(ds, side):
    """S = TUNED minus the best single-feature deletion rule of U4's C3 grammar, chosen on calibration."""
    sys.path.insert(0, R)
    sys.path.insert(0, U1)
    import adapter as AD
    from cora_cross_domain_transfer.adapters import bbbc039 as B
    m = man(ds)
    rp = os.path.join(W, ds, "seg", "STRONG_NATIVE_RULE.json")
    os.makedirs(os.path.join(W, ds, "seg", "S"), exist_ok=True)

    def feats(L, I):
        F = B.Features(L, I)
        return {k: np.asarray(F.get(k), float) for k in AD.FEATS}

    if side == "calibration":
        t0 = time.process_time()
        cal = sorted(u for u, v in m["images"].items() if v["side"] == "calibration")
        Fs, stats = {}, {}
        for u in cal:
            L, I = lab(ds, "tuned", u), inten(ds, u)
            ref, ign = refign(ds, u)
            Fs[u] = feats(L, I)
            stats[u] = (int(ref.max()), C.pred_tp(ref, L), C.counted_mask(L, ign))
        pf = {f: np.concatenate([Fs[u][f][1:] for u in cal]) for f in AD.FEATS}
        best = None
        for k, rule in enumerate(AD.c3_rules(pf)):
            nr = npd = tp = dels = 0
            for u in cal:
                d = AD.rule_deletes(rule, Fs[u])
                keep = stats[u][2] & ~d
                nr += stats[u][0]
                npd += int(keep.sum())
                tp += int((keep & stats[u][1]).sum())
                dels += int(d[stats[u][2]].sum())
            f1 = C.f1_of(nr, npd, tp)
            key = (-round(f1, 12), dels, k)
            if best is None or key < best[0]:
                best = (key, rule, f1)
        json.dump({"rule": list(best[1]), "cal_pooled_f1": best[2], "cpu_s": round(time.process_time() - t0, 1)},
                  open(rp, "w"), indent=1)
    rule = tuple(json.load(open(rp))["rule"])
    units = sorted(u for u, v in m["images"].items() if v["side"] == side)
    for u in units:
        L, I = lab(ds, "tuned", u), inten(ds, u)
        d = AD.rule_deletes(rule, feats(L, I))
        x = L.copy()
        x[d[L]] = 0
        np.savez_compressed(os.path.join(W, ds, "seg", "S", f"{u}.npz"), labels=C.relabel(x))
    print(ds, side, "STRONG_NATIVE rule", rule)


# ------------------------------------------------------------------------------------------------ image sets -------
class ImgSet:
    """Images of one dataset for the policy: current labels per uid; demonstrations carry the reference."""

    def __init__(self, ds, uids, stage="S", with_ref=False, labels=None, share=None):
        self.ds, self.uids, self.with_ref = ds, list(uids), with_ref
        mf = man(ds)["images"]
        self.parent = {u: mf[u]["parent"] for u in self.uids}
        self.parents = sorted(set(self.parent.values()))
        self.pidx = {p: i for i, p in enumerate(self.parents)}
        self.L = {u: (labels[u] if labels else lab(ds, stage, u)) for u in self.uids}
        if share is not None:                               # reuse the read-only arrays of another set
            self._I, self._low, self._ref = share._I, share._low, share._ref
        else:
            self._I, self._low, self._ref = {}, {}, {}
        self._img = {}
        self._img_parent = share._img if share is not None else None   # read-only lookups of unchanged images

    def I(self, u):
        if u not in self._I:
            self._I[u] = inten(self.ds, u)
        return self._I[u]

    def low(self, u):
        if u not in self._low:
            p = os.path.join(W, self.ds, "seg", "low", f"{u}.npz")
            self._low[u] = np.load(p)["labels"].astype(np.int32) if os.path.exists(p) else None
        return self._low[u]

    def ref(self, u):
        if u not in self._ref:
            self._ref[u] = refign(self.ds, u)
        return self._ref[u]

    def image(self, u):
        k = (u, C.sha(self.L[u]))
        if k not in self._img and self._img_parent is not None and k in self._img_parent:
            return self._img_parent[k]
        if k not in self._img:
            if self.with_ref:
                WORK["exact_image_matchings"] += 1
                ref, ign = self.ref(u)
                self._img[k] = C.Image(self.L[u], self.I(u), self.low(u), ref, ign)
            else:
                self._img[k] = C.Image(self.L[u], self.I(u), self.low(u))
        return self._img[k]

    def base(self):
        """(P, 3) per-parent n_ref, counted predictions, matched (demonstrations only)."""
        b = np.zeros((len(self.parents), 3))
        for u in self.uids:
            b[self.pidx[self.parent[u]]] += self.image(u).base()
        return b

    def copy_labels(self):
        return {u: self.L[u].copy() for u in self.uids}


_UNITS = {}
WORK = {"exact_image_matchings": 0, "unit_tables": 0, "policy_runs": 0, "exact_certified_programs": 0}


def work_snapshot():
    """Counters of charged work (Amendment 3): exact matchings of whole images, unit tables, policy runs, and the
    program-scoring counters of u5policy."""
    return {**WORK, **{f"policy_{k}": v for k, v in P.WORK.items()}}


def set_units(S, op):
    """Concatenated units of op over an image set (cached by image state)."""
    feats = {t: [] for t in range(len(C.THETA[op]))}
    valid, cls = {t: [] for t in feats}, {t: [] for t in feats}
    dtp, dn = {t: [] for t in feats}, {t: [] for t in feats}
    conf = {t: [] for t in feats}
    parent, img, keys = [], [], []
    for u in S.uids:
        k = (S.ds, u, C.sha(S.L[u]), op, S.with_ref)
        if k not in _UNITS:
            _UNITS[k] = C.units(S.image(u), op, with_effects=S.with_ref)
            WORK["unit_tables"] += 1
        x = _UNITS[k]
        n = len(x["keys"])
        off = len(keys)
        keys += [(u, kk) for kk in x["keys"]]
        parent += [S.pidx[S.parent[u]]] * n
        for t in feats:
            feats[t].append(x["feats"][t])
            valid[t].append(x["valid"][t])
            cls[t].append(x["cls"][t])
            if len(x["conflicts"][t]):
                conf[t].append(x["conflicts"][t] + off)
            if S.with_ref:
                dtp[t].append(x["dTP"][t])
                dn[t].append(x["dN"][t])
    nf = len(C.FEATS[op])
    out = {"keys": keys, "parent": np.array(parent, int),
           "feats": {t: (np.concatenate(v) if v else np.zeros((0, nf))) for t, v in feats.items()},
           "valid": {t: (np.concatenate(v) if v else np.zeros(0, bool)) for t, v in valid.items()},
           "cls": {t: (np.concatenate(v) if v else np.zeros(0, int)) for t, v in cls.items()},
           "conflicts": {t: (np.concatenate(v) if v else np.zeros((0, 2), int)) for t, v in conf.items()}}
    if S.with_ref:
        out["dTP"] = {t: (np.concatenate(v) if v else np.zeros(0, int)) for t, v in dtp.items()}
        out["dN"] = {t: (np.concatenate(v) if v else np.zeros(0, int)) for t, v in dn.items()}
    return out


def apply_accepted(S, op, keys, acc, theta):
    """Apply accepted units (bool over keys) with their theta index through u5core.apply, image by image, and
    reconcile (Amendment 3): accepted == applied == logged must hold for every image and operator."""
    per = {}
    for (u, kk), a, t in zip(keys, acc, theta):
        if a:
            per.setdefault(u, []).append((kk, int(t)))
    log = []
    for u, lst in per.items():
        img = S.image(u)
        newL, applied = C.apply(img, op, lst)
        entries = [{"uid": u, "op": op, "key": kk if not isinstance(kk, tuple) else list(kk), "theta": t,
                    "before_sha": C.sha(S.L[u])} for kk, t in applied]
        if not (len(lst) == len(applied) == len(entries)):
            raise AssertionError(f"accepted {len(lst)} != applied {len(applied)} for {u} {op}")
        log += entries
        S.L[u] = newL
    return log


def certify(sp, du, S, progs, op):
    """Amendment 3: exact certification of decisive programs on the demonstration parents: each program's selected
    edits are applied by u5core.apply on every demonstration image and the whole segmentation is re-matched; the
    per-parent changes in matched and counted objects must equal the scored ones, and nothing may be dropped."""
    n_img = 0
    for i in progs:
        s, _ = P.select(sp, i, du)
        t = sp.progs[i][0]
        per = {}
        for (u, kk), x in zip(du["keys"], s):
            if x:
                per.setdefault(u, []).append((kk, t))
        d = np.zeros((len(S.parents), 2))
        for u, lst in per.items():
            img = S.image(u)
            newL, applied = C.apply(img, op, lst)
            if len(applied) != len(lst):
                raise AssertionError(f"certification: {op} program {i} dropped edits on {u}")
            b0 = img.base()
            ref, ign = S.ref(u)
            b1 = C.Image(newL, S.I(u), S.low(u), ref, ign).base()
            WORK["exact_image_matchings"] += 1
            d[S.pidx[S.parent[u]]] += (b1[2] - b0[2], b1[1] - b0[1])
            n_img += 1
        if not (np.array_equal(d[:, 0], sp.Dtp[i]) and np.array_equal(d[:, 1], sp.Dn[i])):
            raise AssertionError(f"certification: {op} program {i} scored counts differ from exact execution")
    WORK["exact_certified_programs"] = WORK.get("exact_certified_programs", 0) + len(progs)
    return {"programs": len(progs), "image_applications": n_img, "all_equal": True}


# ------------------------------------------------------------------------------------------------ policy -----------
def run_policy(grammar, demos, queries, reverse_check=True, rule="strict"):
    """Section 10 over an ordered grammar. demos: ImgSet with references; queries: ImgSet or None. Labels of both
    sets are updated in place with the accepted edits. Returns per-operator records and edit logs. Amendment 8:
    rule="tolerant" uses `u5policy.verify_tolerant` (the CORA_TOLERANT secondary arm) with the same conflict rule,
    certification and accepted == applied == logged checks; the default is the protocol's rule."""
    assert rule in ("strict", "tolerant"), rule
    verify = P.verify if rule == "strict" else P.verify_tolerant
    recs, qlog, dlog = [], [], []
    qstats = {}
    t0 = time.process_time()
    WORK["policy_runs"] += 1
    for op in grammar:
        du = set_units(demos, op)
        sp = P.Space(du, demos.base(), len(demos.parents))
        npar = len(set(du["parent"].tolist())) if len(du["keys"]) else 0
        res_d = verify(sp, npar, du, reverse_check)
        rec = {"op": op, "status": res_d["status"], "fit": res_d["fit"], "demo_units": len(du["keys"]),
               "top": None if res_d["top"] is None else _prog_text(sp, res_d["top"])}
        if rule != "strict":
            rec.update(rule=rule, n_folds=res_d.get("n_folds"), top_share=res_d.get("top_share"))
        res_q = None
        if res_d["status"] == "EVIDENCE" and queries is not None:
            qu = set_units(queries, op)
            res_q = verify(sp, npar, qu, reverse_check)
            rec["status"] = res_q["status"]
        if res_d["status"] == "EVIDENCE":
            fit_idx = res_d.get("fit_idx", [])
            sample = sorted(np.random.default_rng(0).choice(fit_idx, size=min(50, len(fit_idx)), replace=False).tolist()) \
                if fit_idx else []
            rec["certification"] = certify(sp, du, demos, sorted(set([res_d["top"]] + res_d["fold_tops"] + sample)), op)
        if rec["status"] == "EVIDENCE":
            if res_q is not None:
                before_q = len(qlog)
                st = qstats.setdefault(op, {})
                for (u, _), s_, a_ in zip(qu["keys"], res_q["selected_by_some"], res_q["accepted"]):
                    x = st.setdefault(u, [0, 0, 0])
                    x[0] += 1
                    x[1] += int(s_ and not a_)
                    x[2] += int(a_)
                rec["query_units"] = len(qu["keys"])
                rec["query_accepted"] = int(res_q["accepted"].sum())
                rec["query_abstained"] = int((res_q["selected_by_some"] & ~res_q["accepted"]).sum())
                qlog += apply_accepted(queries, op, qu["keys"], res_q["accepted"], res_q["theta"])
                rec["query_applied"] = len(qlog) - before_q
            rec["demo_accepted"] = int(res_d["accepted"].sum())
            before_d = len(dlog)
            dlog += apply_accepted(demos, op, du["keys"], res_d["accepted"], res_d["theta"])
            rec["demo_applied"] = len(dlog) - before_d
        recs.append(rec)
    return {"ops": recs, "query_log": qlog, "demo_log": dlog, "query_stats": qstats,
            "cpu_s": round(time.process_time() - t0, 2)}


def _prog_text(sp, i):
    t, g = sp.progs[i]
    pr = sp.preds[t]
    return {"theta_index": t, "guard": [[pr[k][0], pr[k][1], pr[k][2]] for k in g]}


# ------------------------------------------------------------------------------------------------ scoring ----------
def score_set(S):
    """Per-parent (n_ref, counted predictions, matched) and pooled F1 for an ImgSet with references."""
    b = S.base()
    nr, n, tp = b.sum(0)
    return b, C.f1_of(nr, n, tp)


def run_policy_proposals(proposals, demos, queries):
    """Section 15: the section 10 rule with the neural proposer's programs as the candidate set, operator by operator
    in canonical order. proposals: {"programs": [{"operator", "theta_index", "guard": [[name, op, q], ...]}]}."""
    recs, qlog, dlog, qstats = [], [], [], {}
    t0 = time.process_time()
    by_op = {}
    bad = 0
    for p in proposals.get("programs", []):
        op = p.get("operator")
        try:
            assert op in C.OPS
            t = int(p["theta_index"])
            assert 0 <= t < len(C.THETA[op])
            g = [(C.FEATS[op].index(f), c, float(q)) for f, c, q in p["guard"]]
            assert len(g) <= 2 and all(c in ("<", ">") for _, c, _ in g) and len({j for j, _, _ in g}) == len(g)
            by_op.setdefault(op, []).append((t, g))
        except Exception:                                    # noqa: BLE001
            bad += 1
    for op in C.OPS:
        if op not in by_op:
            continue
        du = set_units(demos, op)
        sp = P.ProposedSpace(du, demos.base(), len(demos.parents), by_op[op][:2000])
        npar = len(set(du["parent"].tolist())) if len(du["keys"]) else 0
        res_d = P.verify(sp, npar, du)
        rec = {"op": op, "proposals": len(by_op[op]), "status": res_d["status"], "fit": res_d["fit"]}
        res_q = None
        if res_d["status"] == "EVIDENCE":
            # Amendment 5: the same exact certification of decisive programs as run_policy, before any query edit
            fit_idx = res_d.get("fit_idx", [])
            sample = sorted(np.random.default_rng(0).choice(fit_idx, size=min(50, len(fit_idx)), replace=False).tolist()) \
                if fit_idx else []
            rec["certification"] = certify(sp, du, demos, sorted(set([res_d["top"]] + res_d["fold_tops"] + sample)), op)
            qu = set_units(queries, op)
            res_q = P.verify(sp, npar, qu)
            rec["status"] = res_q["status"]
        if rec["status"] == "EVIDENCE":
            st = qstats.setdefault(op, {})
            for (u, _), s_, a_ in zip(qu["keys"], res_q["selected_by_some"], res_q["accepted"]):
                x = st.setdefault(u, [0, 0, 0])
                x[0] += 1
                x[1] += int(s_ and not a_)
                x[2] += int(a_)
            rec["query_accepted"] = int(res_q["accepted"].sum())
            b_q = len(qlog)
            qlog += apply_accepted(queries, op, qu["keys"], res_q["accepted"], res_q["theta"])
            rec["query_applied"] = len(qlog) - b_q
            b_d = len(dlog)
            dlog += apply_accepted(demos, op, du["keys"], res_d["accepted"], res_d["theta"])
            rec["demo_applied"] = len(dlog) - b_d
        recs.append(rec)
    return {"ops": recs, "query_log": qlog, "demo_log": dlog, "query_stats": qstats, "discarded_by_schema": bad,
            "cpu_s": round(time.process_time() - t0, 2)}
