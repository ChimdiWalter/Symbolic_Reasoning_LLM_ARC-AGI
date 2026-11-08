"""U5 verify-or-abstain over object programs (PROTOCOL.md section 10), and the program-scoring machinery shared with
MATCHED_SEARCH (section 12). Pure numpy.

Inputs for one operator: demonstration units (concatenated over demonstration images) with parent index, features
per theta, validity, result class and effects (dTP, dN), plus per-parent base counts (n_ref, n_pred, tp); query units
with features, validity and class. A program is (theta index, guard); a guard is () (true), (p,) or (p, q), predicates
being (feature index, '<' or '>', threshold) at the deciles of the demonstration units."""
import itertools

import numpy as np

RASHOMON, CHUNK = 0.9, 256
DECILES = tuple(range(10, 100, 10))
WORK = {"spaces": 0, "programs_scored": 0, "fits": 0, "program_selections": 0}


def adjacency(pairs, U):
    """Symmetric sparse adjacency of conflicting unit pairs (Amendment 3), or None if there are none."""
    pairs = np.asarray(pairs, int).reshape(-1, 2)
    if not len(pairs):
        return None
    from scipy import sparse
    r = np.r_[pairs[:, 0], pairs[:, 1]]
    c = np.r_[pairs[:, 1], pairs[:, 0]]
    return sparse.csr_matrix((np.ones(len(r), np.float32), (r, c)), shape=(U, U))


def executed(S, A):
    """Units of selection S (bool, programs x U or U) that apply would actually execute: a selected unit that
    conflicts with another selected unit is abstained on, as in `u5core.apply` (Amendment 3)."""
    if A is None:
        return S
    if S.ndim == 1:
        return S & ~(A @ S.astype(np.float32) > 0)
    conf = (A @ S.T.astype(np.float32)).T > 0
    return S & ~np.asarray(conf)


def predicates(feats, valid):
    """Predicates (j, op, q) for one theta: deciles of each feature over the valid demonstration units (all units if
    fewer than 10 are valid). Duplicates removed, order: feature, threshold, '<' then '>'."""
    X = feats[valid] if valid.sum() >= 10 else feats
    out = []
    if len(X) == 0:
        return out
    for j in range(X.shape[1]):
        qs = sorted(set(float(np.percentile(X[:, j], d)) for d in DECILES))
        for q in qs:
            out.append((j, "<", q))
            out.append((j, ">", q))
    return out


def pred_matrix(preds, feats):
    if not preds:
        return np.zeros((0, len(feats)), bool)
    return np.array([(feats[:, j] < q) if op == "<" else (feats[:, j] > q) for j, op, q in preds], bool)


def guards(preds):
    """Guard index list: () first, then singles, then pairs on different features."""
    g = [()]
    g += [(i,) for i in range(len(preds))]
    g += [(i, k) for i, k in itertools.combinations(range(len(preds)), 2) if preds[i][0] != preds[k][0]]
    return g


