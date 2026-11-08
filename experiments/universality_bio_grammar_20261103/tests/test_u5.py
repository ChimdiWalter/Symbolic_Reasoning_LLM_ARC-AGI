"""U5 tests on synthetic images (no study data): operators, effects, exact application, the policy, the taxonomy."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import u5core as C     # noqa: E402
import u5policy as P   # noqa: E402
import u5tax as TX     # noqa: E402


def disk_at(shape, cy, cx, r):
    yy, xx = np.indices(shape)
    return (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r


def scene(seed=0, shape=(96, 128)):
    """Reference: separate discs and touching pairs. Prediction: some touching pairs merged into one object, some
    discs split in two, one false positive, one disc with a hole."""
    rng = np.random.default_rng(seed)
    ref = np.zeros(shape, np.int32)
    pred = np.zeros(shape, np.int32)
    k = 0
    for i, (cy, cx) in enumerate([(20, 20), (20, 60), (60, 20), (60, 60), (20, 100), (60, 100)]):
        r = 8 + rng.integers(0, 2)
        if i in (0, 3):                                   # touching pair, merged in pred
            a, b = disk_at(shape, cy, cx - 6, r), disk_at(shape, cy, cx + 6, r) & ~disk_at(shape, cy, cx - 6, r)
            ref[a], ref[b] = k + 1, k + 2
            k += 2
            pred[a | b] = pred.max() + 1
        elif i == 1:                                      # split in pred
            a = disk_at(shape, cy, cx, r)
            k += 1
            ref[a] = k
            left = a & (np.indices(shape)[1] < cx)
            pred[left] = pred.max() + 1
            pred[a & ~left] = pred.max() + 1
        elif i == 2:                                      # hole in pred
            a = disk_at(shape, cy, cx, r)
            k += 1
            ref[a] = k
            pred[a & ~disk_at(shape, cy, cx, 3)] = pred.max() + 1
        else:
            a = disk_at(shape, cy, cx, r)
            k += 1
            ref[a] = k
            pred[a] = pred.max() + 1
    pred[disk_at(shape, 88, 120, 3)] = pred.max() + 1    # false positive
    I = (ref > 0).astype(np.float32) * 0.8 + rng.random(shape).astype(np.float32) * 0.05
    return C.relabel(pred), C.relabel(ref), I


def test_counts_and_effects():
    pred, ref, I = scene()
    img = C.Image(pred, I, None, ref, None)
    n_ref, n, tp = img.base()
    assert n_ref == 8 and n == 8
    u = C.units(img, "delete", with_effects=True)
    assert len(u["keys"]) == n
    assert set(u["dN"][0].tolist()) == {-1}
    u = C.units(img, "split_dt", with_effects=True)
    best = max(range(len(u["keys"])), key=lambda i: max(u["dTP"][t][i] for t in u["dTP"]))
    assert max(u["dTP"][t][best] for t in u["dTP"]) >= 1          # splitting a merged pair adds a match
    u = C.units(img, "merge_pairs", with_effects=True)
    assert len(u["keys"]) == 1 and u["dN"][0][0] == -1 and u["dTP"][0][0] >= 0   # the two halves merge
    u = C.units(img, "fill_holes", with_effects=True)
    assert u["valid"][0].sum() + u["valid"][1].sum() >= 1


def test_apply_matches_effects():
    pred, ref, I = scene(1)
    img = C.Image(pred, I, None, ref, None)
    u = C.units(img, "split_dt", with_effects=True)
    t = 1
    acc = [(k, t) for k, v, d in zip(u["keys"], u["valid"][t], u["dTP"][t]) if v and d > 0]
    L2, applied = C.apply(img, "split_dt", acc)
    want = sum(int(d) for k, v, d in zip(u["keys"], u["valid"][t], u["dTP"][t]) if v and d > 0)
    got = C.Image(L2, I, None, ref, None).base()[2] - img.base()[2]
    assert got == want and len(applied) == len(acc)


def test_policy_accepts_and_abstains():
    imgs = [C.Image(*scene(s)[:1], scene(s)[2], None, scene(s)[1], None) for s in range(6)]
    demo = {"parent": [], "feats": {}, "valid": {}, "cls": {}, "dTP": {}, "dN": {}}
    us = [C.units(im, "split_dt", with_effects=True) for im in imgs]
    for t in range(3):
        demo["feats"][t] = np.concatenate([x["feats"][t] for x in us])
        demo["valid"][t] = np.concatenate([x["valid"][t] for x in us])
        demo["cls"][t] = np.concatenate([x["cls"][t] for x in us])
        demo["dTP"][t] = np.concatenate([x["dTP"][t] for x in us])
        demo["dN"][t] = np.concatenate([x["dN"][t] for x in us])
    demo["parent"] = np.concatenate([[i] * len(x["keys"]) for i, x in enumerate(us)]).astype(int)
    base = np.array([im.base() for im in imgs], float)
    sp = P.Space(demo, base, len(imgs))
    res = P.verify(sp, len(imgs), demo)
    assert res["status"] == "EVIDENCE", res["status"]
    assert res["accepted"].sum() >= 6
    good = sum(int(demo["dTP"][int(t)][i]) > 0 for i, (a, t) in enumerate(zip(res["accepted"], res["theta"])) if a)
    assert good == res["accepted"].sum()


def test_taxonomy_and_oracle():
    pred, ref, I = scene(2)
    info = TX.classify(pred, ref, None)
    c = sorted(info["cls"].values())
    assert c.count("SPLIT") == 2 and c.count("MERGE") == 1 and c.count("DELETE") == 1
    full = TX.corrected(pred, ref, info, {"SPLIT", "MERGE", "DELETE", "FILL", "GROW", "SHRINK"})
    assert TX.pooled_f1([(ref, full, None)]) == 1.0


def test_ignore():
    pred, ref, I = scene(3)
    ign = np.zeros(pred.shape, bool)
    ign[80:, 110:] = True                                 # covers the false positive
    img = C.Image(pred, I, None, C.drop_ignored(ref, ign), ign)
    assert img.base()[1] == int(pred.max()) - 1


# ----------------------------------------------------------------------------- Amendment 3: conflict-aware scoring
def _exact(img, op, keys, theta=0):
    """Summed unit effects of the units apply would execute, and the exact full-mask change, for a selection."""
    u = C.units(img, op, with_effects=True)
    ids = np.array([u["keys"].index(k) for k in keys], int)
    s = np.zeros(len(u["keys"]), bool)
    s[ids] = True
    e = P.executed(s, P.adjacency(u["conflicts"][theta], len(s)))
    pred = (int(u["dTP"][theta][e].sum()), int(u["dN"][theta][e].sum()))
    new, applied = C.apply(img, op, [(k, theta) for k in keys])
    b0 = img.base()
    b1 = C.Image(new, img.I, img.L_low, img.ref, img.ign).base()
    return pred, (b1[2] - b0[2], b1[1] - b0[1]), int(e.sum()), len(applied)


def test_disjoint_cases_from_the_independent_audit():
    lab = np.zeros((12, 20), np.int32)
    lab[2:5, 2:5], lab[2:5, 12:15] = 1, 2
    ref = np.zeros_like(lab)
    ref[2:5, 2:5] = 1
    img = C.Image(lab, np.full(lab.shape, 0.5, np.float32), ref=ref)
    pred, exact, ne, na = _exact(img, "delete", [1, 2])
    assert pred == exact == (-1, -2) and ne == na == 2
    lab = np.zeros((24, 42), np.int32)
    ref = np.zeros_like(lab)
    for y, x, obj in ((3, 3, 1), (13, 24, 2)):
        lab[y:y + 6, x:x + 6] = obj
        lab[y:y + 6, x + 8:x + 14] = obj
        lab[y + 2:y + 4, x + 6:x + 8] = obj
        ref[y:y + 6, x:x + 6] = 2 * obj - 1
        ref[y:y + 6, x + 8:x + 14] = 2 * obj
    img = C.Image(lab, np.full(lab.shape, 0.5, np.float32), ref=ref)
    pred, exact, ne, na = _exact(img, "split_dt", [1, 2])
    assert pred == exact == (4, 2) and ne == na == 2
    lab = np.zeros((22, 30), np.int32)
    ref = np.zeros_like(lab)
    lab[2:6, 2:4], lab[2:6, 5:7] = 1, 2
    ref[2:6, 2:7] = 1
    lab[12:16, 20:22], lab[12:16, 23:25] = 3, 4
    ref[12:16, 20:25] = 2
    img = C.Image(lab, np.full(lab.shape, 0.5, np.float32), ref=ref)
    keys = C.units(img, "merge_pairs")["keys"]
    pred, exact, ne, na = _exact(img, "merge_pairs", keys)
    assert pred == exact == (2, -2) and ne == na == 2
    lab = np.zeros((12, 20), np.int32)
    lab[2:5, 2:5], lab[2:5, 12:15] = 1, 2
    ign = np.zeros(lab.shape, bool)
    ign[1:6, 11:16] = True
    img = C.Image(lab, np.full(lab.shape, 0.5, np.float32), ref=C.drop_ignored(lab.copy(), ign), ign=ign)
    pred, exact, ne, na = _exact(img, "delete", [1, 2])
    assert pred == exact == (-1, -1) and ne == na == 2


def _collision_image():
    lab = np.zeros((12, 12), np.int32)
    lab[3:8, 3] = 1
    lab[3:8, 5] = 2
    I = np.full(lab.shape, 0.5, np.float32)
    cs, _, masks, _ = C.result_of(C.Image(lab, I), "dilate", 1, 0)
    ref = np.zeros_like(lab)
    ref[cs][masks[0]] = 1
    return C.Image(lab, I, ref=ref)


def test_shared_background_collision_is_scored_as_executed():
    img = _collision_image()
    u = C.units(img, "dilate", with_effects=True)
    assert u["conflicts"][0].tolist() == [[0, 1]]
    pred, exact, ne, na = _exact(img, "dilate", [1, 2])
    assert pred == exact == (0, 0) and ne == na == 0            # both abstained, and scored that way
    pred, exact, ne, na = _exact(img, "dilate", [1])
    assert pred == exact and ne == na == 1


def test_policy_accepts_only_what_executes():
    """The independent audit's counterexample: two demonstration parents with two colliding dilations. The policy must
    not certify the pair; whatever it accepts must be applied, and its predicted F1 must equal the exact F1."""
    img = _collision_image()
    u = C.units(img, "dilate", with_effects=True)
    demo = {"parent": np.array([0, 0, 1, 1]), "feats": {}, "valid": {}, "cls": {}, "dTP": {}, "dN": {},
            "conflicts": {}}
    for t in range(len(C.THETA["dilate"])):
        demo["feats"][t] = np.vstack([u["feats"][t], u["feats"][t]])
        for k in ("valid", "cls", "dTP", "dN"):
            demo[k][t] = np.tile(u[k][t], 2)
        demo["conflicts"][t] = np.vstack([u["conflicts"][t], u["conflicts"][t] + 2])
    sp = P.Space(demo, np.array([img.base(), img.base()]), 2)
    q = {k: {t: u[k][t] for t in u[k]} for k in ("feats", "valid", "cls", "conflicts")}
    res = P.verify(sp, 2, q)
    acc = [u["keys"][i] for i in np.flatnonzero(res["accepted"])]
    t = int(res["theta"][res["accepted"]][0]) if res["accepted"].any() else 0
    new, applied = C.apply(img, "dilate", [(k, t) for k in acc])
    assert len(applied) == len(acc)                              # accepted == applied
    if res["top"] is not None and res["status"] == "EVIDENCE":
        b1 = C.Image(new, img.I, None, img.ref, None).base()
        exact_f1 = 2 * b1[2] / (b1[0] + b1[1])
        assert abs(sp.f1_new[res["top"], 0] - exact_f1) < 1e-12 or not res["accepted"].any()


def test_random_scenes_programs_match_exact_execution():
    """Every program of the space, on synthetic scenes with crowded growth: predicted per-parent counts equal the exact
    counts after applying that program's selection with apply's conflict rule."""
    rng = np.random.default_rng(5)
    for seed in range(3):
        pred, ref, I = scene(seed)
        img = C.Image(pred, I, None, ref, None)
        for op in ("dilate", "close", "merge_pairs", "split_int", "delete"):
            u = C.units(img, op, with_effects=True)
            if not len(u["keys"]):
                continue
            for t in u["valid"]:
                for _ in range(8):
                    s = u["valid"][t] & (rng.random(len(u["keys"])) < 0.6)
                    e = P.executed(s, P.adjacency(u["conflicts"][t], len(s)))
                    keys = [k for k, x in zip(u["keys"], s) if x]
                    new, applied = C.apply(img, op, [(k, t) for k in keys])
                    assert len(applied) == int(e.sum())
                    b0, b1 = img.base(), C.Image(new, I, None, ref, None).base()
                    assert (b1[2] - b0[2], b1[1] - b0[1]) == (int(u["dTP"][t][e].sum()), int(u["dN"][t][e].sum()))


def crowded(seed):
    """A grid of square objects separated by one free pixel (growth collides everywhere), with references slightly
    larger, some fragments and a merged pair."""
    rng = np.random.default_rng(seed)
    lab = np.zeros((40, 40), np.int32)
    ref = np.zeros_like(lab)
    k = 0
    for y in range(2, 36, 6):
        for x in range(2, 36, 6):
            k += 1
            lab[y:y + 5, x:x + 5] = k
            ref[y - 1 if y > 2 else y:y + 5, x:x + 5] = k
    lab[2:7, 7] = 1                                               # bridge -> a merge of objects 1 and 2 columns
    I = np.clip((ref > 0) * 0.7 + rng.random(lab.shape).astype(np.float32) * 0.1, 0, 1).astype(np.float32)
    return C.relabel(lab), C.relabel(ref), I


def test_crowded_scenes_conflicts_are_exercised_and_exact():
    rng = np.random.default_rng(7)
    seen = 0
    for seed in range(3):
        pred, ref, I = crowded(seed)
        img = C.Image(pred, I, None, ref, None)
        for op in ("dilate", "close", "merge_pairs"):
            u = C.units(img, op, with_effects=True)
            for t in u["valid"]:
                seen += len(u["conflicts"][t])
                for _ in range(6):
                    s = u["valid"][t] & (rng.random(len(u["keys"])) < 0.7)
                    e = P.executed(s, P.adjacency(u["conflicts"][t], len(s)))
                    new, applied = C.apply(img, op, [(k, t) for k, x in zip(u["keys"], s) if x])
                    assert len(applied) == int(e.sum())
                    b0, b1 = img.base(), C.Image(new, I, None, ref, None).base()
                    assert (b1[2] - b0[2], b1[1] - b0[1]) == (int(u["dTP"][t][e].sum()), int(u["dN"][t][e].sum()))
    assert seen > 0


def _demo_from(imgs, op):
    us = [C.units(im, op, with_effects=True) for im in imgs]
    T = len(C.THETA[op])
    demo = {"parent": [], "feats": {}, "valid": {}, "cls": {}, "dTP": {}, "dN": {}, "conflicts": {}}
    for t in range(T):
        demo["feats"][t] = np.vstack([x["feats"][t] for x in us])
        for k in ("valid", "cls", "dTP", "dN"):
            demo[k][t] = np.concatenate([x[k][t] for x in us])
        offs = np.cumsum([0] + [len(x["keys"]) for x in us])
        demo["conflicts"][t] = np.vstack([x["conflicts"][t] + o for x, o in zip(us, offs[:-1])]).reshape(-1, 2)
    demo["parent"] = np.concatenate([[i] * len(x["keys"]) for i, x in enumerate(us)]).astype(int)
    demo["keys"] = [(i, k) for i, x in enumerate(us) for k in x["keys"]]
    return demo


def _exact_rows(imgs, op, sp, prog, demo):
    s, _ = P.select(sp, prog, demo)
    t = sp.progs[prog][0]
    d = np.zeros((len(imgs), 2))
    for i, im in enumerate(imgs):
        keys = [k for (j, k), x in zip(demo["keys"], s) if x and j == i]
        new, applied = C.apply(im, op, [(k, t) for k in keys])
        assert len(applied) == len(keys)                         # a valid program never has dropped edits
        b0, b1 = im.base(), C.Image(new, im.I, im.L_low, im.ref, im.ign).base()
        d[i] = (b1[2] - b0[2], b1[1] - b0[1])
    return d


def test_conflicting_programs_are_invalid():
    img = _collision_image()
    demo = _demo_from([img, img], "dilate")
    sp = P.Space(demo, np.array([img.base(), img.base()]), 2)
    both = [i for i, (t, g) in enumerate(sp.progs) if t == 0 and g == ()]       # the true guard selects both units
    assert sp.conflicted[both[0]]
    fit, top = sp.fit()
    assert all(not sp.conflicted[i] for i in fit)
    if top is not None:
        assert np.array_equal(_exact_rows([img, img], "dilate", sp, top, demo), np.c_[sp.Dtp[top], sp.Dn[top]])


def test_fit_and_fold_tops_equal_exact_execution():
    """Every FIT program and fold top on crowded and ordinary scenes: scored per-parent counts equal exact execution."""
    for op in ("dilate", "close", "merge_pairs", "split_int"):
        imgs = []
        for s in range(3):
            pred, ref, I = crowded(s)
            imgs.append(C.Image(pred, I, None, ref, None))
            pred, ref, I = scene(s)
            imgs.append(C.Image(pred, I, None, ref, None))
        demo = _demo_from(imgs, op)
        sp = P.Space(demo, np.array([im.base() for im in imgs], float), len(imgs))
        fit, top = sp.fit()
        res = P.verify(sp, len(imgs), demo)
        progs = set(fit.tolist()) | set(res.get("fold_tops", []))
        for i in sorted(progs)[:60]:
            assert np.array_equal(_exact_rows(imgs, op, sp, i, demo), np.c_[sp.Dtp[i], sp.Dn[i]]), (op, i)


# ----------------------------------------------------------------------------- Amendment 5 regressions
import u5run as RN      # noqa: E402
import u5static as ST   # noqa: E402
import u5eval as EV     # noqa: E402


class FakeSet:
    """In-memory stand-in for u5run.ImgSet over synthetic images (one parent per image)."""

    def __init__(self, scenes, tag):
        self.ds, self.with_ref = "fake_" + tag, True
        self.uids = [f"{tag}{i}" for i in range(len(scenes))]
        self.L = {u: s[0].copy() for u, s in zip(self.uids, scenes)}
        self._I = {u: s[2] for u, s in zip(self.uids, scenes)}
        self._ref = {u: (s[1], None) for u, s in zip(self.uids, scenes)}
        self.parent = {u: u for u in self.uids}
        self.parents = list(self.uids)
        self.pidx = {u: i for i, u in enumerate(self.uids)}

    def I(self, u):
        return self._I[u]

    def low(self, u):
        return None

    def ref(self, u):
        return self._ref[u]

    def image(self, u):
        r, g = self._ref[u]
        return C.Image(self.L[u], self._I[u], None, r, g)

    def base(self):
        return np.array([self.image(u).base() for u in self.uids], float)

    def copy_labels(self):
        return {u: self.L[u].copy() for u in self.uids}


def _collision_scene():
    img = _collision_image()
    return img.L.copy(), img.ref.copy(), img.I.copy()


def test_matched_search_never_ranks_a_conflicting_program():
    """The independent review's counterexample: the all-units dilation program collides and must not be ranked;
    every scored program is counted, and every returned candidate's gain equals exact execution."""
    S = FakeSet([_collision_scene(), _collision_scene()], "col")
    work = {}
    cands = ST._step_candidates(S, ["dilate"], work=work)
    du = RN.set_units(S, "dilate")
    sp = P.Space(du, S.base(), len(S.parents))
    assert work["programs_scored"] == len(sp.progs) and work["programs_scored"] > len(cands)
    assert work["conflicted_excluded"] == int(sp.conflicted.sum()) > 0
    nr, n, tp = S.base().sum(0)
    f0 = 2 * tp / (nr + n)
    for gain, e, npred, op, t, guard in cands:
        T = FakeSet([_collision_scene(), _collision_scene()], "col")
        ST.apply_program(T, [{"op": op, "theta_index": t, "guard": guard}])
        b = T.base().sum(0)
        assert abs((2 * b[2] / (b[0] + b[1]) - f0) - gain) < 1e-12


