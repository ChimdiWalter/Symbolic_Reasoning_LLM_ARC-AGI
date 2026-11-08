"""U5 core (PROTOCOL.md sections 7, 8.1, 10, 14.1): matching, unit features, the eleven literature operators, unit
effects against a reference, and the exact application of accepted edits. numpy / scipy / scikit-image / cv2 only.

A *unit* is what one edit acts on: an object (most operators), a mutual-best touching pair (merge_pairs) or a candidate
new object (add_lowthresh). For each operator and theta, `units()` returns, per unit, its features, whether the edit is
valid (changes something), a result class (theta values whose results agree at IoU >= 0.9 share a class) and, when a
reference is given, its effect on matching (dTP: change in objects matched at IoU > 0.5; dN: change in counted
objects). Edits of different units are local and additive under one-to-one matching at IoU > 0.5."""
import hashlib

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import disk
from skimage.segmentation import watershed

OPS = ("add_lowthresh", "fill_holes", "split_dt", "split_int", "merge_pairs", "close", "open", "dilate", "erode",
       "delete", "clear_border")
CLASS = {"add_lowthresh": "ADD", "fill_holes": "FILL", "split_dt": "SPLIT", "split_int": "SPLIT",
         "merge_pairs": "MERGE", "close": "GROW", "open": "SHRINK", "dilate": "GROW", "erode": "SHRINK",
         "delete": "DELETE", "clear_border": "DELETE"}
CLASSES = ("SPLIT", "MERGE", "FILL", "GROW", "SHRINK", "DELETE", "ADD")
THETA = {"add_lowthresh": (0,), "fill_holes": (0.1, 1.0), "split_dt": (0.15, 0.3, 0.45),
         "split_int": (0.05, 0.1, 0.2), "merge_pairs": (0,), "close": (1, 2, 3), "open": (1, 2, 3),
         "dilate": (1, 2, 3), "erode": (1, 2), "delete": (0,), "clear_border": (0,)}
FEATS = {"add_lowthresh": ("area_rel", "intensity_rel", "contrast", "solidity"),
         "fill_holes": ("hole_frac", "area_rel", "solidity"),
         "split_dt": ("area_rel", "solidity", "ecc", "n_cores", "contrast"),
         "split_int": ("area_rel", "solidity", "ecc", "n_cores", "contrast"),
         "merge_pairs": ("u_solidity", "u_area_rel", "b_contrast", "area_ratio"),
         "close": ("solidity", "area_rel", "contrast"),
         "open": ("solidity", "area_rel", "ecc"),
         "dilate": ("area_rel", "contrast", "intensity_rel"),
         "erode": ("area_rel", "contrast", "intensity_rel"),
         "delete": ("area_rel", "intensity_rel", "contrast", "solidity", "ecc", "n_neigh"),
         "clear_border": ("area_rel", "border_frac")}
IOU_MATCH, SAME_IOU, IGN_FRAC, MIN_PART = 0.5, 0.9, 0.5, 3
_DISK = {r: disk(r).astype(bool) for r in (1, 2, 3)}
_E8 = np.ones((3, 3), bool)


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes() + str(a.shape).encode()).hexdigest()


def relabel(lab):
    lab = np.asarray(lab)
    m = int(lab.max()) if lab.size else 0
    if m == 0:
        return np.zeros(lab.shape, np.int32)
    present = np.bincount(lab.ravel(), minlength=m + 1) > 0
    present[0] = False
    mp = np.zeros(m + 1, np.int32)
    mp[present] = np.arange(1, int(present.sum()) + 1, dtype=np.int32)
    return mp[lab]


# --------------------------------------------------------------------------------------------- matching ------------
def drop_ignored(lab, ign):
    """Remove objects with at least half of their pixels in the ignore mask (PROTOCOL.md 3.2), then relabel."""
    if ign is None or not ign.any() or lab.max() == 0:
        return lab
    n = int(lab.max())
    a = np.bincount(lab.ravel(), minlength=n + 1)
    b = np.bincount(lab[ign].ravel(), minlength=n + 1)
    bad = b >= IGN_FRAC * np.maximum(a, 1)
    bad[0] = False
    out = lab.copy()
    out[bad[lab]] = 0
    return relabel(out)


