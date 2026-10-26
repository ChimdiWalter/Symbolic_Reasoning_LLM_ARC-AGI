"""Capability-gap analysis of CORA-only on the 120 public ARC-AGI-2 evaluation puzzles.

Label: exposed public evaluation, development evidence. The public evaluation set is public and has been used in
development before; nothing here is a competition score. The expected outputs are read for analysis only; no solver
reads them, and nothing here changes a solver.

Usage: python3 scripts/eval120_capability_gaps.py DATA_DIR RUNS_DIR OUT_JSON
  DATA_DIR  the extracted competition archive (arc-agi_evaluation_challenges.json, arc-agi_evaluation_solutions.json)
  RUNS_DIR  the downloaded outputs of the private Kaggle development runs (cora-only-g3-dev-eval-a and -b)

Measures per puzzle:
1. the output-shape relation (same shape; crop, i.e. the output is a sub-grid of the input; scale up or down by an
   integer factor; tiling by a multiple of the input shape; constant output shape; other);
2. which CORA source produced attempts in the recorded runs, and, where the original engine fitted the demonstrations,
   how its prediction differs from the expected output;
3. on same-shape puzzles, the change profile and observables of the existing real-puzzle scripts (imported read-only);
4. oracle-style checks of simple whole-grid rules (colour map, dihedral transform, integer scaling, tiling by dihedral
   copies, crop to one object chosen by a simple selector): does the rule reproduce every demonstration, and does it
   then also predict the expected test output? These need no new solver; they bound what simple extensions could open.
"""
import collections
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

LABEL = "exposed public evaluation, development evidence"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "scripts", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arr(g):
    return np.asarray(g, dtype=int)


# ------------------------------------------------------------------ 1. shape relation
def is_subgrid(A, B):
    (H, W), (h, w) = A.shape, B.shape
    if h > H or w > W:
        return False
    win = np.lib.stride_tricks.sliding_window_view(A, (h, w))
    return bool((win == B).all(axis=(2, 3)).any())


def shape_relation(pairs):
    """Primary relation over all pairs with a known output, in a fixed priority order."""
    if all(A.shape == B.shape for A, B in pairs):
        return "same shape"
    if all(is_subgrid(A, B) and A.shape != B.shape for A, B in pairs):
        return "crop (output is a sub-grid of the input)"
    ks = set()
    for A, B in pairs:
        (H, W), (h, w) = A.shape, B.shape
        ks.add((h / H, w / W))
    if len(ks) == 1:
        ry, rx = next(iter(ks))
        if ry == rx and ry > 1 and float(ry).is_integer():
            return "scale up by an integer factor"
        if ry == rx and ry < 1 and float(1 / ry).is_integer():
            return "scale down by an integer factor"
        if ry >= 1 and rx >= 1 and float(ry).is_integer() and float(rx).is_integer():
            return "tile (output is a multiple of the input shape)"
    if len({B.shape for _, B in pairs}) == 1:
        return "constant output shape"
    return "other size change"


# ------------------------------------------------------------------ 4. oracle-style simple rules
DIHEDRAL = [lambda g: g, np.fliplr, np.flipud, lambda g: np.rot90(g, 1), lambda g: np.rot90(g, 2),
            lambda g: np.rot90(g, 3), np.transpose, lambda g: np.rot90(np.transpose(g), 2)]


def rule_colour_map(train):
    m = {}
    for A, B in train:
        if A.shape != B.shape:
            return None
        for a, b in zip(A.ravel(), B.ravel()):
            if m.setdefault(int(a), int(b)) != int(b):
                return None
    if all(k == v for k, v in m.items()):
        return None                                                      # the identity is not a rule
    return lambda A: np.vectorize(lambda x: m.get(int(x), int(x)))(A)


def rule_dihedral(train):
    for k, T in enumerate(DIHEDRAL[1:], 1):
        if all(T(A).shape == B.shape and (T(A) == B).all() for A, B in train):
            return T
    return None