def test_transfer_labels_one_and_two_targets():
    f = {X: {c: np.array([0.5, 0.6, 0.7]) for c in ("CORA", "ABSTAIN_ALL", "ALL_ON", "MATCHED_SEARCH",
                                                     "FAILURE_BLIND", "SHUFFLED")} for X in ("b", "c")}
    one = EV.transfer_block(f, {"b": "CROSS_DOMAIN_USEFUL"}, ["b"])
    assert one["status"] == "TRANSFER_SINGLE_TARGET" and "LEARNED_TRANSFER" not in one
    assert not any("two targets" in k for k in one)
    two = EV.transfer_block(f, {"b": "CROSS_DOMAIN_USEFUL", "c": "NO_MEASURED_GAIN"}, ["b", "c"])
    assert two["status"] == "TWO_TARGETS" and two["LEARNED_TRANSFER"] is False
    assert EV.transfer_block(f, {}, [])["status"] == "INSUFFICIENT_TARGETS"


def test_growth_gates_are_executable():
    ind = {"CORA": {"admitted": [], "admission_cpu_s": 10.0, "trail": [{"work": {"candidate_validations": 3}}]},
           "FAILURE_BLIND": {"1": {"admission_cpu_s": 30.0, "trail": [{"work": {"candidate_validations": 3}}]}},
           "SHUFFLED": {"1": {"admission_cpu_s": 9.0, "trail": [{"work": {"candidate_validations": 3}}]}}}
    ok, info = EV.alias_gate(ind)
    assert ok is False                                            # nothing admitted: no comparison ran
    wm = EV.work_match(ind)
    assert wm["controls"]["FAILURE_BLIND_1"]["matched"] is False   # 3x CORA's CPU
    assert wm["controls"]["SHUFFLED_1"]["matched"] is True and wm["all_matched"] is False
    ind["CORA"]["admitted"] = ["dilate"]
    ind["CORA"]["trail"].insert(0, {"op": "dilate", "edits_on_validation": 4, "alias_share": 0.0,
                                    "checks": {"not_alias": True}})
    assert EV.alias_gate(ind)[0] is True


