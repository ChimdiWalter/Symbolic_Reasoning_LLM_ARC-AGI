"""Growth-repair pilot v2: composition, the evaluator's legs and ladder, the
verifier's independent scoring, the sample rule (synthetic fixtures only;
no ARC data, no solutions)."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_pilot2 import evaluator as EV                              # noqa: E402
from cora_pilot2 import reasoner as RS                               # noqa: E402

TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
G1, G2, G3 = [[1, 0]], [[2, 2]], [[3]]


def test_donor_is_the_next_key_cyclic():
    keys = ["kb", "ka", "kc"]
    assert RS.donor(keys, "ka") == "kb" and RS.donor(keys, "kc") == "ka"


def test_cora_never_displaces_native_attempt_1():
    nat = {"attempt_1": [G1, None], "attempt_2": [G2, G3]}
    cora = {"activated": True, "cora_prediction": [G3, G1]}
    assert RS.system_attempts(nat, cora, 2) == [[G1, G3], [G1, G3]]
    assert RS.system_attempts(nat, {"activated": False, "cora_prediction": [G3, G3]}, 2) == [[G1, G2], [None, G3]]
    assert RS.system_attempts({}, cora, 2) == [[G3, None], [G1, None]]


def _cora_row(activated, pred, *, sep=True, controls=None, gates=None, loo=True):
    g = {x: True for x in ("compile", "accepted", "uses", "replay", "attribution", "prediction", "determinism",
                           "unanimity", "support")}
    g["loo"] = loo
    g.update(gates or {})
    controls = controls or {}
    return {"path_class": "ACTIVATED" if activated else "LOO_FAILURE", "activated": activated,
            "cora_prediction": pred if activated else None, "gates": g, "restored": True,
            "unchanged_baseline": True, "fc": {"proposals": [{"name": "gx_x"}]},
            "separation": {"separated": sep},
            "kalone": {"accepted": False, "program_sha": None, "predictions": [None]},
            "with_e": {"predictions": pred},
            "removed": {"accepted": False, "program_sha": None, "predictions": [None]},
            "matched": {"predictions": [None]},
            "controls": {a: ({"class": "INSTALLED", "with_e": {"predictions": controls[a]}} if a in controls
                             else {"class": "NO_PROPOSAL"}) for a in ("DEMO_ONLY", "SHUFFLED_FAILURE")}}


def _fixture():
    """Five synthetic tasks, one test output each (target G1)."""
    tasks = {k: {"train": [], "test": [{"input": G2}]} for k in ("k1", "k2", "k3", "k4", "k5")}
    native = {k: {"attempt_1": [None], "attempt_2": [None]} for k in tasks}
    native["k3"] = {"attempt_1": [G1], "attempt_2": [None]}                 # native solves k3
    cora = {"k1": _cora_row(True, [G1]),                                  # invention witness
            "k2": _cora_row(True, [G1], controls={"DEMO_ONLY": [G1]}),     # causal only: a control is right
            "k3": _cora_row(False, [G2], loo=False),
            "k4": _cora_row(True, [G2]),                                  # wrong activation
            "k5": _cora_row(False, [G1], loo=False)}                      # missed rescue
    keymap = {"keys": {k: {"task_id": f"t{k}", "n_test": 1, "stratum": "n3"} for k in tasks}}
    solutions = {f"t{k}": [G1] for k in tasks}
    return tasks, native, cora, keymap, solutions


def test_evaluator_legs_outcomes_and_ladder():
    tasks, native, cora, keymap, solutions = _fixture()
    preds = RS.compose(tasks, native, cora)
    res = EV.evaluate(keymap, preds, cora, native, solutions, set(), {"problems": {}})
    t = res["tasks"]
    assert t["k1"]["witness"] and t["k1"]["invention_witness"] and t["k1"]["outcome"] == "CORRECT_CAUSAL_RESCUE"
    assert t["k2"]["witness"] and not t["k2"]["invention_witness"] and not t["k2"]["legs"]["F"]
    assert t["k3"]["outcome"] == "BASELINE_ALREADY_SOLVES"
    assert t["k4"]["outcome"] == "WRONG_ACTIVATION"
    assert t["k5"]["outcome"] == "MISSED_RESCUE"
    assert res["outcome"] == "REAL_ARC_INVENTION_WITNESS_ESTABLISHED"
    assert res["summary"]["invention_witness_keys"] == ["k1"] and res["summary"]["witness_keys"] == ["k1", "k2"]
    assert res["safety"] == "SAFE"              # 1 wrong <= 2 right activations, no lost solve, net +2
    cora["k1"] = _cora_row(True, [G1], sep=False)                         # separation fails
    preds = RS.compose(tasks, native, cora)
    res = EV.evaluate(keymap, preds, cora, native, solutions, set(), {"problems": {}})
    assert res["outcome"] == "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED"
    assert EV.evaluate(keymap, preds, cora, native, solutions, set(), {"problems": {"x": ["refused"]}})[
        "outcome"] == "PILOT_LEAKAGE"
    errs = dict(cora, k4={"path_class": "RUN_ERROR", "activated": False})
    assert EV.evaluate(keymap, RS.compose(tasks, native, errs), errs, native, solutions, set(),
                       {"problems": {}})["outcome"] == "NO_VERDICT_RUN_ERROR"
    sealed = {"tk1"}                                                      # a sealed task is never a rescue
    res = EV.evaluate(keymap, preds, cora, native, solutions, sealed, {"problems": {}})
    assert res["tasks"]["k1"]["outcome"] == "BASELINE_ALREADY_SOLVES" and not res["tasks"]["k1"]["legs"]["B"]


def test_verifier_scoring_agrees_with_the_evaluator():
    import pilot_v2_verify as VF
    tasks, native, cora, keymap, solutions = _fixture()
    preds = RS.compose(tasks, native, cora)
    res = EV.evaluate(keymap, preds, cora, native, solutions, set(), {"problems": {}})
    for k in tasks:
        native_ok, wit, inv, out = VF.independent_outcome(preds[k], cora[k], solutions[f"t{k}"], False)
        t = res["tasks"][k]
        assert (native_ok, wit, inv, out) == (t["native_solved"], t["witness"], t["invention_witness"],
                                              t["outcome"]), k


def test_sample_rule_refuses_an_unregistered_n():
    import pilot_v2_select as SEL
    with pytest.raises(SystemExit):
        SEL.main(["50"])
    with pytest.raises(SystemExit):
        SEL.main([])


@pytest.mark.engine
def test_instances_phase_on_a_synthetic_task(tmp_path):
    """Phase B on the bridge test's band task: the extraction writes its
    evidence file and the row counts the instances."""
    code = r'''
import json, os, sys, numpy as np
sys.path.insert(0, %(here)r)
from cora_pilot import native as N
from cora_pilot2 import reasoner as RS
from cora_reach import measure as M
M.BUDGET_S = 20.0
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
    train.append({"input": g.tolist(), "output": o.tolist()})
task = {"train": train, "test": [{"input": train[0]["input"]}]}
obj = N.prepare_object_dir(os.path.join(%(tmp)r, "engine"))
row = RS.run_instances("ksyn", task, obj, os.path.join(%(tmp)r, "instances"))
saved = json.load(open(os.path.join(%(tmp)r, "instances", "ksyn.json")))["instances"]
print(json.dumps({"row": row, "saved": len(saved)}))
''' % {"here": HERE, "tmp": str(tmp_path)}
    from cora_pilot.native import CHAIN_FLAGS
    env = {k: v for k, v in os.environ.items() if not k.startswith("ARC_")}
    env.update(CHAIN_FLAGS)
    env.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=os.pathsep.join([HERE, os.path.join(HERE, "src"), TTI]))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=900, env=env, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["row"]["instances"] == out["saved"] > 0 and not out["row"]["timeout"]
    assert out["row"]["demos_with_instances"] == [0, 1, 2, 3]
