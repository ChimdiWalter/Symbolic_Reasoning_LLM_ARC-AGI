"""Regression tests for the calibrated-acceptance harness (<python environment>: python -I -m pytest tests/test_calacc.py).
Synthetic tests check the new rule against brute force; the real-data tests use NuInsSeg CALIBRATION images only and
open no PUMA image except through the guards (which must refuse)."""
import hashlib
import json
import os
import sys

import numpy as np
import pytest

ROOT = "/path/to/repository/experiments/calibrated_acceptance_20261108"
U5 = "/path/to/repository/experiments/universality_bio_grammar_20261103"
for p in (os.path.join(U5, "scripts"), os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)
import cadata as CD      # noqa: E402
import calrule as CR     # noqa: E402
import u5policy as P     # noqa: E402


def _synthetic(n_img=6, U=120, F=3, seed=1):
    rng = np.random.default_rng(seed)
    par = rng.integers(0, n_img, U)
    du = {"parent": par, "feats": {0: rng.normal(size=(U, F)), 1: rng.normal(size=(U, F))},
          "valid": {0: rng.random(U) < 0.9, 1: rng.random(U) < 0.8},
          "dTP": {0: rng.integers(-1, 2, U), 1: rng.integers(-1, 2, U)},
          "dN": {0: rng.integers(-1, 2, U), 1: rng.integers(-1, 2, U)}}
    base = np.column_stack([rng.integers(20, 40, n_img), rng.integers(20, 40, n_img), rng.integers(5, 15, n_img)])
    return du, base


def test_judged_matches_u5_replay_rule():
    for dtp in (-2, -1, 0, 1, 2):
        for dn in (-2, -1, 0, 1, 2):
            ben, harm = CR.judged([dtp], [dn])
            k = 0 if (dtp > 0 or (dtp == 0 and dn < 0)) else (1 if (dtp < 0 or (dtp == 0 and dn > 0)) else 2)
            assert (bool(ben[0]), bool(harm[0])) == (k == 0, k == 1)


def test_judged_sums_match_brute_force_and_space():
    du, base = _synthetic()
    sp = P.Space(du, base, 6)
    A, H, Bf = CR.judged_sums(sp, du)
    for i in list(range(0, len(sp.progs), 37)) + [len(sp.progs) - 1]:
        t, g = sp.progs[i]
        s = du["valid"][t].copy()
        for k in g:
            j, op, q = sp.preds[t][k]
            s &= (du["feats"][t][:, j] < q) if op == "<" else (du["feats"][t][:, j] > q)
        ben, harm = CR.judged(du["dTP"][t], du["dN"][t])
        for img in range(6):
            m = s & (du["parent"] == img)
            assert A[i, img] == m.sum()
            assert H[i, img] == (m & harm).sum()
            assert Bf[i, img] == (m & ben).sum()
            assert sp.Dtp[i, img] == du["dTP"][t][m].sum()


def test_fold_program_respects_harm_constraint():
    du, base = _synthetic(seed=3)
    sp = P.Space(du, base, 6)
    A, H, Bf = CR.judged_sums(sp, du)
    keep = np.ones(6, bool)
    top = CR.fold_program(sp, A, H, keep, alpha=1.0)
    top_c = CR.fold_program(sp, A, H, keep, alpha=0.2)
    if top_c is not None:
        assert H[top_c].sum() <= 0.2 * A[top_c].sum() + 1e-9
        assert sp.pooled_gain(keep)[top_c] > 0
    if top is not None and H[top].sum() > 0.2 * A[top].sum():
        assert top_c != top


def test_cluster_bounds_behave():
    org = np.repeat(np.arange(8), 5)
    d = np.full(40, 0.01)
    a = np.full(40, 2.0)
    h = np.zeros(40)
    b = CR.cluster_bounds(org, 8, d, h, a, 0.05 / 3)
    assert b["lcb_gain"] > 0 and b["ucb_harmful_rate"] == 0.0
    d2 = np.where(org % 2 == 0, 0.02, -0.02)
    b2 = CR.cluster_bounds(org, 8, d2, h, a, 0.05 / 3)
    assert b2["lcb_gain"] < 0
    h3 = np.where(org < 4, 2.0, 0.0)
    b3 = CR.cluster_bounds(org, 8, d, h3, a, 0.05 / 3)
    assert abs(b3["harmful_rate"] - 0.5) < 1e-12 and b3["ucb_harmful_rate"] > 0.5
    assert CR.cluster_bounds(org, 8, d, h, np.zeros(40), 0.05)["ucb_harmful_rate"] is None


def test_calibrate_op_false_acceptance_near_nominal_on_noise():
    """Pure-noise operators (each unit's effect is +1 or -1 matched object at random): the organ-clustered t rule
    accepts at about its nominal 5% level (at most 8 of 60 here); the percentile bootstrap, recorded only, accepts
    more often (development finding behind the switch to t bounds)."""
    rng = np.random.default_rng(123)
    acc_t = acc_boot = 0
    for s in range(60):
        du, base = _synthetic(n_img=12, U=300, seed=1000 + s)
        du["dTP"] = {t: rng.choice([-1, 1], len(du["parent"])) for t in (0, 1)}
        du["dN"] = {t: np.zeros(len(du["parent"]), int) for t in (0, 1)}
        sp = P.Space(du, base, 12)
        A, H, Bf = CR.judged_sums(sp, du)
        rec, final = CR.calibrate_op(sp, A, H, Bf, np.arange(12) % 6, 6, 3)
        acc_t += int(final is not None)
        acc_boot += int(rec["bootstrap_bounds_descriptive"]["lcb_gain"] > 0)
    assert acc_t <= 8
    assert acc_t <= acc_boot