def test_proposals_arm_certifies_and_reconciles():
    """The neural-proposal arm runs the same exact certification and accepted == applied == logged checks."""
    scenes = [scene(s) for s in range(4)]
    D, Q = FakeSet(scenes, "pd"), FakeSet([scene(s) for s in range(4, 6)], "pq")
    props = {"programs": [{"operator": "merge_pairs", "theta_index": 0, "guard": [["area_ratio", ">", 0.1]]},
                          {"operator": "merge_pairs", "theta_index": 0, "guard": []},
                          {"operator": "dilate", "theta_index": 9, "guard": []}]}
    r = RN.run_policy_proposals(props, D, Q)
    assert r["discarded_by_schema"] == 1
    for o in r["ops"]:
        if o["status"] == "EVIDENCE":
            assert o["certification"]["all_equal"] and o["query_accepted"] == o["query_applied"]


def test_admission_records_serialize():
    """Amendment 6: admission records with numpy booleans and floats are written as plain JSON."""
    import json
    import u5induce as IN
    rec = {"checks": dict(zip(("a", "b"), (np.bool_(True), bool(np.float64(1.0) > 0)))), "x": np.float64(0.5),
           "n": np.int64(3), "arr": np.arange(3)}
    s = json.dumps(rec, default=IN._jsonable)
    assert json.loads(s) == {"checks": {"a": True, "b": True}, "x": 0.5, "n": 3, "arr": [0, 1, 2]}