def rule_scale(train):
    A, B = train[0]
    if B.shape[0] % A.shape[0] == 0 and B.shape[0] > A.shape[0]:
        k = B.shape[0] // A.shape[0]
        f = lambda X: np.kron(X, np.ones((k, k), dtype=int))                # noqa: E731
        if all(f(A).shape == B.shape and (f(A) == B).all() for A, B in train):
            return f
    if A.shape[0] % B.shape[0] == 0 and A.shape[0] > B.shape[0]:
        k = A.shape[0] // B.shape[0]
        f = lambda X: X[::k, ::k]                                           # noqa: E731
        if all(f(A).shape == B.shape and (f(A) == B).all() for A, B in train):
            return f
    return None


def rule_tile(train):
    """The output is an a x b arrangement of dihedral copies of the input, with the same copy at each position."""
    pattern = None
    for A, B in train:
        h, w = A.shape
        if B.shape[0] % h or B.shape[1] % w or B.shape == A.shape:
            return None
        a, b = B.shape[0] // h, B.shape[1] // w
        cur = []
        for i in range(a):
            for j in range(b):
                blk = B[i * h:(i + 1) * h, j * w:(j + 1) * w]
                ids = [k for k, T in enumerate(DIHEDRAL) if T(A).shape == blk.shape and (T(A) == blk).all()]
                if not ids:
                    return None
                cur.append(set(ids))
        key = (a, b)
        if pattern is None:
            pattern = (key, cur)
        elif pattern[0] != key:
            return None
        else:
            pattern = (key, [p & c for p, c in zip(pattern[1], cur)])
            if any(not p for p in pattern[1]):
                return None
    (a, b), ids = pattern

    def f(X):
        h, w = X.shape
        out = np.zeros((a * h, b * w), dtype=int)
        for n, s in enumerate(ids):
            i, j = divmod(n, b)
            out[i * h:(i + 1) * h, j * w:(j + 1) * w] = DIHEDRAL[min(s)](X)
        return out
    return f


SELECTORS = {
    "most cells": lambda objs: max(objs, key=lambda o: len(o[0])),
    "fewest cells": lambda objs: min(objs, key=lambda o: len(o[0])),
    "largest box": lambda objs: max(objs, key=lambda o: o[2]),
    "smallest box": lambda objs: min(objs, key=lambda o: o[2]),
}


def _objects(A, view):
    from cora_neural_v2g3 import scene as SC
    objs, bg = SC.native_objects(A.tolist(), view)
    out = []
    for o in objs:
        rs, cs = zip(*o.cells)
        box = (min(rs), max(rs) + 1, min(cs), max(cs) + 1)
        out.append((frozenset(o.cells), box, (box[1] - box[0]) * (box[3] - box[2]), int(o.color)))
    return out, bg


def _crops(A, obj, bg):
    cells, (r0, r1, c0, c1), _, _ = obj
    region = A[r0:r1, c0:c1].copy()
    only = np.full_like(region, bg)
    for r, c in cells:
        only[r - r0, c - c0] = A[r, c]
    return region, only


def _unique(objs, key):
    vals = [key(o) for o in objs]
    best = max(vals)
    return vals.count(best) == 1


def rule_crop_object(train, views):
    """Crop to the bounding box of one object chosen by a simple selector, in one view (region or object only)."""
    for view in views:
        for sname, sel in SELECTORS.items():
            for variant in (0, 1):
                ok = True
                for A, B in train:
                    objs, bg = _objects(A, view)
                    if not objs:
                        ok = False
                        break
                    o = sel(objs)
                    if sum(1 for p in objs if (len(p[0]), p[2]) == (len(o[0]), o[2])) > 1:
                        ok = False                                      # a tie: the selector is ambiguous
                        break
                    c = _crops(A, o, bg)[variant]
                    if c.shape != B.shape or not (c == B).all():
                        ok = False
                        break
                if ok:
                    def f(X, view=view, sel=sel, variant=variant):
                        objs, bg = _objects(X, view)
                        return _crops(X, sel(objs), bg)[variant] if objs else X
                    return f, f"{view}/{sname}/{'region' if variant == 0 else 'object only'}"
    return None, None


