"""Reach v1 measurement: gates, controls, separation and freeze (synthetic
fixtures only; no ARC data)."""
import ast
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_reach import measure as M                                  # noqa: E402

TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"


def _bbox_task():
    """Inputs with L-shaped objects; outputs fill each object's bounding box
    with the object's colour (bbox_fill)."""
    pairs = []
    for shapes in ([((1, 1), 3, 3), ((6, 7), 2, 2)], [((2, 4), 3, 2)], [((0, 0), 2, 3), ((5, 5), 3, 3)]):
        a = np.zeros((9, 10), dtype=int)
        b = np.zeros((9, 10), dtype=int)
        for (r, c), h, w in shapes:
            for i in range(h):
                a[r + i, c] = 4
            for j in range(w):
                a[r + h - 1, c + j] = 4
            b[r:r + h, c:c + w] = 4
        pairs.append((a, b))
    return pairs


def test_gates_are_the_pilot_order():
    tree = ast.parse(open(os.path.join(HERE, "cora_pilot", "reasoner.py")).read())
    pilot = next(ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "GATES")
    assert M.GATES == pilot


def test_components_are_eight_connected():
    a = np.zeros((5, 5), dtype=int)
    a[0, 0] = a[1, 1] = 3                         # diagonal: one component
    a[3, 3] = 5
    a[3, 4] = 6                                   # two colours, adjacent: one component
    comps = sorted(M.components(a), key=min)
    assert comps == [{(0, 0), (1, 1)}, {(3, 3), (3, 4)}]


def test_demonstration_only_control():
    train = _bbox_task()
    out = M.demo_only_propose(train)
    fams = [p["ext"]["family"] for p in out["proposals"]]
    assert "bbox_fill" in fams and out["why"] is None
    changed = [(a.copy(), b) for a, b in train]
    changed[0][0][1, 1] = 7                       # an input cell the output overwrites
    assert M.demo_only_propose(changed)["why"] == "input_cell_changes"
    one = [train[0], (train[1][0], train[1][0].copy()), (train[2][0], train[2][0].copy())]
    assert M.demo_only_propose(one)["why"] == "support"


def test_substitution_touches_only_the_selected_mode():
    prog = {"rules": [{"action": {"delta_type": "grow", "params": {
        "mode": {"args": ["gx_a"], "expr_class": "GrowModeExpr", "op": "const"},
        "color": {"args": [3], "expr_class": "ColorExpr", "op": "const"}}}},
        {"action": {"delta_type": "grow", "params": {
            "mode": {"args": ["halo"], "expr_class": "GrowModeExpr", "op": "const"}}}}]}
    out = M.substituted(prog, "gx_a", "gx_b")
    assert out["rules"][0]["action"]["params"]["mode"]["args"] == ["gx_b"]
    assert out["rules"][1]["action"]["params"]["mode"]["args"] == ["halo"]
    assert out["rules"][0]["action"]["params"]["color"]["args"] == [3]
    assert prog["rules"][0]["action"]["params"]["mode"]["args"] == ["gx_a"]      # input untouched


def test_freeze_detects_a_change(tmp_path):
    state = M.freeze_state(HERE)
    assert state == M.freeze_state(HERE)
    good = tmp_path / "manifest.json"
    good.write_text(json.dumps({"state": state}))
    assert M.freeze_problems(HERE, str(good)) == []
    bad_state = json.loads(json.dumps(state))
    bad_state["files"]["cora_reach/relations.py"] = "0" * 64
    bad_state["limits"]["max_proposals"] = 9
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"state": bad_state}))
    problems = M.freeze_problems(HERE, str(bad))
    assert "file cora_reach/relations.py" in problems and "limits" in problems
    assert M.freeze_problems(HERE, str(tmp_path / "missing.json")) == ["no manifest"]


def _engine_env():
    from cora_pilot.native import CHAIN_FLAGS
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(CHAIN_FLAGS)
    env.update(ARC_DIHEDRAL_FRAMES="2", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI]))
    return env