# ---------------------------------------------------------------------- Amendment 7: the re-review's regressions ----
ARMS5 = ("ABSTAIN_ALL", "ALL_ON", "MATCHED_SEARCH", "FAILURE_BLIND", "SHUFFLED")


def _matched_controls():
    w = [{"work": {"candidate_validations": 3}}]
    return {"CORA": {"admitted": ["dilate"], "admission_cpu_s": 100.0, "trail": list(w)},
            "FAILURE_BLIND": {"1": {"admission_cpu_s": 90.0, "trail": list(w)}},
            "SHUFFLED": {"1": {"admission_cpu_s": 110.0, "trail": list(w)}}}


def test_a_underworked_matched_search_gives_incomplete_controls_and_no_learned_transfer():
    """(a) Every held contrast positive and the blind and shuffled controls work-matched, but MATCHED_SEARCH
    underworked: each target is INCOMPLETE_CONTROLS and the two-target transfer is not learned."""
    con = {f"CORA - {c}": {"f1": {"mean": 0.02, "ci95": [0.01, 0.04]}} for c in ARMS5}
    raw = EV.claim_label(19, 12, 25, con)
    assert raw == "CROSS_DOMAIN_USEFUL"
    wm = EV.work_match(_matched_controls())
    assert wm["all_matched"] is True
    tgt = {"CORA_calibration_cpu_s": 1000.0, "CORA_calibration_cpu_s_unrounded": 1000.0}
    sched = [list(s) for s in ST.SCHEDULE]
    under = {"cpu_s": 10.0, "cpu_s_exact": 10.0, "stopped": "budget reached", "schedule": sched,
             "work": {"stopped_inside_step": 1, "stages_completed": sched[:1]}}
    ok, info = EV.matched_search_work(under, tgt)
    assert ok is False and info["by_cpu"] is False and info["full_schedule_completed"] is False
    labels = {X: EV.gated_label(raw, wm["all_matched"], ok) for X in ("b", "c")}
    assert labels == {"b": "INCOMPLETE_CONTROLS", "c": "INCOMPLETE_CONTROLS"}
    assert EV.evidence_gate(wm["all_matched"], ok, True) == "WITHHELD_UNMATCHED_MATCHED_SEARCH"
    f = {X: {c: np.array([0.5, 0.6, 0.7]) + (0.05 if c == "CORA" else 0.0) for c in ("CORA",) + ARMS5}
         for X in ("b", "c")}
    tr = EV.transfer_block(f, labels, ["b", "c"])
    assert tr["status"] == "TWO_TARGETS" and tr["LEARNED_TRANSFER"] is False
    # sensitivity of the test: the same case with MATCHED_SEARCH work-matched passes both gates
    ok2, _ = EV.matched_search_work(dict(under, cpu_s=600.0, cpu_s_exact=600.0), tgt)
    assert ok2 is True and EV.evidence_gate(True, ok2, True) == "SUPPORTED"
    lab2 = {X: EV.gated_label(raw, True, ok2) for X in ("b", "c")}
    assert EV.transfer_block(f, lab2, ["b", "c"])["LEARNED_TRANSFER"] is True
    # evaluate applies the work gates to each target's label before the transfer block reads the labels
    import inspect
    src = inspect.getsource(EV._evaluate)                                  # Amendment 8: evaluate's body
    assert src.index("matched_search_work(") < src.index("gated_label(") < src.index("transfer_block(")
    assert "_evaluate(cfg)" in inspect.getsource(EV.evaluate)


