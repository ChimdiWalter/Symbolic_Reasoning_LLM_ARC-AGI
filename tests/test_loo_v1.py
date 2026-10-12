"""Adaptive LOO stability v1: the observation-only instrument (synthetic
fixtures; the unit list reads reach v1's committed rows; no target)."""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_loo import diagnose as DG                                  # noqa: E402
from cora_loo import freeze as FZ                                    # noqa: E402
from cora_loo import instrument as IN                                # noqa: E402
from cora_reach import growth_ext as GE                              # noqa: E402

TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"


def _copy_instances():
    """Three demonstrations, one shape each, copied one gap to its right."""
    out = []
    for d, (cells, col) in enumerate((([(1, 1), (2, 1), (2, 2)], 3), ([(4, 2), (4, 3), (5, 1)], 5),
                                      ([(1, 6), (2, 7), (2, 6)], 2))):
        a = np.zeros((8, 16), dtype=int)
        for r, c in cells:
            a[r, c] = col
        w = max(c for _, c in cells) - min(c for _, c in cells) + 1
        inn = [[[r, c], col] for r, c in cells]
        out.append({"variant": "S1", "demo": d, "grid": a.tolist(), "in": inn,
                    "out": inn + [[[r, c + w + 1], col] for r, c in cells], "bounds": [8, 16]})
    return out


def test_variant_analysis_and_heldout_check():
    raw = _copy_instances()
    e = GE.make("copies_bbox", {"sr": 0, "sc": 1, "gap": 1, "until_border": False})
    va = IN.variant_analysis(raw, e)
    v = va["variants"]["S1"]
    assert v["instances"] == 3 and v["demos"] == [0, 1, 2] and v["support_ok"] and v["full_ext_reproduces"] == 3
    assert v["settings_reproducing_all"][0]["family"] == "copies_bbox"
    wrong = GE.make("copies_bbox", {"sr": 0, "sc": 1, "gap": 0, "until_border": False})
    chk = IN.heldout_check(raw, 2, [{"ext": e, "variant": "S1"}, {"ext": wrong, "variant": "S1"}])
    assert [(c["heldout_instances"], c["reproduces"]) for c in chk] == [(1, 1), (1, 0)]
    assert IN.variant_analysis(raw[:1], e)["variants"]["S1"]["support_ok"] is False


def test_spies_restore_their_targets():
    import geocat_arc.object_reasoning.correspondence as CO
    import geocat_arc.object_reasoning.inducer as I
    from cora_reach import bridge as BR
    before = (I._check_deadline, CO.detect_grow)
    with IN.deadline_spy() as hits:
        assert I._check_deadline is not before[0]
        with pytest.raises(I._BudgetExhausted):
            I._check_deadline(0.0)                    # a past deadline raises and is counted
    assert I._check_deadline is before[0] and sum(hits.values()) == 1
    e = GE.make("bbox_ring", {})
    saved = BR.originals()
    with BR.installed(e):
        inner = CO.detect_grow
        with IN.substitution_spy(e["name"]):
            assert CO.detect_grow is not inner
        assert CO.detect_grow is inner
    assert BR.restored(saved) and CO.detect_grow is before[1]


def test_units_from_the_reach_v1_rows():
    ctx = DG.load_context(HERE)
    assert sorted(ctx) == ["k017955a77fc5", "k5991e227189e", "k5a49896251a2", "kf892487f1049"]
    assert ctx["kf892487f1049"]["ext"]["family"] == "bbox_fill" and ctx["kf892487f1049"]["n_train"] == 4
    units = DG.units(ctx)
    assert len(units) == 4 + 14 and units[0] == "kf892487f1049:full"
    assert sum(1 for u in units if not u.endswith(":full")) == 14


def test_freeze_detects_a_change(tmp_path):
    state = FZ.freeze_state(HERE)
    good = tmp_path / "m.json"
    good.write_text(json.dumps({"state": state}))
    assert FZ.freeze_problems(HERE, str(good)) == []
    bad = json.loads(json.dumps(state))
    bad["files"]["cora_loo/instrument.py"] = "0" * 64
    bad["constants"]["cpu_wall_cap_s"] = 1
    (tmp_path / "b.json").write_text(json.dumps({"state": bad}))
    p = FZ.freeze_problems(HERE, str(tmp_path / "b.json"))
    assert "file cora_loo/instrument.py" in p and "constants" in p


def _engine(code, tmp_path, timeout=1500):
    from cora_pilot.native import CHAIN_FLAGS
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(CHAIN_FLAGS)
    env.update(ARC_DIHEDRAL_FRAMES="2", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI]))
    r = subprocess.run([sys.executable, "-c", code % {"here": HERE, "tmp": str(tmp_path)}], capture_output=True,
                       text=True, timeout=timeout, env=env, cwd=HERE)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