@pytest.mark.engine
def test_run_task_rejection_path_on_a_copy_task(tmp_path):
    """Every arm of the fixed policy runs on a synthetic copy task (each
    shape copied one gap to its right) with hand-written memorized instances,
    in a fresh process: gates, leave-one-out, pool, controls, separation and
    restoration are all recorded, and the engine state is untouched after.
    (The engine sees the copy as a separate object, so this exercises the
    rejection paths.)"""
    code = r'''
import json, os, sys, numpy as np
sys.path.insert(0, %(here)r)
from cora_reach import bridge as BR, measure as M
M.MATCHED_MIN_S, M.MATCHED_MAX_S = 6.0, 12.0
shapes = [{(1, 1): 0, (2, 1): 0, (2, 2): 0, (3, 3): 0}, {(4, 2): 0, (4, 3): 0, (5, 1): 0, (6, 3): 0},
          {(1, 4): 0, (2, 5): 0, (2, 6): 0, (3, 4): 0}]
colours, train, inst = [3, 5, 2], [], []
for d, (sh, col) in enumerate(zip(shapes, colours)):
    a = np.zeros((8, 16), dtype=int)
    for (r, c) in sh: a[r, c] = col
    b = a.copy()
    for (r, c) in sh: b[r, c + 4] = col
    train.append({"input": a.tolist(), "output": b.tolist()})
    inn = [[[r, c], col] for (r, c) in sorted(sh)]
    out = inn + [[[r, c + 4], col] for (r, c) in sorted(sh)]
    inst.append({"variant": "S1", "demo": d, "grid": a.tolist(), "in": inn, "out": out, "bounds": [8, 16]})
t = np.zeros((8, 16), dtype=int)
for (r, c) in [(2, 2), (3, 2), (3, 4), (4, 3)]: t[r, c] = 6
task = {"train": train, "test": [{"input": t.tolist()}]}
idir = os.path.join(%(tmp)r, "instances")
os.makedirs(idir, exist_ok=True)
json.dump({"instances": inst}, open(os.path.join(idir, "ksyn.json"), "w"))
saved = BR.originals()
ctx = {"dirs": M.engine_dirs(os.path.join(%(tmp)r, "engine")), "instances_dir": idir, "donor": "kdonor",
       "extract_seconds": 0.0, "budget_s": 6.0}
row = M.run_task("ksyn", task, ctx)
json.dumps(row)
print(json.dumps({"row": row, "restored_after": BR.restored(saved) and BR.originals() == saved}, default=str))
''' % {"here": HERE, "tmp": str(tmp_path)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=1500,
                       env=_engine_env(), cwd=HERE)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    row = out["row"]
    assert out["restored_after"] and row["restored"]
    assert row["path_class"] in M.PATH_CLASSES
    assert set(row["progression"]) == set(M.PROGRESSION)
    fams = [p["family"] for p in row["fc"]["proposals"]]
    assert fams[:2] == ["copies_bbox", "copies_offset"], fams          # grammar order; a pool of two
    assert set(row["gates"]) == {g for g, _ in M.GATES}
    assert row["progression"]["candidate"] and row["progression"]["compile"] and row["progression"]["install"]
    assert len(row["loo"]["folds"]) == 3 and all(f["class"] for f in row["loo"]["folds"])
    assert row["pool"]["size"] == len(row["fc"]["proposals"])
    assert set(row["separation"]) >= {"non_renaming", "non_caching", "non_composition_bounded", "separated"}
    assert row["separation"]["non_caching"] and row["separation"]["instances_checked"] == 3
    assert row["controls"]["SHUFFLED_FAILURE"]["class"] == "NO_PROPOSAL"
    assert row["controls"]["DEMO_ONLY"]["class"] in ("INSTALLED", "NO_PROPOSAL")
    assert row["matched"]["budget_s"] <= 12.0 and "spent_s" in row["matched"]
    w = row["with_e"]
    if w["accepted"]:
        assert row["gates"]["replay"] and row["gates"]["attribution"], w
        assert "support" in w and len(w["support"]["e_cells_per_test"]) == 1
        assert row["pool"]["others"] is not None and len(row["pool"]["others"]) == row["pool"]["size"] - 1
    failed = [cls for gate, cls in M.GATES if not row["gates"][gate]]
    assert row["path_class"] == (failed[0] if failed else "ACTIVATED")