def _fake_imgset(scenes, tag):
    def make(ds, uids, stage="S", with_ref=False, labels=None, share=None):
        F = FakeSet(scenes, tag)
        if labels:
            F.L = {u: labels[u].copy() for u in F.uids}
        return F
    return make


def _run_matched(monkeypatch, inject=None):
    """fit_matched on synthetic scenes with a two-stage schedule; optionally an in-step budget stop at call `inject`
    (the budget fires before the last operator's program space, as in `_step_candidates`)."""
    scenes = [scene(s) for s in range(3)]
    monkeypatch.setattr(ST, "SCHEDULE", [(1, 2), (2, 2)])
    monkeypatch.setattr(RN, "ImgSet", _fake_imgset(scenes, "ms"))
    real, calls, snap = ST._step_candidates, [], {}

    def wrapped(S, ops, t0=None, budget_s=None, work=None):
        calls.append(len(work["stages_completed"]))
        if inject is not None and len(calls) == inject:
            before = work["programs_scored"]
            out = real(S, ops[:-1], None, None, work)
            work["stopped_inside_step"] = work.get("stopped_inside_step", 0) + 1
            snap.update(applications=work["exact_beam_applications"], before=before,
                        after=work["programs_scored"], partial=len(out))
            return out
        return real(S, ops, t0, budget_s, work)

    monkeypatch.setattr(ST, "_step_candidates", wrapped)
    r = ST.fit_matched("fake_ms", [f"ms{i}" for i in range(3)], 1e9)
    monkeypatch.setattr(ST, "_step_candidates", real)
    return r, calls, snap


