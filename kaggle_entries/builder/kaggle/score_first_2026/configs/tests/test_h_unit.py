"""Entry H, unit and process-level checks (CPU only, no model):
- the evidence mode of the side process: compact_evidence and re-validation;
- merge_packages with cast_selective_v2's own insert_attempt2, using synthetic reports:
  - tier1:B3 replaces a different attempt 2 only with a B3-accepted grid that differs from attempt 1;
  - tier0 replaces only identical pairs;
  - attempt 1 never changes;
  - a failed report, a raising or misbehaving insert function, and malformed grids all keep C4's entry;
  - package priority (the constructor hook);
- the real cast_selective_v2 through the side process on real tasks: status OK, the same evidence in either task
  order, and the merge on stub neural attempts applying exactly the B3-accepted grids.

Run: CUDA_VISIBLE_DEVICES= python3 -m pytest -q -p no:cacheprovider configs/tests/test_h_unit.py
"""
import copy
import json
import os
import subprocess
import sys
import textwrap
import time

import numpy as np
import pytest

CONFIGS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF_HOME = os.path.dirname(CONFIGS)
REPO = os.path.dirname(os.path.dirname(SF_HOME))
sys.path.insert(0, CONFIGS)
from sfb import cast_side as CS  # noqa: E402
from sfb import merge as M  # noqa: E402

V2_DIR = os.path.join(REPO, "experiments", "cora_cast_20261026", "kaggle_pkg", "cast_selective_v2")
sys.path.insert(0, V2_DIR)
import cast_selective_v2 as V2  # noqa: E402

DATA = os.path.join(REPO, "outputs", "score_first", "data")


def g(v, h=2, w=2):
    return [[v] * w for _ in range(h)]


def rep_ok(queries):
    return {"status": "OK", "version": "x", "queries": queries}


def q(cand=None, b3=None, b1=None, b2=None):
    return {"candidate": cand, "candidate_module": "m2" if cand else None, "accepted": {"B1": b1, "B2": b2, "B3": b3},
            "accepted_module": {"B1": None, "B2": None, "B3": "m2" if b3 else None}}


def test_compact_evidence_converts_and_marks_malformed():
    rep = {"status": "OK", "version": "v", "n_demos": 3, "cpu_s": 1.0, "wall_s": 2.0,
           "queries": [{"candidate": np.array([[1, 2], [3, 4]]), "candidate_module": "m4",
                        "accepted": {"B3": np.array([[1, 2], [3, 4]]), "B1": None}, "accepted_module": {"B3": "m4"}},
                       {"candidate": np.array([1, 2, 3]), "accepted": {"B3": np.array([[0.5]])}},
                       "junk"]}
    c = CS.compact_evidence(rep)
    json.dumps(c)                                                   # plain JSON
    assert c["queries"][0]["candidate"] == [[1, 2], [3, 4]] and c["queries"][0]["accepted"]["B3"] == [[1, 2], [3, 4]]
    assert c["queries"][1]["candidate"] == "MALFORMED" and c["queries"][1]["accepted"]["B3"] == "MALFORMED"
    assert c["queries"][2] is None
    rec = {"killed_by_parent": False, "too_big": False, "signal": None}
    out = CS.interpret_evidence({"ok": True, "res": c}, rec, 3)
    assert out["status"] == "OK" and out["malformed"] == 3
    assert out["evidence"]["queries"][1]["candidate"] is None and out["evidence"]["queries"][1]["accepted"]["B3"] is None
    assert CS.interpret_evidence({"ok": True, "res": c}, rec, 2)["status"] == "MALFORMED_SHAPE"
    assert CS.interpret_evidence(None, dict(rec, killed_by_parent=True), 3)["status"] == "KILLED_WALL"


def run_merge(entry_pairs, queries, policy, insert_fn=None, status="OK"):
    n = len(entry_pairs)
    ch = {"t": {"train": [{"input": g(1), "output": g(2)}] * 2, "test": [{"input": g(0)} for _ in range(n)]}}
    sub_a = {"t": [{"attempt_1": a, "attempt_2": b} for a, b in entry_pairs]}
    res = {"t": {"status": "OK", "grids": [x.get("candidate") if x else None for x in queries],
                 "evidence": dict(rep_ok(queries), status=status)}}
    pk = [{"name": "v2", "mode": "evidence", "policy": policy}]
    sub_b, rep = M.merge_packages(sub_a, ch, pk, {"v2": res}, {"v2": insert_fn or V2.insert_attempt2})
    return sub_a, sub_b, rep, ch