@pytest.mark.engine
def test_run_task_accepted_path_on_a_band_task(tmp_path):
    """The accepted path end to end on the bridge test's synthetic task (each
    object's rows filled with its colour): the evidence is the engine's own
    extraction, the unchanged gate accepts a program using e, replay,
    attribution and the growth support contract are evaluated inside the
    bridge, every fold rebuilds its own extension; and pool substitution
    executes a second member in the accepted program."""
    code = r'''
import json, os, sys, numpy as np
sys.path.insert(0, %(here)r)
from cora_reach import bridge as BR, growth_ext as GE, instances as INST, measure as M
M.MATCHED_MIN_S, M.MATCHED_MAX_S = 10.0, 20.0
shapes = [{(1,4):3,(2,4):3}, {(3,6):4,(3,7):4,(4,7):4}, {(2,2):2}, {(4,9):6,(5,9):6}]
train = []
for sh in shapes:
    g = np.zeros((7, 12), dtype=int)
    for (r, c), v in sh.items(): g[r, c] = v
    o = g.copy()
    col = next(iter(sh.values()))
    for r in {r for r, _ in sh}:
        for c in range(12):
            if o[r, c] == 0: o[r, c] = col
    train.append((g, o))
t = np.zeros((7, 12), dtype=int); t[1, 3] = 5; t[1, 4] = 5; t[5, 8] = 5
task = {"train": [{"input": a.tolist(), "output": b.tolist()} for a, b in train], "test": [{"input": t.tolist()}]}
idir = os.path.join(%(tmp)r, "instances"); os.makedirs(idir, exist_ok=True)
dirs = M.engine_dirs(os.path.join(%(tmp)r, "engine"))
_ind, inst = INST.extract(train, dirs["extract"], budget_s=20.0)
json.dump({"instances": inst}, open(os.path.join(idir, "kband.json"), "w"))
saved = BR.originals()
row = M.run_task("kband", task, {"dirs": dirs, "instances_dir": idir, "donor": "kdonor", "extract_seconds": 0.0,
                                 "budget_s": 20.0})
e = row["extension"]
run, prog = M.object_run("kband_pool", train, [t], dirs["fc"], ext=e, budget_s=20.0)
cross = GE.make("band", {"axis": "cross"})
others = M.pool_predictions(prog, e, [{"ext": e}, {"ext": cross}], [t]) if prog else None
print(json.dumps({"row": row, "others": others, "run_predictions": run["predictions"],
                  "restored_after": BR.restored(saved) and BR.originals() == saved}, default=str))
''' % {"here": HERE, "tmp": str(tmp_path)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=1500,
                       env=_engine_env(), cwd=HERE)
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    row, w = out["row"], out["row"]["with_e"]
    assert out["restored_after"] and row["restored"]
    assert row["fc"]["proposals"][0]["family"] == "band"
    assert w["accepted"] and w["uses"], w                          # as in test_reach_bridge
    assert row["gates"]["replay"] and row["gates"]["attribution"] and row["gates"]["prediction"]
    sup = w["support"]
    assert sup["e_cells_per_test"][0] > 0 and sup["e_rules"] >= 1
    assert row["gates"]["support"] == sup["ok"]
    assert len(row["loo"]["folds"]) == 4
    assert all(f["class"] in ("SUCCESS", "LOO_FAILURE", "NO_PROPOSAL", "RESOURCE_EXHAUSTED")
               for f in row["loo"]["folds"])
    assert row["separation"]["non_renaming"] and row["separation"]["non_caching"]
    others = out["others"]
    assert others is not None and [m["family"] for m in others] == ["band"] and others[0]["params"] == {
        "axis": "cross"}
    assert others[0]["predictions"][0] is not None
    assert others[0]["predictions"] != out["run_predictions"]      # cross also fills columns
    failed = [cls for gate, cls in M.GATES if not row["gates"][gate]]
    assert row["path_class"] == (failed[0] if failed else "ACTIVATED")