def test_b_in_step_stop_in_the_final_stage_is_budget_reached_and_unmatched(monkeypatch):
    """(b) An in-step budget stop at the last step of the final stage: "budget reached", the partial candidate list
    counted but never applied, the final stage not completed, and MATCHED_SEARCH unmatched when its work is short."""
    r0, calls, _ = _run_matched(monkeypatch)
    last = len(calls)
    assert calls[-1] == 1 and r0["stopped"] == "schedule exhausted"      # the last call is in the final stage
    r, calls2, snap = _run_matched(monkeypatch, inject=last)
    assert len(calls2) == last and snap["partial"] > 0
    assert r["stopped"] == "budget reached" and r["work"]["stopped_inside_step"] == 1
    assert r["work"]["stages_completed"] == [[1, 2]]
    assert r["work"]["exact_beam_applications"] == snap["applications"]   # the partial beam was not applied
    assert r["work"]["programs_scored"] == snap["after"] > snap["before"]  # its scored programs were counted
    assert r["work"]["partial_step_candidates_discarded"] == snap["partial"]
    assert len(r["program"]) <= 1                                          # only completed depth levels count
    assert isinstance(r["cpu_s_exact"], float)
    ok, info = EV.matched_search_work(r, {"CORA_calibration_cpu_s_unrounded": 1e6})
    assert ok is False and info["full_schedule_completed"] is False


def test_c_full_schedule_exhaustion_stays_matched(monkeypatch):
    """(c) Control: a search that completes its whole schedule with no in-step stop is work-matched whatever its CPU;
    records claiming exhaustion with an in-step stop or a missing stage are not."""
    r, calls, _ = _run_matched(monkeypatch)
    assert r["stopped"] == "schedule exhausted" and r["work"]["stopped_inside_step"] == 0
    assert r["work"]["stages_completed"] == r["schedule"] == [[1, 2], [2, 2]]
    ok, info = EV.matched_search_work(r, {"CORA_calibration_cpu_s_unrounded": 1e6})
    assert ok is True and info["full_schedule_completed"] is True and info["by_cpu"] is False
    forged = dict(r, work=dict(r["work"], stopped_inside_step=1))
    assert EV.matched_search_work(forged, {"CORA_calibration_cpu_s_unrounded": 1e6})[0] is False
    short = dict(r, work=dict(r["work"], stages_completed=[[1, 2]]))
    assert EV.matched_search_work(short, {"CORA_calibration_cpu_s_unrounded": 1e6})[0] is False


def test_d_rounding_near_zero_cannot_make_a_comparator_matched():
    """Amendment 7: factor-of-two decisions use unrounded CPU when recorded, otherwise the worst case of the
    one-decimal record."""
    w = [{"work": {"candidate_validations": 2}}]
    ind = {"CORA": {"admitted": [], "admission_cpu_s": 0.1, "trail": list(w)},
           "FAILURE_BLIND": {"1": {"admission_cpu_s": 0.1, "trail": list(w)}},
           "SHUFFLED": {"1": {"admission_cpu_s": 0.2, "trail": list(w)}}}
    assert EV.work_match(ind)["controls"]["FAILURE_BLIND_1"]["matched"] is False   # true ratio anywhere in [1/3, 3]
    ind["CORA"]["admission_cpu_s_exact"], ind["FAILURE_BLIND"]["1"]["admission_cpu_s_exact"] = 0.1234, 0.1301
    assert EV.work_match(ind)["controls"]["FAILURE_BLIND_1"]["matched"] is True
    ms = {"cpu_s": 0.5, "stopped": "budget reached", "work": {"stopped_inside_step": 1, "stages_completed": []}}
    assert EV.matched_search_work(ms, {"CORA_calibration_cpu_s": 1.0})[0] is False
    ms["cpu_s_exact"] = 0.62                      # Amendment 9: a recorded sum of 1.0 s needs 0.65 s, so 0.62 is short
    assert not EV.matched_search_work(ms, {"CORA_calibration_cpu_s": 1.0, "CORA_calibration_cpu_s_unrounded": 1.0})[0]
    ms["cpu_s_exact"] = 0.70
    assert EV.matched_search_work(ms, {"CORA_calibration_cpu_s": 1.0, "CORA_calibration_cpu_s_unrounded": 1.0})[0]