def test_tier1_b3_rules_with_the_package_insert():
    pairs = [(g(1), g(2)), (g(1), g(1)), (g(1), g(2)), (g(1), g(2)), (g(1), g(2))]
    qs = [q(cand=g(5), b3=g(5)),          # distinct pair, B3 accepts 5: replaced
          q(cand=g(6), b3=g(6)),          # identical pair, B3 accepts 6: replaced (tier 0 position)
          q(cand=g(7), b3=None),          # candidate but B3 rejects: unchanged under tier1:B3
          q(cand=g(1), b3=g(1)),          # B3 accepts attempt 1 itself: unchanged
          q(cand=g(2), b3=g(2))]          # B3 accepts attempt 2 itself: unchanged
    a, b, rep, ch = run_merge(pairs, qs, "tier1:B3")
    assert [x["attempt_2"] for x in b["t"]] == [g(5), g(6), g(2), g(2), g(2)]
    assert all(x["attempt_1"] == y["attempt_1"] for x, y in zip(a["t"], b["t"]))
    assert (rep["replaced_tier0"], rep["replaced_tier1"]) == (1, 1)
    assert M.self_check(a, b, ch, 1) == []
    a, b, rep, _ = run_merge(pairs, qs, "tier0")
    assert [x["attempt_2"] for x in b["t"]] == [g(2), g(6), g(2), g(2), g(2)]   # only the identical pair


def test_failures_keep_the_neural_entry():
    pairs = [(g(1), g(2))]
    qs = [q(cand=g(5), b3=g(5))]
    a, b, _, _ = run_merge(pairs, qs, "tier1:B3", status="TIMEOUT")
    assert b == a

    def boom(*x, **k):
        raise RuntimeError("x")
    a, b, rep, _ = run_merge(pairs, qs, "tier1:B3", insert_fn=boom)
    assert b == a and rep["per_package"]["v2"]["errors"] == 1

    def changes_a1(task, neural, policy, report):
        return [[g(9), g(5)]]
    a, b, rep, _ = run_merge(pairs, qs, "tier1:B3", insert_fn=changes_a1)
    assert b == a and rep["per_package"]["v2"]["rejected_output"] == 1

    def bad_grid(task, neural, policy, report):
        return [[neural[0][0], [[1, 2], [3]]]]
    a, b, _, _ = run_merge(pairs, qs, "tier1:B3", insert_fn=bad_grid)
    assert b == a

    def wrong_len(task, neural, policy, report):
        return []
    a, b, _, _ = run_merge(pairs, qs, "tier1:B3", insert_fn=wrong_len)
    assert b == a
    with pytest.raises(ValueError):
        M.policy_tier("tier2")


def test_package_priority_first_proposal_wins():
    ch = {"t": {"train": [{"input": g(1), "output": g(2)}] * 2, "test": [{"input": g(0)}, {"input": g(0)}]}}
    a = {"t": [{"attempt_1": g(1), "attempt_2": g(2)}, {"attempt_1": g(1), "attempt_2": g(2)}]}
    res_v2 = {"t": {"status": "OK", "grids": [g(5), None], "evidence": rep_ok([q(g(5), g(5)), q()])}}
    res_r29 = {"t": {"status": "OK", "grids": [g(7), g(8)]}}
    pk = [{"name": "v2", "mode": "evidence", "policy": "tier1:B3"},
          {"name": "r29", "mode": "grids", "policy": "tier1"}]
    b, rep = M.merge_packages(a, ch, pk, {"v2": res_v2, "r29": res_r29}, {"v2": V2.insert_attempt2})
    assert [x["attempt_2"] for x in b["t"]] == [g(5), g(8)]
    assert rep["per_package"]["v2"]["applied"] == 1 and rep["per_package"]["r29"]["applied"] == 1
    pk[1]["policy"] = "tier0"                                   # a tier-0 package may not touch a distinct pair
    b, _ = M.merge_packages(a, ch, pk, {"v2": res_v2, "r29": res_r29}, {"v2": V2.insert_attempt2})
    assert [x["attempt_2"] for x in b["t"]] == [g(5), g(2)]