def iou_table(ref, pred):
    """Overlapping (ref id, pred id, intersection, IoU)."""
    nr, npd = int(ref.max()), int(pred.max())
    if not nr or not npd:
        z = np.zeros(0, np.int64)
        return z, z, z, np.zeros(0)
    ar = np.bincount(ref.ravel(), minlength=nr + 1).astype(np.int64)
    ap = np.bincount(pred.ravel(), minlength=npd + 1).astype(np.int64)
    both = (ref > 0) & (pred > 0)
    key = ref[both].astype(np.int64) * (npd + 1) + pred[both].astype(np.int64)
    uk, cnt = np.unique(key, return_counts=True)
    r, p = uk // (npd + 1), uk % (npd + 1)
    return r, p, cnt, cnt / np.maximum(ar[r] + ap[p] - cnt, 1)


THRESH = tuple(round(0.5 + 0.05 * i, 2) for i in range(10))


def counts(ref, pred):
    """Matching counts of one image: n_ref, n_pred and TP at each IoU threshold (strict >, one-to-one since t >= 0.5)."""
    _, _, _, iou = iou_table(ref, pred)
    return {"n_ref": int(ref.max()), "n_pred": int(pred.max()), "tp_at": [int((iou > t).sum()) for t in THRESH]}


def pool_counts(cs):
    nr = sum(c["n_ref"] for c in cs)
    npd = sum(c["n_pred"] for c in cs)
    tp = np.sum([c["tp_at"] for c in cs], axis=0) if cs else np.zeros(len(THRESH))
    return nr, npd, tp


def f1_of(nr, npd, tp):
    return 1.0 if nr + npd == 0 else 2.0 * tp / (nr + npd)


def ap_of(nr, npd, tp_at):
    """Mean over IoU 0.50..0.95 of TP / (TP + FP + FN) = TP / (n_pred + n_ref - TP)."""
    if nr + npd == 0:
        return 1.0
    return float(np.mean([t / max(nr + npd - t, 1) for t in tp_at]))


def pred_tp(ref, pred):
    """Per predicted id 0..n: True if some reference object has IoU > 0.5 with it."""
    out = np.zeros(int(pred.max()) + 1, bool)
    r, p, _, iou = iou_table(ref, pred)
    out[p[iou > IOU_MATCH]] = True
    return out


def counted_mask(lab, ign):
    """Per id 0..n: True if the object counts (fewer than half of its pixels are in the ignore mask)."""
    n = int(lab.max())
    ok = np.ones(n + 1, bool)
    ok[0] = False
    if ign is not None and ign.any() and n:
        a = np.bincount(lab.ravel(), minlength=n + 1)
        b = np.bincount(lab[ign].ravel(), minlength=n + 1)
        ok &= b < IGN_FRAC * np.maximum(a, 1)
    return ok


# --------------------------------------------------------------------------------------------- features ------------
def _crop(sl, shape, m):
    y0, y1 = max(sl[0].start - m, 0), min(sl[0].stop + m, shape[0])
    x0, x1 = max(sl[1].start - m, 0), min(sl[1].stop + m, shape[1])
    return slice(y0, y1), slice(x0, x1)


def _solidity(mask):
    a = int(mask.sum())
    if a < 3:
        return 1.0
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.convexHull(np.vstack(cnts))
    canvas = np.zeros(mask.shape, np.uint8)
    cv2.fillPoly(canvas, [hull], 1)
    return a / max(int((canvas.astype(bool) | mask).sum()), a)


def _largest(mask):
    lab, n = ndi.label(mask, structure=_E8)
    if n <= 1:
        return mask
    c = np.bincount(lab.ravel())
    c[0] = 0
    return lab == int(np.argmax(c))