# ---------------------------------------------------------------- Amendment 8: the CORA_TOLERANT secondary arm -----
class _FoldSpace:
    """A stand-in space with fixed fold tops: tops[p] is the top program when parent p is held out."""

    def __init__(self, tops, harm_rows=(), P=6):
        self.P, self.tops = P, tops
        self.base = np.ones((P, 3))
        self.progs = [(0, (0,)), (0, (1,)), (0, (0, 1))]
        self.preds = {0: [(0, ">", 0.5), (1, "<", 0.5)]}
        self.harm = np.zeros((3, P), bool)
        for i in harm_rows:
            self.harm[i, 0] = True
        self.conflicted = np.zeros(3, bool)

    def fit(self, keep=None, reverse=False):
        held = int(np.flatnonzero(~keep)[0])
        return np.zeros(0, int), self.tops[held]


def _q4():
    F = np.array([[0.9, 0.1], [0.9, 0.9], [0.1, 0.1], [0.7, 0.2]])
    return {"feats": {0: F}, "valid": {0: np.ones(4, bool)}, "cls": {0: np.zeros(4, int)},
            "conflicts": {0: np.zeros((0, 2), int)}}


def test_tolerant_rule_is_two_thirds_of_folds_and_no_demo_harm():
    q = _q4()
    r = P.verify_tolerant(_FoldSpace([0, 0, 0, 0, 1, 2]), 6, q)              # 4/6 = two-thirds exactly: passes
    assert r["status"] == "EVIDENCE" and r["top"] == 0 and r["n_folds"] == 6
    assert r["accepted"].tolist() == [True, True, False, True]              # program 0: feature 0 > 0.5
    assert P.verify_tolerant(_FoldSpace([0, 0, 0, 1, 1, 2]), 6, q)["status"] == "NO_TOLERANT_MAJORITY"   # 3/6
    assert P.verify_tolerant(_FoldSpace([0, 0, 0, 0, 1, None]), 6, q)["status"] == "EVIDENCE"            # 4/6
    assert P.verify_tolerant(_FoldSpace([None] * 6), 6, q)["status"] == "NO_FIT"
    assert P.verify_tolerant(_FoldSpace([0, 0, 0, 0, 0, 0], harm_rows=(0,)), 6,
                             q)["status"] == "HARMS_DEMONSTRATION_PARENT"
    assert P.verify_tolerant(_FoldSpace([0] * 6), 1, q)["status"] == "INSUFFICIENT_DEMONSTRATIONS"
    assert P.TOLERANCE == (2, 3)


def test_tolerant_policy_certifies_and_reconciles():
    """The tolerant arm runs the same exact certification and accepted == applied == logged checks; on these scenes
    it accepts split_dt, merge_pairs and delete (the protocol's rule abstains on delete: RESTART_UNSTABLE). On crowded
    scenes with conflicting units nothing fits under either rule."""
    D, Q = FakeSet([scene(s) for s in range(6)], "tD"), FakeSet([scene(s) for s in range(6, 9)], "tQ")
    r = RN.run_policy(list(C.OPS), D, Q, rule="tolerant")
    ev = [o["op"] for o in r["ops"] if o["status"] == "EVIDENCE"]
    assert ev == ["split_dt", "merge_pairs", "delete"]
    for o in r["ops"]:
        assert o["rule"] == "tolerant"
        if o["status"] == "EVIDENCE":
            assert o["certification"]["all_equal"] and o["query_accepted"] == o["query_applied"] > 0
            assert o["demo_accepted"] == o["demo_applied"] and 3 * o["top_share"] >= 2
    assert len(r["query_log"]) == sum(o.get("query_applied", 0) for o in r["ops"])
    s = RN.run_policy(list(C.OPS), FakeSet([scene(s) for s in range(6)], "sD"),
                      FakeSet([scene(s) for s in range(6, 9)], "sQ"))
    assert all("rule" not in o for o in s["ops"])                           # the protocol's rule is unchanged
    assert [o["status"] for o in s["ops"] if o["op"] == "delete"] == ["RESTART_UNSTABLE"]
    c = RN.run_policy(list(C.OPS), FakeSet([crowded(s) for s in range(5)], "cd"),
                      FakeSet([crowded(s) for s in range(5, 8)], "cq"), rule="tolerant")
    assert not any(o["status"] == "EVIDENCE" for o in c["ops"])