def test_side_evidence_mode_with_a_stub(tmp_path):
    d = tmp_path / "stub_ev"
    d.mkdir()
    (d / "__init__.py").write_text(textwrap.dedent("""
        import numpy as np
        VERSION = 'stub'
        def evaluate(task, cpu_s=15, wall_s=30):
            n = len(task['test'])
            qs = [{'candidate': np.array([[3, 3]]), 'candidate_module': 'm2', 'accepted': {'B3': np.array([[3, 3]])},
                   'accepted_module': {'B3': 'm2'}} for _ in range(n)]
            return {'status': 'OK', 'version': 'stub', 'queries': qs}
        """))
    ch = {"s0": {"train": [{"input": g(1), "output": g(2)}] * 2, "test": [{"input": g(5)}, {"input": g(5)}]}}
    (tmp_path / "ch.json").write_text(json.dumps(ch))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([CONFIGS, str(tmp_path)]), CUDA_VISIBLE_DEVICES="")
    r = subprocess.run([sys.executable, "-m", "sfb.cast_side", "--challenges", str(tmp_path / "ch.json"),
                        "--out", str(tmp_path / "out"), "--package", "stub_ev", "--entry", "evaluate",
                        "--mode", "evidence", "--deadline", str(time.time() + 120)], cwd=str(tmp_path), env=env,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-1500:]
    res = json.loads((tmp_path / "out" / "s0.json").read_text())
    assert res["status"] == "OK" and res["evidence"]["queries"][0]["accepted"]["B3"] == [[3, 3]]
    assert res["grids"] == [[[3, 3]], [[3, 3]]]


REAL = ["62593bfd", "981571dc", "0934a4d8", "2c181942"]


def real_side(tmp, ids, name):
    ev = json.load(open(os.path.join(DATA, "arc-agi_evaluation_challenges.json")))
    ch = {k: ev[k] for k in ids}
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(ch))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([CONFIGS, V2_DIR]), CUDA_VISIBLE_DEVICES="",
               PYTHONHASHSEED=str(len(name)))
    r = subprocess.run([sys.executable, "-m", "sfb.cast_side", "--challenges", str(p), "--out", str(tmp / name),
                        "--package", "cast_selective_v2", "--entry", "evaluate", "--mode", "evidence",
                        "--deadline", str(time.time() + 1500)], cwd=str(tmp), env=env, capture_output=True,
                       text=True, timeout=2000)
    assert r.returncode == 0, r.stderr[-1500:]
    return ch, {f[:-5]: json.loads((tmp / name / f).read_text()) for f in os.listdir(tmp / name)
                if f.endswith(".json") and f != "status.json"}


def test_real_v2_side_process_and_merge(tmp_path):
    ch, fwd = real_side(tmp_path, REAL, "fwd")
    _, rev = real_side(tmp_path, list(reversed(REAL)), "reverse")
    def stable(v):                                         # timing fields differ run to run; everything else must not
        ev = v.get("evidence")
        return (v["status"], None if ev is None else (ev.get("status"), ev.get("queries")))
    assert {k: stable(v) for k, v in fwd.items()} == {k: stable(v) for k, v in rev.items()}
    assert all(v["status"] in ("OK", "TIMEOUT", "TIMEOUT_IN_FOLD") for v in fwd.values())
    # stub neural attempts: two copies of the test input (the C4 fallback) for every query
    sub_a = {k: [{"attempt_1": x["input"], "attempt_2": x["input"]} for x in t["test"]] for k, t in ch.items()}
    pk = [{"name": "cast_selective_v2", "mode": "evidence", "policy": "tier1:B3"}]
    sub_b, rep = M.merge_packages(sub_a, ch, pk, {"cast_selective_v2": fwd}, {"cast_selective_v2": V2.insert_attempt2})
    expect = 0
    for k, t in ch.items():
        ev = fwd[k]["evidence"]
        for j, x in enumerate(t["test"]):
            acc = ev["queries"][j]["accepted"].get("B3") if ev and ev.get("status") == "OK" else None
            if acc is not None and acc != x["input"]:
                expect += 1
                assert sub_b[k][j]["attempt_2"] == acc
            else:
                assert sub_b[k][j]["attempt_2"] == x["input"]
            assert sub_b[k][j]["attempt_1"] == x["input"]
    assert rep["replaced_tier0"] + rep["replaced_tier1"] == expect
    print(json.dumps({k: [v["status"], [qq["accepted"].get("B3") is not None for qq in v["evidence"]["queries"]]
                          if v.get("evidence") else None] for k, v in fwd.items()}), "B3 insertions", expect)