class Image:
    """One image: label image L (int32), intensity I (float32 in [0, 1]), optional low-threshold labels, optional
    reference (int32) and ignore mask (bool). Object features are computed on demand."""

    def __init__(self, L, I, L_low=None, ref=None, ign=None):
        self.L = relabel(L)
        self.I = I.astype(np.float32)
        self.L_low, self.ref, self.ign = L_low, ref, ign
        self.n = int(self.L.max())
        self.H, self.W = self.L.shape
        self.area = np.bincount(self.L.ravel(), minlength=self.n + 1).astype(np.float64)
        self.mean = np.bincount(self.L.ravel(), self.I.ravel().astype(np.float64), self.n + 1) / np.maximum(self.area, 1)
        a = self.area[1:]
        self.med_area = float(np.median(a[a > 0])) if self.n else 1.0
        self.med_int = float(np.median(self.mean[1:][a > 0])) if self.n else 1.0
        self.std = float(self.I.std()) + 1e-6
        self.sl = ndi.find_objects(self.L)
        self._f = None
        if ref is not None:
            self.ref_area = np.bincount(ref.ravel(), minlength=int(ref.max()) + 1).astype(np.int64)
            self.tp = pred_tp(ref, self.L)
            self.cnt = counted_mask(self.L, ign)

    def feats(self):
        """Per object 1..n: area_rel, intensity_rel, contrast, solidity, ecc, n_neigh, hole_frac, border, border_frac."""
        if self._f is not None:
            return self._f
        n = self.n
        f = {k: np.zeros(n + 1) for k in ("area_rel", "intensity_rel", "contrast", "solidity", "ecc", "n_neigh",
                                          "hole_frac", "border", "border_frac")}
        f["area_rel"] = self.area / max(self.med_area, 1e-6)
        f["intensity_rel"] = self.mean / max(self.med_int, 1e-6)
        lab = self.L.ravel()
        yy, xx = np.divmod(np.arange(self.H * self.W, dtype=np.float64), self.W)
        a = np.maximum(self.area, 1)
        sx, sy = np.bincount(lab, xx, n + 1) / a, np.bincount(lab, yy, n + 1) / a
        cxx = np.bincount(lab, xx * xx, n + 1) / a - sx * sx
        cyy = np.bincount(lab, yy * yy, n + 1) / a - sy * sy
        cxy = np.bincount(lab, xx * yy, n + 1) / a - sx * sy
        tr, det = cxx + cyy, cxx * cyy - cxy * cxy
        disc = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
        l1, l2 = tr / 2 + disc, np.maximum(tr / 2 - disc, 0)
        f["ecc"] = np.sqrt(np.clip(1 - l2 / np.maximum(l1, 1e-12), 0, 1))
        edge = np.zeros(self.L.shape, bool)
        edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
        eb = np.bincount(self.L[edge], minlength=n + 1).astype(np.float64)
        f["border"] = (eb > 0).astype(float)
        f["border_frac"] = eb / np.maximum(2 * np.sqrt(np.pi * self.area), 1)
        for i, s in enumerate(self.sl, start=1):
            if s is None:
                continue
            cs = _crop(s, self.L.shape, 3)
            Lc, Ic = self.L[cs], self.I[cs]
            m = Lc == i
            f["solidity"][i] = _solidity(m)
            ring = ndi.binary_dilation(m, _E8, iterations=2) & ~m & (Lc == 0)
            mi = float(Ic[m].mean())
            mr = float(Ic[ring].mean()) if ring.any() else mi
            f["contrast"][i] = (mi - mr) / self.std
            holes = ndi.binary_fill_holes(m) & ~m & (Lc == 0)
            f["hole_frac"][i] = holes.sum() / max(m.sum(), 1)
            nb = np.unique(Lc[ndi.binary_dilation(m, _E8)])
            f["n_neigh"][i] = int(((nb != 0) & (nb != i)).sum())
        self._f = f
        return f

    # ------------------------------------------------------------------ effects against the reference ---------
    def _res_tp_cnt(self, cs, masks):
        """Matched and counted flags of result masks (crop coordinates)."""
        tp = cnt = 0
        rc = self.ref[cs]
        ic = None if self.ign is None else self.ign[cs]
        for mk in masks:
            a = int(mk.sum())
            if a == 0:
                continue
            if ic is not None and (mk & ic).sum() >= IGN_FRAC * a:
                continue
            cnt += 1
            ids = rc[mk]
            ids = ids[ids > 0]
            if len(ids):
                u, c = np.unique(ids, return_counts=True)
                iou = c / (a + self.ref_area[u] - c)
                tp += int(iou.max() > IOU_MATCH)
        return tp, cnt

    def effect(self, objs, cs, masks):
        """(dTP, dN) of replacing objects `objs` by `masks` (crop cs)."""
        t1, c1 = self._res_tp_cnt(cs, masks)
        t0 = int(sum(bool(self.tp[o] and self.cnt[o]) for o in objs))
        c0 = int(sum(bool(self.cnt[o]) for o in objs))
        return t1 - t0, c1 - c0

    def base(self):
        """(n_ref, counted predicted objects, counted and matched objects) of the current segmentation."""
        return int(self.ref.max()), int(self.cnt[1:].sum()), int((self.tp & self.cnt)[1:].sum())