def test_tolerant_induction_writes_its_own_record(monkeypatch, tmp_path):
    import json
    import u5induce as IN
    os.makedirs(tmp_path / "x")
    monkeypatch.setattr(IN, "W", str(tmp_path))
    fr = {"per_class": {}, "probe_cpu_s": 1.0}
    monkeypatch.setattr(IN, "specify", lambda ds, relabel=None: (["dilate"], fr, {}))
    calls = []

    def admit(ds, cands, rule="strict"):
        calls.append(rule)
        return [], [{"work": {"candidate_validations": len(cands), "cpu_s": 0.1, "cpu_s_exact": 0.1234}}], 0.1
    monkeypatch.setattr(IN, "admit", admit)
    IN.induce("x", "tolerant")
    assert sorted(os.listdir(tmp_path / "x")) == ["INDUCTION_TOLERANT.json"] and set(calls) == {"tolerant"}
    d = json.load(open(tmp_path / "x" / "INDUCTION_TOLERANT.json"))
    assert d["rule"] == "tolerant" and d["CORA"]["admission_cpu_s_exact"] == 0.1234


def test_alias_check_handles_add_lowthresh_edits(monkeypatch):
    """Amendment 8: the alias check of an accepted add_lowthresh edit reads the low-threshold labels the policy used
    (it crashed without them); an added object is neither a deletion nor reproducible by object operators."""
    import u5induce as IN
    L = disk_at((64, 64), 20, 20, 7).astype(np.int32)
    low = L.copy()
    low[disk_at((64, 64), 44, 44, 6)] = 2
    I = np.random.default_rng(1).random((64, 64)).astype(np.float32)
    keys = C.units(C.Image(L, I, low), "add_lowthresh", with_effects=False)["keys"]
    assert len(keys) >= 1
    monkeypatch.setattr(IN, "_low_labels", lambda ds, uid: low)
    monkeypatch.setattr(IN.RN, "inten", lambda ds, uid: I)
    k = keys[0]
    edit = {"uid": "u", "op": "add_lowthresh", "key": list(k) if isinstance(k, tuple) else k, "theta": 0,
            "before_sha": C.sha(L)}
    assert IN.alias_share("fake", "add_lowthresh", [edit], ["dilate"], {"u": L}) == (0.0, 1)


# ------------------------------------------------------------------- Amendment 9: the legacy CPU bound and waterfall --
def test_near_threshold_legacy_cpu_is_unmatched():
    """The re-review's counterexample: recorded CORA CPU 1.0 s, MATCHED_SEARCH exact 0.58 s, budget-stopped. The 0.155 s
    slack said matched (0.58 >= 1.155 / 2); with probe-child rounding the bound is at least 0.295 s and the legacy slack
    0.30 s makes it unmatched (0.58 < 1.30 / 2), for every record without exact CPU."""
    assert EV.LEGACY_SLACK_S >= 0.155 + 7 * 40 * 0.0005
    ms = {"cpu_s": 0.6, "cpu_s_exact": 0.58, "stopped": "budget reached",
          "work": {"stopped_inside_step": 1, "stages_completed": []}}
    variants = [{"CORA_calibration_cpu_s": 1.0, "CORA_calibration_cpu_s_unrounded": 1.0},           # Amendments 7-8
                {"CORA_calibration_cpu_s": 1.0, "CORA_calibration_cpu_s_recorded_sum": 1.0},        # Amendment 9
                {"CORA_calibration_cpu_s": 1.0, "CORA_calibration_cpu_s_conservative_upper": 1.0 + EV.LEGACY_SLACK_S},
                {"CORA_calibration_cpu_s": 1.0}]                                                   # one-decimal only
    for tgt in variants:
        ok, info = EV.matched_search_work(ms, tgt)
        assert ok is False and info["by_cpu"] is False and info["cora_cpu_s_high"] >= 1.295, tgt
    for tgt in variants[:3]:
        assert EV.matched_search_work(dict(ms, cpu_s_exact=0.66), tgt)[0] is True              # 0.66 >= 0.65
    assert EV.matched_search_work(dict(ms, cpu_s_exact=0.66), variants[3])[0] is False         # needs 0.675
    assert EV.matched_search_work(dict(ms, cpu_s_exact=0.68), variants[3])[0] is True


def test_waterfall_repeats_verify_stage_by_stage():
    """The acceptance waterfall reproduces verify's FIT size, status and accepted units, and its stages only narrow."""
    import u5waterfall as WF
    D, Q = FakeSet([scene(s) for s in range(6)], "wD"), FakeSet([scene(s) for s in range(6, 9)], "wQ")
    seen = set()
    for op in C.OPS:
        du = RN.set_units(D, op)
        if not len(du["keys"]):
            continue
        sp = P.Space(du, D.base(), len(D.parents))
        npar = len(set(du["parent"].tolist()))
        qu = RN.set_units(Q, op)
        w = WF.waterfall(sp, npar, qu)
        r = P.verify(sp, npar, qu, True)
        if w.get("stop") == "NO_FIT":
            assert r["status"] in ("NO_FIT", "INSUFFICIENT_DEMONSTRATIONS")
            continue
        seen.add(r["status"])
        assert w["fit"] == r["fit"] and w["verify_status"] == r["status"] and w["accepted"] == int(r["accepted"].sum())
        assert w["programs"] >= w["admissible"] >= w["fit"] >= 1
        assert w["selected_by_some_fit"] >= w["near_top_intersection"] >= w["intersection_with_fold_tops"]
        assert w["intersection_with_fold_tops"] >= w["after_class_agreement"]
        if r["status"] == "EVIDENCE":
            assert w["accepted"] == w["after_class_agreement"]
        assert w["top_guard_selected"] == w["top_executed"] + w["top_conflict_abstained"]
    assert "EVIDENCE" in seen                    # split_dt, merge_pairs and delete, each on the original state
