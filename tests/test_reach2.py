"""Reach v2: the variant-carrying installation repair and the successor
policy (synthetic fixtures only; no ARC data)."""
import ast
import contextlib
import dataclasses
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_reach2 import variant as VA                                # noqa: E402

TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"


def _pairs():
    """Two demonstrations whose outputs hold new shapes: every variant but
    S7 is incoherent (coverage 0.14); S7 is coherent."""
    from geocat_arc.object_reasoning.types import to_grid_pairs
    a = np.zeros((7, 7), int)
    a[0, 0] = 3
    b = a.copy()
    b[2:6, 2:6] = 6
    b[3:5, 3:5] = 0
    a2 = np.zeros((7, 7), int)
    a2[6, 6] = 4
    b2 = a2.copy()
    b2[1:4, 1:5] = 2
    return to_grid_pairs([(a, b), (a2, b2)])


def check_overlay(factory, variant="S6"):
    """The repair's contract, as a checker the mutation test reuses."""
    import geocat_arc.object_reasoning.inducer as I
    order0, eval0 = I.SEGMENTATION_TRIAL_ORDER, I.evaluate_variant
    pairs = _pairs()
    V = next(x for x in order0 if x.value == variant)
    W = next(x for x in order0 if x.value == "S7")
    assert eval0(V, pairs).coherent is False and eval0(W, pairs).coherent is True      # the fixture
    try:
        with factory(variant) as rec:
            assert I.SEGMENTATION_TRIAL_ORDER[0] is V, "the variant is searched first"
            assert [x for x in I.SEGMENTATION_TRIAL_ORDER if x is not V] == [x for x in order0 if x is not V], \
                "every other variant keeps its order"
            assert I.evaluate_variant(V, pairs).coherent is True, "the variant is admitted"
            assert I.evaluate_variant(W, pairs).coherent is True
            for x in order0:
                if x is not V:
                    assert I.evaluate_variant(x, pairs).coherent == eval0(x, pairs).coherent, "others unchanged"
            assert rec["admitted_incoherent"] >= 1
        assert I.SEGMENTATION_TRIAL_ORDER is order0 and I.evaluate_variant is eval0, "restored on exit"
    finally:
        I.SEGMENTATION_TRIAL_ORDER, I.evaluate_variant = order0, eval0


def test_variant_first_contract():
    check_overlay(VA.variant_first)
    assert VA.restored()


def test_variant_first_restores_after_an_exception_and_refuses_nesting():
    import geocat_arc.object_reasoning.inducer as I
    saved = VA.originals()
    with pytest.raises(ValueError):
        with VA.variant_first("S6"):
            raise ValueError("boom")
    assert VA.originals() == saved and VA.restored()
    with VA.variant_first("S6"):
        with pytest.raises(RuntimeError):
            with VA.variant_first("S7"):
                pass
    assert VA.originals() == saved
    with pytest.raises(ValueError):
        with VA.variant_first("S9"):
            pass
    assert I.SEGMENTATION_TRIAL_ORDER is saved[0]


def _mutant(kind):
    @contextlib.contextmanager
    def factory(variant):
        import geocat_arc.object_reasoning.inducer as I
        order0, eval0 = I.SEGMENTATION_TRIAL_ORDER, I.evaluate_variant
        v = next(x for x in order0 if x.value == variant)
        moved = next(x for x in order0 if x.value == "S1") if kind == "wrong_variant" else v
        rec = {"admitted_incoherent": 0}

        def ev(x, pairs):
            r = eval0(x, pairs)
            if x is v and not r.coherent and kind != "no_admission":
                rec["admitted_incoherent"] += 1
                r = dataclasses.replace(r, coherent=True)
            return r
        if kind != "no_reorder":
            I.SEGMENTATION_TRIAL_ORDER = (moved,) + tuple(x for x in order0 if x is not moved)
        I.evaluate_variant = ev
        try:
            yield rec
        finally:
            if kind != "no_restore":
                I.SEGMENTATION_TRIAL_ORDER, I.evaluate_variant = order0, eval0
    return factory


@pytest.mark.parametrize("kind", ["no_reorder", "no_admission", "no_restore", "wrong_variant"])
def test_mutants_are_caught(kind):
    with pytest.raises(AssertionError):
        check_overlay(_mutant(kind))
    assert VA.restored()