BAND = r'''
import json, os, sys, numpy as np
sys.path.insert(0, %(here)r)
from cora_reach import bridge as BR, growth_ext as GE, measure as M
from cora_loo import diagnose as DG, instrument as IN
M.BUDGET_S = 15.0
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
task = {"train": [{"input": a.tolist(), "output": b.tolist()} for a, b in train], "test": [{"input": train[0][0].tolist()}]}
dirs = DG.engine_dirs(os.path.join(%(tmp)r, "engine"))
e = GE.make("band", {"axis": "rows"})
saved = BR.originals()
'''


@pytest.mark.engine
def test_traced_engine_run_under_both_clocks(tmp_path):
    out = _engine(BAND + r'''
res = {}
for clock in IN.CLOCKS:
    run, prog = IN.engine_run("kband_" + clock, train, [train[0][0]], dirs["a_e"], ext=e, clock=clock)
    res[clock] = {k: run.get(k) for k in ("accepted", "uses", "clock", "cpu_s", "wall_s", "cpu_share", "timeout",
                                          "deadline_hits", "substitutions", "restored", "frames_run")}
    res[clock]["inductions"] = len(run["trace"]["inductions"])
    res[clock]["inner_loo_folds"] = sum(len(x["folds"]) for x in run["trace"]["inner_loo"])
    res[clock]["clock_patched"] = run["trace"]["clock_patched_modules"]
    res[clock]["first"] = run["trace"]["inductions"][0].get("accepted")
alone, _ = IN.engine_run("kband_K", train, [], dirs["a_k"])
print(json.dumps({"res": res, "alone_inductions": len(alone["trace"]["inductions"]),
                  "restored_after": BR.restored(saved) and BR.originals() == saved}))
''', tmp_path)
    for clock in ("WALL", "CPU1"):
        r = out["res"][clock]
        assert r["accepted"] and r["uses"] and r["restored"] and not r["timeout"], r
        assert r["inductions"] >= 1 and r["inner_loo_folds"] >= 4 and r["first"] is True
        assert r["substitutions"]["installed"] > 0 and isinstance(r["deadline_hits"], dict)
        assert r["cpu_s"] > 0 and r["wall_s"] > 0
    assert out["res"]["WALL"]["clock_patched"] == 0 and out["res"]["CPU1"]["clock_patched"] > 0
    assert out["alone_inductions"] >= 1 and out["restored_after"]


@pytest.mark.engine
def test_fold_unit_records_every_arm(tmp_path):
    out = _engine(BAND + r'''
from cora_reach import instances as INST
_ind, raw = INST.extract(train, dirs["extract"], budget_s=15.0)
c = {"ext": e, "variant": "S1", "raw": raw, "n_train": 4, "reach_v1": {"folds": []}}
row = DG.fold_unit("kband", task, 1, c, dirs)
json.dumps(row, default=str)
keep = {k: row[k] for k in ("n_rest", "e_full", "restricted")}
for clock in IN.CLOCKS:
    b = row["B_" + clock]
    keep["B_" + clock] = {"selected": b["selected"], "same_as_full": b["same_as_full"],
                          "engine": {k: (b.get("engine") or {}).get(k) for k in ("accepted", "uses", "heldout_exact", "clock")},
                          "distinguish": b["heldout_distinguish"], "extract_clock": b["extract"]["clock"]}
    keep["C_" + clock] = {k: v for k, v in row["C_" + clock].items() if k != "engine"}
keep["D"] = {k: row["D_WALL"].get(k) for k in ("accepted", "installed", "heldout_exact")}
keep["E"] = {k: row["E_WALL"].get(k) for k in ("accepted", "budget_s", "spent_s")}
keep["extract_hits"] = isinstance(row["B_WALL"]["extract"].get("deadline_hits"), dict)
sys.path.insert(0, os.path.join(%(here)r, "scripts"))
import loo_v1_classify as LC
row["e_full"] = e["name"]
(h, sub), ev = LC.classify_fold(row)
keep["classified"] = [h, sub, h in LC.HYPOTHESES]
print(json.dumps({"row": keep, "restored_after": BR.restored(saved) and BR.originals() == saved}, default=str))
''', tmp_path)
    row = out["row"]
    assert out["restored_after"] and row["n_rest"] == 3 and row["e_full"] == GE.make("band", {"axis": "rows"})["name"]
    for clock in ("WALL", "CPU1"):
        b = row["B_" + clock]
        assert b["extract_clock"] == clock and b["engine"]["clock"] in (clock, None)
        if b["same_as_full"]:
            assert row["C_" + clock] == {"same_as_B": True}
        else:
            assert row["C_" + clock]["forensic_only"] is True
        assert b["distinguish"][-1]["name"] == row["e_full"]          # e_full is always checked last
    assert row["D"]["installed"] is None and 10.0 <= row["E"]["budget_s"] <= 20.0
    assert "proposals" in row["restricted"] and "variants" in row["restricted"]["analysis"]
    assert row["extract_hits"] and row["classified"][2] is True, row["classified"]
