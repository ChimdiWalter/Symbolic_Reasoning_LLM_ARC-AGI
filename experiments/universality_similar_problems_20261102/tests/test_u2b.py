"""U2b tests on synthetic tasks (no benchmark task is read). Run: python3 -m pytest -q tests"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import u2b_analysis as UA  # noqa: E402
import u2b_blind as UB  # noqa: E402


def recolour_task(contradict=False):
    def pair(a):
        return {"input": a, "output": [[2 if v == 1 else v for v in r] for r in a]}
    tr = [pair([[1, 0, 3], [0, 1, 0]]), pair([[3, 1], [1, 1]]), pair([[0, 0, 1], [3, 3, 1], [1, 0, 0]])]
    if contradict:
        tr[2] = {"input": [[0, 0, 1], [3, 3, 1], [1, 0, 0]], "output": [[0, 0, 4], [3, 3, 4], [4, 0, 0]]}
    return {"train": tr, "test": [{"input": [[1, 3], [0, 1]]}]}


def test_blind_search_finds_the_recolour_and_passes_leave_one_out():
    out = UB.solve(recolour_task(), 5.0)
    assert out["answer"] == [[[2, 3], [0, 2]]] and out["depth"] == 1 and out["loo_pass"]


def test_blind_search_without_budget_gives_no_answer():
    out = UB.solve(recolour_task(), 0.0)
    assert out["answer"] == [None] and not out["loo_pass"]


def test_contradictory_demonstrations_fail():
    out = UB.solve(recolour_task(contradict=True), 2.0)
    assert out["answer"] == [None] or not out["loo_pass"]


def test_non_copy_accounting():
    assert UA.single([[1]], [[1]], [[1]]) == {"answered": False, "correct": False, "pass2": True}
    assert UA.single([[2]], [[1]], [[2]]) == {"answered": True, "correct": True, "pass2": True}
    assert UA.single(None, [[1]], [[2]]) == {"answered": False, "correct": False, "pass2": False}


def test_analysis_end_to_end_on_a_synthetic_workspace(tmp_path, monkeypatch):
    import json
    import score as SC
    D = tmp_path / "data"
    runs = D / "runs"
    g_in, g_out = [[1, 0]], [[2, 0]]
    for b, grp in (("concept_arc", "C1"), ("mini_arc", None), ("1d_arc", "T1")):
        pre = D / "prepared" / b
        (pre / "solutions_scorer_only").mkdir(parents=True)
        tids = [f"{b[:2]}{i:04d}" for i in range(3)]
        ch = {t: {"train": [{"input": g_in, "output": g_out}], "test": [{"input": g_in}]} for t in tids}
        for v in ("real", "shuffled"):
            json.dump(ch, open(pre / f"{v}.json", "w"))
        json.dump({t: [g_out] for t in tids}, open(pre / "solutions_scorer_only" / "solutions.json", "w"))
        json.dump({t: {"group": grp, "file": t, "donor": t, "n_test": 1} for t in tids}, open(pre / "meta.json", "w"))
        for v in ("real", "shuffled"):
            good = v == "real"
            ans = g_out if good else [[3, 0]]
            sub = {t: [{"attempt_1": ans, "attempt_2": g_in}] for t in tids}
            for sy in ("a", "c"):
                d = runs / f"{sy}_{b}_{v}"
                (d / "run" / "shard_0").mkdir(parents=True)
                json.dump(sub, open(d / "submission.json", "w"))
                for t in tids:
                    r = {"status": "OK", "grids": [ans], "module": ["m2"], "child": {"cpu_s": 0.5}}
                    json.dump(r, open(d / "run" / "shard_0" / f"{t}.json", "w"))
                    for k, nm in enumerate(SC.PKGS_A):
                        (d / "run" / f"pkg{k}_{nm}" / "shard_0").mkdir(parents=True, exist_ok=True)
                        json.dump(r, open(d / "run" / f"pkg{k}_{nm}" / "shard_0" / f"{t}.json", "w"))
            d = runs / f"b_{b}_{v}"
            (d / "side").mkdir(parents=True)
            json.dump({t: [{"attempt_1": g_in, "attempt_2": ans if good else g_in}] for t in tids},
                      open(d / "submission_B.json", "w"))
            for t in tids:
                q = {"candidate": ans, "candidate_module": "m2",
                     "accepted": {"B1": ans, "B2": ans, "B3": ans if good else None},
                     "accepted_module": {"B1": "m2", "B2": "m2", "B3": "m2" if good else None}}
                json.dump({"status": "OK", "evidence": {"queries": [q]}, "child": {"cpu_s": 0.5}},
                          open(d / "side" / f"{t}.json", "w"))
            d = runs / f"u2b_{b}_{v}"
            d.mkdir(parents=True)
            for t in tids:
                json.dump({"ok": True, "answer": [ans], "loo_pass": good, "budget_s": 0.5, "main_cpu_s": 0.1,
                           "folds": [], "child_cpu_s": 0.2}, open(d / f"{t}.json", "w"))
    Ex = tmp_path / "exp"
    (Ex / "results").mkdir(parents=True)
    json.dump({"u2b_protocol_sha256": "test"}, open(Ex / "U2B_FREEZE.json", "w"))
    monkeypatch.setattr(SC, "DATA", str(D))
    monkeypatch.setattr(SC, "RUNS", str(runs))
    monkeypatch.setattr(UA, "DATA", str(D))
    monkeypatch.setattr(UA, "E", str(Ex))
    UA.main()
    out = json.load(open(Ex / "results" / "U2B_RESULTS.json"))
    pooled = out["benchmarks"]["pooled"]
    assert pooled["FIT_ONLY | real"]["precision"]["point"] == 1.0
    assert pooled["MATCHED_SEARCH_LOO | shuffled"]["answered"] == 0
    assert out["primary"]["point"] == 0.0 and out["primary"]["decision"] == "NOT_SHOWN"
    assert len(out["secondary"]) == 13 and all("p_holm" in c for c in out["secondary"].values())
    assert out["primary"]["decision"] in ("B3_POLICY_RAISES_PRECISION", "NOT_SHOWN")
    assert out["loo_specific_wording_allowed"] is False
    ids = out["cpu"]["concept_arc_real"]["identity_checks"]
    assert ids["B3_same_module_accepted"] == 3 and ids["B3_grid_differs_from_candidate"] == 0
    assert out["clusters"]["mini_arc"]["unit"] == "task (unclustered)"


def _gate():
    """The single expression assigned to res["loo_specific_wording_allowed"], evaluated as the reviewers' probe does."""
    import ast
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "u2b_analysis.py")
    tree = ast.parse(open(src).read())
    found = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets
             if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "res"
             and isinstance(t.slice, ast.Constant) and t.slice.value == "loo_specific_wording_allowed"]
    assert len(found) == 1
    code = compile(ast.Expression(found[0]), src, "eval")
    return lambda s11, s13, res: eval(code, {"bool": bool, "all": all}, {"s11": s11, "s13": s13, "res": res})


FAV = {"significant_holm_0.05": True, "point": 0.2, "ci95": [0.1, 0.3]}


def _res(b2=0, b3=0, benches=("concept_arc_real", "mini_arc_real", "1d_arc_real")):
    return {"cpu": {k: {"identity_checks": {"B2_grid_differs_from_candidate": b2 if k == "concept_arc_real" else 0,
                                            "B3_grid_differs_from_candidate": b3 if k == "concept_arc_real" else 0}}
                    for k in benches}}


def test_wording_gate_rejects_a_single_b2_mismatch_and_accepts_zero():
    g = _gate()
    assert g(FAV, FAV, _res(b2=1)) is False                      # the reviewers' adversarial case
    assert g(FAV, FAV, _res(b2=0)) is True                       # same statistics, zero mismatches


def test_wording_gate_other_failures():
    g = _gate()
    assert g(FAV, FAV, _res(b3=1)) is False                      # B3 identity mismatch
    assert g(FAV, FAV, _res(benches=("concept_arc_real",))) is False          # a REAL benchmark missing
    weak = dict(FAV, **{"significant_holm_0.05": False})
    assert g(weak, FAV, _res()) is False and g(FAV, dict(FAV, ci95=[-0.1, 0.3]), _res()) is False