def test_measure2_is_the_recorded_build_of_v1():
    import build_measure2 as B
    assert open(B.TARGET).read() == B.build()
    v1 = B.v1_functions()
    src = open(B.TARGET).read()
    lines = src.splitlines(keepends=True)
    marked = 0
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in B.FUNCS:
            body = lines[node.lineno - 1:node.end_lineno]
            for line in body:
                if line.rstrip().endswith("# V2"):
                    marked += 1
                else:
                    assert line in v1[node.name], f"{node.name}: unmarked line not in v1: {line!r}"
    assert marked == 11


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


@pytest.mark.engine
def test_the_engine_searches_the_promoted_variant_first(tmp_path):
    out = _engine(r'''
import json, sys, numpy as np
sys.path.insert(0, %(here)r)
import geocat_arc.object_reasoning.inducer as I
from geocat_arc.object_reasoning.types import to_grid_pairs
from cora_reach2 import variant as VA
pairs = []
for r0 in (1, 3, 5):
    a = np.zeros((7, 9), int); a[r0, 2] = 3; a[r0, 3] = 4
    b = a.copy(); b[r0, 6] = 3
    pairs.append((a, b))
gp = to_grid_pairs(pairs)
tried = []
orig = I._induce_on_table
def spy(seg, *a, **k):
    tried.append(seg.variant.value)
    return orig(seg, *a, **k)
I._induce_on_table = spy
res = {}
try:
    for mode in ("plain", "S7"):
        tried.clear()
        cfg = I.InductionConfig(budget_s=5.0)
        ctx = VA.variant_first("S7") if mode == "S7" else None
        if ctx: ctx.__enter__()
        try:
            I._induce_candidate(gp, cfg, I.time.monotonic() + 5.0, I._Meta())
        finally:
            if ctx: ctx.__exit__(None, None, None)
        res[mode] = list(tried)
finally:
    I._induce_on_table = orig
print(json.dumps({"res": res, "restored": VA.restored()}))
''', tmp_path)
    assert out["restored"]
    assert out["res"]["S7"] and out["res"]["S7"][0] == "S7"
    assert out["res"]["plain"] and out["res"]["plain"][0] != "S7"


@pytest.mark.engine
def test_successor_policy_end_to_end_on_a_synthetic_task(tmp_path):
    """The successor's run_task on the bridge test's band task: every arm
    runs, the variant overlay is recorded on the installed runs and
    restored, and the gates and class follow the frozen order."""
    out = _engine(r'''
import json, os, sys, numpy as np
sys.path.insert(0, %(here)r)
from cora_reach import bridge as BR, instances as INST, measure as M
from cora_reach2 import measure2 as M2, variant as VA
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
saved = BR.originals(); vsaved = VA.originals()
row = M2.run_task("kband", task, {"dirs": dirs, "instances_dir": idir, "donor": "kdonor", "extract_seconds": 0.0,
                                  "budget_s": 20.0})
json.dumps(row, default=str)
print(json.dumps({"version": row["version"], "path": row["path_class"], "gates": row["gates"],
                  "vf": row["with_e"].get("variant_first"), "variant": row["fc"]["proposals"][0]["variant"],
                  "folds": [(f["class"], f.get("selected_variant")) for f in row["loo"]["folds"]],
                  "restored": row["restored"] and BR.restored(saved) and VA.originals() == vsaved and VA.restored()},
                 default=str))
''', tmp_path)
    assert out["version"] == "reach-v2-measure" and out["restored"]
    assert out["vf"]["variant"] == out["variant"] and out["vf"]["restored"] is True and out["vf"]["evaluations"] >= 1
    assert len(out["folds"]) == 4 and all(c for c, _v in out["folds"])
    import cora_reach.measure as M
    failed = [cls for gate, cls in M.GATES if not out["gates"][gate]]
    assert out["path"] == (failed[0] if failed else "ACTIVATED")


def test_recheck_units_pair_every_task_with_both_arms():
    from cora_loo import recheck as RC
    tasks = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
    fc = RC.fc_keys(HERE)
    units = RC.units(sorted(tasks), fc)
    assert len(units) == 120 and len(set(units)) == 120
    assert {u.split("|")[0] for u in units[:8]} == fc and fc == {"k017955a77fc5", "k5991e227189e",
                                                                  "k5a49896251a2", "kf892487f1049"}
    assert all(units[i].split("|")[0] == units[i + 1].split("|")[0] for i in range(0, 120, 2))
