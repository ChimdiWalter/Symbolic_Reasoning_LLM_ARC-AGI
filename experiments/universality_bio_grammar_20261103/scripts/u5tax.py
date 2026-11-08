"""U5 needed corrections (PROTOCOL.md section 8.1), oracle corrections from the reference, and the calibration gate
(section 6). Calibration images only.

`classify(S, ref, ign)` assigns each counted, unmatched object of S at most one class (precedence SPLIT, MERGE, FILL,
GROW/SHRINK, DELETE) and lists missed reference objects (ADD). `corrected(S, ref, info, which)` returns S with the
corrections of the given classes applied from the reference: DELETE removes the object; SPLIT replaces it by the
reference objects it covers; MERGE replaces the fragments by their reference object; FILL fills the object's enclosed
background; GROW and SHRINK replace it by its dominant reference object; ADD draws the missed reference object. New
objects take free pixels only, and a reference object already matched by another prediction is never drawn twice."""
from collections import defaultdict

import numpy as np
from scipy import ndimage as ndi

import u5core as C

COVER = 0.5


def classify(S, ref, ign=None):
    cnt = C.counted_mask(S, ign)
    n, nr = int(S.max()), int(ref.max())
    ap = np.bincount(S.ravel(), minlength=n + 1).astype(np.int64)
    ar = np.bincount(ref.ravel(), minlength=nr + 1).astype(np.int64)
    r, p, inter, iou = C.iou_table(ref, S)
    tp = np.zeros(n + 1, bool)
    tp[p[iou > C.IOU_MATCH]] = True
    ref_matched = np.zeros(nr + 1, bool)
    ref_matched[r[iou > C.IOU_MATCH]] = True
    cover = inter / np.maximum(ar[r], 1)            # share of r inside p
    frac = inter / np.maximum(ap[p], 1)             # share of p inside r
    inside_count = np.bincount(r[frac >= COVER], minlength=nr + 1)
    by_p = defaultdict(list)
    for k in range(len(p)):
        by_p[int(p[k])].append(k)
    sl = ndi.find_objects(S)
    cls, fill = {}, {}
    for o in range(1, n + 1):
        if not cnt[o] or ap[o] == 0:
            continue
        ks = by_p.get(o, [])
        if sum(cover[k] >= COVER for k in ks) >= 2:       # Amendment 2: matched objects covering two references too
            cls[o] = "SPLIT"
            continue
        if tp[o]:
            continue
        if any(frac[k] >= COVER and inside_count[r[k]] >= 2 for k in ks):
            cls[o] = "MERGE"
            continue
        kd = max(ks, key=lambda k: inter[k]) if ks else None
        rd = int(r[kd]) if kd is not None else 0
        if rd and not ref_matched[rd] and sl[o - 1] is not None:
            cs = C._crop(sl[o - 1], S.shape, 1)
            m = S[cs] == o
            holes = ndi.binary_fill_holes(m) & ~m & (S[cs] == 0)
            if holes.any():
                mf = m | holes
                ii = int((ref[cs][mf] == rd).sum())
                if ii / (mf.sum() + ar[rd] - ii) > C.IOU_MATCH:
                    cls[o] = "FILL"
                    fill[o] = (cs, mf)
                    continue
        if rd and 0.2 < iou[kd] <= C.IOU_MATCH:
            cls[o] = "GROW" if ap[o] < ar[rd] else "SHRINK"
            continue
        cls[o] = "DELETE"
    covered = np.zeros(nr + 1, bool)
    covered[r[cover >= COVER]] = True
    missed = [int(x) for x in range(1, nr + 1) if ar[x] > 0 and not covered[x]]
    dom = {o: int(r[max(by_p[o], key=lambda k: inter[k])]) for o in cls if by_p.get(o)}
    return {"cls": cls, "missed": missed, "dom": dom, "fill": fill, "ref_matched": ref_matched, "tp": tp, "cnt": cnt,
            "r": r, "p": p, "cover": cover, "frac": frac, "inside_count": inside_count, "by_p": by_p}


def corrected(S, ref, info, which):
    """S with the corrections of classes `which` applied from the reference (one-to-one consistent)."""
    L = S.copy()
    nxt = int(L.max()) + 1
    r, cover, frac, inside, by_p = info["r"], info["cover"], info["frac"], info["inside_count"], info["by_p"]
    used = set(int(x) for x in np.flatnonzero(info["ref_matched"]))
    todo = sorted((o, c) for o, c in info["cls"].items() if c in which)
    matched_by = {}
    rr_, pp_, _, iou_ = C.iou_table(ref, S)
    for a_, b_ in zip(rr_[iou_ > C.IOU_MATCH], pp_[iou_ > C.IOU_MATCH]):
        matched_by.setdefault(int(b_), []).append(int(a_))

    def free_refs_of(o):                               # a replaced object no longer holds the reference it matched
        for x in matched_by.get(o, []):
            used.discard(x)

    def put(rr):
        nonlocal nxt
        if rr in used:
            return
        m = (ref == rr) & (L == 0)
        if m.any():
            L[m] = nxt
            nxt += 1
        used.add(rr)

    merged_refs = set()
    for o, c in todo:
        if c == "DELETE":
            L[L == o] = 0
        elif c == "SPLIT":
            refs = [int(r[k]) for k in by_p[o] if cover[k] >= COVER]
            L[L == o] = 0
            free_refs_of(o)
            for rr in refs:
                put(rr)
        elif c == "MERGE":
            for k in by_p[o]:
                if frac[k] >= COVER and inside[r[k]] >= 2:
                    merged_refs.add(int(r[k]))
        elif c == "FILL":
            cs, mf = info["fill"][o]
            Lc = L[cs]
            Lc[mf & ((Lc == 0) | (Lc == o))] = o
        elif c in ("GROW", "SHRINK"):
            L[L == o] = 0
            put(info["dom"][o])
    for rr in sorted(merged_refs):
        for o, c in info["cls"].items():
            if c == "MERGE" and any(int(r[k]) == rr and frac[k] >= COVER for k in by_p[o]):
                L[L == o] = 0
        put(rr)
    if "ADD" in which:
        for rr in info["missed"]:
            put(rr)
    return C.relabel(L)


def pooled_f1(pairs):
    """pairs: [(ref, pred, ign)] -> pooled object F1 at IoU > 0.5 (ignored objects dropped)."""
    nr = npd = tp = 0
    for ref, pred, ign in pairs:
        pr = C.drop_ignored(pred, ign) if ign is not None and ign.any() else pred
        c = C.counts(ref, pr)
        nr, npd, tp = nr + c["n_ref"], npd + c["n_pred"], tp + c["tp_at"][0]
    return C.f1_of(nr, npd, tp)