def test_held_selection_rules():
    rois = [f"training_set_{s}_roi_{i:03d}" for s in ("primary", "metastatic") for i in range(1, 104)]
    fmt = CD.format_roi(rois)
    h1, r1 = CD.held_selection("a" * 64, rois)
    h1b, _ = CD.held_selection("a" * 64, rois)
    h2, _ = CD.held_selection("b" * 64, rois)
    assert h1 == h1b and h1 != h2
    assert sum(v == "primary" for v in h1.values()) == 50 and sum(v == "metastatic" for v in h1.values()) == 50
    assert fmt not in h1 and fmt not in r1 and not set(h1) & set(r1)
    assert set(h1) | set(r1) | {fmt} == set(rois)


def test_format_roi_is_the_recorded_one():
    assert CD.format_roi() == json.load(open(os.path.join(CD.WORK, "format_check", "FORMAT_CHECK.json")))["format_roi"]


def test_reader_guards_before_go():
    if os.path.exists(CD.HELD_MANIFEST):
        pytest.skip("after GO")
    rd = CD.Reader()
    other = [r for r in CD.rois() if r != rd._fmt][0]
    with pytest.raises(PermissionError):
        rd.image(other)
    with pytest.raises(PermissionError):
        rd.reference(rd._fmt, (1024, 1024))
    with pytest.raises(PermissionError):
        rd.reference(other, (1024, 1024), format_check=True)
    with pytest.raises(PermissionError):
        rd.open_evaluator()


def test_geojson_rasterization_keeps_smaller_object():
    big = {"geometry": {"type": "Polygon", "coordinates": [[[2, 2], [20, 2], [20, 20], [2, 20], [2, 2]]]}}
    small = {"geometry": {"type": "Polygon", "coordinates": [[[5, 5], [9, 5], [9, 9], [5, 9], [5, 5]]]}}
    multi = {"geometry": {"type": "MultiPolygon", "coordinates": [[[[25, 25], [28, 25], [28, 28], [25, 28]]],
                                                                  [[[30, 30], [33, 30], [33, 33], [30, 33]]]]}}
    lab = CD.geojson_labels((40, 40), [big, small, multi])
    assert lab.max() == 3
    assert lab[7, 7] != lab[15, 15] and lab[7, 7] > 0 and lab[15, 15] > 0
    assert lab[26, 26] == lab[31, 31] > 0


def test_image_parents_match_organ_sums():
    import u5run as RN
    m = RN.man("nuinsseg")["images"]
    cal = sorted(u for u, v in m.items() if v["side"] == "calibration")[:8]
    S = RN.ImgSet("nuinsseg", cal, "S", True)
    T = CR.ImageParents("nuinsseg", cal, "S", True)
    b_org, b_img = S.base(), T.base()
    assert b_img.shape[0] == len(cal)
    for o, p in enumerate(S.parents):
        rows = [T.pidx[u] for u in cal if T.organ[u] == p]
        assert np.allclose(b_img[rows].sum(0), b_org[o])


def test_run_calibrated_small_real_subset():
    import u5run as RN
    m = RN.man("nuinsseg")["images"]
    org = {}
    for u, v in sorted(m.items()):
        if v["side"] == "calibration":
            org.setdefault(v["parent"], []).append(u)
    sub = sorted(u for o in sorted(org)[:3] for u in org[o][:2])
    D = CR.ImageParents("nuinsseg", sub, "S", True)
    r = CR.run_calibrated(["erode"], D, None, K=3)
    o = r["ops"][0]
    assert o["status"] in ("ACCEPTED", "GAIN_NOT_CERTIFIED", "HARM_NOT_CERTIFIED", "NO_OUT_OF_FOLD_EDIT",
                           "NO_FINAL_PROGRAM", "NO_UNITS")
    if o["status"] == "ACCEPTED":
        assert o["demo_applied"] == o["final_calibration"]["accepted"]


def test_u5_code_unchanged():
    fz = json.load(open(os.path.join(U5, "CODE_FREEZE.json")))["files"]
    for p, hh in fz.items():
        assert hashlib.sha256(open(os.path.join(U5, p), "rb").read()).hexdigest() == hh, p


def test_in_fold_limit_and_bound_are_separate():
    assert CR.LAMBDA == 0.40 and CR.ALPHA == 0.60
    du, base = _synthetic(n_img=12, U=400, seed=11)
    sp = P.Space(du, base, 12)
    A, H, Bf = CR.judged_sums(sp, du)
    rec, final = CR.calibrate_op(sp, A, H, Bf, np.arange(12) % 6, 6, 3, alpha=0.6, lam=0.4)
    assert rec["lambda_in_fold"] == 0.4 and rec["alpha"] == 0.6
    for t in rec["fold_programs"]:
        if t is not None:
            assert H[t].sum() <= A[t].sum()            # a program exists; its in-fold rate was checked on 5 organs
    if final is not None:
        assert H[final].sum() <= 0.4 * A[final].sum() + 1e-9
