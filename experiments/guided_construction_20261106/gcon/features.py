"""Cheap features of a block, computed after the pair analysis and before any verification (PROTOCOL.md section 5).
No test input, no test output and no benchmark name enters them."""
import math

from gcon import engine as EN
from objgrow import construct as CS, scene as SC

KINDS = ("S", "T", "W")


def _l(x):
    return math.log1p(max(0.0, float(x)))


NAMES = (["h_pairs", "h_area", "h_same_shape", "h_rank0", "h_rank1", "h_rank2", "h_gridop"]
         + ["v_" + v for v in SC.VIEWS]
         + ["v_changed", "v_appeared", "v_objects", "v_required", "v_explained_share", "v_unexplained_share",
            "v_full", "v_partial", "v_growth", "v_common", "v_cover", "v_conj"]
         + ["k_" + k for k in KINDS]
         + ["e_" + t for t in EN.EDIT_TYPES]
         + ["e_param", "e_proposing_share", "e_place", "b_ops_bound", "w_crop_targets", "w_one_colour"])


def hole_part(hs):
    hole = hs.hole
    n = len(hole)
    area = sum(len(x) * len(x[0]) for x, _ in hole) / max(1, n)
    same = all((len(x), len(x[0])) == (len(y), len(y[0])) for x, y in hole)
    rank = int(hs.meta.get("rank", 0))
    gridop = 1.0 if (hs.meta.get("inner") or hs.meta.get("outer")) else 0.0
    return [_l(n), _l(area), float(same)] + [1.0 if rank == k else 0.0 for k in (0, 1, 2)] + [gridop]


def view_part(vs):
    out = [1.0 if vs.vi == k else 0.0 for k in range(len(SC.VIEWS))]
    r = vs.rec
    npairs = max(1, len(vs.pairs))
    req = sum(len(p.required) for p in vs.pairs)
    ch, ap = r["changed_objects"], r["appeared_cells"]
    out += [_l(ch), _l(ap), _l(sum(r["objects"]) / npairs), _l(req),
            (r["explained_objects"] / ch) if ch else 0.0, (r["unexplained_cells"] / ap) if ap else 0.0,
            float(r["full"]), float(r["partial"]), float(vs.growth), _l(len(vs.common)), _l(len(vs.cov)),
            _l(len(vs.cov_all) - len(vs.cov))]
    return out


#: content comparisons made by the W flag (an object's bounding-box crop compared with a target), for reporting
CMP = {"n": 0}


def _w_flags(vs):
    """(1 if every pair has an input object whose bounding-box crop EQUALS the target, content included; 1 if every
    target is one colour). Pixel comparisons, not operations; counted in CMP."""
    crop = True
    for p in vs.pairs:
        x, y, s = p.x, p.y, p.s
        t = False
        for o in s.objs:
            i0, j0, i1, j1 = o.box
            if (o.h, o.w) == (len(y), len(y[0])):
                CMP["n"] += 1
                if tuple(tuple(x[i][j0:j1 + 1]) for i in range(i0, i1 + 1)) == y:
                    t = True
                    break
        if not t:
            crop = False
            break
    one = all(len({v for r in p.y for v in r}) == 1 for p in vs.pairs)
    return float(crop), float(one)


def block_part(hs, vs, b):
    kind, vi, j = b
    out = [1.0 if kind == k else 0.0 for k in KINDS]
    et = [0.0] * len(EN.EDIT_TYPES)
    param = prop = place = 0.0
    npairs = max(1, len(vs.pairs))
    if kind == "S":
        e = vs.common[j]
        if e[0] in EN.EDIT_TYPES:
            et[EN.EDIT_TYPES.index(e[0])] = 1.0
        param = _l(sum(abs(v) for v in e[1:] if isinstance(v, int)))
        prop = vs.proposing.get(e, 0) / npairs
        place = j / max(1, len(vs.common))
        bound = len(vs.cov_all) * npairs
    elif kind == "T":
        cnt = {}
        for p, i in vs.req_objs:
            for e in p.bound[i]:
                cnt[e] = 1
        m = min(CS.MAX_TWO_RULE_EDITS, len(cnt))
        bound = m * max(0, m - 1) * len(vs.preds)
    else:
        bound = len(vs.preds) * npairs
    wc, wo = _w_flags(vs) if kind == "W" else (0.0, 0.0)
    return out + et + [param, prop, place, _l(bound), wc, wo]


def hole_features(hs):
    """{block: feature list} for every block of the hole."""
    hp = hole_part(hs)
    out = {}
    for vs in hs.views:
        if vs.skipped:
            continue
        vp = view_part(vs)
        for b in vs.blocks:
            out[b] = hp + vp + block_part(hs, vs, b)
    return out


assert len(NAMES) == 7 + 12 + 12 + 3 + len(EN.EDIT_TYPES) + 6