# ----- C4's child-path defect, corrected in H's merge cell (reviewer checklist item 4) -------------------------------
def guard_fixture(tmp, child=None, pools=None, progress=None, public=None):
    ch = {"t1": {"train": [], "test": [{"input": g(0)}]}, "t2": {"train": [], "test": [{"input": g(0)}, {"input": g(0)}]}}
    k = tmp / "kaggle"
    run = k / "working" / "guarded_run_abc"
    for d in ("pools", "progress"):
        (run / d).mkdir(parents=True)
    fb = {tid: [{"attempt_1": x["input"], "attempt_2": x["input"]} for x in t["test"]] for tid, t in ch.items()}
    (k / "working" / "submission.json").write_text(json.dumps(public or fb))
    (tmp / "ch.json").write_text(json.dumps(ch))
    if child is not None:
        (run / "child_submission.json").write_text(child if isinstance(child, str) else json.dumps(child))
    for folder, recs in (("pools", pools or {}), ("progress", progress or {})):
        for tid, sel in recs.items():
            (run / folder / f"{tid}.json").write_text(json.dumps({"task": tid, "selected": sel}))
    return ch, k


C4_GUARD_DIR = os.path.join(CONFIGS, "h", "c4_frozen")


def test_reconcile_uses_child_only_output(tmp_path):
    child = {"t1": [{"attempt_1": g(5), "attempt_2": g(6)}],
             "t2": [{"attempt_1": g(7), "attempt_2": g(8)}, {"attempt_1": g(1), "attempt_2": g(2)}]}
    ch, k = guard_fixture(tmp_path, child=child)
    rep = M.reconcile_guard_output(str(k / "working" / "submission.json"), str(tmp_path / "ch.json"), str(k), C4_GUARD_DIR)
    assert rep["applied"] and rep["changed_queries"] == 3
    assert json.loads((k / "working" / "submission.json").read_text()) == child


def test_reconcile_keeps_pool_and_progress_precedence(tmp_path):
    child = {"t1": [{"attempt_1": g(5), "attempt_2": g(6)}],
             "t2": [{"attempt_1": g(7), "attempt_2": g(8)}, {"attempt_1": g(1), "attempt_2": g(2)}]}
    ch, k = guard_fixture(tmp_path, child=child,
                          pools={"t1": [{"attempt_1": g(9), "attempt_2": g(3)}]},
                          progress={"t2": [{"attempt_1": g(4), "attempt_2": g(3)}]})
    M.reconcile_guard_output(str(k / "working" / "submission.json"), str(tmp_path / "ch.json"), str(k), C4_GUARD_DIR)
    out = json.loads((k / "working" / "submission.json").read_text())
    assert out["t1"][0] == {"attempt_1": g(9), "attempt_2": g(3)}        # completed pool beats the child file
    assert out["t2"][0] == {"attempt_1": g(4), "attempt_2": g(3)}        # in-flight progress beats the child file
    assert out["t2"][1] == child["t2"][1]                                # the child file fills the rest


@pytest.mark.parametrize("child", ['{"t1": [{"attempt_1": [[1, 2], [3]]', '[]', None])
def test_reconcile_failure_keeps_public(tmp_path, child):
    public = {"t1": [{"attempt_1": g(3), "attempt_2": g(4)}],
              "t2": [{"attempt_1": g(3), "attempt_2": g(4)}, {"attempt_1": g(3), "attempt_2": g(4)}]}
    ch, k = guard_fixture(tmp_path, child=child, public=public,
                          pools={"t1": [{"attempt_1": g(3), "attempt_2": g(4)}],
                                 "t2": [{"attempt_1": g(3), "attempt_2": g(4)}, {"attempt_1": g(3), "attempt_2": g(4)}]})
    M.reconcile_guard_output(str(k / "working" / "submission.json"), str(tmp_path / "ch.json"), str(k), C4_GUARD_DIR)
    assert json.loads((k / "working" / "submission.json").read_text()) == public


def test_reconcile_noop_without_guard_run(tmp_path):
    (tmp_path / "kaggle" / "working").mkdir(parents=True)
    rep = M.reconcile_guard_output("x", "y", str(tmp_path / "kaggle"), C4_GUARD_DIR)
    assert not rep["applied"] and rep["reason"] == "0 guarded_run folders"