# --------------------------------------------------------------------------------------------- operators -----------
def _same(r1, r2):
    """Two results (lists of masks in the same crop) agree: same number of objects, matched at IoU >= 0.9."""
    if len(r1) != len(r2):
        return False
    if not r1:
        return True
    used = set()
    for a in r1:
        ok = False
        for j, b in enumerate(r2):
            if j in used:
                continue
            inter = (a & b).sum()
            if inter / max((a | b).sum(), 1) >= SAME_IOU:
                used.add(j)
                ok = True
                break
        if not ok:
            return False
    return True


def _obj_result(img, op, i, th, cs):
    """Result masks of operator op at theta th on object i, in crop cs; None if the edit changes nothing."""
    Lc = img.L[cs]
    m = Lc == i
    free = Lc == 0
    if op == "delete" or op == "clear_border":
        return []
    if op == "fill_holes":
        holes = ndi.binary_fill_holes(m) & ~m & free
        if not holes.any():
            return None
        hl, k = ndi.label(holes)
        sizes = np.bincount(hl.ravel())
        keep = np.flatnonzero(sizes <= th * m.sum())
        keep = keep[keep > 0]
        if not len(keep):
            return None
        return [m | np.isin(hl, keep)]
    if op in ("close", "dilate"):
        se = _DISK[th]
        grown = ndi.binary_closing(np.pad(m, th + 1), se)[th + 1:-th - 1, th + 1:-th - 1] if op == "close" \
            else ndi.binary_dilation(m, se)
        new = m | (grown & free)
        return None if (new == m).all() else [new]
    if op in ("open", "erode"):
        se = _DISK[th]
        shr = ndi.binary_opening(m, se) if op == "open" else ndi.binary_erosion(m, se)
        shr = _largest(shr)
        if not shr.any() or (shr == m).all():
            return None
        return [shr]
    if op in ("split_dt", "split_int"):
        cores, f = _cores(img, op, i, th, cs)
        if cores is None:
            return None
        parts = watershed(-f, cores, mask=m)
        out = [parts == k for k in range(1, int(parts.max()) + 1)]
        out = [p for p in out if p.sum() >= MIN_PART]
        return out if len(out) >= 2 else None
    raise KeyError(op)


def _hmax(f, h):
    """Classical h-maxima (regional maxima of the reconstruction of f - h under f), the implementation of the earlier
    CORA nuclei study (`cora_cross_domain_transfer.adapters.bbbc039.h_maxima`, unchanged): two peaks joined by a saddle
    shallower than h give one marker (skimage's h_maxima would give two)."""
    import sys as _s
    _r = "/path/to/repository"
    if _r not in _s.path:
        _s.path.insert(0, _r)
    from cora_cross_domain_transfer.adapters import bbbc039 as _B
    return _B.h_maxima(f, h)