def crop_object_exists(train, views):
    """Upper bound: in every demonstration the output is the box crop of SOME object, in one view."""
    for view in views:
        if all(any(c.shape == B.shape and (c == B).all() for o in _objects(A, view)[0]
                   for c in _crops(A, o, _objects(A, view)[1])) for A, B in train):
            return view
    return None


# ------------------------------------------------------------------ main
def main():
    data, runs, out_json = sys.argv[1:4]
    ch = json.load(open(os.path.join(data, "arc-agi_evaluation_challenges.json")))
    sol = json.load(open(os.path.join(data, "arc-agi_evaluation_solutions.json")))
    A_ = os.path.join(runs, "cora-only-g3-dev-eval-a")
    B_ = os.path.join(runs, "cora-only-g3-dev-eval-b")
    prov = json.load(open(os.path.join(A_, "attempt_provenance.json")))
    sub = json.load(open(os.path.join(A_, "submission.json")))
    rows = {}
    with open(os.path.join(A_, "run", "progress.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            rows[r["task_id"]] = r

    def search_rec(base, tid):
        p = os.path.join(base, tid + ".json")
        return json.load(open(p)) if os.path.exists(p) else None
    tax = load_script("neural_cora_v2g3_realarc_failure_taxonomy")
    obs = load_script("neural_cora_g4_realarc_observables")
    from cora_neural_v2 import search as G1S
    views = list(G1S.VIEWS)

    per = {}
    for tid in sorted(ch):
        t = ch[tid]
        train = [(arr(p["input"]), arr(p["output"])) for p in t["train"]]
        tests = [(arr(p["input"]), arr(s)) for p, s in zip(t["test"], sol[tid])]
        rec = {"shape": shape_relation(train + tests), "n_train": len(train), "n_test": len(tests)}
        # 2. recorded CORA sources and the original engine's wrong fits
        srcs = [[a["source"] for a in tinp] for tinp in prov.get(tid, [])]
        rec["sources"] = sorted({s for ss in srcs for s in ss})
        row = rows.get(tid, {})
        rec["native_solved_claim"] = bool(row.get("solved"))
        rec["native_layer"] = row.get("layer")
        rec["native_family"] = row.get("family_or_strategy")
        rec["object_failure_stage"] = (row.get("object") or {}).get("failure_stage")
        for name, base in (("g3", os.path.join(A_, "run", "G3")), ("C1", os.path.join(B_, "run", "C1")),
                           ("C2", os.path.join(B_, "run", "C2"))):
            s = search_rec(base, tid)
            rec[name + "_status"] = None if s is None else s.get("status")
            rec[name + "_fits"] = None if s is None else s.get("n_consistent")
        claims = []
        for k, (tinp, (X, Y)) in enumerate(zip(srcs, tests)):
            for j, s in enumerate(tinp):
                if s in ("NATIVE_CLAIMED", "NATIVE_PARTIAL"):
                    P = arr(sub[tid][k][f"attempt_{j + 1}"])
                    d = {"source": s, "test": k, "shape_match": P.shape == Y.shape}
                    if d["shape_match"]:
                        d["cell_accuracy"] = round(float((P == Y).mean()), 3)
                        d["changed_cells_right"] = None if X.shape != Y.shape else \
                            round(float(((P == Y) & (X != Y)).sum() / max(1, (X != Y).sum())), 3)
                    d["equals_test_input"] = P.shape == X.shape and bool((P == X).all())
                    d["equals_a_training_output"] = any(P.shape == B.shape and (P == B).all() for _, B in train)
                    claims.append(d)
        rec["native_attempts"] = claims
        # 3. change profile on same-shape puzzles (existing scripts, read-only)
        if rec["shape"] == "same shape":
            tl = [(A.tolist(), B.tolist()) for A, B in train]
            try:
                rec["change_profile"] = tax.change_profile(tl)
            except Exception as e:                                       # noqa: BLE001
                rec["change_profile"] = {"error": repr(e)[:120]}
            try:
                o = obs.task_observables(tl)
                rec["observables"] = {"part_level_share": round(o["part_level_objects"] / max(1, o["changed_objects"]), 3),
                                      "changed_objects": o["changed_objects"], "grouping_outputs": o["grouping_outputs"],
                                      "additive": o["additive"]}
            except Exception as e:                                       # noqa: BLE001
                rec["observables"] = {"error": repr(e)[:120]}
        # 4. oracle-style simple rules
        orc = {}
        for name, fn in (("colour map", rule_colour_map), ("dihedral", rule_dihedral), ("scale", rule_scale),
                         ("tile", rule_tile)):
            try:
                f = fn(train)
            except Exception:                                            # noqa: BLE001
                f = None
            if f is not None:
                try:
                    orc[name] = all((lambda P: P.shape == Y.shape and bool((P == Y).all()))(f(X)) for X, Y in tests)
                except Exception:                                        # noqa: BLE001
                    orc[name] = False
        if rec["shape"].startswith("crop") or rec["shape"] == "constant output shape" or rec["shape"] == "other size change":
            f, how = rule_crop_object(train, views)
            if f is not None:
                orc["crop to one object (" + how + ")"] = all((lambda P: P.shape == Y.shape and bool((P == Y).all()))(f(X))
                                                               for X, Y in tests)
            rec["crop_object_exists_view"] = crop_object_exists(train, views)
        rec["oracle_rules"] = orc
        per[tid] = rec
        print(tid, rec["shape"], rec["sources"], list(orc), flush=True)

    # aggregates
    agg = {"label": LABEL, "n": len(per)}
    agg["shape"] = dict(collections.Counter(r["shape"] for r in per.values()))
    agg["sources"] = dict(collections.Counter(s for r in per.values() for s in r["sources"]))
    agg["puzzles_with_native_claim_or_partial"] = sum(bool(r["native_attempts"]) for r in per.values())
    na = [d for r in per.values() for d in r["native_attempts"]]
    agg["native_attempts"] = {
        "n": len(na), "shape_mismatch": sum(not d["shape_match"] for d in na),
        "shape_match_cell_accuracy_ge_0.9": sum(d.get("cell_accuracy", 0) >= 0.9 for d in na if d["shape_match"]),
        "shape_match_cell_accuracy_0.5_to_0.9": sum(0.5 <= d.get("cell_accuracy", 0) < 0.9 for d in na if d["shape_match"]),
        "shape_match_cell_accuracy_lt_0.5": sum(d.get("cell_accuracy", 0) < 0.5 for d in na if d["shape_match"]),
        "equals_test_input": sum(d["equals_test_input"] for d in na),
        "equals_a_training_output": sum(d["equals_a_training_output"] for d in na),
        "by_source": dict(collections.Counter(d["source"] for d in na))}
    agg["native_claim_by_shape"] = dict(collections.Counter(r["shape"] for r in per.values() if r["native_attempts"]))
    agg["search_fits"] = {k: sum((r[k + "_fits"] or 0) > 0 for r in per.values()) for k in ("g3", "C1", "C2")}
    agg["search_status"] = {k: dict(collections.Counter(str(r[k + "_status"]) for r in per.values())) for k in ("g3", "C1", "C2")}
    same = [r for r in per.values() if r["shape"] == "same shape"]
    prof = [r["change_profile"] for r in same if isinstance(r.get("change_profile"), dict) and "explained" in r["change_profile"]]
    agg["same_shape_profiles"] = {
        "n": len(same), "with_profile": len(prof),
        "explained_ge_0.5": sum(p["explained"] >= 0.5 for p in prof),
        "additive_ge_0.5": sum(p["additive"] >= 0.5 for p in prof),
        "other_ge_0.5": sum(p["other"] >= 0.5 for p in prof),
        "median_explained": float(np.median([p["explained"] for p in prof])) if prof else None,
        "median_additive": float(np.median([p["additive"] for p in prof])) if prof else None}
    ob = [r["observables"] for r in same if isinstance(r.get("observables"), dict) and "part_level_share" in r["observables"]]
    agg["same_shape_observables"] = {
        "n": len(ob), "part_level_share_ge_0.5": sum(o["part_level_share"] >= 0.5 for o in ob),
        "with_grouping_outputs": sum(o["grouping_outputs"] > 0 for o in ob),
        "additive_dominant_kind": dict(collections.Counter(max(o["additive"], key=o["additive"].get)
                                                           for o in ob if sum(o["additive"].values())))}
    agg["oracle_rules_fit_demos"] = dict(collections.Counter(k.split(" (")[0] for r in per.values() for k in r["oracle_rules"]))
    agg["oracle_rules_predict_test"] = dict(collections.Counter(k.split(" (")[0] for r in per.values()
                                                                for k, ok in r["oracle_rules"].items() if ok))
    agg["oracle_puzzles_predicted"] = sorted(t for t, r in per.items() if any(r["oracle_rules"].values()))
    agg["crop_object_exists"] = sum(bool(r.get("crop_object_exists_view")) for r in per.values())
    json.dump({"aggregate": agg, "per_puzzle": per}, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(agg, indent=1, default=str))


def extra():
    """Second pass over the saved JSON: how pure each same-shape puzzle's change is, and degenerate native fits.
    Usage: python3 scripts/eval120_capability_gaps.py --extra DATA_DIR OUT_JSON"""
    data, out_json = sys.argv[2:4]
    ch = json.load(open(os.path.join(data, "arc-agi_evaluation_challenges.json")))
    d = json.load(open(out_json))
    per, agg = d["per_puzzle"], d["aggregate"]
    pure = collections.Counter()
    mostly = collections.Counter()
    sparsity = []
    for tid, r in per.items():
        if r["shape"] != "same shape" or "additive" not in (r.get("observables") or {}):
            continue
        train = [(arr(p["input"]), arr(p["output"])) for p in ch[tid]["train"]]
        changed = sum(int((A != B).sum()) for A, B in train)
        cells = sum(A.size for A, _ in train)
        sparsity.append(changed / cells)
        r["changed_cells"] = changed
        add = r["observables"]["additive"]
        for kind, n in add.items():
            if changed and n / changed >= 0.9:
                pure[kind] += 1
            if changed and n / changed >= 0.5:
                mostly[kind] += 1
        prof = r.get("change_profile") or {}
        if prof.get("explained", 0) >= 0.9:
            pure["whole-object changes (recolour, move, delete)"] += 1
    agg["same_shape_change_kind_ge_0.9_of_changed_cells"] = dict(pure)
    agg["same_shape_change_kind_ge_0.5_of_changed_cells"] = dict(mostly)
    agg["same_shape_median_changed_cell_share"] = round(float(np.median(sparsity)), 3) if sparsity else None
    deg = [t for t, r in per.items() if r["native_attempts"] and all(a["equals_test_input"] for a in r["native_attempts"])]
    agg["native_puzzles_all_attempts_equal_test_input"] = len(deg)
    agg["native_layers_on_claims"] = dict(collections.Counter(str(r["native_layer"]) for r in per.values()
                                                              if r["native_attempts"]))
    agg["native_families_on_claims"] = dict(collections.Counter(str(r["native_family"]) for r in per.values()
                                                                if r["native_attempts"]))
    agg["C2_fit_puzzles"] = sorted(t for t, r in per.items() if (r.get("C2_fits") or 0) > 0)
    agg["multi_test_puzzles"] = sum(r["n_test"] > 1 for r in per.values())
    json.dump(d, open(out_json, "w"), indent=1, default=str)
    for k in ("same_shape_change_kind_ge_0.9_of_changed_cells", "same_shape_change_kind_ge_0.5_of_changed_cells",
              "same_shape_median_changed_cell_share", "native_puzzles_all_attempts_equal_test_input",
              "native_layers_on_claims", "native_families_on_claims", "C2_fit_puzzles", "multi_test_puzzles"):
        print(k, ":", json.dumps(agg[k], default=str)[:400])


def groups():
    """Third pass, on same-shape puzzles whose changes are mostly whole-object changes: for each change group (the
    objects with one fate), does version 4's selector induction find an exact, natively confirmed selector, and does
    its group inversion find a rule that passes the local check? Both imported read-only.
    Usage: python3 scripts/eval120_capability_gaps.py --groups DATA_DIR OUT_JSON"""
    from cora_neural_v2 import search as G1S
    from cora_neural_v2g2 import search as S2
    from cora_neural_v2g3 import scene as SC
    from cora_neural_v2g4 import invert as INV
    data, out_json = sys.argv[2:4]
    ch = json.load(open(os.path.join(data, "arc-agi_evaluation_challenges.json")))
    d = json.load(open(out_json))
    per, agg = d["per_puzzle"], d["aggregate"]
    todo = [t for t, r in per.items() if r["shape"] == "same shape" and (r.get("change_profile") or {}).get("explained", 0) >= 0.5]
    res = {}
    for tid in todo:
        train = [(p["input"], p["output"]) for p in ch[tid]["train"]]
        ev = S2.evidence2(train)
        best = None
        for v in G1S.distinct_views({"train": train, "test_inputs": [p["input"] for p in ch[tid]["test"]]}):
            sc = SC.analyse(train, v)
            if sc is None or not sc.groups:
                continue
            tables = INV.feature_tables(train, v)
            tests = INV.single_tests(tables)
            keys = [k for k in sc.groups if len(k) == 1 and k[0] in ("recoloured", "moved", "deleted")]
            n_other = sum(o.fate == "other" for demo in sc.objects for o in demo)
            with_sel = with_rule = 0
            for k in keys:
                if INV.induce_selectors(v, train, tables, tests, sc.groups[k]):
                    with_sel += 1
                if INV._group_rules(v, train, sc, k, tables, tests, ev):
                    with_rule += 1
            cur = {"view": v, "groups": len(keys), "with_selector": with_sel, "with_rule": with_rule,
                   "other_fate_objects": n_other}
            if best is None or (with_rule, with_sel, -n_other) > (best["with_rule"], best["with_selector"], -best["other_fate_objects"]):
                best = cur
        res[tid] = best
        print(tid, best, flush=True)
    rows = [r for r in res.values() if r]
    agg["whole_object_groups"] = {
        "puzzles": len(todo), "analysed": len(rows),
        "every_group_has_a_selector": sum(r["groups"] > 0 and r["with_selector"] == r["groups"] for r in rows),
        "every_group_has_a_rule": sum(r["groups"] > 0 and r["with_rule"] == r["groups"] for r in rows),
        "every_group_has_a_rule_and_no_other_fate": sum(r["groups"] > 0 and r["with_rule"] == r["groups"]
                                                        and r["other_fate_objects"] == 0 for r in rows),
        "some_group_lacks_a_selector": sum(r["with_selector"] < r["groups"] for r in rows),
        "selector_but_no_rule_for_some_group": sum(r["with_selector"] > r["with_rule"] for r in rows)}
    for t, r in res.items():
        per[t]["whole_object_groups"] = r
    json.dump(d, open(out_json, "w"), indent=1, default=str)
    print(json.dumps(agg["whole_object_groups"]))


if __name__ == "__main__":
    {"--extra": extra, "--groups": groups}.get(sys.argv[1] if len(sys.argv) > 1 else "", main)()