class Space:
    """All programs of one operator over the demonstration units, with per-parent effect sums."""

    def __init__(self, demo, base, n_parents):
        self.T = len(demo["feats"])
        self.P = n_parents
        self.base = np.asarray(base, float)                       # (P, 3): n_ref, n_pred, tp
        self.progs, self.Dtp, self.Dn, self.E, self.npred = [], [], [], [], []
        self.conflicted = []                                        # Amendment 3: conservative conflict rule
        self.preds = {}
        par = demo["parent"]
        WORK["spaces"] += 1
        for t in range(self.T):
            F, V = demo["feats"][t], demo["valid"][t]
            pr = predicates(F, V)
            self.preds[t] = pr
            Pm = pred_matrix(pr, F)
            G = guards(pr)
            A = adjacency(demo.get("conflicts", {}).get(t, []), len(par))
            W = np.zeros((len(par), 2 * self.P), np.float32)
            if len(par):
                W[np.arange(len(par)), par] = demo["dTP"][t]
                W[np.arange(len(par)), self.P + par] = demo["dN"][t]
            for c0 in range(0, len(G), CHUNK):
                gs = G[c0:c0 + CHUNK]
                S = np.empty((len(gs), len(par)), bool)
                for r, g in enumerate(gs):
                    s = V.copy()
                    for i in g:
                        s &= Pm[i]
                    S[r] = s
                # Amendment 3: a program whose selection contains two units that apply would abstain on together
                # (intersecting write sets, or a shared object) on any demonstration parent is invalid for FIT,
                # leave-one-out and ranking. Every valid program's selection is conflict-free, so apply executes all
                # of it and its summed (dTP, dN) are exact (tests; runtime certification in u5run).
                if A is not None:
                    self.conflicted.append((executed(S, A) != S).any(1))
                else:
                    self.conflicted.append(np.zeros(len(gs), bool))
                WORK["programs_scored"] += len(gs)
                M = S.astype(np.float32) @ W
                self.Dtp.append(M[:, :self.P])
                self.Dn.append(M[:, self.P:])
                self.E.append(S.sum(1))
                self.npred += [len(g) for g in gs]
                self.progs += [(t, g) for g in gs]
        self.Dtp = np.concatenate(self.Dtp) if self.Dtp else np.zeros((0, self.P))
        self.Dn = np.concatenate(self.Dn) if self.Dn else np.zeros((0, self.P))
        self.E = np.concatenate(self.E) if self.E else np.zeros(0)
        self.conflicted = np.concatenate(self.conflicted) if self.conflicted else np.zeros(0, bool)
        self.npred = np.array(self.npred)
        nr, n, tp = self.base.T
        self.f1_base = np.where(nr + n > 0, 2 * tp / np.maximum(nr + n, 1e-12), 1.0)
        self.f1_new = np.where(nr + n + self.Dn > 0, 2 * (tp + self.Dtp) / np.maximum(nr + n + self.Dn, 1e-12), 1.0)
        self.harm = self.f1_new < self.f1_base - 1e-12            # (N, P)

    def pooled_gain(self, keep):
        """Pooled F1 gain over the parents in `keep` (bool P) for every program."""
        nr, n, tp = (self.base[keep]).sum(0)
        b = 2 * tp / max(nr + n, 1e-12) if nr + n > 0 else 1.0
        den = nr + n + self.Dn[:, keep].sum(1)
        new = np.where(den > 0, 2 * (tp + self.Dtp[:, keep].sum(1)) / np.maximum(den, 1e-12), 1.0)
        return new - b

    def rank_key(self, reverse=False):
        order = np.arange(len(self.progs))
        return order[::-1] if reverse else order

    def fit(self, keep=None, reverse=False):
        """FIT (indices) and the top program over parents `keep` (section 10, steps 3 and 4)."""
        keep = np.ones(self.P, bool) if keep is None else keep
        WORK["fits"] += 1
        if len(self.progs) == 0 or keep.sum() == 0:
            return np.zeros(0, int), None
        G = self.pooled_gain(keep)
        ok = ~self.harm[:, keep].any(1) & (G > 1e-12) & (self.E > 0) & ~self.conflicted
        if not ok.any():
            return np.zeros(0, int), None
        gmax = G[ok].max()
        fit = np.flatnonzero(ok & (G >= RASHOMON * gmax - 1e-15))
        enum = self.rank_key(reverse)
        pos = np.empty(len(enum), int)
        pos[enum] = np.arange(len(enum))
        best = sorted(fit, key=lambda i: (-round(G[i], 12), int(self.E[i]), int(self.npred[i]), pos[i]))[0]
        return fit, int(best)


def select(space, prog, q):
    """Units that program index `prog` would execute on units q (its selection, minus the units apply would abstain on
    because they conflict with another selected unit), and their result classes."""
    t, g = space.progs[prog]
    F, V, C = q["feats"][t], q["valid"][t], q["cls"][t]
    s = V.copy()
    pr = space.preds[t]
    for i in g:
        j, op, th = pr[i]
        s &= (F[:, j] < th) if op == "<" else (F[:, j] > th)
    cache = q.setdefault("_adj", {})
    if t not in cache:
        cache[t] = adjacency(q.get("conflicts", {}).get(t, []), len(V))
    s = executed(s, cache[t])
    WORK["program_selections"] += 1
    return s, np.where(s, C, -1)


def verify(space, demo_parents_with_units, q, reverse_check=True):
    """Section 10 steps 3 to 6. Returns dict: status, accepted (bool over query units), theta index per accepted unit,
    fit size, top program, fold tops, abstention share."""
    U = len(q["valid"][0]) if q["valid"] else 0
    out = {"status": "", "accepted": np.zeros(U, bool), "theta": np.full(U, -1), "fit": 0, "top": None,
           "fold_tops": [], "selected_by_some": np.zeros(U, bool)}
    if demo_parents_with_units < 2:
        out["status"] = "INSUFFICIENT_DEMONSTRATIONS"
        return out
    res = {}
    for rev in ((False, True) if reverse_check else (False,)):
        fit, top = space.fit(reverse=rev)
        if top is None:
            out["status"] = "NO_FIT"
            return out
        tops = []
        for p in range(space.P):
            if space.base[p][0] + space.base[p][1] == 0:
                continue
            keep = np.ones(space.P, bool)
            keep[p] = False
            _, tp_ = space.fit(keep, reverse=rev)
            if tp_ is None or space.harm[tp_, p]:
                out.update(status="LOO_FAIL", fit=len(fit), top=top)
                return out
            tops.append(tp_)
        all_sel = np.ones(U, bool)
        some = np.zeros(U, bool)
        cls0 = None
        for i in list(fit) + tops:
            s, c = select(space, i, q)
            some |= s
            all_sel &= s
            if cls0 is None:
                cls0 = c
            all_sel &= (c == cls0)
        res[rev] = (all_sel, fit, top, tops, some)
    acc, fit, top, tops, some = res[False]
    if reverse_check and not np.array_equal(acc, res[True][0]):
        out.update(status="RESTART_UNSTABLE", fit=len(fit), top=top)
        return out
    t_top = space.progs[top][0]
    theta = np.where(acc, t_top, -1)
    # every accepted unit has one class under every program; use the top program's theta (same result class)
    out.update(status="EVIDENCE", accepted=acc, theta=theta, fit=len(fit), top=top, fold_tops=tops,
               selected_by_some=some, fit_idx=[int(i) for i in fit])
    return out