def _cores(img, op, i, th, cs):
    """Markers (labelled) of a split at theta th, and the field the watershed descends; (None, None) if < 2."""
    Lc = img.L[cs]
    m = Lc == i
    a = int(m.sum())
    if a < 20:
        return None, None
    if op == "split_dt":
        f = ndi.distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1]
        h = th * np.sqrt(a / np.pi)
    else:
        f = ndi.gaussian_filter(img.I[cs].astype(np.float64), 1.0) + 1e-3
        h = th
    f = np.where(m, f, 0.0).astype(np.float32)
    mk = _hmax(f, h) & m
    lab, k = ndi.label(mk, structure=_E8)
    if k < 2:
        return None, None
    return lab, f


def n_cores(img, op, i, th, cs):
    lab, _ = _cores(img, op, i, th, cs)
    return 0 if lab is None else int(lab.max())


def _pairs(img):
    """Mutual-best touching pairs (gap <= 2 px): each object's partner with the largest b_contrast."""
    from skimage.segmentation import expand_labels
    L1 = expand_labels(img.L, 1)
    A, B = [], []
    for s1, s2 in ((np.s_[:, :-1], np.s_[:, 1:]), (np.s_[:-1, :], np.s_[1:, :])):
        a, b = L1[s1], L1[s2]
        mm = (a != b) & (a > 0) & (b > 0)
        A.append(np.minimum(a[mm], b[mm]))
        B.append(np.maximum(a[mm], b[mm]))
    A, B = np.concatenate(A), np.concatenate(B)
    if not len(A):
        return []
    key = np.unique(A.astype(np.int64) * (img.n + 1) + B)
    pairs = [(int(k // (img.n + 1)), int(k % (img.n + 1))) for k in key]
    info = {}
    for a, b in pairs:
        info[(a, b)] = _pair_geom(img, a, b)
    best = {}
    for (a, b), g in info.items():
        for o in (a, b):
            if o not in best or g["b_contrast"] > info[best[o]]["b_contrast"] or \
                    (g["b_contrast"] == info[best[o]]["b_contrast"] and (a, b) < best[o]):
                best[o] = (a, b)
    return [(p, info[p]) for p in pairs if best.get(p[0]) == p and best.get(p[1]) == p]


def _pair_geom(img, a, b):
    sa, sb = img.sl[a - 1], img.sl[b - 1]
    s = (slice(min(sa[0].start, sb[0].start), max(sa[0].stop, sb[0].stop)),
         slice(min(sa[1].start, sb[1].start), max(sa[1].stop, sb[1].stop)))
    cs = _crop(s, img.L.shape, 2)
    Lc, Ic = img.L[cs], img.I[cs]
    ma, mb = Lc == a, Lc == b
    da, db = ndi.binary_dilation(ma, _E8), ndi.binary_dilation(mb, _E8)
    gap = da & db & (Lc == 0)
    u = ma | mb | gap
    bnd = (da & mb) | (db & ma) | gap
    inner = float(Ic[ma | mb].mean())
    bc = float(Ic[bnd].mean()) / max(inner, 1e-6) if bnd.any() else 0.0
    aa, ab = int(ma.sum()), int(mb.sum())
    return {"cs": cs, "u": u, "b_contrast": bc, "u_solidity": _solidity(u), "u_area_rel": u.sum() / img.med_area,
            "area_ratio": min(aa, ab) / max(aa, ab, 1)}


def _write_set(img, op, objs, cs, r):
    """The pixels an edit writes, exactly as `result_of` reports them to `apply` (flat global indices)."""
    if op == "merge_pairs":
        ws = r[0] & (img.L[cs] != objs[0])
    elif op == "add_lowthresh":
        ws = r[0]
    else:
        m = img.L[cs] == objs[0]
        union = np.zeros(m.shape, bool)
        for x in r:
            union |= x
        ws = union ^ m
    ys, xs = np.nonzero(ws)
    return (ys + cs[0].start) * img.W + (xs + cs[1].start)


def _conflicts(wsets, objsets):
    """Pairs (i, j), i < j, of units whose write sets intersect or that touch the same object: the pairs `apply` would
    abstain on together if both were selected (Amendment 3)."""
    pairs = set()
    if wsets:
        pix = np.concatenate([w for _, w in wsets]) if wsets else np.zeros(0, np.int64)
        uid = np.concatenate([np.full(len(w), i) for i, w in wsets]) if wsets else np.zeros(0, int)
        if len(pix):
            o = np.argsort(pix, kind="stable")
            pix, uid = pix[o], uid[o]
            starts = np.flatnonzero(np.r_[True, pix[1:] != pix[:-1]])
            ends = np.r_[starts[1:], len(pix)]
            for s0, e0 in zip(starts, ends):
                if e0 - s0 > 1:
                    us = sorted(set(uid[s0:e0].tolist()))
                    for a in range(len(us)):
                        for b in range(a + 1, len(us)):
                            pairs.add((us[a], us[b]))
    owner = {}
    for i, objs in objsets:
        for o in objs:
            owner.setdefault(o, []).append(i)
    for us in owner.values():
        for a in range(len(us)):
            for b in range(a + 1, len(us)):
                pairs.add((min(us[a], us[b]), max(us[a], us[b])))
    return np.array(sorted(pairs), int).reshape(-1, 2)


def units(img, op, with_effects=False):
    """Units of operator op on this image. Returns dict: keys (list of unit keys), feats {theta index: (U x F)},
    valid {t: (U,)}, cls {t: (U,) int}, conflicts {t: (K, 2) unit pairs that apply would abstain on together}, and
    with effects dTP {t}, dN {t}."""
    TH = THETA[op]
    T = len(TH)
    keys, rows, valid, cls, dtp, dn = [], {t: [] for t in range(T)}, {t: [] for t in range(T)}, \
        {t: [] for t in range(T)}, {t: [] for t in range(T)}, {t: [] for t in range(T)}
    wsets, objsets = {t: [] for t in range(T)}, {t: [] for t in range(T)}

    def push(key, frow, results, objs, cs):
        keys.append(key)
        firsts = []
        for t in range(T):
            r = results[t]
            rows[t].append(frow[t] if isinstance(frow, dict) else frow)
            valid[t].append(r is not None)
            if r is not None:
                wsets[t].append((len(keys) - 1, _write_set(img, op, objs, cs, r)))
                objsets[t].append((len(keys) - 1, tuple(objs)))
            c = -1
            if r is not None:
                for (t2, c2) in firsts:
                    if _same(r, results[t2]):
                        c = c2
                        break
                if c < 0:
                    c = len(firsts)
                    firsts.append((t, c))
            cls[t].append(c)
            if with_effects:
                if r is None:
                    dtp[t].append(0)
                    dn[t].append(0)
                else:
                    e = img.effect(objs, cs, r)
                    dtp[t].append(e[0])
                    dn[t].append(e[1])

    if op == "merge_pairs":
        for (a, b), g in _pairs(img):
            frow = [g[k] for k in FEATS[op]]
            push((a, b), frow, [[g["u"]]], (a, b), g["cs"])
    elif op == "add_lowthresh":
        if img.L_low is not None and img.L_low.max() > 0:
            Ll = relabel(img.L_low)
            for c, s in enumerate(ndi.find_objects(Ll), start=1):
                if s is None:
                    continue
                cs = _crop(s, Ll.shape, 3)
                mc = Ll[cs] == c
                free = mc & (img.L[cs] == 0)
                if free.sum() < 5 or free.sum() < 0.9 * mc.sum():
                    continue
                free = _largest(free)
                Ic = img.I[cs]
                ring = ndi.binary_dilation(free, _E8, iterations=2) & ~free & (img.L[cs] == 0) & ~mc
                mi = float(Ic[free].mean())
                mr = float(Ic[ring].mean()) if ring.any() else mi
                frow = [free.sum() / img.med_area, mi / max(img.med_int, 1e-6), (mi - mr) / img.std, _solidity(free)]
                push(("add", c), frow, [[free]], (), cs)
    else:
        F = img.feats()
        objs = range(1, img.n + 1)
        if op == "clear_border":
            objs = [i for i in objs if F["border"][i] > 0]
        for i in objs:
            s = img.sl[i - 1]
            if s is None:
                continue
            margin = 4 if op not in ("close", "dilate") else max(THETA[op]) + 2
            cs = _crop(s, img.L.shape, margin)
            results = [_obj_result(img, op, i, th, cs) for th in TH]
            if op in ("split_dt", "split_int"):
                frow = {}
                for t, th in enumerate(TH):
                    frow[t] = [F[k][i] if k != "n_cores" else (0 if results[t] is None else len(results[t]))
                               for k in FEATS[op]]
            else:
                frow = [F[k][i] for k in FEATS[op]]
            push(i, frow, results, (i,), cs)
    U = len(keys)
    nf = len(FEATS[op])
    out = {"keys": keys, "feats": {t: np.array(rows[t], float).reshape(U, nf) for t in range(T)},
           "valid": {t: np.array(valid[t], bool) for t in range(T)}, "cls": {t: np.array(cls[t], int) for t in range(T)},
           "conflicts": {t: _conflicts(wsets[t], objsets[t]) for t in range(T)}}
    if with_effects:
        out["dTP"] = {t: np.array(dtp[t], np.int32) for t in range(T)}
        out["dN"] = {t: np.array(dn[t], np.int32) for t in range(T)}
    return out


def result_of(img, op, key, t, th=None):
    """(crop, objs replaced, result masks, write set) of one unit at theta index t, or at the explicit theta value th
    (ALL_ON's own grids), recomputed and deterministic."""
    th = THETA[op][t] if th is None else th
    if op == "merge_pairs":
        a, b = key
        g = _pair_geom(img, a, b)
        cs = g["cs"]
        return cs, (a, b), [g["u"]], g["u"] & (img.L[cs] != a)
    if op == "add_lowthresh":
        Ll = relabel(img.L_low)
        c = key[1]
        s = ndi.find_objects(Ll)[c - 1]
        cs = _crop(s, Ll.shape, 3)
        free = _largest((Ll[cs] == c) & (img.L[cs] == 0))
        return cs, (), [free], free
    i = key
    s = img.sl[i - 1]
    margin = 4 if op not in ("close", "dilate") else max(THETA[op]) + 2
    cs = _crop(s, img.L.shape, margin)
    r = _obj_result(img, op, i, th, cs)
    m = img.L[cs] == i
    if r is None:
        return cs, (i,), None, np.zeros(m.shape, bool)
    union = np.zeros(m.shape, bool)
    for x in r:
        union |= x
    return cs, (i,), r, union ^ m


def apply(img, op, accepted, th=None):
    """Apply accepted edits [(key, t), ...] of one operator exactly (theta index t, or the explicit value th for all).
    Edits whose write sets overlap, or that touch the same object, are all abstained on (PROTOCOL.md section 10,
    step 7). Returns (new label image, applied list)."""
    recs = []
    for key, t in accepted:
        cs, objs, res, ws = result_of(img, op, key, t, th)
        if res is None:
            continue
        recs.append((key, t, cs, objs, res, ws))
    W = np.zeros(img.L.shape, np.int16)
    owner = {}
    for k, (_, _, cs, objs, res, ws) in enumerate(recs):
        W[cs] += ws.astype(np.int16)
        for o in objs:
            owner.setdefault(o, []).append(k)
    bad = set()
    for k, (_, _, cs, objs, res, ws) in enumerate(recs):
        if (W[cs][ws] > 1).any() or any(len(owner[o]) > 1 for o in objs):
            bad.add(k)
    L = img.L.copy()
    nxt = int(L.max()) + 1
    applied = []
    for k, (key, t, cs, objs, res, ws) in enumerate(recs):
        if k in bad:
            continue
        Lc = L[cs]
        for o in objs:
            Lc[Lc == o] = 0
        for x in res:
            Lc[x & (Lc == 0)] = nxt
            nxt += 1
        applied.append((key, t))
    return relabel(L), applied
