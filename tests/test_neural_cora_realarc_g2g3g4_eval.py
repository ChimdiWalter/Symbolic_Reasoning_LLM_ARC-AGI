"""The real-task check's runner (scripts/neural_cora_realarc_g2g3g4_eval.py): refusals, the lock check, answer
separation, the error definition, the arm-E hook, and a DEV smoke of the arms through `run_one` (never a cohort task,
never the frozen solve command)."""
import builtins
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import zlib

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
_spec = importlib.util.spec_from_file_location("realarc_g2g3g4_eval", os.path.join(HERE, "scripts", "neural_cora_realarc_g2g3g4_eval.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402


def dev_task(src, scene, seed=0, n=3, n_tests=2):
    prog = G.parse(src)
    rng = np.random.default_rng(zlib.crc32(f"{src}|{seed}".encode()))
    pairs = []
    for _ in range(400):
        g = scene(rng)
        if g is None:
            continue
        out = G.execute(prog, g)
        if out is None or np.array_equal(out, g):
            continue
        pairs.append((g.tolist(), out.tolist()))
        if len(pairs) == n + n_tests:
            break
    return {"task_id": "dev", "train": pairs[:n], "test_inputs": [p[0] for p in pairs[n:]]}, [np.asarray(p[1]) for p in pairs[n:]]


def test_solve_refuses_without_authorized():
    r = subprocess.run([sys.executable, os.path.join(HERE, "scripts", "neural_cora_realarc_g2g3g4_eval.py"), "solve"],
                       cwd=HERE, capture_output=True, text=True)
    assert r.returncode != 0 and "--authorized" in (r.stdout + r.stderr)


def test_lock_check_catches_a_modified_file(tmp_path):
    for rel in [E.PROTOCOL, "scripts/neural_cora_realarc_g2g3g4_eval.py"] + \
            [os.path.join("cora_neural_v2g4", f) for f in os.listdir(os.path.join(HERE, "cora_neural_v2g4")) if f.endswith(".py")]:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(HERE, rel), dst)
    man = {"code": E.code_hashes(str(tmp_path)), "protocol_sha256": E.sha_file(str(tmp_path / E.PROTOCOL))}
    assert E.lock_problems(str(tmp_path), man, check_inputs=False, check_native=False) == []
    with open(tmp_path / "cora_neural_v2g4" / "construct.py", "a") as fh:
        fh.write("\n# edit\n")
    probs = E.lock_problems(str(tmp_path), man, check_inputs=False, check_native=False)
    assert any("construct.py" in p for p in probs)


def test_solver_side_never_reads_expected_outputs(monkeypatch):
    for fn in (E.load_inputs, E.run_one, E._g2_arm, E._e_arm, E._job, E.solve):
        src = inspect.getsource(fn)
        assert "SOLUTIONS" not in src and "load_pinned" not in src
    from cora_pilot import bundle as B
    real_open = builtins.open
    sol = os.path.basename(B.SOLUTIONS)

    def guarded(f, *a, **k):
        if sol in str(f):
            raise AssertionError("the solver side opened the solutions file")
        return real_open(f, *a, **k)
    monkeypatch.setattr(builtins, "open", guarded)
    dev = json.load(real_open(os.path.join(HERE, "records", "pilot_v1", "selection.json")))["dev"][:1]   # exposed dev60
    t = E.load_inputs(dev)[0]
    assert set(t) == {"task_id", "train", "test_inputs"}


def test_error_definition():
    assert E.is_error({"arm": "g4", "exception": "ValueError()"})
    assert not E.is_error({"arm": "native", "rec": {"error": "object_hard_timeout"}})
    assert E.is_error({"arm": "native", "rec": {"error": "KeyError('window')"}})
    assert not E.is_error({"arm": "g3", "rec": {"cpu_s": 120.0}})


def test_arm_e_is_not_run_without_a_frozen_addendum():
    assert not os.path.exists(os.path.join(HERE, E.E_MANIFEST)) and E.arm_e_status() is None


@pytest.mark.parametrize("arm", ["g2", "g3", "g4"])
def test_dev_smoke_every_test_input_gets_attempts(arm):
    task, answers = dev_task(F.P("(rule (test is_line == #t) (recolor (color 6)))"), F.scene_mixed)
    r = E.run_one(task, arm, budget=1000, cpu_cap_s=30.0)
    assert len(r["attempts_by_test"]) == len(task["test_inputs"]) == 2
    rec = E._ncv2_record(r, [a.tolist() for a in answers])
    assert rec["pass2_all"] and rec["per_test"] == [True, True] and rec["coverage_first"]


def test_decision_rule_thresholds():
    def s(b, c, d, ccpu, l_cb, l_dc):
        arm = lambda p, cov: {"pass2_all": p, "coverage_first": cov}             # noqa: E731
        return {"arms": {"g2": arm(*b), "g3": arm(*c), "g4": arm(*d), "g3_cpu": arm(*ccpu)},
                "paired": {"g3_vs_g2": {"losses": l_cb}, "g4_vs_g3": {"losses": l_dc}}}
    assert E.decide(s((2, 3), (5, 6), (8, 9), (6, 7), 1, 1)) == {"g3": "GO_REAL_G3", "g4": "GO_REAL_G4"}
    assert E.decide(s((2, 3), (4, 6), (8, 9), (6, 7), 0, 0))["g3"] == "NO_REAL_GAIN_G3"          # pass@2 gain only 2
    assert E.decide(s((2, 3), (5, 6), (8, 9), (6, 8), 0, 0))["g4"] == "NO_REAL_GAIN_G4"          # g4 - g3_cpu coverage 1
    assert E.decide(s((2, 3), (5, 6), (8, 9), (6, 7), 2, 0))["g3"] == "NO_REAL_GAIN_G3"          # 2 losses