TOLERANCE = (2, 3)        # Amendment 8: top program in at least two-thirds of the leave-one-parent-out folds


def verify_tolerant(space, demo_parents_with_units, q, reverse_check=None):
    """Amendment 8, the CORA_TOLERANT secondary arm (fixed before any evaluation outcome; no other tolerance is tried).
    A program passes if it is the top program in at least two-thirds of the leave-one-parent-out folds AND harms no
    demonstration parent. Fold tops come from the same fit as section 10 (no harm on the fold's parents, positive
    pooled gain, at least one edit, no conflicting selection), so the conflict rule is unchanged. At most one program
    can be the top of two-thirds of the folds, so there is no tie to break and no restart check. The accepted query
    units are the passing program's executed selection. `reverse_check` is ignored."""
    U = len(q["valid"][0]) if q["valid"] else 0
    out = {"status": "", "accepted": np.zeros(U, bool), "theta": np.full(U, -1), "fit": 0, "top": None,
           "fold_tops": [], "selected_by_some": np.zeros(U, bool), "fit_idx": [], "rule": "tolerant"}
    if demo_parents_with_units < 2:
        out["status"] = "INSUFFICIENT_DEMONSTRATIONS"
        return out
    folds = [p for p in range(space.P) if space.base[p][0] + space.base[p][1] > 0]
    tops = []
    for p in folds:
        keep = np.ones(space.P, bool)
        keep[p] = False
        tops.append(space.fit(keep)[1])
    counts = {}
    for t in tops:
        if t is not None:
            counts[t] = counts.get(t, 0) + 1
    num, den = TOLERANCE
    passing = [i for i, c in counts.items() if den * c >= num * len(folds)]
    out.update(fold_tops=[int(t) for t in tops if t is not None], n_folds=len(folds),
               top_share=(max(counts.values()) / len(folds)) if counts and folds else 0.0)
    if not passing:
        out["status"] = "NO_TOLERANT_MAJORITY" if counts else "NO_FIT"
        return out
    top = int(passing[0])
    out["top"] = top
    if space.conflicted[top]:                       # cannot happen: fold tops exclude conflicted programs
        out["status"] = "CONFLICTED"
        return out
    if space.harm[top].any():
        out["status"] = "HARMS_DEMONSTRATION_PARENT"
        return out
    s, _ = select(space, top, q)
    out.update(status="EVIDENCE", accepted=s, theta=np.where(s, space.progs[top][0], -1), selected_by_some=s.copy())
    return out


class ProposedSpace(Space):
    """Section 15: the CORA rule with an explicit candidate set (the neural proposer's programs for one operator)
    instead of the enumerated guard space. programs: [(theta index, [(feature index, '<' or '>', threshold), ...])]."""

    def __init__(self, demo, base, n_parents, programs):
        self.T = len(demo["feats"])
        self.P = n_parents
        self.base = np.asarray(base, float)
        par = demo["parent"]
        self.preds, self.progs = {}, []
        Dtp, Dn, E, npred = [], [], [], []
        adj_cache, conf = {}, []
        for t, guard in programs:
            pr = self.preds.setdefault(t, [])
            idx = []
            for g in guard:
                g = (int(g[0]), str(g[1]), float(g[2]))
                if g not in pr:
                    pr.append(g)
                idx.append(pr.index(g))
            self.progs.append((t, tuple(idx)))
            F, V = demo["feats"][t], demo["valid"][t]
            s = V.copy()
            for j, op, q in (pr[i] for i in idx):
                s &= (F[:, j] < q) if op == "<" else (F[:, j] > q)
            if t not in adj_cache:
                adj_cache[t] = adjacency(demo.get("conflicts", {}).get(t, []), len(par))
            conf.append(bool((executed(s, adj_cache[t]) != s).any()))
            WORK["programs_scored"] += 1
            dtp = np.bincount(par[s], weights=demo["dTP"][t][s], minlength=self.P) if s.any() else np.zeros(self.P)
            dn = np.bincount(par[s], weights=demo["dN"][t][s], minlength=self.P) if s.any() else np.zeros(self.P)
            Dtp.append(dtp)
            Dn.append(dn)
            E.append(int(s.sum()))
            npred.append(len(idx))
        self.Dtp = np.array(Dtp, float).reshape(len(self.progs), self.P)
        self.Dn = np.array(Dn, float).reshape(len(self.progs), self.P)
        self.E, self.npred = np.array(E), np.array(npred)
        self.conflicted = np.array(conf, bool)
        nr, n, tp = self.base.T
        self.f1_base = np.where(nr + n > 0, 2 * tp / np.maximum(nr + n, 1e-12), 1.0)
        self.f1_new = np.where(nr + n + self.Dn > 0, 2 * (tp + self.Dtp) / np.maximum(nr + n + self.Dn, 1e-12), 1.0)
        self.harm = self.f1_new < self.f1_base - 1e-12
